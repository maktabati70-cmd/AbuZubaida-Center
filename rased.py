# -*- coding: utf-8 -*-
"""
مركز أبو زبيدة للتتبع والرصد (ملف واحد)
=================================================
يرصد: الأخبار العالمية والعربية، مراكز الأبحاث الأجنبية والعربية، مراكز مكافحة
الإرهاب والتطرف، الحروب والنزاعات والدفاع، التغريدات، وكلمات مفتاحية تختارها أنت.
كل المحتوى يُترجم تلقائياً إلى العربية ويُخزَّن محلياً.

التثبيت (مرة واحدة):
    pip install flask feedparser requests deep-translator
اختياري ولكن يُنصح به (يحسّن فتح المقالات المحمية واستخراج نصها):
    pip install curl_cffi trafilatura
اختياري: مترجم محلي يعمل بلا إنترنت كاحتياط أخير (حجمه كبير نسبياً):
    pip install argostranslate

التشغيل:
    python rased.py
ثم افتح:  http://127.0.0.1:5050

ملاحظات:
- عند أول تشغيل يُنشأ ملف rased_sources.json بجانب هذا الملف؛ عدّله لإضافة أو حذف مصادر.
- أي مصدر لا يعمل رابط RSS الخاص به يُجلب تلقائياً عبر بحث أخبار Google لنفس الموقع.
- التغريدات: منصة X أوقفت الوصول المجاني، فلتفعيلها ضع مفتاح X API في متغير البيئة X_BEARER_TOKEN.
  قنوات تيليغرام العامة تعمل مجاناً بلا مفتاح، وتضيفها أو تحذفها من قسم «التغريدات وتيليغرام».
"""

import os
import re
import sys
import json
import time
import html
import sqlite3
import hashlib
import calendar
import logging
import threading
import io
import base64
import webbrowser
from collections import Counter
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import quote, quote_plus, urlparse

VERSION = "2026.11.25"

# التشغيل بلا نافذة سوداء (pythonw أو exe بلا وحدة تحكم): نوجّه المخرجات إلى «لا شيء» حتى لا تتعطل الطباعة
if sys.stdout is None or sys.stderr is None:
    _null = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null
DEFAULT_REPO = "maktabati70-cmd/AbuZubaida-Center"     # مستودع GitHub الذي تُسحب منه التحديثات

# نسخة exe: إن وُجد rased.py محدَّث بجانب الملف التنفيذي (نزّله التحديث التلقائي) يُشغَّل بدل النسخة المدمجة
if getattr(sys, "frozen", False) and not os.environ.get("RASED_EXTERNAL"):
    _ext = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "rased.py")
    if os.path.exists(_ext):
        os.environ["RASED_EXTERNAL"] = "1"
        try:
            import runpy
            runpy.run_path(_ext, run_name="__main__")
            sys.exit(0)
        except SystemExit:
            raise
        except Exception as _e:              # فشل التحديث: نكمل بالنسخة المدمجة
            print("تعذّر تشغيل النسخة المحدَّثة، سيُشغَّل الإصدار المدمج:", _e, flush=True)
            os.environ.pop("RASED_EXTERNAL", None)

import requests
import feedparser
from flask import Flask, jsonify, request, Response, redirect, send_file

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None
try:                                   # اختياري: يتجاوز حماية كثير من المواقع (pip install curl_cffi)
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None
try:                                   # اختياري: مترجم محلي بلا إنترنت (pip install argostranslate)
    import argostranslate.package as argos_pkg
    import argostranslate.translate as argos_tr
except Exception:
    argos_tr = None
try:                                   # اختياري: أدق مستخرج لنص المقالات (pip install trafilatura)
    import trafilatura
except ImportError:
    trafilatura = None

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ───────────────────────── الإعدادات ─────────────────────────
if getattr(sys, "frozen", False):          # نسخة exe: البيانات بجانب الملف التنفيذي لا في المجلد المؤقت
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "rased.db")
SOURCES_PATH = os.path.join(BASE_DIR, "rased_sources.json")
PORT = 5050
FETCH_INTERVAL = 600          # كل 10 دقائق
MAX_ITEMS_PER_FEED = 25
RETENTION_DAYS = 14          # الأخبار
STUDY_DAYS = 92              # مراكز البحث والدراسات: 3 أشهر
LONG_CATS = ("think_global", "think_arab", "terror", "intel")
TG_PER_CHANNEL = 3           # عدد المنشورات المعروضة من كل قناة تيليغرام
TG_INTERVAL = 120            # تحديث تيليغرام كل دقيقتين
X_BEARER = os.environ.get("X_BEARER_TOKEN", "").strip()
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()      # اختياري: ترجمة احتياطية عبر Claude
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")
MYMEMORY_EMAIL = os.environ.get("MYMEMORY_EMAIL", "").strip()       # اختياري: يرفع حد MyMemory اليومي
JINA_KEY = os.environ.get("JINA_API_KEY", "").strip()               # اختياري: يرفع حد قارئ Jina
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}
BROWSER_HEADERS = {
    **HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "cross-site",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("rased")
try:                                       # سجل يُحفظ بجانب البرنامج للرجوع إليه عند أي مشكلة
    from logging.handlers import RotatingFileHandler
    _fh = RotatingFileHandler(os.path.join(BASE_DIR, "rased.log"), maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(_fh)
except Exception:
    pass
logging.getLogger("werkzeug").setLevel(logging.WARNING)

CATEGORIES = [
    ("world",        "الأخبار العالمية",           "#5B9BD5"),
    ("arab",         "الأخبار العربية",            "#4FD1C5"),
    ("think_global", "مراكز الأبحاث الأجنبية",     "#A48FE0"),
    ("think_arab",   "مراكز الأبحاث العربية",      "#E0A458"),
    ("terror",       "مكافحة الإرهاب والتطرف",     "#E5484D"),
    ("war",          "الحروب والنزاعات والدفاع",   "#E8774A"),
    ("intel",        "الأمن والاستخبارات",          "#F472B6"),
    ("official",     "البيانات الرسمية",            "#94A3B8"),
    ("economy",      "الأخبار الاقتصادية",         "#3DD68C"),
    ("tweets",       "التغريدات وتيليغرام",        "#6CB6E8"),
    ("keywords",     "رصد الكلمات المفتاحية",      "#E8C987"),
]


# المصادر الافتراضية في ملف مستقل: sources_default.py
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if not os.path.exists(os.path.join(BASE_DIR, "sources_default.py")):
    # وصل rased.py وحده من تحديث نسخة قديمة: ننزّل ملف المصادر من المستودع قبل المتابعة
    try:
        _repo = DEFAULT_REPO
        try:
            import sqlite3 as _sq
            _c = _sq.connect(os.path.join(BASE_DIR, "rased.db"))
            _row = _c.execute("SELECT v FROM kv WHERE k='upd_repo'").fetchone()
            _c.close()
            if _row and _row[0]:
                _repo = _row[0]
        except Exception:
            pass
        _r = requests.get(f"https://raw.githubusercontent.com/{_repo}/main/sources_default.py", timeout=60)
        _r.raise_for_status()
        with open(os.path.join(BASE_DIR, "sources_default.py"), "wb") as _f:
            _f.write(_r.content)
    except Exception as _e:
        print("تعذّر تنزيل sources_default.py:", _e, flush=True)
from sources_default import (F, YT, DEFAULT_FEEDS, DEFAULT_BSKY, SOURCES_VERSION,  # noqa: E402
                             DEFAULT_TG_CHANNELS, DEFAULT_X_ACCOUNTS, TOPIC_TAGS)


# ───────────────────────── الدول: كل مادة تُربط بالدول التي تتحدث عنها ─────────────────────────
# (الاسم العربي، الرمز، المنطقة، كلمات عربية، كلمات إنجليزية). الكلمة الإنجليزية المسبوقة بـ = تُطابَق كاملة فقط.
ME, AF, AS, EU, CA, AM, OC = "الشرق الأوسط", "أفريقيا", "آسيا", "أوروبا", "القوقاز وآسيا الوسطى", "الأمريكتان", "أوقيانوسيا"
COUNTRIES = [
    ("سوريا", "SY", ME, ["سوريا", "سورية", "سوري", "سوريين", "سوريون", "دمشق", "حلب", "ادلب", "دير الزور", "الرقة", "حمص", "اللاذقية", "درعا", "السويداء"],
     ["syria", "damascus", "aleppo", "idlib", "deir ez", "raqqa", "homs", "latakia", "daraa", "sweida"]),
    ("العراق", "IQ", ME, ["العراق", "عراقي", "عراقيين", "بغداد", "الموصل", "البصرة", "اربيل", "كركوك", "الانبار", "كردستان العراق"],
     ["iraq", "baghdad", "mosul", "basra", "erbil", "kirkuk", "anbar"]),
    ("إيران", "IR", ME, ["ايران", "ايراني", "طهران", "الحرس الثوري", "خامنئي"], ["iran", "tehran", "irgc", "khamenei"]),
    ("تركيا", "TR", ME, ["تركيا", "تركي", "الاتراك", "انقرة", "اسطنبول", "اردوغان"],
     ["turkey", "türkiye", "turkiye", "turkish", "ankara", "istanbul", "erdogan", "erdoğan"]),
    ("لبنان", "LB", ME, ["لبنان", "لبناني", "بيروت", "حزب الله"], ["lebanon", "lebanese", "beirut", "hezbollah"]),
    ("الأردن", "JO", ME, ["الاردن", "اردني", "عمّان"], ["jordan", "amman"]),
    ("فلسطين", "PS", ME, ["فلسطين", "فلسطيني", "غزة", "الضفة الغربية", "رام الله", "جنين", "نابلس", "خان يونس", "رفح"],
     ["palestin", "gaza", "west bank", "ramallah", "jenin", "nablus", "khan younis", "rafah"]),
    ("إسرائيل", "IL", ME, ["اسرائيل", "اسرائيلي", "تل ابيب", "نتنياهو"], ["israel", "tel aviv", "netanyahu", "=idf"]),
    ("مصر", "EG", ME, ["مصر", "مصري", "القاهرة", "سيناء"], ["egypt", "cairo", "sinai"]),
    ("السعودية", "SA", ME, ["السعودية", "سعودي", "الرياض"], ["saudi", "riyadh", "jeddah"]),
    ("الإمارات", "AE", ME, ["الامارات", "اماراتي", "ابوظبي", "ابو ظبي", "دبي"], ["emirat", "=uae", "abu dhabi", "dubai"]),
    ("قطر", "QA", ME, ["قطر", "قطري", "الدوحة"], ["qatar", "doha"]),
    ("الكويت", "KW", ME, ["الكويت", "كويتي"], ["kuwait"]),
    ("البحرين", "BH", ME, ["البحرين", "بحريني", "المنامة"], ["bahrain", "manama"]),
    ("عُمان", "OM", ME, ["سلطنة عمان", "العماني", "مسقط"], ["oman", "muscat"]),
    ("اليمن", "YE", ME, ["اليمن", "يمني", "صنعاء", "عدن", "الحوثي", "الحوثيين", "الحديدة", "مأرب", "تعز", "المكلا", "حضرموت"],
     ["yemen", "sanaa", "sana'a", "=aden", "houthi", "hodeidah", "marib", "taiz", "hadramout"]),
    ("ليبيا", "LY", AF, ["ليبيا", "ليبي", "طرابلس الليبية", "بنغازي", "حفتر"], ["libya", "tripoli", "benghazi", "haftar"]),
    ("تونس", "TN", AF, ["تونس", "تونسي"], ["tunisia", "tunis"]),
    ("الجزائر", "DZ", AF, ["الجزائر", "جزائري"], ["algeria", "algiers"]),
    ("المغرب", "MA", AF, ["المغرب", "مغربي", "الرباط"], ["morocc", "rabat"]),
    ("موريتانيا", "MR", AF, ["موريتانيا", "موريتاني", "نواكشوط"], ["mauritania", "nouakchott"]),
    ("السودان", "SD", AF, ["السودان", "سوداني", "الخرطوم", "الفاشر", "دارفور", "الدعم السريع"],
     ["=sudan", "sudanese", "khartoum", "darfur", "el fasher", "=rsf"]),
    ("جنوب السودان", "SS", AF, ["جنوب السودان", "جوبا"], ["south sudan", "=juba"]),
    ("الصومال", "SO", AF, ["الصومال", "صومالي", "مقديشو"], ["somali", "mogadishu", "al-shabaab", "al shabaab"]),
    ("مالي", "ML", AF, ["جمهورية مالي", "دولة مالي", "شمال مالي", "وسط مالي", "باماكو"], ["=mali", "malian", "bamako"]),
    ("النيجر", "NE", AF, ["النيجر", "نيامي"], ["=niger", "nigerien", "niamey"]),
    ("بوركينا فاسو", "BF", AF, ["بوركينا فاسو", "بوركينا", "واغادوغو"], ["burkina", "ouagadougou"]),
    ("نيجيريا", "NG", AF, ["نيجيريا", "نيجيري", "ابوجا", "بوكو حرام"], ["nigeria", "abuja", "boko haram"]),
    ("تشاد", "TD", AF, ["تشاد", "تشادي", "انجامينا"], ["=chad", "chadian", "n'djamena"]),
    ("إثيوبيا", "ET", AF, ["اثيوبيا", "اثيوبي", "اديس ابابا", "تيغراي"], ["ethiopia", "addis ababa", "tigray"]),
    ("الكونغو الديمقراطية", "CD", AF, ["الكونغو", "كينشاسا"], ["congo", "kinshasa", "=m23"]),
    ("موزمبيق", "MZ", AF, ["موزمبيق", "كابو ديلغادو"], ["mozambiq", "cabo delgado"]),
    ("أفغانستان", "AF", AS, ["افغانستان", "افغاني", "طالبان"], ["afghan", "kabul", "taliban"]),
    ("باكستان", "PK", AS, ["باكستان", "باكستاني", "اسلام اباد", "بلوشستان"], ["pakistan", "islamabad", "balochistan", "baloch"]),
    ("الهند", "IN", AS, ["الهند", "هندي", "نيودلهي", "كشمير"], ["=india", "=indian", "new delhi", "kashmir", "=modi"]),
    ("الصين", "CN", AS, ["الصين", "صيني", "بكين", "شي جين بينغ"], ["china", "chinese", "beijing", "xi jinping"]),
    ("تايوان", "TW", AS, ["تايوان", "تايبيه"], ["taiwan", "taipei"]),
    ("كوريا الشمالية", "KP", AS, ["كوريا الشمالية", "بيونغ يانغ", "كيم جونغ"], ["north korea", "pyongyang", "kim jong"]),
    ("كوريا الجنوبية", "KR", AS, ["كوريا الجنوبية"], ["south korea", "seoul"]),
    ("اليابان", "JP", AS, ["اليابان", "ياباني", "طوكيو"], ["japan", "tokyo"]),
    ("ميانمار", "MM", AS, ["ميانمار", "بورما"], ["myanmar", "burma"]),
    ("إندونيسيا", "ID", AS, ["اندونيسيا", "جاكرتا"], ["indonesia", "jakarta"]),
    ("الفلبين", "PH", AS, ["الفلبين", "مانيلا"], ["philippin", "manila"]),
    ("روسيا", "RU", EU, ["روسيا", "روسي", "الروس", "موسكو", "الكرملين", "بوتين"], ["russia", "moscow", "kremlin", "putin"]),
    ("أوكرانيا", "UA", EU, ["اوكرانيا", "اوكراني", "كييف", "زيلينسكي", "خاركيف", "دونباس"],
     ["ukrain", "kyiv", "kiev", "zelensk", "kharkiv", "donbas"]),
    ("بيلاروسيا", "BY", EU, ["بيلاروسيا", "مينسك"], ["belarus", "minsk", "lukashenko"]),
    ("بريطانيا", "GB", EU, ["بريطانيا", "بريطاني", "المملكة المتحدة", "لندن"], ["britain", "british", "united kingdom", "=uk", "london"]),
    ("فرنسا", "FR", EU, ["فرنسا", "فرنسي", "باريس", "ماكرون"], ["france", "=french", "paris", "macron"]),
    ("ألمانيا", "DE", EU, ["المانيا", "الماني", "برلين"], ["german", "berlin"]),
    ("إيطاليا", "IT", EU, ["ايطاليا", "ايطالي", "روما"], ["italy", "italian", "=rome"]),
    ("إسبانيا", "ES", EU, ["اسبانيا", "اسباني", "مدريد"], ["spain", "spanish", "madrid"]),
    ("بولندا", "PL", EU, ["بولندا", "وارسو"], ["poland", "warsaw"]),
    ("السويد", "SE", EU, ["السويد", "ستوكهولم"], ["sweden", "swedish", "stockholm"]),
    ("هولندا", "NL", EU, ["هولندا", "امستردام"], ["netherlands", "=dutch", "amsterdam"]),
    ("بلجيكا", "BE", EU, ["بلجيكا"], ["belgium", "belgian"]),
    ("اليونان", "GR", EU, ["اليونان", "اثينا"], ["greece", "greek", "athens"]),
    ("صربيا", "RS", EU, ["صربيا", "بلغراد"], ["serbia", "belgrade"]),
    ("أذربيجان", "AZ", CA, ["اذربيجان", "باكو"], ["azerbaijan", "=baku"]),
    ("أرمينيا", "AM", CA, ["ارمينيا", "يريفان"], ["armenia", "yerevan"]),
    ("جورجيا", "GE", CA, ["جورجيا", "تبليسي"], ["=georgia", "tbilisi"]),
    ("كازاخستان", "KZ", CA, ["كازاخستان", "استانا"], ["kazakhstan", "astana"]),
    ("أوزبكستان", "UZ", CA, ["اوزبكستان", "طشقند"], ["uzbekistan", "tashkent"]),
    ("طاجيكستان", "TJ", CA, ["طاجيكستان", "دوشنبه"], ["tajikistan", "dushanbe"]),
    ("الولايات المتحدة", "US", AM, ["الولايات المتحدة", "امريكا", "اميركا", "امريكي", "اميركي", "واشنطن", "البنتاغون", "البيت الابيض", "ترامب"],
     ["united states", "u.s.", "america", "washington", "pentagon", "white house", "=trump"]),
    ("كندا", "CA", AM, ["كندا", "كندي", "اوتاوا"], ["canada", "canadian", "ottawa"]),
    ("المكسيك", "MX", AM, ["المكسيك", "مكسيكي"], ["mexic"]),
    ("فنزويلا", "VE", AM, ["فنزويلا", "كاراكاس", "مادورو"], ["venezuela", "caracas", "maduro"]),
    ("كولومبيا", "CO", AM, ["كولومبيا", "بوغوتا"], ["colombia", "bogota"]),
    ("البرازيل", "BR", AM, ["البرازيل", "برازيلي"], ["brazil"]),
    ("أستراليا", "AU", OC, ["استراليا", "كانبرا"], ["australia", "canberra"]),
]
COUNTRY_INFO = {c[0]: {"iso": c[1], "region": c[2]} for c in COUNTRIES}
_AR_DIAC = re.compile(r"[\u064B-\u0652\u0640]")


def norm_ar(t):
    t = _AR_DIAC.sub("", t or "")
    return t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي")


def _country_re(ar_terms, en_terms):
    ar = "|".join(sorted({re.escape(norm_ar(t)) for t in ar_terms}, key=len, reverse=True))
    pre = [re.escape(t) for t in en_terms if not t.startswith("=")]
    exact = [re.escape(t[1:]) for t in en_terms if t.startswith("=")]
    en_parts = []
    if pre:
        en_parts.append(r"\b(?:" + "|".join(pre) + ")")
    if exact:
        en_parts.append(r"\b(?:" + "|".join(exact) + r")\b")
    ar_re = re.compile(r"(?<![\u0600-\u06FF])(?:[وفبلك])?(?:ال|ل)?(?:" + ar +
                       r")(?:ة|ات|ون|ين|يون|يين|ي|ية)?(?![\u0600-\u06FF])")
    return ar_re, re.compile("|".join(en_parts))


AR_FALSE = ("قطرة", "قطرات")       # كلمات تشبه أسماء دول وليست منها
COUNTRY_RES = [(c[0], *_country_re(c[3], c[4])) for c in COUNTRIES]


def compute_countries(*texts):
    """يعيد الدول المذكورة في النص بترتيب ظهورها: |سوريا|تركيا|"""
    raw = " ".join(t for t in texts if t)
    ar_t, en_t = norm_ar(raw), raw.lower()
    found = []
    for name, ar_re, en_re in COUNTRY_RES:
        m1 = next((m for m in ar_re.finditer(ar_t) if not m.group(0).endswith(AR_FALSE)), None)
        m2 = en_re.search(en_t)
        pos = min([m.start() for m in (m1, m2) if m] or [-1])
        if pos >= 0:
            found.append((pos, name))
    found.sort()
    names = [n for _, n in found][:6]
    return ("|" + "|".join(names) + "|") if names else ""


# ───────────────────────── الأخبار النوعية: كشف الأحداث الميدانية المهمة ─────────────────────────
# (الاسم، اللون، كلمات عربية، كلمات إنجليزية). الترتيب مهم: الأدق أولاً.
EVENT_TYPES = [
    ("اغتيال", "#DC2626", ["اغتيال", "اغتال", "يغتال", "تغتال", "اغتيل", "تصفية القيادي", "مقتل القيادي", "مقتل قيادي", "مقتل زعيم", "استهداف القيادي"],
     ["assassinat", "targeted killing", "killed a senior", "killed the leader", "killed top"]),
    ("اعتقال شخصية مهمة", "#A855F7", [], []),          # يُستنتج: اعتقال + صفة قيادية
    ("توغل إسرائيلي", "#2563EB", [], []),               # يُستنتج: توغل/اقتحام + إسرائيل
    ("ضربة مسيّرة", "#F97316", ["طائرة مسيرة", "طائرات مسيرة", "بطائرة مسيرة", "مسيرة انتحارية", "مسيرات انتحارية", "هجوم بالمسيرات",
                                 "ضربة بمسيرة", "استهدفت مسيرة", "درون", "مسيرة اسرائيلية", "مسيرة تركية", "مسيرة روسية", "مسيرة اوكرانية"],
     ["drone strike", "drone attack", "kamikaze drone", "uav strike", "drone hit", "drones hit", "drone swarm", "shahed"]),
    ("غارة جوية", "#EF4444", ["غارة", "غارات", "قصف جوي", "ضربة جوية", "ضربات جوية", "الطيران الحربي", "طائرات حربية", "قصف اسرائيلي", "قصف روسي"],
     ["airstrike", "air strike", "air raid", "warplanes", "bombarded", "bombing raid", "struck by israeli", "israeli strike", "russian strike"]),
    ("هجوم صاروخي", "#EAB308", ["قصف صاروخي", "هجوم صاروخي", "رشقة صاروخية", "رشقات صاروخية", "سقوط صاروخ", "اطلاق صواريخ", "صواريخ على",
                                 "صاروخ باليستي", "قذائف صاروخية"],
     ["missile strike", "missile attack", "rocket fire", "rockets fired", "ballistic missile", "rocket attack", "missiles at"]),
    ("انفجار", "#F59E0B", ["انفجار", "تفجير", "عبوة ناسفة", "سيارة مفخخة", "مفخخة", "انتحاري", "حزام ناسف"],
     ["explosion", "blast", "car bomb", "suicide bomb", "=ied", "detonat", "explosive device"]),
    ("هجوم إرهابي", "#B91C1C", ["هجوم ارهابي", "عملية ارهابية", "اعتداء ارهابي", "تبنى تنظيم", "يتبنى الهجوم", "تبنت داعش", "داعش يتبنى"],
     ["terror attack", "terrorist attack", "claimed responsibility", "jihadist attack", "isis claims", "islamic state claims"]),
    ("اشتباك", "#FB923C", ["اشتباك", "اشتباكات", "مواجهات مسلحة", "هجوم مسلح", "تبادل اطلاق النار", "معارك عنيفة", "كمين"],
     ["clash", "firefight", "gunfight", "fighting erupted", "gunmen", "armed attack", "shootout", "ambush", "heavy fighting"]),
    ("اعتقال", "#8B5CF6", ["اعتقال", "اعتقل", "تعتقل", "يعتقل", "اعتقالات", "القبض على", "قبض على", "توقيف", "احتجاز", "مداهمة", "مداهمات", "تداهم"],
     ["arrest", "detained", "apprehended", "taken into custody", "raid on", "raids on"]),
    ("توغل عسكري", "#0EA5E9", ["توغل", "توغلت", "تتوغل", "يتوغل", "اقتحام", "اقتحمت", "اقتحم", "تقتحم", "يقتحم", "اقتحامات"], ["incursion", "stormed", "ground raid", "ground incursion"]),
]
EVENT_COLORS = {e[0]: e[1] for e in EVENT_TYPES}
EVENT_CATS = ("world", "arab", "war", "terror", "intel", "tweets", "keywords", "think_global", "think_arab")
STUDY_EV_CATS = ("think_global", "think_arab")      # المقالات والدراسات: يُفحص العنوان فقط
_VIP_AR = ["قيادي", "القيادي", "زعيم", "قائد", "امير", "مسؤول", "وزير", "جنرال", "مستشار", "نائب", "رئيس", "ضابط كبير"]
_VIP_EN = ["leader", "commander", "senior", "top official", "minister", "general", "emir", "chief", "deputy", "mastermind", "kingpin"]
_ISR_AR = ["اسرائيل", "الاحتلال", "الجيش الاسرائيلي", "قوات الاحتلال", "جيش الاحتلال"]
_ISR_EN = ["israel", "=idf"]


def _ar_re(terms):
    if not terms:
        return None
    alt = "|".join(sorted({re.escape(norm_ar(t)) for t in terms}, key=len, reverse=True))
    return re.compile(r"(?<![\u0600-\u06FF])(?:[وفبلك])?(?:ال)?(?:" + alt + ")")


def _en_re(terms):
    if not terms:
        return None
    pre = [re.escape(t) for t in terms if not t.startswith("=")]
    exact = [re.escape(t[1:]) for t in terms if t.startswith("=")]
    parts = ([r"\b(?:" + "|".join(pre) + ")"] if pre else []) + ([r"\b(?:" + "|".join(exact) + r")\b"] if exact else [])
    return re.compile("|".join(parts))


EVENT_RES = [(e[0], _ar_re(e[2]), _en_re(e[3])) for e in EVENT_TYPES]
VIP_RES = (_ar_re(_VIP_AR), _en_re(_VIP_EN))
ISR_RES = (_ar_re(_ISR_AR), _en_re(_ISR_EN))
_EVR = {n: (a, b) for n, a, b in EVENT_RES}


def _hit(pair, ar_t, en_t):
    a, b = pair
    return bool((a and a.search(ar_t)) or (b and b.search(en_t)))


def events_for(cat, title, title_ar=None, summary=None, summary_ar=None):
    if cat in STUDY_EV_CATS:
        return compute_events(cat, title, title_ar)
    return compute_events(cat, title, title_ar, (summary or "")[:300], (summary_ar or "")[:300])


def compute_events(cat, *texts):
    """يصنّف الخبر حسب نوع الحدث الميداني (غارة، انفجار، اعتقال...). يُطبَّق على الأخبار فقط."""
    if cat not in EVENT_CATS:
        return ""
    raw = " ".join(t for t in texts if t)
    ar_t, en_t = norm_ar(raw), raw.lower()
    found = [n for n, a, b in EVENT_RES if (a or b) and _hit((a, b), ar_t, en_t)]
    if "اعتقال" in found and _hit(VIP_RES, ar_t, en_t):
        found[found.index("اعتقال")] = "اعتقال شخصية مهمة"
    if "توغل عسكري" in found and _hit(ISR_RES, ar_t, en_t):
        found[found.index("توغل عسكري")] = "توغل إسرائيلي"
    order = [e[0] for e in EVENT_TYPES]
    found = sorted(set(found), key=order.index)[:3]
    return ("|" + "|".join(found) + "|") if found else ""


# ───────────────────────── وسوم ملكية وسائل الإعلام ─────────────────────────
# «حكومي»: خاضع لسيطرة حكومة. «ممول حكومياً»: تموّله حكومة مع استقلال تحريري معلن. «ملكية مرتبطة بحكومة»: ملكية خاصة قريبة من حكومة.
MEDIA_LABELS = [
    (["روسيا اليوم عربي", "آر تي عربي", "rtarabic"], "حكومي", "روسيا"),
    (["بي بي سي - العالم", "بي بي سي عربي", "بي بي سي - اقتصاد", "بي بي سي عاجل", "يوتيوب: بي بي سي عربي", "bbcarabic"], "ممول حكومياً", "بريطانيا"),
    (["دويتشه فيله", "دويتشه فيله عربي", "يوتيوب: دويتشه فيله"], "ممول حكومياً", "ألمانيا"),
    (["فرانس 24", "فرانس 24 عربي", "يوتيوب: فرانس 24", "france24_ar"], "ممول حكومياً", "فرنسا"),
    (["الجزيرة", "الجزيرة نت", "الجزيرة الإنجليزية", "يوتيوب: الجزيرة", "يوتيوب: الجزيرة الإنجليزية", "AJArabic", "AJENews"], "ممول حكومياً", "قطر"),
    (["العربية", "يوتيوب: العربية", "الحدث", "alarabiya", "AlHadath"], "ملكية مرتبطة بحكومة", "السعودية"),
    (["الشرق الأوسط", "اقتصاد الشرق مع بلومبرغ", "الشرق للأخبار", "إندبندنت عربية", "asharqnews"], "ملكية مرتبطة بحكومة", "السعودية"),
    (["سكاي نيوز عربية", "يوتيوب: سكاي نيوز عربية", "skynewsarabia"], "ملكية مرتبطة بحكومة", "الإمارات"),
    (["أخبار الأمم المتحدة: الشرق الأوسط", "أخبار الأمم المتحدة بالعربية"], "منظمة دولية", ""),
]
_ML = {}
for names, kind_, ctry_ in MEDIA_LABELS:
    for n_ in names:
        _ML[n_.lower()] = (kind_, ctry_)


def media_label(source_ar, source=""):
    k = _ML.get((source_ar or "").lower()) or _ML.get((source or "").replace("t.me/", "").lower())
    return f"{k[0]} · {k[1]}" if k and k[1] else (k[0] if k else "")


# ───────────────────────── قاعدة البيانات ─────────────────────────
WRITE_LOCK = threading.Lock()


def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def q(sql, args=(), one=False):
    con = db()
    try:
        rows = con.execute(sql, args).fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        con.close()


def x(sql, args=(), many=False):
    with WRITE_LOCK:
        con = db()
        try:
            if many:
                con.executemany(sql, args)
            else:
                con.execute(sql, args)
            con.commit()
        finally:
            con.close()


def init_db():
    con = db()
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS items(
        id TEXT PRIMARY KEY, cat TEXT, source TEXT, source_ar TEXT,
        title TEXT, summary TEXT, link TEXT, published INTEGER, fetched INTEGER,
        lang TEXT, title_ar TEXT, summary_ar TEXT, translated INTEGER DEFAULT 0,
        tags TEXT DEFAULT '', kind TEXT DEFAULT 'article', author TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS ix_items_pub ON items(published DESC);
    CREATE INDEX IF NOT EXISTS ix_items_cat ON items(cat, published DESC);
    CREATE INDEX IF NOT EXISTS ix_items_tr ON items(translated);
    CREATE TABLE IF NOT EXISTS source_status(
        name TEXT PRIMARY KEY, cat TEXT, ok INTEGER, count INTEGER, via TEXT,
        last_try INTEGER, last_ok INTEGER, error TEXT
    );
    CREATE TABLE IF NOT EXISTS keywords(word TEXT PRIMARY KEY, added INTEGER);
    CREATE TABLE IF NOT EXISTS tcache(h TEXT PRIMARY KEY, ar TEXT);
    CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS tg_sent(id TEXT PRIMARY KEY, sent INTEGER, title TEXT);
    CREATE TABLE IF NOT EXISTS books(
        id TEXT PRIMARY KEY, topic TEXT, title TEXT, title_ar TEXT, authors TEXT, publisher TEXT,
        published TEXT, year INTEGER, description TEXT, description_ar TEXT, image TEXT, link TEXT,
        lang TEXT, pages INTEGER, categories TEXT, fetched INTEGER, translated INTEGER DEFAULT 0
    );
    """)
    cols = {r[1] for r in con.execute("PRAGMA table_info(items)")}
    if "countries" not in cols:
        con.execute("ALTER TABLE items ADD COLUMN countries TEXT")
    if "events" not in cols:
        con.execute("ALTER TABLE items ADD COLUMN events TEXT")
    if "cluster" not in cols:
        con.execute("ALTER TABLE items ADD COLUMN cluster TEXT")
        con.execute("ALTER TABLE items ADD COLUMN nsrc INTEGER DEFAULT 1")
    scols = {r[1] for r in con.execute("PRAGMA table_info(sanctions)")}
    if scols and "groups" not in scols:
        con.execute("ALTER TABLE sanctions ADD COLUMN groups TEXT")
    if "edits" not in cols:
        con.execute("ALTER TABLE items ADD COLUMN edits INTEGER DEFAULT 0")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS title_changes(item_id TEXT, old_title TEXT, new_title TEXT, old_ar TEXT, changed INTEGER);
    CREATE INDEX IF NOT EXISTS ix_tc ON title_changes(changed DESC);
    CREATE TABLE IF NOT EXISTS archive(item_id TEXT PRIMARY KEY, link TEXT, title TEXT, title_ar TEXT, source TEXT,
        cat TEXT, published INTEGER, captured INTEGER, paras TEXT, paras_ar TEXT, via TEXT, wayback TEXT, reason TEXT);
    CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, title TEXT, descr TEXT, created INTEGER, updated INTEGER);
    CREATE TABLE IF NOT EXISTS case_items(case_id TEXT, item_id TEXT, note TEXT, added INTEGER, snap TEXT,
        PRIMARY KEY(case_id, item_id));
    CREATE TABLE IF NOT EXISTS sanctions(uid TEXT PRIMARY KEY, list TEXT, name TEXT, type TEXT, program TEXT,
        remarks TEXT, listed TEXT, first_seen INTEGER, is_new INTEGER DEFAULT 0, groups TEXT);
    CREATE INDEX IF NOT EXISTS ix_sanc_seen ON sanctions(first_seen DESC);
    """)
    con.execute("CREATE TABLE IF NOT EXISTS icons(key TEXT PRIMARY KEY, ctype TEXT, data BLOB, fetched INTEGER, ok INTEGER)")
    con.execute("""CREATE TABLE IF NOT EXISTS net_alerts(id TEXT PRIMARY KEY, iso TEXT, name TEXT, source TEXT,
                   level TEXT, ts INTEGER, value REAL, hist REAL)""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_net_ts ON net_alerts(ts DESC)")
    con.execute("""CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, kind TEXT, key TEXT, level INTEGER,
                   cnt INTEGER, base REAL, created INTEGER, msg TEXT, detail TEXT)""")
    con.commit()
    con.close()


def kv_get(k, default=None):
    r = q("SELECT v FROM kv WHERE k=?", (k,), one=True)
    return r["v"] if r else default


def kv_set(k, v):
    x("INSERT OR REPLACE INTO kv(k, v) VALUES(?, ?)", (k, str(v)))


def cleanup_removed():
    """يحذف بقايا الميزات الملغاة (GDELT) من قاعدة البيانات."""
    x("DELETE FROM items WHERE cat='gdelt'")
    x("DELETE FROM source_status WHERE cat='gdelt' OR name LIKE 'GDELT:%'")


def repair_translations():
    """يحذف «ترجمات» محفوظة ليست عربية (كانت تُرجَع أحياناً بالنص الأصلي) ويعيد ترجمة عناصرها."""
    bad = [(r["h"],) for r in q("SELECT h, ar FROM tcache") if not ARABIC_RE.search(r["ar"] or "")]
    if bad:
        x("DELETE FROM tcache WHERE h=?", bad, many=True)
    redo = [(r["id"],) for r in q("SELECT id, title_ar FROM items WHERE translated=1 AND lang != 'ar'")
            if not ARABIC_RE.search(r["title_ar"] or "")]
    if redo:
        x("UPDATE items SET translated=0 WHERE id=?", redo, many=True)
    x("UPDATE items SET translated=0 WHERE translated < 0")
    if bad or redo:
        log.info("إصلاح الترجمة: حُذفت %s ترجمة غير صالحة، وأُعيدت %s مادة للترجمة", len(bad), len(redo))


def load_sources():
    if not os.path.exists(SOURCES_PATH):
        with open(SOURCES_PATH, "w", encoding="utf-8") as f:
            json.dump({"version": SOURCES_VERSION, "feeds": DEFAULT_FEEDS, "x_accounts": DEFAULT_X_ACCOUNTS,
                       "telegram_channels": DEFAULT_TG_CHANNELS},
                      f, ensure_ascii=False, indent=2)
    with open(SOURCES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("feeds", DEFAULT_FEEDS)
    data.setdefault("x_accounts", DEFAULT_X_ACCOUNTS)
    data.setdefault("telegram_channels", DEFAULT_TG_CHANNELS)
    data.setdefault("bluesky_accounts", DEFAULT_BSKY)
    if data.get("version", 1) < SOURCES_VERSION:      # إضافة المصادر الجديدة دون حذف تعديلاتك
        defaults = {f["name_ar"]: f for f in DEFAULT_FEEDS}
        if data.get("version", 1) < 10:               # تصحيح روابط مصادر كانت معطلة
            fixed = {"مركز مالكوم كير–كارنيغي", "مشروع الاستخبارات - مركز بلفر", "مجلة الاستخبارات والأمن القومي",
                     "وزارة الدفاع التركية", "التقنية ضد الإرهاب", "المركز الأفريقي لدراسة وأبحاث الإرهاب ACSRT"}
            data["feeds"] = [dict(defaults[f["name_ar"]]) if f["name_ar"] in fixed and f["name_ar"] in defaults else f
                             for f in data["feeds"] if f["name_ar"] != "دراسات الأمن بجامعة ماكواري"]
        have = {f["name_ar"] for f in data["feeds"]}
        data["feeds"] += [f for f in DEFAULT_FEEDS if f["name_ar"] not in have]
        tg = data.setdefault("telegram_channels", [])
        have_tg = {c["channel"].lower() for c in tg}
        tg += [c for c in DEFAULT_TG_CHANNELS if c["channel"].lower() not in have_tg]
        bs = data.setdefault("bluesky_accounts", [])
        have_bs = {c["handle"].lower() for c in bs}
        bs += [c for c in DEFAULT_BSKY if c["handle"].lower() not in have_bs]
        data["version"] = SOURCES_VERSION
        with open(SOURCES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return data


SOURCES_LOCK = threading.Lock()


def save_sources(data):
    with SOURCES_LOCK, open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ───────────────────────── أدوات نصية ─────────────────────────
TAG_RE = re.compile(r"<[^>]+>")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def now():
    return int(time.time())


def clean(text):
    text = html.unescape(TAG_RE.sub(" ", text or ""))
    return " ".join(text.split())


def is_arabic(text):
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if ARABIC_RE.match(c)) / len(letters) > 0.4


def get_keywords():
    return [r["word"] for r in q("SELECT word FROM keywords ORDER BY added")]


def compute_tags(text, kws, keep=""):
    t = (text or "").lower()
    tags = [tag for tag, keys in TOPIC_TAGS.items() if any(k in t for k in keys)]
    for w in kws:
        if w.lower() in t:
            tags.append("★" + w)
    for k in (keep or "").strip("|").split("|"):
        if k.startswith("★") and k not in tags:
            tags.append(k)
    return ("|" + "|".join(tags) + "|") if tags else ""


# ───────────────────────── الترجمة: عدة مزودين، وكل مزود متعطل يُتجاوز تلقائياً ─────────────────────────
GT_URL = "https://translate.googleapis.com/translate_a/single"
GT_MULTI = "https://clients5.google.com/translate_a/t"
LINGVA = ["https://lingva.ml", "https://lingva.lunar.icu", "https://lingva.garudalinux.org",
          "https://translate.plausibility.cloud", "https://lingva.dialectapp.org"]
_LINGVA_BAD = {}
TR_SESSION = requests.Session()
TR_SESSION.headers.update(HEADERS)
PIECE_CHARS = 1200          # أقصى طول للقطعة الواحدة
BATCH_CHARS = 3500          # أقصى مجموع أحرف في الدفعة
BATCH_ITEMS = 40
TRANSLATE_WORKERS = 2
PROVIDER_NAMES = {"bing": "Microsoft Bing", "microsoft": "Microsoft (مترجم Edge)", "google_multi": "Google (دفعات)", "google": "Google",
                  "lingva": "Lingva", "mymemory": "MyMemory", "deep": "deep-translator",
                  "claude": "Claude", "argos": "Argos (محلي بلا إنترنت)"}
# أقل فاصل زمني بين طلبين لكل مزود (ثوانٍ) — يمنع حظر Google وغيره بسبب كثرة الطلبات
MIN_GAP = {"bing": 0.7, "microsoft": 0.4, "google_multi": 2.5, "google": 2.0, "lingva": 0.8, "mymemory": 2.0, "deep": 2.0}
_GAP_LOCK = threading.Lock()
_GAP_NEXT = {}
PROV = {k: {"ok": 0, "fail": 0, "streak": 0, "off_until": 0, "err": ""} for k in PROVIDER_NAMES}
TR_STATS = {"ok": 0, "fail": 0, "last_error": "", "backoff_until": 0, "providers": PROV}


class RateLimited(Exception):
    pass


def _hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def has_ar(text):
    return bool(ARABIC_RE.search(text or ""))


def anthropic_key():
    try:
        return (kv_get("anthropic_key") or ANTHROPIC_KEY or "").strip()
    except Exception:
        return ANTHROPIC_KEY


def prov_ready(name):
    if name == "claude" and not anthropic_key():
        return False
    if name == "deep" and GoogleTranslator is None:
        return False
    if name == "argos" and argos_tr is None:
        return False
    return time.time() >= PROV[name]["off_until"]


def throttle(name):
    gap = MIN_GAP.get(name, 0)
    if not gap:
        return
    with _GAP_LOCK:
        now_t = time.time()
        slot = max(now_t, _GAP_NEXT.get(name, 0))
        _GAP_NEXT[name] = slot + gap
    if slot > now_t:
        time.sleep(slot - now_t)


def prov_result(name, ok, err=""):
    p = PROV[name]
    if ok:
        p["ok"] += 1
        p["streak"] = 0
    else:
        p["fail"] += 1
        p["streak"] += 1
        p["err"] = str(err)[:160]
        TR_STATS["last_error"] = f"{PROVIDER_NAMES[name]}: {p['err']}"
        if p["streak"] >= 3:      # ثلاث إخفاقات متتالية: نتجاوزه 10 دقائق
            p["off_until"] = time.time() + 600
            p["streak"] = 0


def _check(r):
    if r.status_code == 429 or "/sorry/" in str(getattr(r, "url", "")):
        raise RateLimited("حظر مؤقت بسبب كثرة الطلبات (429)")
    r.raise_for_status()
    if "text/html" in r.headers.get("Content-Type", "") and "translate_a" in str(getattr(r, "url", "")):
        raise RateLimited("Google أعاد صفحة تحقق بدل الترجمة (حظر مؤقت)")


def split_long(text, n=PIECE_CHARS):
    if len(text) <= n:
        return [text]
    chunks, cur = [], ""
    for part in re.split(r"(?<=[.!?؟؛])\s+", text):
        while len(part) > n:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(part[:n])
            part = part[n:]
        if cur and len(cur) + len(part) + 1 > n:
            chunks.append(cur)
            cur = part
        else:
            cur = (cur + " " + part).strip()
    if cur:
        chunks.append(cur)
    return chunks


# ── المزودون
_MS_TOKEN = {"t": "", "exp": 0}
_MS_LOCK = threading.Lock()


def ms_token(refresh=False):
    with _MS_LOCK:
        if refresh or not _MS_TOKEN["t"] or time.time() > _MS_TOKEN["exp"]:
            r = TR_SESSION.get("https://edge.microsoft.com/translate/auth", timeout=15)
            if r.status_code == 404:          # أوقفت Microsoft هذا الباب: نتجاوز المزود يوماً كاملاً
                PROV["microsoft"]["off_until"] = time.time() + 86400
            r.raise_for_status()
            _MS_TOKEN.update(t=r.text.strip(), exp=time.time() + 480)
        return _MS_TOKEN["t"]


_BING = {"ig": "", "key": "", "token": "", "exp": 0, "lock": threading.Lock()}


def bing_auth(refresh=False):
    with _BING["lock"]:
        if refresh or not _BING["token"] or time.time() > _BING["exp"]:
            r = TR_SESSION.get("https://www.bing.com/translator", timeout=20,
                               headers={"User-Agent": BROWSER_HEADERS.get("User-Agent", HEADERS["User-Agent"])})
            r.raise_for_status()
            ig = re.search(r'IG:"([^"]+)"', r.text)
            ab = re.search(r'params_AbusePreventionHelper\s*=\s*\[(\d+),"([^"]+)",(\d+)\]', r.text)
            if not (ig and ab):
                raise ValueError("تعذّر الحصول على رمز Bing")
            _BING.update(ig=ig.group(1), key=ab.group(1), token=ab.group(2),
                         exp=time.time() + min(int(ab.group(3)) / 1000, 3000) - 60)
        return _BING


def p_bing_one(text):
    for attempt in (0, 1):
        a = bing_auth(refresh=attempt == 1)
        throttle("bing")
        r = TR_SESSION.post(f"https://www.bing.com/ttranslatev3?isVertical=1&IG={a['ig']}&IID=translator.5023.1",
                            data={"fromLang": "auto-detect", "to": "ar", "text": text, "token": a["token"], "key": a["key"]},
                            headers={"User-Agent": BROWSER_HEADERS.get("User-Agent", HEADERS["User-Agent"]),
                                     "Referer": "https://www.bing.com/translator"}, timeout=25)
        _check(r)
        try:
            d = r.json()
        except Exception:
            d = None
        if isinstance(d, list) and d and d[0].get("translations"):
            return d[0]["translations"][0].get("text", "")
        if attempt == 0:
            continue
        raise ValueError("استجابة Bing غير متوقعة")


def p_bing(texts):
    """مترجم Microsoft Bing عبر صفحة الترجمة العامة: نجمع عدة فقرات في طلب واحد (حتى 950 حرفاً)."""
    out = [None] * len(texts)
    groups, cur, size = [], [], 0
    for i, t in enumerate(texts):
        if cur and size + len(t) + 1 > 950:
            groups.append(cur)
            cur, size = [], 0
        cur.append(i)
        size += len(t) + 1
    if cur:
        groups.append(cur)
    for g in groups:
        if len(g) == 1:                       # فقرة طويلة: نقسمها لأن Bing يقبل 1000 حرف كحد أقصى
            out[g[0]] = " ".join(p_bing_one(part) for part in split_long(texts[g[0]], 900))
            continue
        res = p_bing_one("\n".join(texts[i] for i in g)).split("\n")
        res = [x_.strip() for x_ in res if x_.strip()]
        if len(res) == len(g):
            for i, t in zip(g, res):
                out[i] = t
        else:
            for i in g:
                out[i] = p_bing_one(texts[i])
    return [o or "" for o in out]


def p_microsoft(texts):
    """مترجم Microsoft المدمج في متصفح Edge: دفعات كبيرة، بلا مفتاح."""
    for attempt in (0, 1):
        throttle("microsoft")
        r = TR_SESSION.post("https://api-edge.cognitive.microsofttranslator.com/translate",
                            params={"to": "ar", "api-version": "3.0"},
                            headers={"Authorization": "Bearer " + ms_token(refresh=attempt == 1),
                                     "Content-Type": "application/json"},
                            data=json.dumps([{"Text": t} for t in texts]), timeout=30)
        if r.status_code == 401 and attempt == 0:
            continue
        _check(r)
        data = r.json()
        if isinstance(data, list) and len(data) == len(texts):
            return [((d.get("translations") or [{}])[0]).get("text", "") for d in data]
        raise ValueError("استجابة غير متوقعة")
    raise ValueError("رمز الدخول مرفوض")


def p_google_multi(texts):
    throttle("google_multi")
    params = [("client", "dict-chrome-ex"), ("sl", "auto"), ("tl", "ar")] + [("q", t) for t in texts]
    r = TR_SESSION.get(GT_MULTI, params=params, timeout=25)
    _check(r)
    data = r.json()
    if isinstance(data, list):
        if len(texts) == 1 and data and isinstance(data[0], str):
            return [data[0]]
        if len(data) == len(texts):
            out = []
            for el in data:
                while isinstance(el, list):
                    el = el[0] if el else ""
                out.append(el if isinstance(el, str) else "")
            return out
    raise ValueError("استجابة غير متوقعة")


def p_google(text):
    throttle("google")
    r = TR_SESSION.get(GT_URL, params={"client": "gtx", "sl": "auto", "tl": "ar", "dt": "t", "q": text}, timeout=20)
    _check(r)
    return "".join(seg[0] for seg in r.json()[0] if seg and seg[0])


def p_lingva(text):
    last = None
    for base in LINGVA:
        if time.time() < _LINGVA_BAD.get(base, 0):      # مرآة متعطلة: نتجاوزها نصف ساعة
            continue
        try:
            throttle("lingva")
            r = TR_SESSION.get(f"{base}/api/v1/auto/ar/{quote(text, safe='')}", timeout=20)
            _check(r)
            return r.json().get("translation", "")
        except RateLimited:
            _LINGVA_BAD[base] = time.time() + 1800
            last = RateLimited("كل مرايا Lingva محظورة مؤقتاً")
        except Exception as e:
            _LINGVA_BAD[base] = time.time() + 1800
            last = e
    raise last or ValueError("Lingva لا يستجيب")


def p_mymemory(text):
    throttle("mymemory")
    params = {"q": text[:480], "langpair": "en|ar"}
    if MYMEMORY_EMAIL:
        params["de"] = MYMEMORY_EMAIL
    r = TR_SESSION.get("https://api.mymemory.translated.net/get", params=params, timeout=20)
    _check(r)
    d = r.json()
    if str(d.get("responseStatus")) not in ("200", "None"):
        raise ValueError(str(d.get("responseDetails"))[:120])
    return (d.get("responseData") or {}).get("translatedText", "")


def p_deep(text):
    throttle("deep")
    return GoogleTranslator(source="auto", target="ar").translate(text)


_ARGOS = {"ready": False, "lock": threading.Lock()}


def p_argos(text):
    """مترجم محلي بلا إنترنت (من الإنجليزية فقط). يُنزّل نموذج الترجمة مرة واحدة عند أول استخدام."""
    with _ARGOS["lock"]:
        if not _ARGOS["ready"]:
            langs = {l.code for l in argos_tr.get_installed_languages()}
            if not {"en", "ar"} <= langs:
                argos_pkg.update_package_index()
                pkg = next(pk for pk in argos_pkg.get_available_packages() if pk.from_code == "en" and pk.to_code == "ar")
                argos_pkg.install_from_path(pkg.download())
            _ARGOS["ready"] = True
    return argos_tr.translate(text, "en", "ar")


def p_claude(texts):
    prompt = ("Translate each string in this JSON array into Modern Standard Arabic, as a professional news "
              "translator. Keep names of people, places and organisations accurate. Reply with ONLY a JSON array "
              "of the translations, same length and order, no commentary.\n\n" + json.dumps(texts, ensure_ascii=False))
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, json={
        "model": CLAUDE_MODEL, "max_tokens": 8000, "messages": [{"role": "user", "content": prompt}]},
        headers={"x-api-key": anthropic_key(), "anthropic-version": "2023-06-01", "content-type": "application/json"})
    _check(r)
    txt = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip()
    out = json.loads(txt)
    if not isinstance(out, list) or len(out) != len(texts):
        raise ValueError("عدد الترجمات لا يطابق")
    return [str(o) for o in out]


SINGLE_CHAIN = [("bing", p_bing_one), ("google", p_google), ("microsoft", lambda t: p_microsoft([t])[0]), ("lingva", p_lingva),
                ("deep", p_deep), ("mymemory", p_mymemory), ("argos", p_argos)]


def _fail(name, e):
    if isinstance(e, RateLimited):
        PROV[name]["off_until"] = time.time() + 1800     # حظر مؤقت: نريحه نصف ساعة
        if name in ("google", "google_multi", "deep"):   # الثلاثة يستخدمون Google نفسه
            for n_ in ("google", "google_multi", "deep"):
                PROV[n_]["off_until"] = max(PROV[n_]["off_until"], time.time() + 1800)
    prov_result(name, False, e)


def translate_piece(text):
    """قطعة واحدة عبر سلسلة المزودين، ولا نقبل إلا ناتجاً عربياً."""
    for name, fn in SINGLE_CHAIN:
        if not prov_ready(name):
            continue
        try:
            out = fn(text)
            if has_ar(out):
                prov_result(name, True)
                return out.strip()
            prov_result(name, False, "أعاد نصاً غير عربي")
        except Exception as e:
            _fail(name, e)
    return None


def _subchunks(idx, pieces, limit):
    out, cur, size = [], [], 0
    for j in idx:
        if cur and size + len(pieces[j]) > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(j)
        size += len(pieces[j])
    if cur:
        out.append(cur)
    return out


def _batch_with(name, fn, pieces, res, limit):
    missing = [j for j, t in enumerate(res) if not t]
    if not missing or not prov_ready(name):
        return
    for chunk in _subchunks(missing, pieces, limit):
        if not prov_ready(name):
            return
        try:
            got = fn([pieces[j] for j in chunk])
            good = 0
            for j, t in zip(chunk, got):
                if has_ar(t):
                    res[j] = t.strip()
                    good += 1
            if good:
                prov_result(name, True)
            else:
                prov_result(name, False, "أعاد نصاً غير عربي")
        except Exception as e:
            _fail(name, e)


def translate_batch(pieces):
    """دفعة: Microsoft ثم Google (دفعات) ثم Claude إن وُجد مفتاحه، ثم قطعة قطعة."""
    res = [None] * len(pieces)
    _batch_with("bing", p_bing, pieces, res, 3000)
    _batch_with("microsoft", p_microsoft, pieces, res, 4500)
    _batch_with("google_multi", p_google_multi, pieces, res, 1800)
    _batch_with("claude", p_claude, pieces, res, 12000)
    for j, t in enumerate(res):
        if not t:
            res[j] = translate_piece(pieces[j])
    return res


def translate_many(texts):
    """يترجم قائمة نصوص بأقل عدد من الطلبات. يعيد قائمة بنفس الطول (None عند الفشل)."""
    out = [None] * len(texts)
    norm = [" ".join((t or "").split()) for t in texts]
    todo = []
    for i, t in enumerate(norm):
        if not t:
            out[i] = ""
        elif is_arabic(t):
            out[i] = t
        else:
            todo.append(i)
    if todo:   # الذاكرة المؤقتة (ترجمات عربية فقط)
        hashes = {i: _hash(norm[i]) for i in todo}
        found, hl = {}, list(set(hashes.values()))
        for k in range(0, len(hl), 400):
            part = hl[k:k + 400]
            for r in q(f"SELECT h, ar FROM tcache WHERE h IN ({','.join('?' * len(part))})", part):
                if has_ar(r["ar"]):
                    found[r["h"]] = r["ar"]
        rest = []
        for i in todo:
            if hashes[i] in found:
                out[i] = found[hashes[i]]
            else:
                rest.append(i)
        todo = rest
    if not todo:
        return out
    pieces = [(i, k, p) for i in todo for k, p in enumerate(split_long(norm[i]))]
    batches, cur, size = [], [], 0
    for pc in pieces:
        if cur and (size + len(pc[2]) > BATCH_CHARS or len(cur) >= BATCH_ITEMS):
            batches.append(cur)
            cur, size = [], 0
        cur.append(pc)
        size += len(pc[2])
    if cur:
        batches.append(cur)

    def do_batch(batch):
        got = translate_batch([pc[2] for pc in batch])
        return {(pc[0], pc[1]): t for pc, t in zip(batch, got) if t}

    done = {}
    with ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS) as ex:
        for r in ex.map(do_batch, batches):
            done.update(r)
    cache_rows = []
    for i in todo:
        n_pieces = len(split_long(norm[i]))
        parts = [done.get((i, k)) for k in range(n_pieces)]
        if all(parts):
            out[i] = " ".join(parts)
            cache_rows.append((_hash(norm[i]), out[i]))
            TR_STATS["ok"] += 1
        else:
            TR_STATS["fail"] += 1
    if cache_rows:
        x("INSERT OR REPLACE INTO tcache(h, ar) VALUES(?, ?)", cache_rows, many=True)
    return out


def translate_text(text):
    return translate_many([text])[0]


def all_providers_down():
    return not any(prov_ready(n) for n in PROVIDER_NAMES)


def translate_rows(rows, summary_days=None):
    """يترجم صفوف عناصر ويحدّثها. summary_days: لا تُترجم ملخصات الأقدم من ذلك (تُترجم عند الفتح)."""
    titles = translate_many([r["title"] for r in rows])
    cutoff = now() - summary_days * 86400 if summary_days else 0
    want = [bool(r["summary"]) and r["published"] >= cutoff for r in rows]
    sums = translate_many([r["summary"] if w else "" for r, w in zip(rows, want)])
    kws = get_keywords()
    done, failed = [], []
    for r, t_ar, s_ar, w in zip(rows, titles, sums, want):
        if not t_ar:
            failed.append((r["id"],))
            continue
        s_ar = (s_ar or None) if w else None
        tags = compute_tags(" ".join([r["title"], r["summary"] or "", t_ar, s_ar or ""]), kws, r["tags"])
        ctry = compute_countries(r["title"], r["summary"], t_ar, s_ar)
        evs = events_for(r["cat"], r["title"], t_ar, r["summary"], s_ar)
        done.append((t_ar, s_ar, tags, ctry, evs, r["id"]))
    if done:
        x("UPDATE items SET title_ar=?, summary_ar=?, translated=1, tags=?, countries=?, events=? WHERE id=?", done, many=True)
    if failed:
        x("UPDATE items SET translated = translated - 1 WHERE id=?", failed, many=True)
    return len(done)


def translator_loop():
    last_retry = time.time()
    while True:
        try:
            if all_providers_down():
                time.sleep(30)
                continue
            if time.time() - last_retry > 600:      # إعادة محاولة ما فشل كل 10 دقائق
                x("UPDATE items SET translated=0 WHERE translated <= -3")
                last_retry = time.time()
            rows = q("SELECT id, cat, title, summary, tags, published FROM items "
                     "WHERE translated <= 0 AND translated > -3 ORDER BY published DESC LIMIT 40")
            if not rows:
                time.sleep(2)
                continue
            if not translate_rows(rows, summary_days=3):
                time.sleep(20)
        except Exception:
            log.exception("translator loop")
            time.sleep(5)


# ───────────────────────── الجلب ─────────────────────────
STATE = {"running": False, "last_cycle": 0, "next_cycle": 0, "cycle_secs": 0}
WAKE = threading.Event()


def safe(fn):
    def wrapper(*a):
        try:
            return fn(*a)
        except Exception as e:
            log.warning("%s failed: %s", fn.__name__, str(e)[:160])
    return wrapper


def gnews_url(query, lang="en"):
    if lang == "ar":
        loc = "hl=ar&gl=EG&ceid=EG:ar"
    elif lang == "tr":
        loc = "hl=tr&gl=TR&ceid=TR:tr"
    else:
        loc = "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&{loc}"


GN = {"lock": threading.Lock(), "next": 0.0, "pause_until": 0.0}
GN_GAP = 2.5                 # ثوانٍ بين طلبين لأخبار Google (يمنع الحظر بسبب كثرة الطلبات)


class GNewsPaused(Exception):
    pass


def _gnews_wait():
    if time.time() < GN["pause_until"]:
        raise GNewsPaused(f"أخبار Google موقوفة مؤقتاً بعد حظر 429، تُستأنف بعد {int((GN['pause_until'] - time.time()) / 60) + 1} دقيقة")
    with GN["lock"]:
        slot = max(time.time(), GN["next"])
        GN["next"] = slot + GN_GAP
    if slot > time.time():
        time.sleep(slot - time.time())


def fetch_rss(url):
    is_gn = "news.google.com/" in url
    if is_gn:
        _gnews_wait()
    r, err = None, None
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except Exception as e:
        err = e
    if is_gn and r is not None and r.status_code == 429:
        GN["pause_until"] = time.time() + 20 * 60
        r.raise_for_status()
    entries = []
    if r is not None and r.status_code == 200:
        entries = feedparser.parse(r.content).entries or []
    # الحماية (403/406/503) أو صفحة HTML بدل الخلاصة: إعادة المحاولة بهوية متصفح حقيقية
    if not entries and not is_gn and cffi_requests is not None:
        try:
            r2 = cffi_requests.get(url, impersonate="chrome", timeout=25)
            if r2.status_code == 200:
                entries = feedparser.parse(r2.content).entries or []
                if entries:
                    return entries
        except Exception:
            pass
    if entries:
        return entries
    if err:
        raise err
    if r is not None and r.status_code != 200:
        r.raise_for_status()
    return []


def parse_time(e):
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        t = e.get(k)
        if t:
            try:
                return min(int(calendar.timegm(t)), now())
            except Exception:
                pass
    return now()


def retention_days(cat):
    return STUDY_DAYS + 3 if cat in LONG_CATS else RETENTION_DAYS


def make_item(e, cat, source, source_ar, lang, kind="article", gnews=False,
              source_from_title=False, extra_tags=""):
    title = clean(e.get("title", ""))
    if not title:
        return None
    link = e.get("link", "") or ""
    if gnews and " - " in title:
        title, pub = title.rsplit(" - ", 1)
        if source_from_title:
            source_ar = pub.strip()
    summary = "" if gnews else clean(e.get("summary") or e.get("description") or "")[:700]
    if summary and summary[:80] == title[:80]:
        summary = ""
    ts = parse_time(e)
    if ts < now() - retention_days(cat) * 86400:
        return None
    iid = hashlib.sha1((link or (title + source_ar)).encode("utf-8")).hexdigest()[:20]
    ar = is_arabic(title)
    return {
        "id": iid, "cat": cat, "source": source, "source_ar": source_ar,
        "title": title, "summary": summary, "link": link, "published": ts,
        "fetched": now(), "lang": "ar" if ar else lang,
        "title_ar": title if ar else None, "summary_ar": summary if ar else None,
        "translated": 1 if ar else 0,
        "tags": compute_tags(title + " " + summary, get_keywords(), extra_tags) if ar else extra_tags,
        "kind": "video" if "youtube.com/watch" in link else kind, "author": "",
        "countries": compute_countries(title, summary),
        "events": events_for(cat, title, None, summary),
    }


def store_items(items):
    if not items:
        return
    cols = ["id", "cat", "source", "source_ar", "title", "summary", "link", "published", "fetched",
            "lang", "title_ar", "summary_ar", "translated", "tags", "kind", "author", "countries", "events"]
    check = [it for it in items if it["kind"] not in ("tweet",)]
    if check:
        ids = [it["id"] for it in check]
        old = {}
        for k in range(0, len(ids), 400):
            part = ids[k:k + 400]
            for r in q(f"SELECT id, title, title_ar FROM items WHERE id IN ({','.join('?' * len(part))})", part):
                old[r["id"]] = r
        changes = []
        for it in check:
            o = old.get(it["id"])
            if o and _title_changed(o["title"], it["title"]):
                changes.append((it, o))
        for it, o in changes:
            x("INSERT INTO title_changes(item_id, old_title, new_title, old_ar, changed) VALUES(?,?,?,?,?)",
              (it["id"], o["title"], it["title"], o["title_ar"], now()))
            ar = is_arabic(it["title"])
            x("UPDATE items SET title=?, title_ar=?, translated=?, edits=COALESCE(edits,0)+1 WHERE id=?",
              (it["title"], it["title"] if ar else o["title_ar"], 1 if ar else 0, it["id"]))
        if changes:
            log.info("رُصد تعديل %s عنوان", len(changes))
    x(f"INSERT OR IGNORE INTO items({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
      [tuple(it[c] for c in cols) for it in items], many=True)


def _title_changed(a, b):
    import difflib
    na = re.sub(r"[^\w]+", " ", (a or "").lower()).strip()
    nb = re.sub(r"[^\w]+", " ", (b or "").lower()).strip()
    if not na or not nb or na == nb:
        return False
    return difflib.SequenceMatcher(None, na, nb).ratio() < 0.93


def set_status(name, cat, ok, count, via, err):
    t = now()
    x("""INSERT INTO source_status(name, cat, ok, count, via, last_try, last_ok, error)
         VALUES(?,?,?,?,?,?,?,?)
         ON CONFLICT(name) DO UPDATE SET cat=excluded.cat, ok=excluded.ok, count=excluded.count,
           via=excluded.via, last_try=excluded.last_try,
           last_ok=CASE WHEN excluded.ok=1 THEN excluded.last_try ELSE source_status.last_ok END,
           error=excluded.error""",
      (name, cat, 1 if ok else 0, count, via, t, t if ok else 0, err))


def fetch_source(src):
    name, cat, lang = src["name_ar"], src["cat"], src.get("lang", "en")
    long_cat = cat in LONG_CATS
    entries, via, err = [], "RSS", ""
    if src.get("url"):
        try:
            entries = fetch_rss(src["url"])
        except Exception as e:
            err = str(e)[:200]
    if src.get("query"):
        try:
            entries = fetch_rss(gnews_url(f"{src['query']} when:{'30d' if long_cat else '3d'}", lang))
            via = "Google News (بحث)"
        except Exception as e:
            err = str(e)[:200]
    elif not entries and src.get("site"):
        # مواد مراكز الدراسات لا تتغير كل دقائق: البحث في أخبار Google كل 3 ساعات لها، وكل 30 دقيقة للأخبار
        key = "gnlast:" + src["name_ar"]
        gap = 3 * 3600 if long_cat else 1800
        if now() - int(kv_get(key, 0)) < gap:
            return
        try:
            entries = fetch_rss(gnews_url(f"site:{src['site']} when:{'30d' if long_cat else '7d'}", lang))
            via = "Google News"
            kv_set(key, now())
        except GNewsPaused:
            return
        except Exception as e:
            err = (err + " | " + str(e))[:300]
    limit = 80 if long_cat else MAX_ITEMS_PER_FEED
    items = [make_item(e, cat, src.get("site") or name, name, lang, gnews=via.startswith("Google News"),
                       source_from_title=bool(src.get("query")))
             for e in entries[:limit]]
    items = [i for i in items if i]
    store_items(items)
    set_status(name, cat, bool(items), len(items), via, "" if items else (err or "لا توجد عناصر"))


def backfill_source(src):
    """جلب أرشيف آخر 3 أشهر لمراكز البحث والدراسات (مرة يومياً حتى تكتمل التغطية)."""
    name, cat, lang = src["name_ar"], src["cat"], src.get("lang", "en")
    items, url = [], src.get("url", "")
    oldest = now() - STUDY_DAYS * 86400
    if url and re.search(r"/feed/?$", url):          # مواقع ووردبريس: صفحات الأرشيف حتى بلوغ 3 أشهر
        for pg in range(2, 13):
            try:
                entries = fetch_rss(url.rstrip("/") + f"/?paged={pg}")
            except Exception:
                break
            if not entries:
                break
            got = [make_item(e, cat, src.get("site") or name, name, lang) for e in entries]
            got = [i for i in got if i]
            items += got
            if got and min(i["published"] for i in got) < oldest:
                break
    have = q("SELECT MIN(published) m FROM items WHERE source_ar=?", (name,), one=True)["m"]
    covered = have and have < now() - (STUDY_DAYS - 7) * 86400
    if src.get("site") and not covered:
        # ثلاث شرائح شهرية، لأن أخبار Google تعيد نحو 100 نتيجة فقط لكل بحث
        for k in range(3):
            end = datetime.fromtimestamp(now() - k * 30 * 86400).strftime("%Y-%m-%d")
            start = datetime.fromtimestamp(now() - (k + 1) * 31 * 86400).strftime("%Y-%m-%d")
            try:
                entries = fetch_rss(gnews_url(f"site:{src['site']} after:{start} before:{end}", lang))
                items += [make_item(e, cat, src.get("site") or name, name, lang, gnews=True) for e in entries[:100]]
            except GNewsPaused:
                break
            except Exception:
                pass
    store_items([i for i in items if i and i["published"] >= oldest])


def fetch_keyword(word):
    total = 0
    for lang in ("ar", "en"):
        try:
            entries = fetch_rss(gnews_url(f'"{word}" when:2d', lang))
        except Exception:
            continue
        items = [make_item(e, "keywords", "news.google.com", "أخبار Google", lang, gnews=True,
                           source_from_title=True, extra_tags=f"|★{word}|")
                 for e in entries[:MAX_ITEMS_PER_FEED]]
        items = [i for i in items if i]
        total += len(items)
        store_items(items)
    set_status(f"كلمة مفتاحية: {word}", "keywords", total > 0, total, "Google News",
               "" if total else "لا نتائج")


def tweet_item(text, link, ts, handle, name_ar, source=None):
    text = clean(text)
    if not text:
        return None
    iid = hashlib.sha1((link or text).encode("utf-8")).hexdigest()[:20]
    ar = is_arabic(text)
    return {
        "id": iid, "cat": "tweets", "source": source or ("@" + handle), "source_ar": name_ar,
        "title": text[:600], "summary": "", "link": link, "published": ts, "fetched": now(),
        "lang": "ar" if ar else "en", "title_ar": text[:600] if ar else None,
        "summary_ar": "" if ar else None, "translated": 1 if ar else 0,
        "tags": compute_tags(text, get_keywords()) if ar else "", "kind": "tweet", "author": handle,
        "countries": compute_countries(text), "events": compute_events("tweets", text),
    }


def fetch_tweets_api(accounts):
    names = {a["handle"].lower(): a["name_ar"] for a in accounts}
    handles = [a["handle"] for a in accounts]
    chunks, cur = [], []
    for h in handles:
        if len(" OR ".join(["from:" + c for c in cur + [h]])) > 440:
            chunks.append(cur)
            cur = []
        cur.append(h)
    if cur:
        chunks.append(cur)
    total = 0
    for ch in chunks:
        query = "(" + " OR ".join("from:" + h for h in ch) + ") -is:retweet"
        r = requests.get("https://api.twitter.com/2/tweets/search/recent",
                         headers={"Authorization": f"Bearer {X_BEARER}"},
                         params={"query": query, "max_results": 50,
                                 "tweet.fields": "created_at,author_id",
                                 "expansions": "author_id", "user.fields": "name,username"},
                         timeout=20)
        data = r.json()
        if r.status_code != 200:
            set_status("X API", "tweets", False, 0, "X API", str(data)[:200])
            return
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        items = []
        for t in data.get("data", []):
            u = users.get(t.get("author_id"), {})
            handle = u.get("username", "")
            ts = int(datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")).timestamp())
            it = tweet_item(t.get("text", ""), f"https://x.com/{handle}/status/{t['id']}", ts,
                            handle, names.get(handle.lower(), u.get("name", handle)))
            if it:
                items.append(it)
        total += len(items)
        store_items(items)
    set_status("X API", "tweets", total > 0, total, "X API", "" if total else "لا تغريدات")


TG_MSG_TEXT = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
TG_POST = re.compile(r'data-post="([^"]+)"')
TG_TIME = re.compile(r'<time[^>]*datetime="([^"]+)"')
TG_BR = re.compile(r"<br\s*/?>", re.I)


def fetch_telegram(ch):
    """آخر 3 منشورات نصية من قناة تيليغرام عامة عبر صفحتها المفتوحة t.me/s/<قناة>."""
    username = ch["channel"].lstrip("@").strip()
    name_ar = ch.get("name_ar") or username
    source = f"t.me/{username}"
    items, err = [], ""
    try:
        r = requests.get(f"https://t.me/s/{username}", headers=HEADERS, timeout=20)
        if (r.status_code != 200 or 'tgme_widget_message_wrap' not in r.text) and cffi_requests is not None:
            try:
                r2 = cffi_requests.get(f"https://t.me/s/{username}", impersonate="chrome", timeout=20)
                if r2.status_code == 200:
                    r = r2
            except Exception:
                pass
        r.raise_for_status()
        blocks = r.text.split('class="tgme_widget_message_wrap')[1:]
        if not blocks:
            if "/s/" not in str(r.url):
                err = "صاحب القناة أوقف المعاينة العامة على الويب، أو اسم القناة تغيّر"
            elif "tgme_page_title" in r.text or "tgme_channel_info" in r.text:
                err = "القناة موجودة لكن لا منشورات ظاهرة (قد تكون المعاينة محجوبة في بلدك)"
            else:
                err = "القناة غير موجودة أو اسمها مختلف؛ تحقق من الاسم في تيليغرام"
            items = fetch_tg_mirror(username, name_ar, source)
        for blk in reversed(blocks):                     # من الأحدث إلى الأقدم
            mp, mt = TG_POST.search(blk), TG_MSG_TEXT.search(blk)
            if not (mp and mt):
                continue     # منشور صورة أو فيديو بلا نص
            text = clean(TG_BR.sub(" ", mt.group(1)))
            mtime = TG_TIME.search(blk)
            try:
                ts = int(datetime.fromisoformat(mtime.group(1)).timestamp()) if mtime else now()
            except Exception:
                ts = now()
            it = tweet_item(text, f"https://t.me/{mp.group(1)}", min(ts, now()), username, name_ar, source=source)
            if it:
                items.append(it)
            if len(items) >= TG_PER_CHANNEL:
                break
    except Exception as e:
        err = str(e)[:200]
    if items:
        store_items(items)
        keep = [i["id"] for i in items]
        x(f"DELETE FROM items WHERE source=? AND id NOT IN ({','.join('?' * len(keep))})", [source] + keep)
    set_status(f"تيليغرام: {name_ar}", "tweets", bool(items), len(items), "Telegram",
               "" if items else (err or "لا توجد منشورات نصية حديثة"))


def fetch_tg_mirror(username, name_ar, source):
    """بديل عند تعذّر صفحة تيليغرام: خدمات عامة تحوّل القنوات إلى RSS."""
    for url in (f"https://rsshub.app/telegram/channel/{username}", f"https://tg.i-c-a.su/rss/{username}"):
        try:
            entries = fetch_rss(url)
        except Exception:
            continue
        out = []
        for e in entries[:TG_PER_CHANNEL]:
            text = clean(e.get("title") or e.get("summary") or "")
            if text:
                it = tweet_item(text, e.get("link", ""), parse_time(e), username, name_ar, source=source)
                if it:
                    out.append(it)
        if out:
            return out
    return []


TG_WAKE = threading.Event()


def fetch_bluesky(acc):
    """آخر 3 منشورات من حساب Bluesky عبر الواجهة العامة (بلا مفتاح)."""
    handle = acc["handle"].lstrip("@").strip()
    name_ar = acc.get("name_ar") or handle
    source = f"bsky/{handle}"
    items, err = [], ""
    try:
        r = requests.get("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed", headers=HEADERS, timeout=20,
                         params={"actor": handle, "limit": 20, "filter": "posts_no_replies"})
        if r.status_code != 200:
            err = (r.json().get("message") if r.headers.get("Content-Type", "").startswith("application/json") else "") or f"رمز {r.status_code}"
        for it in (r.json().get("feed", []) if r.status_code == 200 else []):
            if it.get("reason"):                       # إعادة نشر: نتجاوزها
                continue
            post = it.get("post", {})
            rec = post.get("record", {})
            text = (rec.get("text") or "").strip()
            emb = (post.get("embed") or {}).get("external") or {}
            if emb.get("title") and len(text) < 60:
                text = (text + " " + emb["title"]).strip()
            if not text:
                continue
            try:
                ts = int(datetime.fromisoformat(rec.get("createdAt", "").replace("Z", "+00:00")).timestamp())
            except Exception:
                ts = now()
            rkey = post.get("uri", "").rsplit("/", 1)[-1]
            link = emb.get("uri") if emb.get("uri", "").startswith("http") else f"https://bsky.app/profile/{handle}/post/{rkey}"
            ti = tweet_item(text, link, min(ts, now()), handle, name_ar, source=source)
            if ti:
                ti["author"] = f"https://bsky.app/profile/{handle}/post/{rkey}"
                items.append(ti)
            if len(items) >= TG_PER_CHANNEL:
                break
    except Exception as e:
        err = str(e)[:200]
    if items:
        store_items(items)
        keep = [i["id"] for i in items]
        x(f"DELETE FROM items WHERE source=? AND id NOT IN ({','.join('?' * len(keep))})", [source] + keep)
    set_status(f"Bluesky: {name_ar}", "tweets", bool(items), len(items), "Bluesky",
               "" if items else (err or "لا توجد منشورات حديثة"))


def telegram_loop():
    """تحديث مستقل وسريع لقنوات تيليغرام."""
    time.sleep(2)
    while True:
        try:
            src_ = load_sources()
            chans = src_.get("telegram_channels", [])
            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(safe(fetch_telegram), chans))
                list(ex.map(safe(fetch_bluesky), src_.get("bluesky_accounts", [])))
            STATE["tg_last"] = now()
        except Exception:
            log.exception("telegram loop")
        TG_WAKE.wait(TG_INTERVAL)
        TG_WAKE.clear()


def fetch_cycle():
    STATE["running"] = True
    t0 = time.time()
    src = load_sources()
    if not kv_get("backfill_3m"):            # بعد التحديث إلى 3 أشهر: أرشفة فورية
        kv_set("last_backfill", 0)
        kv_set("backfill_3m", 1)
    do_backfill = now() - int(kv_get("last_backfill", 0)) > 86400
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(safe(fetch_source), s) for s in src["feeds"]]
        if X_BEARER:
            futures.append(ex.submit(safe(fetch_tweets_api), src["x_accounts"]))
        else:
            x("DELETE FROM source_status WHERE name='X (تويتر)'")
        futures += [ex.submit(safe(fetch_keyword), w) for w in get_keywords()]
        for f in futures:
            f.result()
        if do_backfill:                 # الأرشفة بخيطين فقط حتى لا تُحظر أخبار Google
            log.info("جلب أرشيف آخر 3 أشهر لمراكز الدراسات…")
            with ThreadPoolExecutor(max_workers=2) as ex2:
                list(ex2.map(safe(backfill_source), [s for s in src["feeds"] if s["cat"] in LONG_CATS]))
            kv_set("last_backfill", now())
    ph = ",".join("?" * len(LONG_CATS))
    x(f"DELETE FROM items WHERE published < ? AND cat NOT IN ({ph}) AND kind != 'tweet'",
      [now() - RETENTION_DAYS * 86400, *LONG_CATS])
    x(f"DELETE FROM items WHERE published < ? AND cat IN ({ph})", [now() - (STUDY_DAYS + 3) * 86400, *LONG_CATS])
    STATE.update(running=False, last_cycle=now(), cycle_secs=int(time.time() - t0))
    n = q("SELECT COUNT(*) c FROM items", one=True)["c"]
    log.info("اكتملت دورة الجلب خلال %ss — إجمالي العناصر: %s", STATE["cycle_secs"], n)


def fetch_loop():
    while True:
        try:
            fetch_cycle()
        except Exception:
            log.exception("fetch cycle")
            STATE["running"] = False
        STATE["next_cycle"] = now() + FETCH_INTERVAL
        WAKE.wait(FETCH_INTERVAL)
        WAKE.clear()


# ───────────────────────── فك روابط Google News إلى رابط الموقع الأصلي ─────────────────────────
GN_BATCH = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
RESOLVE_TRIES = {}


def is_gnews(url):
    return "news.google.com" in (url or "")


def gnews_decode(url):
    """يحوّل رابط news.google.com/rss/articles/... إلى رابط المقال في موقعه الأصلي."""
    try:
        u = urlparse(url)
        parts = u.path.split("/")
        if "articles" not in parts:
            return None
        gid = parts[parts.index("articles") + 1]
        # الصيغة القديمة: الرابط مُضمَّن داخل المعرّف نفسه
        try:
            raw = base64.urlsafe_b64decode(gid + "=" * (-len(gid) % 4))
            if not raw[4:].startswith(b"AU_yqL"):
                m = re.search(rb"https?://[\x21-\x7e]+", raw)
                if m:
                    cand = m.group(0).decode("ascii", "ignore")
                    if "google." not in urlparse(cand).netloc:
                        return cand
        except Exception:
            pass
        # الصيغة الحديثة: نطلب التوقيع من Google ثم نفك الرابط
        r = requests.get(f"https://news.google.com/rss/articles/{gid}", headers=HEADERS, timeout=15)
        sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
        if not (sg and ts):
            return None
        inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                 '"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]' % (gid, ts.group(1), sg.group(1)))
        body = "f.req=" + quote(json.dumps([[["Fbv4je", inner]]]))
        r2 = requests.post(GN_BATCH, data=body, timeout=15,
                           headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        try:
            data = json.loads(r2.text.split("\n\n")[1])[:-2]
            real = json.loads(data[0][2])[1]
        except Exception:
            m = re.search(r'https?://(?![^"\\]*google\.)[^"\\\s]+', r2.text)
            real = m.group(0) if m else None
        return real if real and not is_gnews(real) else None
    except Exception as e:
        log.warning("gnews decode failed: %s", str(e)[:120])
        return None


def resolve_item(row):
    """يعيد الرابط الحقيقي للعنصر ويحدّثه في قاعدة البيانات."""
    link = row["link"]
    if not is_gnews(link):
        return link
    real = gnews_decode(link)
    if not real:
        RESOLVE_TRIES[row["id"]] = RESOLVE_TRIES.get(row["id"], 0) + 1
        return link
    dup = q("SELECT id FROM items WHERE link=? AND id!=?", (real, row["id"]), one=True)
    if dup:   # نفس المقال موجود من رابط RSS المباشر: نحذف النسخة المكررة
        x("DELETE FROM items WHERE id=?", (row["id"],))
    else:
        x("UPDATE items SET link=? WHERE id=?", (real, row["id"]))
    return real


def resolver_loop():
    """يحوّل روابط Google News في الخلفية إلى روابط المواقع الأصلية، الأحدث أولاً."""
    while True:
        try:
            rows = q("SELECT id, link FROM items WHERE link LIKE '%news.google.com%' "
                     "ORDER BY published DESC LIMIT 40")
            rows = [r for r in rows if RESOLVE_TRIES.get(r["id"], 0) < 2]
            if not rows:
                time.sleep(10)
                continue
            fails = 0
            for r in rows:
                if is_gnews(resolve_item(r)):
                    fails += 1
                time.sleep(0.4)
            if fails == len(rows):
                time.sleep(60)   # غالباً حدّ مؤقت من Google
        except Exception:
            log.exception("resolver loop")
            time.sleep(10)


# ───────────────────────── النص الكامل للمقال ─────────────────────────
SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "aside", "form", "svg", "button", "figure"}


class ParaExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip, self.cur, self.paras = 0, None, []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag in ("p", "h2", "h3") and self.skip == 0:
            self.cur = []

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip > 0:
            self.skip -= 1
        elif tag in ("p", "h2", "h3") and self.cur is not None:
            t = " ".join("".join(self.cur).split())
            if len(t) >= 40 and t not in self.paras and not t.lower().startswith(("subscribe", "sign up", "advertisement")):
                self.paras.append(t)
            self.cur = None

    def handle_data(self, data):
        if self.cur is not None and self.skip == 0:
            self.cur.append(data)


# ───────────────────────── الخادم ─────────────────────────
app = Flask(__name__)
RUN_HOST = "127.0.0.1"
try:
    app.json.ensure_ascii = False
except Exception:
    app.config["JSON_AS_ASCII"] = False


def cat_meta():
    return {k: {"key": k, "name": n, "color": c} for k, n, c in CATEGORIES}


UI_FILES = ["ui/index.html", "ui/style.css", "ui/app.js", "ui/icon-192.png", "ui/icon-512.png"]
APP_FILES = ["rased.py", "sources_default.py"] + UI_FILES + ["start.py", "build_exe.py", "START.bat", "BUILD_EXE.bat"]


def ui_dir():
    """مجلد الواجهة: بجانب البرنامج، أو داخل نسخة exe إن لم يوجد بجانبها."""
    d = os.path.join(BASE_DIR, "ui")
    if os.path.exists(os.path.join(d, "index.html")):
        return d
    mp = getattr(sys, "_MEIPASS", "")
    if mp and os.path.exists(os.path.join(mp, "ui", "index.html")):
        return os.path.join(mp, "ui")
    return d


def ensure_ui():
    """إن وصل rased.py وحده (من تحديث قديم) تُنزَّل ملفات الواجهة من GitHub تلقائياً."""
    missing = [f for f in UI_FILES if not os.path.exists(os.path.join(ui_dir(), os.path.basename(f)))]
    if not missing:
        return True
    try:
        c = update_cfg()
    except Exception:
        c = {"repo": DEFAULT_REPO, "branch": "main"}
    os.makedirs(os.path.join(BASE_DIR, "ui"), exist_ok=True)
    ok = True
    for f in missing:
        try:
            r = requests.get(f"https://raw.githubusercontent.com/{c['repo']}/{c['branch']}/{f}", headers=HEADERS, timeout=60)
            r.raise_for_status()
            with open(os.path.join(BASE_DIR, f), "wb") as fh:
                fh.write(r.content)
            log.info("نُزِّل ملف الواجهة الناقص: %s", f)
        except Exception as e:
            ok = False
            log.warning("تعذّر تنزيل %s: %s", f, e)
    return ok


UI_MISSING = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>ملفات الواجهة ناقصة</title>
<style>body{background:#060B13;color:#E3ECF5;font:16px/1.9 Tahoma,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0}
div{max-width:620px;padding:30px;border:1px solid #24405C;border-radius:12px;background:#0F1A29}code{direction:ltr;display:inline-block}</style></head>
<body><div><h2>ملفات الواجهة غير موجودة</h2>البرنامج صار مقسّماً إلى عدة ملفات، ومجلد <code>ui</code> غير موجود بجانب <code>rased.py</code>،
ولم يتمكن البرنامج من تنزيله تلقائياً. نزّل البرنامج كاملاً من مستودع GitHub (الزر الأخضر Code ← Download ZIP)
وضع المجلد <code>ui</code> بجانب <code>rased.py</code>، ثم أعد تشغيل البرنامج.</div></body></html>"""


def _ui_file(name):
    p_ = os.path.join(ui_dir(), name)
    if not os.path.exists(p_):
        return None
    with open(p_, "rb") as fh:
        return fh.read()


@app.get("/")
def index():
    data = _ui_file("index.html")
    if data is None:
        ensure_ui()
        data = _ui_file("index.html")
    if data is None:
        return Response(UI_MISSING, mimetype="text/html; charset=utf-8")
    return Response(data.decode("utf-8").replace("{{V}}", VERSION), mimetype="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-cache"})


@app.get("/ui/<name>")
def ui_static(name):
    if name not in ("style.css", "app.js"):
        return Response(status=404)
    data = _ui_file(name)
    if data is None:
        return Response(status=404)
    mt = "text/css" if name.endswith(".css") else "application/javascript"
    return Response(data, mimetype=mt + "; charset=utf-8", headers={"Cache-Control": "max-age=86400"})


def threat_index():
    """مؤشر بسيط: نشاط أخبار الحروب والإرهاب في آخر 6 ساعات مقارنة بمتوسط الأسبوع."""
    w6 = q("SELECT COUNT(*) c FROM items WHERE cat IN ('war','terror') AND published >= ?",
           (now() - 6 * 3600,), one=True)["c"]
    w7 = q("SELECT COUNT(*) c FROM items WHERE cat IN ('war','terror') AND published >= ?",
           (now() - 7 * 86400,), one=True)["c"]
    avg = max(w7 / 28.0, 1.0)
    ratio = w6 / avg
    levels = [(0.8, 1, "منخفض"), (1.2, 2, "معتدل"), (1.7, 3, "مرتفع"), (2.5, 4, "عالٍ جداً"), (1e9, 5, "حرج")]
    step, label = next((st, lb) for lim, st, lb in levels if ratio < lim)
    return {"level": step, "label": label, "w6": w6, "avg": round(avg, 1), "ratio": round(ratio, 2)}


@app.get("/api/meta")
def api_meta():
    day = now() - 86400
    counts = {r["cat"]: (r["total"], r["day"] or 0) for r in q(
        "SELECT cat, COUNT(*) total, SUM(CASE WHEN published >= ? THEN 1 ELSE 0 END) day "
        "FROM items GROUP BY cat", (day,))}
    cats = []
    for k, n, c in CATEGORIES:
        total, d = counts.get(k, (0, 0))
        cats.append({"key": k, "name": n, "color": c, "total": total, "day": d})
    tag_counter = Counter()
    for r in q("SELECT tags FROM items WHERE published >= ? AND tags != ''", (now() - 172800,)):
        tag_counter.update(t for t in r["tags"].strip("|").split("|") if t and not t.startswith("★"))
    sources = [{"name": r["source_ar"], "cat": r["cat"]}
               for r in q("SELECT DISTINCT source_ar, cat FROM items ORDER BY source_ar")]
    health = q("SELECT SUM(ok) ok, COUNT(*) n FROM source_status", one=True)
    pending = q("SELECT COUNT(*) c FROM items WHERE translated <= 0 AND translated > -3", one=True)["c"]
    return jsonify(
        categories=cats, sources=sources,
        tags=[{"tag": t, "count": c} for t, c in tag_counter.most_common(24)],
        keywords=get_keywords(), state=STATE, pending=pending, now=now(),
        hour=q("SELECT COUNT(*) c FROM items WHERE published >= ?", (now() - 3600,), one=True)["c"],
        update={"ready": UPDATE["ready"], "version": UPDATE["remote_version"]}, version=VERSION,
        media={n_: (f"{k_[0]} · {k_[1]}" if k_[1] else k_[0]) for n_, k_ in _ML.items()},
        sanc_new=q("SELECT COUNT(*) c FROM sanctions WHERE is_new=1 AND first_seen >= ?", (now() - 7 * 86400,), one=True)["c"],
        threat=threat_index(),
        translator=True,
        tr_stats={"ok": TR_STATS["ok"], "fail": TR_STATS["fail"], "last_error": TR_STATS["last_error"],
                  "providers": [{"name": PROVIDER_NAMES[k], "ready": prov_ready(k), **{kk: v[kk] for kk in ("ok", "fail", "err")}}
                                for k, v in PROV.items() if not (k == "claude" and not anthropic_key())
                                and not (k == "deep" and GoogleTranslator is None)
                                and not (k == "argos" and argos_tr is None)],
                  "down": all_providers_down()},
        reader={"curl_cffi": cffi_requests is not None, "trafilatura": trafilatura is not None},
        tweets_mode="X و تيليغرام" if X_BEARER else "تيليغرام",
        telegram=[{"channel": c["channel"], "name_ar": c.get("name_ar", c["channel"])}
                  for c in load_sources().get("telegram_channels", [])],
        health={"ok": health["ok"] or 0, "fail": (health["n"] or 0) - (health["ok"] or 0)},
    )


@app.get("/api/items")
def api_items():
    a = request.args
    cat, source, tag, text = a.get("cat", "all"), a.get("source", ""), a.get("tag", ""), a.get("q", "").strip()
    hours = int(a.get("hours") or 0)
    page = max(1, int(a.get("page") or 1))
    per = min(100, max(1, int(a.get("per") or 30)))
    where, args = ["1=1"], []
    if cat == "research":                 # البحث في مواد مراكز البحث والدراسات وحدها
        where.append(f"cat IN ({','.join('?' * len(LONG_CATS))})"); args += list(LONG_CATS)
    elif cat and cat != "all":
        where.append("cat=?"); args.append(cat)
    if source:
        where.append("source_ar=?"); args.append(source)
    if tag:
        where.append("tags LIKE ?"); args.append(f"%|{tag}|%")
    if a.get("qual") == "1":
        where.append("events != '' AND events IS NOT NULL")
    if a.get("event"):
        where.append("events LIKE ?"); args.append(f"%|{a['event']}|%")
    country = a.get("country", "")
    if country:
        where.append("countries LIKE ?"); args.append(f"%|{country}|%")
    if hours:
        where.append("published >= ?"); args.append(now() - hours * 3600)
    for w in text.split()[:6]:
        where.append("(title_ar LIKE ? OR summary_ar LIKE ? OR title LIKE ? OR summary LIKE ? OR source_ar LIKE ?)")
        args += [f"%{w}%"] * 5
    wsql = " AND ".join(where)
    if a.get("dedupe") == "1" and not source:
        # دمج المكرر: خبر واحد لكل حدث (الأحدث)، ومعه عدد ما نقله غيره ضمن النتائج نفسها
        base = (f"SELECT *, ROW_NUMBER() OVER (PARTITION BY COALESCE(cluster, id) ORDER BY published DESC) rn, "
                f"COUNT(*) OVER (PARTITION BY COALESCE(cluster, id)) dup FROM items WHERE {wsql}")
        try:
            total = q(f"SELECT COUNT(*) c FROM ({base}) WHERE rn=1", args, one=True)["c"]
            rows = q(f"SELECT * FROM ({base}) WHERE rn=1 ORDER BY published DESC LIMIT ? OFFSET ?",
                     args + [per, (page - 1) * per])
            return jsonify(total=total, items=[dict(r) for r in rows], deduped=True)
        except Exception as e:            # نسخة SQLite قديمة بلا دوال النوافذ: نعرض بلا دمج
            log.warning("dedupe: %s", e)
    total = q(f"SELECT COUNT(*) c FROM items WHERE {wsql}", args, one=True)["c"]
    rows = q(f"SELECT * FROM items WHERE {wsql} ORDER BY published DESC LIMIT ? OFFSET ?",
             args + [per, (page - 1) * per])
    return jsonify(total=total, items=[dict(r) for r in rows])


TICKERS = {
    "breaking": ["world", "arab"],
    "war": ["war", "terror", "intel"],
    "articles": ["think_global", "think_arab"],
    "economy": ["economy"],
}


# ── دليل المراكز
CENTER_CATS = ("think_global", "think_arab", "terror", "war", "intel")
REGIONS = {
    "أمريكا": "brookings.edu csis.org rand.org carnegieendowment.org cfr.org atlanticcouncil.org "
              "washingtoninstitute.org foreignpolicy.com foreignaffairs.com mei.edu wilsoncenter.org stimson.org "
              "ctc.westpoint.edu longwarjournal.org jamestown.org counterextremism.com extremism.gwu.edu "
              "lawfaremedia.org understandingwar.org warontherocks.com defenseone.com breakingdefense.com twz.com "
              "defensenews.com smallwarsjournal.com start.umd.edu thesoufancenter.org fdd.org belfercenter.org "
              "csbaonline.org traccc.gmu.edu acleddata.com justsecurity.org thecipherbrief.com spytalk.co therecord.media "
              "cyberscoop.com belfercenter.org/project/intelligence-project jihadology.net militantwire.com "
              "criticalthreats.org siteintelgroup.com memri.org trackingterrorism.org meforum.org",
    "أوروبا": "chathamhouse.org crisisgroup.org ecfr.eu iiss.org icct.nl gnet-research.org isdglobal.org "
              "bellingcat.com janes.com airwars.org icsr.info sv.uio.no/c-rex crestresearch.ac.uk ifri.org "
              "frstrategie.org iss.europa.eu clingendael.org css.ethz.ch realinstitutoelcano.org nupi.no rusi.org "
              "sipri.org prio.org kyivindependent.com europarabct.com intelligenceonline.com greydynamics.com "
              "tandfonline.com/toc/rint20 techagainstterrorism.org voxpol.eu eeradicalization.com "
              "foi.se diis.dk fiia.fi gcsp.ch pism.pl globsec.org",
    "أفريقيا": "issafrica.org africacenter.org accord.org.za ipss-addis.org cddwestafrica.org wanep.org saiia.org.za",
    "آسيا وأستراليا": "aspistrategist.org.au nsc.anu.edu.au internationalaffairs.org.au",
    "روسيا": "russiancouncil.ru valdaiclub.com imemo.ru riss.ru pircenter.org ivran.ru",
}
SITE_REGION = {site: reg for reg, sites in REGIONS.items() for site in sites.split()}


def region_of(f):
    if f.get("region"):
        return f["region"]
    if f.get("site") in SITE_REGION:
        return SITE_REGION[f["site"]]
    return "العالم العربي" if f["cat"] == "think_arab" or f.get("lang") == "ar" else "دولي"


@app.get("/api/centers")
def api_centers():
    feeds = [f for f in load_sources()["feeds"] if f["cat"] in CENTER_CATS and not f.get("query")]
    ph = ",".join("?" * len(CENTER_CATS))
    stats = {r["source_ar"]: (r["n"], r["last"]) for r in q(
        f"SELECT source_ar, COUNT(*) n, MAX(published) last FROM items WHERE cat IN ({ph}) GROUP BY source_ar",
        CENTER_CATS)}
    tagc = {}
    for r in q(f"SELECT source_ar, tags FROM items WHERE cat IN ({ph}) AND tags != ''", CENTER_CATS):
        tagc.setdefault(r["source_ar"], Counter()).update(
            t for t in r["tags"].strip("|").split("|") if t and not t.startswith("★"))
    status = {r["name"]: r["ok"] for r in q("SELECT name, ok FROM source_status")}
    out = []
    for f in feeds:
        n, last = stats.get(f["name_ar"], (0, 0))
        out.append({
            "name": f["name_ar"], "site": f.get("site", ""), "cat": f["cat"], "region": region_of(f),
            "count": n, "last": last or 0, "ok": status.get(f["name_ar"]),
            "tags": [{"tag": t, "count": c} for t, c in tagc.get(f["name_ar"], Counter()).most_common(12)],
        })
    out.sort(key=lambda c: (-c["count"], c["name"]))
    return jsonify(items=out)


@app.get("/api/boards")
def api_boards():
    out = []
    for k, n, c in CATEGORIES:
        if k == "tweets" or (k == "keywords" and not get_keywords()):
            continue
        rows = q("SELECT * FROM items WHERE cat=? ORDER BY published DESC LIMIT 6", (k,))
        out.append({"key": k, "name": n, "color": c, "items": [dict(r) for r in rows]})
    return jsonify(boards=out)


@app.get("/api/telegram/board")
def api_tg_board():
    chans = load_sources().get("telegram_channels", [])
    status = {r["name"]: dict(r) for r in q("SELECT * FROM source_status WHERE cat='tweets'")}
    out = []
    for c in chans:
        u = c["channel"].lstrip("@")
        name = c.get("name_ar") or u
        rows = q("SELECT * FROM items WHERE source=? ORDER BY published DESC LIMIT ?", (f"t.me/{u}", TG_PER_CHANNEL))
        st = status.get(f"تيليغرام: {name}", {})
        out.append({"channel": u, "name_ar": name, "ok": st.get("ok"), "error": st.get("error") or "",
                    "posts": [dict(r) for r in rows], "platform": "telegram", "url": f"https://t.me/{u}"})
    for c in load_sources().get("bluesky_accounts", []):
        h = c["handle"].lstrip("@")
        name = c.get("name_ar") or h
        rows = q("SELECT * FROM items WHERE source=? ORDER BY published DESC LIMIT ?", (f"bsky/{h}", TG_PER_CHANNEL))
        st = status.get(f"Bluesky: {name}", {})
        out.append({"channel": h, "name_ar": name, "ok": st.get("ok"), "error": st.get("error") or "",
                    "posts": [dict(r) for r in rows], "platform": "bluesky", "url": f"https://bsky.app/profile/{h}"})
    out.sort(key=lambda c: (c["ok"] == 0, -(c["posts"][0]["published"] if c["posts"] else 0)))
    return jsonify(channels=out, interval=TG_INTERVAL, last=STATE.get("tg_last", 0))


@app.post("/api/translate/<iid>")
def api_translate_now(iid):
    """ترجمة فورية لعنصر واحد (عند فتحه، أو بزر «ترجم»)."""
    row = q("SELECT * FROM items WHERE id=?", (iid,), one=True)
    if not row:
        return jsonify(ok=False), 404
    if request.args.get("force") == "1":
        reset_providers()
    if row["translated"] != 1 or (row["summary"] and not row["summary_ar"] and row["lang"] != "ar"):
        translate_rows([row])
        row = q("SELECT * FROM items WHERE id=?", (iid,), one=True)
    return jsonify(ok=row["translated"] == 1, item=dict(row))


def countries_backfill():
    """يربط المواد المخزنة سابقاً بالدول (مرة واحدة بعد التحديث)."""
    if not kv_get("events_v2"):       # إعادة تصنيف المقالات والدراسات بعد إضافتها للأخبار النوعية
        x("UPDATE items SET events=NULL WHERE cat IN ('think_global','think_arab')")
        kv_set("events_v2", 1)
    while True:
        rows = q("SELECT id, title, summary, title_ar, summary_ar FROM items WHERE countries IS NULL LIMIT 2000")
        if not rows:
            break
        x("UPDATE items SET countries=? WHERE id=?",
          [(compute_countries(r["title"], r["summary"], r["title_ar"], r["summary_ar"]), r["id"]) for r in rows], many=True)
    while True:     # الأخبار النوعية للمواد المخزنة سابقاً
        rows = q("SELECT id, cat, title, summary, title_ar, summary_ar FROM items WHERE events IS NULL LIMIT 2000")
        if not rows:
            return
        x("UPDATE items SET events=? WHERE id=?",
          [(events_for(r["cat"], r["title"], r["title_ar"], r["summary"], r["summary_ar"]),
            r["id"]) for r in rows], many=True)


@app.get("/api/qual/stats")
def api_qual_stats():
    hours = int(request.args.get("hours") or 24)
    c = Counter()
    for r in q("SELECT events FROM items WHERE events != '' AND events IS NOT NULL AND published >= ?", (now() - hours * 3600,)):
        c.update(e for e in r["events"].strip("|").split("|") if e)
    return jsonify(types=[{"name": e[0], "color": e[1], "count": c.get(e[0], 0)} for e in EVENT_TYPES],
                   total=sum(c.values()))


@app.get("/api/countries")
def api_countries():
    month, day = Counter(), Counter()
    t_day = now() - 86400
    for r in q("SELECT countries, published FROM items WHERE countries != '' AND published >= ?", (now() - 31 * 86400,)):
        names = [c for c in r["countries"].strip("|").split("|") if c]
        month.update(names)
        if r["published"] >= t_day:
            day.update(names)
    out = [{"name": n, "iso": COUNTRY_INFO.get(n, {}).get("iso", ""), "region": COUNTRY_INFO.get(n, {}).get("region", ""),
            "count": c, "day": day.get(n, 0)} for n, c in month.most_common()]
    return jsonify(items=out)


@app.get("/api/country/<path:name>")
def api_country(name):
    tags, cats = Counter(), Counter()
    rows = q("SELECT tags, cat FROM items WHERE countries LIKE ? AND published >= ?", (f"%|{name}|%", now() - 31 * 86400))
    for r in rows:
        tags.update(t for t in (r["tags"] or "").strip("|").split("|") if t and not t.startswith("★") and t != name)
        cats[r["cat"]] += 1
    info = COUNTRY_INFO.get(name, {})
    return jsonify(name=name, iso=info.get("iso", ""), region=info.get("region", ""), count=len(rows),
                   tags=[{"tag": t, "count": c} for t, c in tags.most_common(14)],
                   cats=[{"cat": k, "count": c} for k, c in cats.most_common()])


# ───────────────────────── مكتبة الكتب (آخر سنتين) ─────────────────────────
BOOK_TOPICS = {
    "terror": ("الإرهاب والتطرف", ["subject:terrorism", "counterterrorism", "jihadist movements", "violent extremism radicalization"],
               ["الإرهاب", "التطرف"]),
    "war": ("الحروب والنزاعات", ['subject:"military history"', "modern warfare", "russia ukraine war", "insurgency"],
            ["الحرب", "الحروب الحديثة"]),
    "politics": ("السياسة والجغرافيا السياسية", ["geopolitics", 'subject:"international relations"', "middle east politics"],
                 ["السياسة الدولية", "الجغرافيا السياسية"]),
    "security": ("الأمن والاستخبارات", ["intelligence agencies espionage", 'subject:"national security"', "cyber warfare"],
                 ["الاستخبارات", "الأمن القومي"]),
}
BOOKS_STATE = {"running": False}


def _book_year(pub):
    m = re.match(r"(\d{4})", pub or "")
    return int(m.group(1)) if m else 0


def fetch_books_google(topic, query, lang):
    r = requests.get("https://www.googleapis.com/books/v1/volumes", timeout=25, headers=HEADERS, params={
        "q": query, "orderBy": "newest", "maxResults": 40, "printType": "books", "langRestrict": lang})
    if r.status_code != 200:
        raise ValueError(f"Google Books: رمز {r.status_code}")
    min_year, today = datetime.now().year - 1, datetime.now().strftime("%Y-%m-%d")
    out = []
    for it in r.json().get("items", []) or []:
        v = it.get("volumeInfo", {})
        pub = v.get("publishedDate", "")
        year = _book_year(pub)
        cats = ", ".join(v.get("categories", []) or [])
        if year < min_year or pub[:10] > today or re.search(r"fiction|juvenile|comics", cats, re.I):
            continue
        desc = clean(v.get("description", ""))
        img = ((v.get("imageLinks") or {}).get("thumbnail") or (v.get("imageLinks") or {}).get("smallThumbnail") or "")
        img = img.replace("http://", "https://").replace("&edge=curl", "")
        if not v.get("title") or (len(desc) < 80 and not img):
            continue
        out.append({"id": "gb:" + it["id"], "topic": topic, "title": v.get("title", "") + (": " + v["subtitle"] if v.get("subtitle") else ""),
                    "authors": "، ".join(v.get("authors", []) or []), "publisher": v.get("publisher", ""),
                    "published": pub, "year": year, "description": desc[:3000], "image": img,
                    "link": v.get("infoLink") or v.get("canonicalVolumeLink") or "", "lang": v.get("language", lang),
                    "pages": v.get("pageCount") or 0, "categories": cats})
    return out


def fetch_books_openlibrary(topic, query):
    q_ = query.replace("subject:", "subject:").replace('"', "")
    r = requests.get("https://openlibrary.org/search.json", timeout=30, headers=HEADERS, params={
        "q": q_, "sort": "new", "limit": 30,
        "fields": "key,title,subtitle,author_name,first_publish_year,cover_i,publisher,language,publish_date"})
    r.raise_for_status()
    min_year, out = datetime.now().year - 1, []
    for d in r.json().get("docs", []):
        year = d.get("first_publish_year") or 0
        if year < min_year or year > datetime.now().year or not d.get("title"):
            continue
        desc = ""
        try:
            w = requests.get(f"https://openlibrary.org{d['key']}.json", timeout=15, headers=HEADERS).json()
            desc = w.get("description", "")
            desc = desc.get("value", "") if isinstance(desc, dict) else desc
        except Exception:
            pass
        out.append({"id": "ol:" + d["key"].split("/")[-1], "topic": topic,
                    "title": d["title"] + (": " + d["subtitle"] if d.get("subtitle") else ""),
                    "authors": "، ".join(d.get("author_name", [])[:4]), "publisher": (d.get("publisher") or [""])[0],
                    "published": str(year), "year": year, "description": clean(desc)[:3000],
                    "image": f"https://covers.openlibrary.org/b/id/{d['cover_i']}-L.jpg" if d.get("cover_i") else "",
                    "link": f"https://openlibrary.org{d['key']}", "lang": (d.get("language") or ["eng"])[0][:2],
                    "pages": 0, "categories": ""})
    return out


def store_books(books):
    cols = ["id", "topic", "title", "authors", "publisher", "published", "year", "description", "image",
            "link", "lang", "pages", "categories"]
    x(f"INSERT OR IGNORE INTO books({','.join(cols)}, fetched, translated) VALUES({','.join('?' * len(cols))}, ?, 0)",
      [tuple(b[c] for c in cols) + (now(),) for b in books], many=True)


def translate_books(rows):
    titles = translate_many([r["title"] for r in rows])
    descs = translate_many([r["description"] or "" for r in rows])
    done = [(t, d or "", r["id"]) for r, t, d in zip(rows, titles, descs) if t and (d is not None)]
    if done:
        x("UPDATE books SET title_ar=?, description_ar=?, translated=1 WHERE id=?", done, many=True)
    return len(done)


def fetch_books():
    if BOOKS_STATE["running"]:
        return
    BOOKS_STATE["running"] = True
    total, errs, via = 0, [], "Google Books"
    try:
        for topic, (_, en_qs, ar_qs) in BOOK_TOPICS.items():
            for query, lang in [(qq, "en") for qq in en_qs] + [(qq, "ar") for qq in ar_qs]:
                try:
                    found = fetch_books_google(topic, query, lang)
                except Exception as e:
                    errs.append(str(e)[:80])
                    found = []
                    if lang == "en":
                        try:
                            found = fetch_books_openlibrary(topic, query)
                            via = "Google Books + Open Library"
                        except Exception as e2:
                            errs.append(str(e2)[:80])
                store_books(found)
                total += len(found)
                time.sleep(1)
        # حذف ما تجاوز السنتين
        x("DELETE FROM books WHERE year < ?", (datetime.now().year - 1,))
        set_status("مكتبة الكتب", "books", total > 0, total, via, "" if total else ("؛ ".join(errs[:2]) or "لا نتائج"))
        kv_set("last_books", now())
        while True:
            rows = q("SELECT id, title, description FROM books WHERE translated=0 ORDER BY year DESC LIMIT 20")
            if not rows or not translate_books(rows):
                break
    finally:
        BOOKS_STATE["running"] = False


def books_loop():
    time.sleep(15)
    while True:
        try:
            if now() - int(kv_get("last_books", 0)) > 12 * 3600:
                fetch_books()
            else:
                rows = q("SELECT id, title, description FROM books WHERE translated=0 LIMIT 20")
                if rows:
                    translate_books(rows)
        except Exception:
            log.exception("books loop")
        time.sleep(600)


@app.get("/api/books")
def api_books():
    a = request.args
    where, args = ["1=1"], []
    if a.get("topic"):
        where.append("topic=?"); args.append(a["topic"])
    if a.get("lang") == "ar":
        where.append("lang='ar'")
    elif a.get("lang") == "foreign":
        where.append("lang!='ar'")
    for w in (a.get("q") or "").split()[:5]:
        where.append("(title LIKE ? OR title_ar LIKE ? OR authors LIKE ? OR description_ar LIKE ?)")
        args += [f"%{w}%"] * 4
    rows = q(f"SELECT * FROM books WHERE {' AND '.join(where)} ORDER BY published DESC LIMIT 400", args)
    counts = {r["topic"]: r["c"] for r in q("SELECT topic, COUNT(*) c FROM books GROUP BY topic")}
    return jsonify(items=[dict(r) for r in rows], running=BOOKS_STATE["running"],
                   topics=[{"key": k, "name": v[0], "count": counts.get(k, 0)} for k, v in BOOK_TOPICS.items()])


@app.post("/api/books/refresh")
def api_books_refresh():
    threading.Thread(target=safe(fetch_books), daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/books/translate/<path:bid>")
def api_book_translate(bid):
    row = q("SELECT * FROM books WHERE id=?", (bid,), one=True)
    if not row:
        return jsonify(ok=False), 404
    reset_providers()
    translate_books([row])
    row = q("SELECT * FROM books WHERE id=?", (bid,), one=True)
    return jsonify(ok=row["translated"] == 1, item=dict(row))


# ───────────────────────── كاتب المقالات والدراسات (عبر Claude) ─────────────────────────
WRITER_MODELS = [("claude-sonnet-5-5", "Claude Sonnet 5.5 (متوازن، يُنصح به)"),
                 ("claude-opus-5-5", "Claude Opus 5.5 (أعلى جودة، أبطأ وأغلى)"),
                 ("claude-haiku-5-5", "Claude Haiku 5.5 (الأسرع والأرخص)")]
WRITE_TYPES = {
    "opinion": ("مقال رأي", "مقال رأي له أطروحة واضحة يدافع عنها الكاتب بحجج وشواهد، بصوت شخصي واثق."),
    "analysis": ("تحليل إخباري", "تحليل يشرح ما حدث ولماذا حدث وما الذي قد يترتب عليه، يربط الوقائع بسياقها."),
    "study": ("دراسة", "دراسة منهجية بأقسام: ملخص تنفيذي، مقدمة وإشكالية، خلفية، محاور تحليلية، سيناريوهات أو استنتاجات، توصيات، ثم قائمة مراجع."),
    "assessment": ("تقدير موقف", "ورقة تقدير موقف موجزة لصانع القرار: الموقف الراهن، الفاعلون ومصالحهم، المسارات المحتملة مع ترجيح، توصيات عملية."),
    "report": ("تقرير معمّق", "تقرير صحفي معمق يبدأ بمشهد أو واقعة محددة ثم يتوسع، يمزج المعلومة بالسياق والأصوات المختلفة."),
}
WRITE_LENGTHS = {"short": ("قصير", "بين 700 و900 كلمة", 4000), "medium": ("متوسط", "بين 1300 و1700 كلمة", 7000),
                 "long": ("طويل", "بين 2500 و3200 كلمة", 14000)}
WRITE_TONES = {"academic": "رصين أكاديمي، دقيق المصطلحات", "journalistic": "صحفي حيّ، جمل واضحة وإيقاع متنوع",
               "analytical": "تحليلي هادئ، يوازن بين الآراء ويزن الأدلة"}

WRITER_SYSTEM = """أنت كاتب ومحلل عربي متمرس في الشؤون السياسية والأمنية والعسكرية، تكتب لمراكز أبحاث وصحف رصينة منذ سنوات.
اكتب كما يكتب إنسان خبير يعرف موضوعه، لا كما تُكتب النصوص الآلية:
- ابدأ مباشرة بفكرة أو واقعة أو سؤال حاد، لا بمقدمات عامة عن «عالم اليوم» أو «في ظل التطورات».
- نوّع طول الجمل والفقرات تنويعاً طبيعياً؛ جملة قصيرة حاسمة بعد جملة طويلة، وفقرة من سطرين بعد فقرة أطول.
- اكتب نثراً متصلاً. لا تستخدم القوائم النقطية إلا حيث تفرضها طبيعة الدراسة (التوصيات مثلاً)، ولا تُكثر من العناوين الفرعية.
- لا تستخدم الخط العريض داخل الفقرات.
- تجنّب العبارات المستهلكة مثل: «في عالم اليوم»، «تجدر الإشارة»، «لا شك أن»، «في الختام»، «من الجدير بالذكر»، «يلعب دوراً محورياً»، «في ظل»، «بشكل عام»، «علاوة على ذلك» المتكررة.
- لا تختم بتلخيص يكرر ما قيل؛ اختم بفكرة تفتح أفقاً أو بحكم واضح.
- اتخذ موقفاً تحليلياً حين يقتضي النوع ذلك، ولا تتوارَ خلف «من جهة… ومن جهة أخرى» في كل فقرة.
- استخدم التفاصيل الملموسة: أسماء وأماكن وتواريخ وأرقام، ولكن من المواد المرفقة أو من معرفتك الموثوقة فقط.
الأمانة شرط لا يُتنازل عنه: لا تخترع أرقاماً أو اقتباسات أو تصريحات أو دراسات أو أسماء مصادر. حين تستند إلى المواد المرفقة اذكر مصدرها بشكل طبيعي داخل النص (مثل: «بحسب تقرير لمعهد واشنطن…»). ما لا تملك عليه دليلاً قدّمه تحليلاً أو ترجيحاً لا خبراً مؤكداً.
اكتب بصيغة Markdown بسيطة: السطر الأول عنوان النص مسبوقاً بـ # ، والعناوين الفرعية بـ ## عند الحاجة فقط."""


def related_items(topic, limit=25):
    words = [w for w in re.split(r"\s+", topic.strip()) if len(w) >= 3][:6]
    if not words:
        return []
    conds = " OR ".join(["(title LIKE ? OR title_ar LIKE ? OR summary_ar LIKE ? OR summary LIKE ? OR countries LIKE ? OR tags LIKE ?)"] * len(words))
    args = []
    for w in words:
        args += [f"%{w}%"] * 6
    rows = q(f"SELECT * FROM items WHERE ({conds}) AND kind != 'tweet' AND published >= ? ORDER BY published DESC LIMIT 200",
             args + [now() - STUDY_DAYS * 86400])
    def score(r):       # الأكثر تطابقاً أولاً، ثم الأحدث
        text = " ".join(str(r[k] or "") for k in ("title", "title_ar", "summary", "summary_ar", "countries", "tags"))
        return sum(text.count(w) for w in words), r["published"]
    rows = sorted(rows, key=score, reverse=True)[:limit]
    return [dict(r) for r in rows]


def build_writer_prompt(o, refs, short=False):
    wt = WRITE_TYPES.get(o.get("type"), WRITE_TYPES["analysis"])
    wl = WRITE_LENGTHS.get(o.get("length"), WRITE_LENGTHS["medium"])
    tone = WRITE_TONES.get(o.get("tone"), WRITE_TONES["analytical"])
    lang = "الإنجليزية" if o.get("lang") == "en" else "العربية الفصحى المعاصرة"
    parts = [f"اكتب {wt[0]} عن الموضوع التالي: {o['topic']}", "", f"طبيعة النص: {wt[1]}",
             f"الطول: {wl[1]}.", f"النبرة: {tone}.", f"اللغة: {lang}."]
    if o.get("angle"):
        parts.append(f"زاوية أو ملاحظات من صاحب الطلب: {o['angle']}")
    if refs:
        parts += ["", "فيما يلي مواد رصدها مركز أبو زبيدة للتتبع والرصد خلال الشهر الأخير عن الموضوع. استند إليها حيث تفيد، "
                  "ولا تنسب إليها ما لم تقله. في نهاية النص أضف قسماً بعنوان «## المصادر» يذكر المواد التي استخدمتها فعلاً فقط، "
                  "كل مصدر في سطر: اسم الجهة، عنوان المادة، التاريخ، الرابط.", ""]
        for i, r in enumerate(refs, 1):
            date = datetime.fromtimestamp(r["published"]).strftime("%Y-%m-%d")
            t = r["title_ar"] or r["title"]
            orig = f" (الأصل: {r['title']})" if r["title"] and r["title"] != t else ""
            summ = (r["summary_ar"] or r["summary"] or "")[:(250 if short else 500)]
            parts.append(f"[{i}] {r['source_ar']} | {date} | {t}{orig}\n{summ}\nالرابط: {r['link']}")
    else:
        parts += ["", "لا توجد مواد مرصودة عن هذا الموضوع؛ اعتمد على معرفتك الموثوقة، ولا تضع قسم مصادر بروابط مخترعة."]
    return "\n".join(parts)


# ── مزودو الكتابة: Ollama (محلي مجاني بلا مفتاح)، Gemini (مفتاح مجاني)، Claude (مدفوع)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_SUGGEST = [("qwen2.5:7b", "Qwen 2.5 7B: عربي جيد، حجمه نحو 4.7 جيجا ويحتاج 8 جيجا ذاكرة"),
                  ("aya-expanse:8b", "Aya Expanse 8B: متخصص في اللغات ومنها العربية، نحو 5 جيجا"),
                  ("qwen2.5:14b", "Qwen 2.5 14B: أفضل جودة، نحو 9 جيجا ويحتاج 16 جيجا ذاكرة")]
PULL = {"model": "", "status": "", "pct": 0, "running": False, "error": ""}
_GEM = {"key": "", "models": [], "t": 0}


def ollama_url():
    return (kv_get("ollama_url") or OLLAMA_URL).rstrip("/")


def ollama_models():
    try:
        r = requests.get(ollama_url() + "/api/tags", timeout=2)
        r.raise_for_status()
        return True, [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return False, []


def gemini_models(key):
    if key == _GEM["key"] and time.time() - _GEM["t"] < 3600 and _GEM["models"]:
        return _GEM["models"]
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200}, timeout=15)
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise ValueError(f"رمز {r.status_code}: {msg[:120]}")
    ms = [m["name"].split("/")[-1] for m in r.json().get("models", [])
          if "generateContent" in m.get("supportedGenerationMethods", []) and "gemini" in m["name"]
          and not re.search(r"embed|vision|tts|image|audio|live|aqa|learnlm", m["name"])]
    ms = sorted(set(ms), reverse=True)
    _GEM.update(key=key, models=ms, t=time.time())
    return ms


def default_gemini(ms):
    for pat in (r"flash$", r"flash", r"pro$", r""):
        for m in ms:
            if re.search(pat, m) and not re.search(r"lite|preview|exp|8b", m):
                return m
    return ms[0] if ms else "gemini-2.5-flash"


# ── محرك مجاني فوري: بلا مفتاح ولا تثبيت (خدمة Pollinations المفتوحة)
FREE_URL = "https://text.pollinations.ai/openai"
FREE_MODELS_URL = "https://text.pollinations.ai/models"
FREE_DEFAULT = [{"id": "openai", "name": "OpenAI (افتراضي، عربي جيد)"}, {"id": "mistral", "name": "Mistral"}]
_FREE = {"models": [], "t": 0}


def free_models():
    if _FREE["models"] and time.time() - _FREE["t"] < 3600:
        return _FREE["models"]
    try:
        r = requests.get(FREE_MODELS_URL, headers=HEADERS, timeout=8)
        r.raise_for_status()
        out = []
        for m in r.json():
            if not isinstance(m, dict) or not m.get("name"):
                continue
            if m.get("tier") not in (None, "anonymous"):          # المتاح بلا حساب فقط
                continue
            if m.get("audio") or "audio" in str(m.get("output_modalities", "")) or m.get("uncensored"):
                continue
            out.append({"id": m["name"], "name": (m.get("description") or m["name"])[:70]})
        _FREE.update(models=out or FREE_DEFAULT, t=time.time())
    except Exception:
        _FREE.update(models=FREE_DEFAULT, t=time.time() - 3000)
    return _FREE["models"]


def _free_stream(model, messages, max_tokens, st):
    """طلب واحد للخدمة المجانية. يملأ st بـ: status, finish, done."""
    st.update(status=0, finish=None, done=False)
    r = requests.post(FREE_URL, stream=True, timeout=(15, 300), headers={**HEADERS, "Content-Type": "application/json"},
                      json={"model": model, "stream": True, "temperature": 0.85, "max_tokens": max_tokens,
                            "private": True, "referrer": "abu-zubaida-osint", "messages": messages})
    st["status"] = r.status_code
    if r.status_code != 200:
        return
    if "event-stream" in r.headers.get("Content-Type", ""):
        try:
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    st["done"] = True
                    break
                try:
                    ev = json.loads(data)
                except Exception:
                    continue
                for ch in ev.get("choices", []) or []:
                    if ch.get("finish_reason"):
                        st["finish"] = ch["finish_reason"]
                    txt = (ch.get("delta") or {}).get("content") or ""
                    if txt:
                        yield txt
        except Exception:
            st["finish"] = "cut"          # انقطع الاتصال في المنتصف
    else:
        body = r.content.decode("utf-8", "replace")
        try:
            j = json.loads(body)
            st["finish"] = j["choices"][0].get("finish_reason")
            body = j["choices"][0]["message"]["content"]
        except Exception:
            pass
        st["done"] = True
        if body:
            yield body


_END_CH = ".!؟?»)\"…"
CONT_MSG = ("توقف النص قبل اكتماله. أكمل الكتابة من آخر كلمة توقفت عندها مباشرة، بنفس الأسلوب واللغة، "
            "دون أن تعيد أي جملة سابقة ودون عنوان أو مقدمة أو تعليق. "
            "إن كان النص قد اكتمل فعلاً بما فيه قسم المصادر إن وُجد، فاكتب [[END]] فقط.")


def _strip_overlap(prev, new):
    n = new.lstrip()
    for k in range(min(len(prev), len(n), 400), 15, -1):
        if prev.endswith(n[:k]):
            return n[k:]
    if prev and new and not new[0].isspace() and prev[-1].isalnum() and new[0].isalnum():
        return " " + new
    return new


def _looks_complete(text, finish, min_words):
    t = text.rstrip()
    if not t or finish in ("length", "cut"):
        return False
    words = len(t.split())
    if re.search(r"^#{1,3}\s*(المصادر|المراجع|Sources|References)", t, re.M) and words >= min_words * 0.6:
        return True
    return t[-1] in _END_CH and (words >= min_words or (finish == "stop" and words >= min_words * 0.6))


def gen_free(prompt, max_tokens, system=None, min_words=None):
    """المحرك المجاني: الخدمة تقطع النص الطويل، فنطلب الإكمال تلقائياً حتى يكتمل."""
    models = [m["id"] for m in free_models()]
    first = kv_get("free_model") if kv_get("free_model") in models else (models[0] if models else "openai")
    order = [first] + [m for m in ("openai", "mistral") if m != first]
    if min_words is None:
        min_words = {4000: 650, 7000: 1150, 14000: 2200}.get(max_tokens, 900)
    sys_msg = {"role": "system", "content": system or WRITER_SYSTEM}
    text, model, mi = "", order[0], 0
    for rnd in range(12):
        msgs = [sys_msg, {"role": "user", "content": prompt}]
        if rnd:
            msgs += [{"role": "assistant", "content": text[-3500:]}, {"role": "user", "content": CONT_MSG}]
        st, buf, started = {}, "", rnd == 0
        for attempt in range(4):
            try:
                for piece in _free_stream(model, msgs, max_tokens, st):
                    if started:
                        text += piece
                        yield piece
                    else:                                    # أول 200 حرف من الإكمال: نزيل أي تكرار
                        buf += piece
                        if len(buf) >= 200:
                            started = True
                            piece2 = _strip_overlap(text, buf)
                            text += piece2
                            yield piece2
            except Exception as e:
                st["status"] = -1
                st["err"] = str(e)[:120]
            if st["status"] == 429:                         # حد الطلبات: ننتظر ثم نعيد
                yield "[[WAIT]]"
                time.sleep(16)
                continue
            if st["status"] not in (200,) and not text and mi + 1 < len(order):
                mi += 1
                model = order[mi]                           # جرّب نموذجاً مجانياً آخر
                continue
            break
        if not started and buf:
            piece2 = _strip_overlap(text, buf)
            text += piece2
            yield piece2
        if st["status"] not in (200,):
            if not text:
                yield (f"[[ERROR]] الخدمة المجانية لم تستجب (رمز {st['status']}). قد تكون مزدحمة أو غيّرت شروطها؛ "
                       "جرّب بعد قليل، أو استخدم Gemini بمفتاحه المجاني.")
                return
            yield "\n\n[[ERROR]] توقفت الخدمة المجانية قبل اكتمال النص. احفظ ما كُتب أو أعد المحاولة بعد قليل."
            return
        if "[[END]]" in text:
            return
        if _looks_complete(text, st["finish"], min_words):
            return
        yield "[[WAIT]]"
        time.sleep(4)
    return


def writer_provider():
    p = kv_get("writer_provider")
    if p in ("free", "ollama", "gemini", "claude"):
        return p
    return "claude" if anthropic_key() else ("gemini" if kv_get("gemini_key") else "free")


def writer_state():
    prov = writer_provider()
    ck, gk = anthropic_key(), (kv_get("gemini_key") or "")
    running, oms = ollama_models()
    gms, gerr = [], ""
    if gk:
        try:
            gms = gemini_models(gk)
        except Exception as e:
            gerr = str(e)[:160]
    om = kv_get("ollama_model") if kv_get("ollama_model") in oms else (oms[0] if oms else "")
    gm = kv_get("gemini_model") if kv_get("gemini_model") in gms else default_gemini(gms)
    fms = free_models() if prov == "free" else _FREE["models"] or FREE_DEFAULT
    ready = {"free": True, "ollama": running and bool(om), "gemini": bool(gk) and not gerr, "claude": bool(ck)}[prov]
    return {
        "provider": prov, "ready": ready,
        "claude": {"has_key": bool(ck), "key_hint": (ck[:7] + "…" + ck[-4:]) if ck else "",
                   "model": kv_get("writer_model") or WRITER_MODELS[0][0], "models": [{"id": m, "name": n} for m, n in WRITER_MODELS]},
        "gemini": {"has_key": bool(gk), "key_hint": (gk[:6] + "…" + gk[-4:]) if gk else "", "models": gms, "model": gm, "error": gerr},
        "free": {"models": fms, "model": kv_get("free_model") if kv_get("free_model") in [m["id"] for m in fms] else fms[0]["id"]},
        "ollama": {"running": running, "models": oms, "model": om, "url": ollama_url(),
                   "suggest": [{"id": m, "name": n} for m, n in OLLAMA_SUGGEST], "pull": PULL},
    }


@app.get("/api/writer/config")
def api_writer_config():
    st = writer_state()
    st.update(types=[{"id": k, "name": v[0]} for k, v in WRITE_TYPES.items()],
              lengths=[{"id": k, "name": v[0]} for k, v in WRITE_LENGTHS.items()],
              tones=[{"id": k, "name": v} for k, v in WRITE_TONES.items()])
    return jsonify(st)


@app.post("/api/writer/config")
def api_writer_config_set():
    b = request.get_json(silent=True) or {}
    if b.get("free_model"):
        kv_set("free_model", b["free_model"])
    if b.get("provider") in ("free", "ollama", "gemini", "claude"):
        kv_set("writer_provider", b["provider"])
    if "key" in b:
        k = (b.get("key") or "").strip()
        if k and not k.startswith("sk-"):
            return jsonify(ok=False, error="مفتاح Anthropic يبدأ عادة بـ sk-ant-"), 400
        kv_set("anthropic_key", k)
    if "gemini_key" in b:
        k = (b.get("gemini_key") or "").strip()
        if k:
            try:
                gemini_models(k)
            except Exception as e:
                return jsonify(ok=False, error=f"المفتاح غير صالح أو لا يعمل: {e}"), 400
        kv_set("gemini_key", k)
    if b.get("model") in [m for m, _ in WRITER_MODELS]:
        kv_set("writer_model", b["model"])
    for k in ("gemini_model", "ollama_model"):
        if b.get(k):
            kv_set(k, b[k])
    if b.get("ollama_url"):
        kv_set("ollama_url", b["ollama_url"].strip())
    reset_providers()
    return jsonify(ok=True)


def _pull(model):
    PULL.update(model=model, status="بدء التنزيل…", pct=0, running=True, error="")
    try:
        r = requests.post(ollama_url() + "/api/pull", json={"name": model, "stream": True}, stream=True, timeout=(10, 7200))
        for line in r.iter_lines():
            if not line:
                continue
            d = json.loads(line)
            if d.get("error"):
                PULL["error"] = d["error"]
                break
            PULL["status"] = d.get("status", "")
            if d.get("total"):
                PULL["pct"] = int(d.get("completed", 0) * 100 / d["total"])
        if not PULL["error"]:
            kv_set("ollama_model", model)
    except Exception as e:
        PULL["error"] = str(e)[:150]
    PULL["running"] = False


@app.post("/api/writer/ollama/pull")
def api_ollama_pull():
    model = ((request.get_json(silent=True) or {}).get("model") or "").strip()
    if not model or PULL["running"]:
        return jsonify(ok=False, error="يجري تنزيل نموذج آخر الآن" if PULL["running"] else "حدد النموذج"), 400
    threading.Thread(target=_pull, args=(model,), daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/writer/sources")
def api_writer_sources():
    topic = ((request.get_json(silent=True) or {}).get("topic") or "").strip()
    refs = related_items(topic, limit=12 if writer_provider() in ("ollama", "free") else 25) if topic else []
    return jsonify(items=[{k: r[k] for k in ("id", "title_ar", "title", "source_ar", "published", "cat")} for r in refs])


def _err_msg(r):
    try:
        return (r.json().get("error") or {}).get("message", "") if isinstance(r.json().get("error"), dict) else str(r.json().get("error", ""))
    except Exception:
        return r.text[:200]


def gen_claude(prompt, max_tokens, system=None, min_words=None):
    key, model = anthropic_key(), kv_get("writer_model") or WRITER_MODELS[0][0]
    r = requests.post("https://api.anthropic.com/v1/messages", stream=True, timeout=(15, 300),
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": model, "max_tokens": max_tokens, "stream": True, "system": system or WRITER_SYSTEM,
                            "messages": [{"role": "user", "content": prompt}]})
    if r.status_code != 200:
        hint = {401: "المفتاح غير صحيح", 403: "المفتاح لا يملك صلاحية", 404: "النموذج غير متاح لحسابك",
                429: "تجاوزت حد الاستخدام، انتظر قليلاً", 529: "الخدمة مزدحمة الآن"}.get(r.status_code, "تعذّر الاتصال بالخدمة")
        yield f"[[ERROR]] {hint} (رمز {r.status_code}). {_err_msg(r)}"
        return
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except Exception:
            continue
        if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
            yield ev["delta"]["text"]
        elif ev.get("type") == "error":
            yield f"\n[[ERROR]] {ev.get('error', {}).get('message', 'خطأ من الخدمة')}"
            return


def gen_gemini(prompt, max_tokens, system=None, min_words=None):
    st = writer_state()["gemini"]
    key, model = kv_get("gemini_key"), st["model"]
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent",
                      params={"alt": "sse", "key": key}, stream=True, timeout=(15, 300),
                      json={"systemInstruction": {"parts": [{"text": system or WRITER_SYSTEM}]},
                            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                            "generationConfig": {"maxOutputTokens": max_tokens + 6000, "temperature": 0.9}})
    if r.status_code != 200:
        hint = {400: "طلب مرفوض (تحقق من المفتاح أو النموذج)", 403: "المفتاح لا يملك صلاحية",
                429: "تجاوزت حد الاستخدام المجاني، انتظر قليلاً أو جرّب لاحقاً"}.get(r.status_code, "تعذّر الاتصال بـ Gemini")
        yield f"[[ERROR]] {hint} (رمز {r.status_code}). {_err_msg(r)}"
        return
    got = False
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except Exception:
            continue
        for c in ev.get("candidates", []) or []:
            for part in (c.get("content") or {}).get("parts", []) or []:
                if part.get("text") and not part.get("thought"):
                    got = True
                    yield part["text"]
            if c.get("finishReason") == "SAFETY":
                yield "\n[[ERROR]] أوقف Gemini الكتابة بسبب فلاتر المحتوى. جرّب صياغة أخرى للموضوع."
                return
    if not got:
        yield "[[ERROR]] لم يُرجع Gemini أي نص. جرّب نموذجاً آخر من القائمة."


def gen_ollama(prompt, max_tokens, system=None, min_words=None):
    st = writer_state()["ollama"]
    if not st["running"]:
        yield "[[ERROR]] برنامج Ollama غير مشغّل على جهازك. ثبّته من ollama.com وشغّله ثم أعد المحاولة."
        return
    if not st["model"]:
        yield "[[ERROR]] لا يوجد نموذج مثبت في Ollama. نزّل نموذجاً من إعدادات الكاتب أولاً."
        return
    try:
        r = requests.post(ollama_url() + "/api/chat", stream=True, timeout=(10, 1800), json={
            "model": st["model"], "stream": True,
            "messages": [{"role": "system", "content": system or WRITER_SYSTEM}, {"role": "user", "content": prompt}],
            "options": {"num_predict": max_tokens, "num_ctx": 12288, "temperature": 0.8, "repeat_penalty": 1.1}})
    except Exception as e:
        yield f"[[ERROR]] تعذّر الاتصال بـ Ollama: {str(e)[:120]}"
        return
    for line in r.iter_lines():
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("error"):
            yield f"\n[[ERROR]] Ollama: {d['error']}"
            return
        txt = (d.get("message") or {}).get("content", "")
        if txt:
            yield txt


@app.post("/api/writer/generate")
def api_writer_generate():
    o = request.get_json(silent=True) or {}
    o["topic"] = (o.get("topic") or "").strip()[:400]
    if not o["topic"]:
        return Response("[[ERROR]] اكتب الموضوع أولاً.", mimetype="text/plain; charset=utf-8")
    prov = writer_provider()
    light = prov in ("ollama", "free")      # محركات أصغر: مواد مرجعية أقل وأقصر
    refs = related_items(o["topic"], limit=12 if light else 25) if o.get("use_sources", True) else []
    prompt = build_writer_prompt(o, refs, short=light)
    max_tokens = WRITE_LENGTHS.get(o.get("length"), WRITE_LENGTHS["medium"])[2]
    fn = {"free": gen_free, "claude": gen_claude, "gemini": gen_gemini, "ollama": gen_ollama}[prov]

    def gen():
        try:
            yield from fn(prompt, max_tokens)
        except Exception as e:
            yield f"\n[[ERROR]] تعذّر الاتصال: {str(e)[:150]}"

    return Response(gen(), mimetype="text/plain; charset=utf-8",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "X-Refs": str(len(refs))})


@app.get("/api/articles")
def api_articles():
    rows = q("SELECT v FROM kv WHERE k LIKE 'article:%'")
    arts = sorted((json.loads(r["v"]) for r in rows), key=lambda a: a["created"], reverse=True)
    return jsonify(items=arts)


@app.post("/api/articles")
def api_articles_save():
    b = request.get_json(silent=True) or {}
    body = (b.get("body") or "").strip()
    if not body:
        return jsonify(ok=False), 400
    aid = b.get("id") or hashlib.sha1((body[:200] + str(time.time())).encode("utf-8")).hexdigest()[:12]
    title = (re.match(r"#\s*(.+)", body) or [None, b.get("topic", "")])[1].strip()
    old = kv_get("article:" + aid)
    created = json.loads(old).get("created", now()) if old else now()
    art = {"id": aid, "title": title, "topic": b.get("topic", ""), "type": b.get("type", ""), "body": body,
           "created": created, "updated": now(), "words": len(body.split()), "engine": b.get("engine") or writer_provider(),
           "length": b.get("length", ""), "lang": b.get("lang", "")}
    kv_set("article:" + aid, json.dumps(art, ensure_ascii=False))
    return jsonify(ok=True, id=aid)


@app.delete("/api/articles")
def api_articles_del_all():
    x("DELETE FROM kv WHERE k LIKE 'article:%'")
    return jsonify(ok=True)


@app.delete("/api/articles/<aid>")
def api_articles_del(aid):
    x("DELETE FROM kv WHERE k=?", ("article:" + aid,))
    return jsonify(ok=True)


# ───────────────────────── بوت تيليغرام: نشر ملخصات المقالات المترجمة آلياً ─────────────────────────
BOT_DEFAULT_CATS = ["world", "think_global", "think_arab"]      # الأخبار العالمية + المقالات والدراسات
BOT_ALLOWED_CATS = ["world", "think_global", "think_arab", "terror", "intel"]
BOT = {"last_sent": 0, "next_due": 0, "last_error": "", "last_instant": 0, "bot_name": "", "running": False}
BOT_LOCK = threading.Lock()


def bot_cfg():
    try:
        c = json.loads(kv_get("bot_cfg") or "{}")
    except Exception:
        c = {}
    c.setdefault("token", ""); c.setdefault("chat", ""); c.setdefault("interval", 60)
    c.setdefault("cats", BOT_DEFAULT_CATS); c.setdefault("enabled", False)
    c.setdefault("preview", True)
    if not c.get("v2"):          # سياسة جديدة: لا أخبار نوعية ولا إنذارات على تيليغرام
        c["cats"] = BOT_DEFAULT_CATS
        c["v2"] = True
    c["cats"] = [k for k in c["cats"] if k in BOT_ALLOWED_CATS] or BOT_DEFAULT_CATS
    c["instant_qual"] = c["prio_qual"] = c["send_alerts"] = False
    return c


def tg_api(token, method, **params):
    for _ in range(3):
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=25)
        d = r.json()
        if d.get("ok"):
            return d["result"]
        if r.status_code == 429:
            time.sleep(int((d.get("parameters") or {}).get("retry_after", 5)) + 1)
            continue
        raise ValueError(d.get("description") or f"رمز {r.status_code}")
    raise ValueError("تيليغرام يطلب الانتظار (حد الرسائل)")


def bot_summary(row):
    """ملخص عربي للمقالة: الملخص المترجم، أو أول فقرات النص الكامل المترجم إن كان الملخص قصيراً."""
    s_ = (row["summary_ar"] or "").strip()
    if len(s_) < 160 and row["kind"] != "tweet":
        try:
            art = get_article(row)
            if art.get("ok"):
                paras = [p_ for p_ in art["paragraphs"] if has_ar(p_) and len(p_) > 60]
                s2 = " ".join(paras[:3])
                if len(s2) > len(s_):
                    s_ = s2
        except Exception:
            pass
    if not s_ and row["summary"]:
        s_ = translate_text(row["summary"]) or ""
    if len(s_) > 850:
        cut = s_[:850]
        k = max(cut.rfind("."), cut.rfind("؟"), cut.rfind("!"))
        s_ = (cut[:k + 1] if k > 300 else cut.rstrip() + "…")
    return s_


def bot_message(row, summary, link):
    e = html.escape
    cat = dict((k, n) for k, n, _ in CATEGORIES).get(row["cat"], "")
    evs = [x for x in (row["events"] or "").strip("|").split("|") if x]
    ctry = [x for x in (row["countries"] or "").strip("|").split("|") if x][:4]
    when = datetime.fromtimestamp(row["published"]).strftime("%Y-%m-%d %H:%M")
    lines = []
    if evs:
        lines.append("🔴 <b>خبر نوعي: " + e("، ".join(evs)) + "</b>")
    lines.append(f"<b>{e(row['title_ar'] or row['title'])}</b>")
    if summary:
        lines += ["", e(summary)]
    lines += ["", f"🏛 {e(row['source_ar'])}  |  🗂 {e(cat)}"]
    if ctry:
        lines.append("📍 " + e("، ".join(ctry)))
    lines.append(f"🕒 {when}")
    if link:
        lines += ["", f'🔗 <a href="{e(link, quote=True)}">قراءة المقال في موقعه</a>']
    lines += ["", "<i>مركز أبو زبيدة للتتبع والرصد</i>"]
    return "\n".join(lines)[:4000]


def bot_pick(cfg, qual_only=False, fresh_minutes=None):
    cats = [c for c in cfg["cats"] if c in dict((k, 1) for k, _, _ in CATEGORIES)] or BOT_DEFAULT_CATS
    ph = ",".join("?" * len(cats))
    where = [f"cat IN ({ph})", "translated=1", "kind NOT IN ('tweet', 'video')", "published >= ?",
             "(events = '' OR events IS NULL)", "id NOT IN (SELECT id FROM tg_sent)"]
    args = cats + [now() - (fresh_minutes * 60 if fresh_minutes else 7 * 86400)]
    if qual_only:
        where.append("events != '' AND events IS NOT NULL")
    order = "(events != '' AND events IS NOT NULL) DESC, published DESC" if cfg["prio_qual"] else "published DESC"
    return q(f"SELECT * FROM items WHERE {' AND '.join(where)} ORDER BY {order} LIMIT 1", args, one=True)


def bot_send(row, cfg, mark=True):
    link = resolve_item(row)
    row = q("SELECT * FROM items WHERE id=?", (row["id"],), one=True) or row
    text = bot_message(row, bot_summary(row), link)
    params = {"chat_id": cfg["chat"], "text": text, "parse_mode": "HTML",
              "link_preview_options": {"is_disabled": not cfg["preview"], "url": link} if link else {"is_disabled": True}}
    if link.startswith("http"):
        params["reply_markup"] = {"inline_keyboard": [[{"text": "📖 اقرأ المقال", "url": link}]]}
    tg_api(cfg["token"], "sendMessage", **params)
    if mark:
        x("INSERT OR REPLACE INTO tg_sent(id, sent, title) VALUES(?, ?, ?)", (row["id"], now(), row["title_ar"] or row["title"]))
    BOT.update(last_sent=now(), last_error="")


def bot_tick(force=False):
    cfg = bot_cfg()
    if not (cfg["token"] and cfg["chat"]) or (not cfg["enabled"] and not force):
        return False
    with BOT_LOCK:
        # تنبيه فوري لكل خبر نوعي جديد (آخر 30 دقيقة)، بفاصل 20 ثانية على الأقل
        if cfg["instant_qual"] and not force and now() - BOT["last_instant"] >= 20:
            row = bot_pick(cfg, qual_only=True, fresh_minutes=30)
            if row:
                bot_send(row, cfg)
                BOT["last_instant"] = now()
                return True
        if force or now() >= BOT["next_due"]:
            BOT["next_due"] = now() + int(cfg["interval"])
            row = bot_pick(cfg)
            if row:
                bot_send(row, cfg)
                return True
    return False


def bot_loop():
    time.sleep(10)
    while True:
        try:
            bot_tick()
        except Exception as e:
            BOT["last_error"] = str(e)[:200]
            log.warning("telegram bot: %s", BOT["last_error"])
            time.sleep(30)
        time.sleep(5)


@app.get("/api/bot")
def api_bot():
    cfg = bot_cfg()
    day0 = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    sent_today = q("SELECT COUNT(*) c FROM tg_sent WHERE sent >= ?", (day0,), one=True)["c"]
    recent = [dict(r) for r in q("SELECT * FROM tg_sent ORDER BY sent DESC LIMIT 12")]
    tok = cfg["token"]
    return jsonify(cfg={**cfg, "token": "", "has_token": bool(tok), "token_hint": (tok[:6] + "…" + tok[-4:]) if tok else ""},
                   state={**BOT, "now": now(), "sent_today": sent_today}, recent=recent,
                   cats=[{"key": k, "name": n} for k, n, _ in CATEGORIES if k in BOT_ALLOWED_CATS])


@app.post("/api/bot")
def api_bot_set():
    b = request.get_json(silent=True) or {}
    cfg = bot_cfg()
    if "token" in b and b["token"].strip():
        tok = b["token"].strip()
        try:
            me = tg_api(tok, "getMe")
        except Exception as e:
            return jsonify(ok=False, error=f"رمز البوت غير صحيح: {e}"), 400
        cfg["token"] = tok
        BOT["bot_name"] = me.get("username", "")
    if "chat" in b:
        cfg["chat"] = str(b["chat"]).strip()
    if "interval" in b:
        cfg["interval"] = max(60, int(b["interval"]))
    if isinstance(b.get("cats"), list):
        cfg["cats"] = b["cats"]
    for k in ("enabled", "preview"):
        if k in b:
            cfg[k] = bool(b[k])
    if cfg["enabled"] and not (cfg["token"] and cfg["chat"]):
        return jsonify(ok=False, error="أضف رمز البوت ومعرّف المحادثة أولاً"), 400
    kv_set("bot_cfg", json.dumps(cfg, ensure_ascii=False))
    if b.get("enabled"):
        BOT["next_due"] = now() + 3
    return jsonify(ok=True)


@app.get("/api/bot/chats")
def api_bot_chats():
    cfg = bot_cfg()
    if not cfg["token"]:
        return jsonify(ok=False, error="أضف رمز البوت أولاً"), 400
    try:
        ups = tg_api(cfg["token"], "getUpdates", limit=100, allowed_updates=["message", "channel_post", "my_chat_member"])
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400
    chats = {}
    for u in ups:
        for key in ("message", "channel_post", "my_chat_member"):
            c = (u.get(key) or {}).get("chat")
            if c:
                chats[c["id"]] = {"id": c["id"], "type": c.get("type", ""),
                                  "name": c.get("title") or " ".join(filter(None, [c.get("first_name"), c.get("last_name")])) or c.get("username", "")}
    return jsonify(ok=True, chats=list(chats.values()))


@app.post("/api/bot/test")
def api_bot_test():
    cfg = bot_cfg()
    if not (cfg["token"] and cfg["chat"]):
        return jsonify(ok=False, error="أضف رمز البوت ومعرّف المحادثة أولاً"), 400
    try:
        tg_api(cfg["token"], "sendMessage", chat_id=cfg["chat"], parse_mode="HTML",
               text="✅ <b>تم ربط البوت بنجاح</b>\nمركز أبو زبيدة للتتبع والرصد سيرسل هنا ملخصات المقالات المترجمة.")
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400


@app.post("/api/bot/send-now")
def api_bot_send_now():
    try:
        sent = bot_tick(force=True)
        return jsonify(ok=True, sent=sent)
    except Exception as e:
        BOT["last_error"] = str(e)[:200]
        return jsonify(ok=False, error=BOT["last_error"]), 400


@app.post("/api/bot/reset")
def api_bot_reset():
    x("DELETE FROM tg_sent")
    return jsonify(ok=True)


# ───────────────────────── التحقق من الخبر: تجميع ما نقلته مصادر مختلفة عن الحدث نفسه ─────────────────────────
VERIFY_CATS = ("world", "arab", "war", "terror", "intel", "tweets", "keywords", "economy")
_STOP = {norm_ar(w) for w in (
    "في من على إلى الى عن مع بعد قبل أن ان إن التي الذي الذين هذا هذه ذلك تلك كما قد لم لن ما لا هو هي هم بين "
    "حول خلال عبر منذ حتى أو او ثم كل أي اي عند قال يقول تقول قالت اليوم أمس الجديد جديد جديدة بشأن وسط ضد نحو "
    "لدى أمام عاجل مصادر مصدر تقرير تقارير بحسب وفق وفقا أكثر أقل أول ثاني يوم الأحد الاثنين الثلاثاء الأربعاء "
    "الخميس الجمعة السبت the a an of in on at to for and or with from by as is are was were be has have said says "
    "after over amid new report reports breaking live update".split())}
_PREF = ("وال", "بال", "فال", "كال", "لل", "ال", "و", "ب", "ل", "ف")


def _toks(text):
    out = set()
    for w in re.findall(r"[\u0600-\u06FF]+|[a-z0-9]+", norm_ar(text or "").lower()):
        if w in _STOP:
            continue
        for pre in _PREF:
            if w.startswith(pre) and len(w) - len(pre) >= 3:
                w = w[len(pre):]
                break
        if len(w) >= 3 and w not in _STOP:
            out.add(w)
    return out


def verify_pass():
    """يجمع الأخبار المتشابهة (آخر 36 ساعة) في عناقيد، ويحسب عدد المصادر المستقلة لكل حدث."""
    ph = ",".join("?" * len(VERIFY_CATS))
    rows = q(f"SELECT id, title, title_ar, source_ar, countries, published FROM items WHERE cat IN ({ph}) "
             f"AND translated=1 AND published >= ? ORDER BY published", [*VERIFY_CATS, now() - 36 * 3600])
    clusters, index, assign = [], {}, {}
    for r in rows:
        tk = _toks(r["title_ar"] or r["title"])
        ct = {c for c in (r["countries"] or "").strip("|").split("|") if c}
        best, best_j = None, 0.0
        if len(tk) >= 3:
            cand = Counter(ci for t in tk for ci in index.get(t, ()))
            for ci, inter in cand.items():
                if inter < 3:
                    continue
                c = clusters[ci]
                if r["published"] - c["t"] > 24 * 3600 or (ct and c["ct"] and not ct & c["ct"]):
                    continue
                j = inter / len(tk | c["tk"])
                if j >= 0.3 and j > best_j:
                    best, best_j = ci, j
        if best is None:
            clusters.append({"id": r["id"], "tk": tk, "ct": ct, "t": r["published"], "src": set()})
            best = len(clusters) - 1
            for t in tk:
                index.setdefault(t, []).append(best)
        clusters[best]["src"].add(r["source_ar"])
        assign[r["id"]] = best
    x("UPDATE items SET cluster=?, nsrc=? WHERE id=?",
      [(clusters[ci]["id"], len(clusters[ci]["src"]), iid) for iid, ci in assign.items()], many=True)


@app.get("/api/cluster/<cid>")
def api_cluster(cid):
    rows = q("SELECT * FROM items WHERE cluster=? ORDER BY published", (cid,))
    return jsonify(items=[dict(r) for r in rows])


# ───────────────────────── الإنذار المبكر: ارتفاع مفاجئ في الحديث عن دولة أو موضوع ─────────────────────────
ALERT_WIN = 3 * 3600


def alerts_pass():
    t = now()
    rows = q("SELECT countries, tags, events, published, cat FROM items WHERE published >= ? AND cat NOT IN "
             "('think_global','think_arab','economy','keywords')", (t - 7 * 86400,))
    rec, hist, field = Counter(), Counter(), {}
    for r in rows:
        keys = [("country", c) for c in (r["countries"] or "").strip("|").split("|") if c]
        keys += [("topic", g) for g in (r["tags"] or "").strip("|").split("|") if g and not g.startswith("★")
                 and g not in COUNTRY_INFO]
        if r["published"] >= t - ALERT_WIN:
            rec.update(keys)
            evs = [e for e in (r["events"] or "").strip("|").split("|") if e]
            if evs and r["published"] >= t - 2 * 3600:
                for k, c in keys:
                    if k == "country":
                        f_ = field.setdefault(c, {"n": 0, "evs": Counter()})
                        f_["n"] += 1
                        f_["evs"].update(evs)
        else:
            hist.update(keys)
    buckets = (7 * 86400 - ALERT_WIN) / ALERT_WIN
    new = []
    for (kind, key), cnt in rec.items():
        base = hist.get((kind, key), 0) / buckets
        ratio = (cnt + 1) / (base + 1)
        if cnt >= 6 and ratio >= 3:
            level = 3 if (ratio >= 6 or cnt >= 25) else 2
            what = "أخبار" if kind == "country" else "الحديث عن"
            usual = "بعد أن كان شبه غائب عن الأخبار" if base < 0.5 else f"مقابل متوسط {base:.1f} عادةً (×{ratio:.0f})"
            msg = f"ارتفاع مفاجئ في {what} {key}: {cnt} خبراً خلال 3 ساعات، {usual}"
            new.append((kind, key, level, cnt, base, msg, ""))
    for c, f_ in field.items():
        n, evc = f_["n"], f_["evs"]
        if n >= 3:
            level = 3 if n >= 6 else 2
            top = "، ".join(e for e, _ in evc.most_common(3))
            new.append(("field", c, level, n, 0, f"تصاعد ميداني في {c}: {n} أحداث نوعية خلال ساعتين ({top})", top))
    created = []
    for kind, key, level, cnt, base, msg, detail in new:
        last = q("SELECT level, cnt, created FROM alerts WHERE kind=? AND key=? ORDER BY created DESC LIMIT 1", (kind, key), one=True)
        if last and t - last["created"] < 6 * 3600 and level <= last["level"] and cnt < last["cnt"] * 2:
            continue
        aid = hashlib.sha1(f"{kind}|{key}|{t}".encode("utf-8")).hexdigest()[:16]
        x("INSERT OR IGNORE INTO alerts(id, kind, key, level, cnt, base, created, msg, detail) VALUES(?,?,?,?,?,?,?,?,?)",
          (aid, kind, key, level, cnt, base, t, msg, detail))
        created.append({"kind": kind, "key": key, "level": level, "msg": msg})
    if created:
        log.info("إنذارات جديدة: %s", len(created))
        try:
            cfg = bot_cfg()
            if cfg["enabled"] and cfg["token"] and cfg["chat"] and cfg.get("send_alerts", True):
                for a_ in created:
                    tg_api(cfg["token"], "sendMessage", chat_id=cfg["chat"], parse_mode="HTML",
                           text=f"{'🚨' if a_['level'] >= 3 else '⚠️'} <b>إنذار مبكر</b>\n{html.escape(a_['msg'])}\n\n<i>مركز أبو زبيدة للتتبع والرصد</i>")
        except Exception as e:
            log.warning("alert to telegram failed: %s", e)
    x("DELETE FROM alerts WHERE created < ?", (t - 14 * 86400,))


def analysis_loop():
    """التحقق من الأخبار كل 3 دقائق، والإنذار كل 5 دقائق."""
    time.sleep(20)
    last_alert = 0
    while True:
        try:
            verify_pass()
        except Exception:
            log.exception("verify")
        if time.time() - last_alert > 300:
            try:
                alerts_pass()
            except Exception:
                log.exception("alerts")
            last_alert = time.time()
        time.sleep(180)


@app.get("/api/alerts")
def api_alerts():
    hours = int(request.args.get("hours") or 48)
    rows = q("SELECT * FROM alerts WHERE created >= ? ORDER BY created DESC LIMIT 200", (now() - hours * 3600,))
    return jsonify(items=[dict(r) for r in rows], now=now())


# ───────────────────────── الخريطة التفاعلية ─────────────────────────
CENTROIDS = {
    "سوريا": (35.0, 38.5), "العراق": (33.2, 43.7), "إيران": (32.4, 53.7), "تركيا": (39.0, 35.2), "لبنان": (33.85, 35.86),
    "الأردن": (31.2, 36.5), "فلسطين": (31.9, 35.2), "إسرائيل": (31.4, 34.9), "مصر": (26.8, 30.8), "السعودية": (23.9, 45.1),
    "الإمارات": (23.4, 53.8), "قطر": (25.35, 51.2), "الكويت": (29.3, 47.5), "البحرين": (26.05, 50.55), "عُمان": (21.5, 55.9),
    "اليمن": (15.6, 48.0), "ليبيا": (26.3, 17.2), "تونس": (34.0, 9.5), "الجزائر": (28.0, 1.7), "المغرب": (31.8, -7.1),
    "موريتانيا": (21.0, -10.9), "السودان": (15.5, 30.2), "جنوب السودان": (7.0, 30.0), "الصومال": (5.2, 46.2),
    "مالي": (17.6, -4.0), "النيجر": (17.6, 8.1), "بوركينا فاسو": (12.2, -1.6), "نيجيريا": (9.1, 8.7), "تشاد": (15.5, 18.7),
    "إثيوبيا": (9.1, 40.5), "الكونغو الديمقراطية": (-2.9, 23.7), "موزمبيق": (-18.7, 35.5), "أفغانستان": (33.9, 67.7),
    "باكستان": (30.4, 69.3), "الهند": (21.0, 78.0), "الصين": (35.9, 104.2), "تايوان": (23.7, 121.0),
    "كوريا الشمالية": (40.3, 127.5), "كوريا الجنوبية": (36.5, 127.9), "اليابان": (36.2, 138.3), "ميانمار": (21.9, 95.9),
    "إندونيسيا": (-2.5, 118.0), "الفلبين": (12.9, 121.8), "روسيا": (56.0, 40.0), "أوكرانيا": (48.4, 31.2),
    "بيلاروسيا": (53.7, 27.9), "بريطانيا": (54.0, -2.0), "فرنسا": (46.2, 2.2), "ألمانيا": (51.2, 10.4), "إيطاليا": (42.8, 12.6),
    "إسبانيا": (40.4, -3.7), "بولندا": (51.9, 19.1), "السويد": (60.1, 18.6), "هولندا": (52.1, 5.3), "بلجيكا": (50.5, 4.5),
    "اليونان": (39.1, 21.8), "صربيا": (44.0, 21.0), "أذربيجان": (40.1, 47.6), "أرمينيا": (40.1, 45.0), "جورجيا": (42.3, 43.4),
    "كازاخستان": (48.0, 66.9), "أوزبكستان": (41.4, 64.6), "طاجيكستان": (38.9, 71.3), "الولايات المتحدة": (39.5, -98.4),
    "كندا": (56.1, -106.3), "المكسيك": (23.6, -102.6), "فنزويلا": (6.4, -66.6), "كولومبيا": (4.6, -74.3),
    "البرازيل": (-14.2, -51.9), "أستراليا": (-25.3, 133.8),
}
# مدن يُحدَّد بها موقع الحدث بدقة أكبر: (الاسم العربي، الاسم الإنجليزي، خط العرض، خط الطول)
CITIES = [
    ("دمشق", "damascus", 33.51, 36.29), ("حلب", "aleppo", 36.20, 37.16), ("ادلب", "idlib", 35.93, 36.63), ("حمص", "homs", 34.73, 36.71),
    ("حماة", "hama", 35.13, 36.75), ("اللاذقية", "latakia", 35.52, 35.79), ("طرطوس", "tartus", 34.89, 35.89),
    ("دير الزور", "deir ez-zor", 35.33, 40.14), ("الرقة", "raqqa", 35.95, 39.01), ("الحسكة", "hasakah", 36.50, 40.75),
    ("القامشلي", "qamishli", 37.05, 41.23), ("درعا", "daraa", 32.62, 36.10), ("السويداء", "sweida", 32.71, 36.57),
    ("القنيطرة", "quneitra", 33.13, 35.82), ("منبج", "manbij", 36.53, 37.95), ("البوكمال", "albukamal", 34.45, 40.92),
    ("تدمر", "palmyra", 34.56, 38.28), ("عفرين", "afrin", 36.51, 36.87), ("الباب", "al-bab", 36.37, 37.52), ("جرابلس", "jarablus", 36.82, 38.01),
    ("عين العرب", "kobani", 36.89, 38.35), ("تل ابيض", "tal abyad", 36.70, 38.95), ("راس العين", "ras al-ain", 36.85, 40.07),
    ("بغداد", "baghdad", 33.31, 44.36), ("الموصل", "mosul", 36.34, 43.13), ("البصرة", "basra", 30.51, 47.78), ("اربيل", "erbil", 36.19, 44.01),
    ("كركوك", "kirkuk", 35.47, 44.39), ("الرمادي", "ramadi", 33.42, 43.30), ("الفلوجة", "fallujah", 33.35, 43.78),
    ("تكريت", "tikrit", 34.60, 43.68), ("السليمانية", "sulaymaniyah", 35.56, 45.44), ("سنجار", "sinjar", 36.32, 41.87),
    ("بيروت", "beirut", 33.89, 35.50), ("صيدا", "sidon", 33.56, 35.37), ("صور", "tyre", 33.27, 35.20), ("النبطية", "nabatieh", 33.38, 35.48),
    ("بعلبك", "baalbek", 34.00, 36.21), ("غزة", "gaza city", 31.50, 34.47), ("خان يونس", "khan younis", 31.35, 34.31),
    ("رفح", "rafah", 31.29, 34.25), ("دير البلح", "deir al-balah", 31.42, 34.35), ("جباليا", "jabalia", 31.53, 34.48),
    ("جنين", "jenin", 32.46, 35.30), ("نابلس", "nablus", 32.22, 35.26), ("رام الله", "ramallah", 31.90, 35.20),
    ("طولكرم", "tulkarm", 32.31, 35.03), ("الخليل", "hebron", 31.53, 35.10), ("القدس", "jerusalem", 31.78, 35.22),
    ("تل ابيب", "tel aviv", 32.08, 34.78), ("حيفا", "haifa", 32.79, 34.99), ("ايلات", "eilat", 29.56, 34.95),
    ("صنعاء", "sanaa", 15.37, 44.19), ("عدن", "aden", 12.79, 45.03), ("الحديدة", "hodeidah", 14.80, 42.95), ("مارب", "marib", 15.46, 45.32),
    ("تعز", "taiz", 13.58, 44.02), ("المكلا", "mukalla", 14.54, 49.12), ("طهران", "tehran", 35.69, 51.39), ("اصفهان", "isfahan", 32.65, 51.67),
    ("تبريز", "tabriz", 38.08, 46.29), ("شيراز", "shiraz", 29.59, 52.58), ("بندر عباس", "bandar abbas", 27.18, 56.27),
    ("انقرة", "ankara", 39.93, 32.86), ("اسطنبول", "istanbul", 41.01, 28.98), ("غازي عنتاب", "gaziantep", 37.07, 37.38),
    ("انطاكيا", "antakya", 36.20, 36.16), ("كلس", "kilis", 36.72, 37.12), ("اورفا", "urfa", 37.16, 38.79),
    ("الخرطوم", "khartoum", 15.50, 32.56), ("ام درمان", "omdurman", 15.65, 32.48), ("الفاشر", "el fasher", 13.63, 25.35),
    ("نيالا", "nyala", 12.05, 24.88), ("بورتسودان", "port sudan", 19.62, 37.22), ("الابيض", "el obeid", 13.18, 30.22),
    ("طرابلس الليبية", "tripoli", 32.89, 13.19), ("بنغازي", "benghazi", 32.12, 20.07), ("مصراتة", "misrata", 32.38, 15.09),
    ("سرت", "sirte", 31.21, 16.59), ("القاهرة", "cairo", 30.04, 31.24), ("العريش", "el-arish", 31.13, 33.80),
    ("الرياض", "riyadh", 24.71, 46.68), ("مقديشو", "mogadishu", 2.05, 45.32), ("باماكو", "bamako", 12.64, -8.0),
    ("نيامي", "niamey", 13.51, 2.11), ("واغادوغو", "ouagadougou", 12.37, -1.52), ("مايدوغوري", "maiduguri", 11.85, 13.16),
    ("كييف", "kyiv", 50.45, 30.52), ("خاركيف", "kharkiv", 49.99, 36.23), ("اوديسا", "odesa", 46.48, 30.72), ("دونيتسك", "donetsk", 48.0, 37.80),
    ("زابوريجيا", "zaporizhzhia", 47.84, 35.14), ("خيرسون", "kherson", 46.64, 32.61), ("لفيف", "lviv", 49.84, 24.03),
    ("موسكو", "moscow", 55.76, 37.62), ("كورسك", "kursk", 51.73, 36.19), ("بيلغورود", "belgorod", 50.60, 36.59),
    ("كابل", "kabul", 34.53, 69.17), ("اسلام اباد", "islamabad", 33.68, 73.05), ("كويتا", "quetta", 30.18, 66.99),
    ("بيشاور", "peshawar", 34.01, 71.58),
]
CITY_RES = [(re.compile(r"(?<![\u0600-\u06FF])(?:[وفبلك])?(?:ال)?" + re.escape(norm_ar(a)) + r"(?![\u0600-\u06FF])"),
             re.compile(r"\b" + re.escape(e) + r"\b"), lat, lon, a) for a, e, lat, lon in CITIES]


def locate(r):
    text_ar = norm_ar(" ".join(filter(None, [r["title_ar"], (r["summary_ar"] or "")[:300]])))
    text_en = " ".join(filter(None, [r["title"], (r["summary"] or "")[:300]])).lower()
    for ar_re, en_re, lat, lon, name in CITY_RES:
        if ar_re.search(text_ar) or en_re.search(text_en):
            return lat, lon, name, True
    ctry = [c for c in (r["countries"] or "").strip("|").split("|") if c]
    if ctry and ctry[0] in CENTROIDS:
        h = int(hashlib.md5(r["id"].encode()).hexdigest()[:6], 16)
        lat, lon = CENTROIDS[ctry[0]]
        return lat + ((h % 100) - 50) / 60, lon + (((h // 100) % 100) - 50) / 60, ctry[0], False
    return None


# ───────────────────────── رصد انقطاع الإنترنت (IODA - معهد جورجيا للتقنية، مجاني بلا مفتاح) ─────────────────────────
IODA_API = "https://api.ioda.inetintel.cc.gatech.edu/v2"
NET_WATCH = ["SY", "IQ", "IR", "LB", "YE", "SD", "LY", "PS", "IL", "EG", "TR", "AF", "PK", "RU", "UA", "SO", "ML", "NE", "BF", "ET"]
NET_SRC_AR = {"bgp": "التوجيه (BGP)", "ping-slash24": "الاستجابة للفحص", "merit-nt": "حركة الشبكة الخلفية",
              "gtr": "حركة Google", "ucsd-nt": "حركة الشبكة الخلفية"}
ISO2AR = {c[1]: c[0] for c in COUNTRIES}
NET = {"last": 0, "error": ""}


def _ent_code(a):
    ent = a.get("entity") or {}
    code = (ent.get("code") or a.get("entityCode") or "").upper()
    if not code and isinstance(a.get("location"), str) and "/" in a["location"]:
        code = a["location"].split("/")[-1].upper()
    return code


def fetch_ioda():
    t = now()
    r = requests.get(f"{IODA_API}/outages/alerts", headers=HEADERS, timeout=45,
                     params={"from": t - 24 * 3600, "until": t, "entityType": "country", "limit": 3000})
    if r.status_code != 200:
        raise ValueError(f"رمز {r.status_code}")
    data = r.json()
    data = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(data, dict):
        data = data.get("alerts") or []
    rows = []
    for a in data or []:
        if not isinstance(a, dict):
            continue
        code = _ent_code(a)
        if code not in ISO2AR:
            continue
        level = (a.get("level") or "").lower()
        if level not in ("critical", "warning", "normal"):
            continue
        ts = int(a.get("time") or a.get("from") or 0)
        src = a.get("datasource") or ""
        rows.append((hashlib.sha1(f"{code}|{src}|{ts}|{level}".encode()).hexdigest()[:16], code, ISO2AR[code], src, level, ts,
                     a.get("value"), a.get("historyValue")))
    if rows:
        x("INSERT OR IGNORE INTO net_alerts(id, iso, name, source, level, ts, value, hist) VALUES(?,?,?,?,?,?,?,?)", rows, many=True)
    x("DELETE FROM net_alerts WHERE ts < ?", (t - 14 * 86400,))
    # إنذار مبكر عند انقطاع حرج حديث
    for r_ in q("SELECT iso, name, source, value, hist, ts FROM net_alerts WHERE level='critical' AND ts >= ? ORDER BY ts DESC",
                (t - 2 * 3600,)):
        last = q("SELECT created FROM alerts WHERE kind='net' AND key=? ORDER BY created DESC LIMIT 1", (r_["name"],), one=True)
        if last and t - last["created"] < 6 * 3600:
            continue
        drop = ""
        if r_["value"] is not None and r_["hist"]:
            try:
                drop = f"، انخفاض نحو {max(0, round((1 - float(r_['value']) / float(r_['hist'])) * 100))}%"
            except Exception:
                drop = ""
        msg = f"انقطاع إنترنت حرج في {r_['name']}: هبوط في {NET_SRC_AR.get(r_['source'], r_['source'])}{drop}"
        x("INSERT OR IGNORE INTO alerts(id, kind, key, level, cnt, base, created, msg, detail) VALUES(?,?,?,?,?,?,?,?,?)",
          (hashlib.sha1(f"net|{r_['name']}|{t}".encode()).hexdigest()[:16], "net", r_["name"], 3, 1, 0, t, msg, r_["iso"]))
    NET.update(last=t, error="")
    set_status("رصد انقطاع الإنترنت (IODA)", "official", True, len(rows), "IODA", "")
    return len(rows)


def net_loop():
    time.sleep(30)
    while True:
        try:
            fetch_ioda()
        except Exception as e:
            NET["error"] = str(e)[:150]
            set_status("رصد انقطاع الإنترنت (IODA)", "official", False, 0, "IODA", NET["error"])
        time.sleep(600)


@app.get("/api/net")
def api_net():
    t = now()
    rows = q("SELECT * FROM net_alerts WHERE ts >= ? ORDER BY ts DESC", (t - 48 * 3600,))
    status = {}
    for r in rows:
        st = status.setdefault(r["iso"], {"iso": r["iso"], "name": r["name"], "level": "normal", "last": 0, "n": 0, "sources": set()})
        st["n"] += 1
        if t - r["ts"] <= 3 * 3600 and r["level"] in ("critical", "warning"):
            if r["level"] == "critical" or st["level"] == "normal":
                st["level"] = r["level"]
            st["sources"].add(NET_SRC_AR.get(r["source"], r["source"]))
        st["last"] = max(st["last"], r["ts"])
    for iso in NET_WATCH:
        status.setdefault(iso, {"iso": iso, "name": ISO2AR.get(iso, iso), "level": "normal", "last": 0, "n": 0, "sources": set()})
    order = {"critical": 0, "warning": 1, "normal": 2}
    out = sorted(status.values(), key=lambda s_: (order[s_["level"]], -s_["n"]))
    for s_ in out:
        s_["sources"] = sorted(s_["sources"])
        lat, lon = CENTROIDS.get(s_["name"], (None, None))
        s_.update(lat=lat, lon=lon, link=f"https://ioda.inetintel.cc.gatech.edu/country/{s_['iso']}")
    recent = [dict(r, source_ar=NET_SRC_AR.get(r["source"], r["source"])) for r in rows if r["level"] != "normal"][:150]
    return jsonify(countries=out, recent=recent, last=NET["last"], error=NET["error"])


# ───────────────────────── شعارات المراكز والمصادر ─────────────────────────
_ICON_LOCK = threading.Lock()


def _img_get(url):
    r = requests.get(url, headers={**HEADERS, "Accept": "image/*,*/*"}, timeout=12, allow_redirects=True)
    ct = r.headers.get("Content-Type", "").split(";")[0]
    if r.status_code == 200 and len(r.content) > 120 and (ct.startswith("image/") or url.endswith(".ico")):
        return r.content, ct or "image/x-icon"
    return None, None


def _fetch_icon(key):
    if key.startswith("tg/"):                       # صورة قناة تيليغرام
        ch = key[3:]
        r = requests.get(f"https://t.me/{ch}", headers=HEADERS, timeout=12)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
        return _img_get(html.unescape(m.group(1))) if m else (None, None)
    if key.startswith("bs/"):                       # صورة حساب Bluesky
        r = requests.get("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile", params={"actor": key[3:]},
                         headers=HEADERS, timeout=12)
        av = r.json().get("avatar") if r.status_code == 200 else None
        return _img_get(av) if av else (None, None)
    for url in (f"https://www.google.com/s2/favicons?domain={key}&sz=128",
                f"https://icons.duckduckgo.com/ip3/{key}.ico",
                f"https://{key}/favicon.ico"):
        try:
            data, ct = _img_get(url)
            if data:
                return data, ct
        except Exception:
            continue
    return None, None


@app.get("/icon/<path:key>")
def site_icon(key):
    key = key.lower().strip().strip("/")
    if not key.startswith(("tg/", "bs/")):
        key = key.split("/")[0].replace("www.", "")
    if not re.fullmatch(r"(tg/|bs/)?[a-z0-9_.\-]{2,120}", key):
        return Response(status=404)
    row = q("SELECT * FROM icons WHERE key=?", (key,), one=True)
    if not row or (not row["ok"] and now() - row["fetched"] > 3 * 86400) or (row["ok"] and now() - row["fetched"] > 30 * 86400):
        with _ICON_LOCK:
            try:
                data, ct = _fetch_icon(key)
            except Exception:
                data, ct = None, None
            x("INSERT OR REPLACE INTO icons(key, ctype, data, fetched, ok) VALUES(?,?,?,?,?)",
              (key, ct or "", data, now(), 1 if data else 0))
        row = q("SELECT * FROM icons WHERE key=?", (key,), one=True)
    if not row or not row["ok"]:
        return Response(status=404, headers={"Cache-Control": "max-age=3600"})
    return Response(row["data"], mimetype=row["ctype"] or "image/png", headers={"Cache-Control": "max-age=604800"})


# ───────────────────────── التحديث التلقائي من GitHub ─────────────────────────
UPDATE = {"state": "", "last": 0, "ready": False, "remote_version": "", "error": "", "checking": False}


def update_cfg():
    return {"repo": (kv_get("upd_repo") or DEFAULT_REPO).strip().strip("/"),
            "branch": (kv_get("upd_branch") or "main").strip(), "auto": kv_get("upd_auto", "1") == "1"}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _local(path):
    pth = os.path.join(BASE_DIR, path)
    if os.path.exists(pth):
        with open(pth, "rb") as f:
            return f.read()
    return None


def check_update(apply=True):
    """يقارن ملفات البرنامج بمستودع GitHub، وينزّل ما تغيّر منها كله دفعة واحدة."""
    if UPDATE["checking"]:
        return UPDATE
    UPDATE.update(checking=True, error="")
    try:
        c = update_cfg()
        raw = f"https://raw.githubusercontent.com/{c['repo']}/{c['branch']}/"
        H = {**HEADERS, "Cache-Control": "no-cache"}
        files = list(APP_FILES)
        try:                                  # قائمة الملفات في المستودع (files.json)
            mr = requests.get(raw + "files.json", headers=H, timeout=30)
            if mr.status_code == 200:
                listed = mr.json().get("files", [])
                if isinstance(listed, list) and "rased.py" in listed:
                    files = [f for f in listed if isinstance(f, str) and re.fullmatch(r"[\w\-./]+", f) and ".." not in f]
        except Exception:
            pass
        new = {}
        for f in files:
            r = requests.get(raw + f, headers=H, timeout=90)
            if r.status_code == 404:
                if f == "rased.py":
                    raise ValueError("لم يُعثر على rased.py في المستودع (تأكد من الاسم وأن المستودع عام Public)")
                continue                      # ملف اختياري غير مرفوع بعد
            r.raise_for_status()
            if r.content != _local(f):
                new[f] = r.content
        code = new.get("rased.py") or _local("rased.py") or b""
        m = re.search(rb'^VERSION\s*=\s*"([^"]+)"', code, re.M)
        rv = m.group(1).decode() if m else ""
        UPDATE.update(last=now(), remote_version=rv)
        if not new:
            UPDATE.update(state="البرنامج محدَّث", ready=False)
            return UPDATE
        for f, data in new.items():           # فحص الملفات قبل تطبيق أي شيء
            if f.endswith(".py"):
                try:
                    compile(data.decode("utf-8"), f, "exec")
                except Exception as e:
                    raise ValueError(f"الملف {f} على GitHub فيه خطأ برمجي فلم يُطبَّق التحديث: {str(e)[:120]}")
        if "rased.py" in new and "مركز أبو زبيدة".encode("utf-8") not in new["rased.py"]:
            raise ValueError("الملف على GitHub ليس برنامج المركز، لم يُطبَّق")
        if not apply:
            UPDATE.update(state=f"يوجد تحديث جديد ({len(new)} ملف)", ready=False)
            return UPDATE
        bdir = os.path.join(BASE_DIR, "backup", datetime.now().strftime("%Y%m%d-%H%M"))
        for f, data in new.items():
            dst = os.path.join(BASE_DIR, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            old = _local(f)
            if old is not None:
                os.makedirs(os.path.dirname(os.path.join(bdir, f)), exist_ok=True)
                with open(os.path.join(bdir, f), "wb") as fh:
                    fh.write(old)
            with open(dst + ".new", "wb") as fh:
                fh.write(data)
        for f in new:
            dst = os.path.join(BASE_DIR, f)
            os.replace(dst + ".new", dst)
        UPDATE.update(state=f"نُزِّل تحديث جديد ({len(new)} ملف)، يُطبَّق عند إعادة التشغيل", ready=True)
        log.info("نُزِّل تحديث من GitHub (الإصدار %s): %s", rv or "؟", "، ".join(new))
    except Exception as e:
        UPDATE.update(error=str(e)[:200], last=now())
        log.warning("التحديث: %s", UPDATE["error"])
    finally:
        UPDATE["checking"] = False
    return UPDATE


def update_loop():
    time.sleep(25)
    while True:
        if update_cfg()["auto"]:
            check_update()
        time.sleep(3 * 3600)


def restart_self():
    import subprocess
    env = {k: v for k, v in os.environ.items() if k != "RASED_EXTERNAL"}
    cmd = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.join(BASE_DIR, "rased.py")]
    subprocess.Popen(cmd, cwd=BASE_DIR, env=env)
    threading.Timer(0.8, lambda: os._exit(0)).start()


@app.get("/api/update")
def api_update():
    return jsonify(cfg=update_cfg(), state=UPDATE, version=VERSION, frozen=bool(getattr(sys, "frozen", False)))


@app.post("/api/update")
def api_update_set():
    b = request.get_json(silent=True) or {}
    if b.get("repo"):
        kv_set("upd_repo", re.sub(r"^https?://github\.com/", "", b["repo"].strip()).strip("/"))
    if b.get("branch"):
        kv_set("upd_branch", b["branch"].strip())
    if "auto" in b:
        kv_set("upd_auto", "1" if b["auto"] else "0")
    return jsonify(ok=True)


@app.post("/api/update/check")
def api_update_check():
    return jsonify(state=check_update(apply=True), version=VERSION)


@app.post("/api/update/restart")
def api_update_restart():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify(ok=False), 403
    restart_self()
    return jsonify(ok=True)


@app.get("/api/map")
def api_map():
    hours = min(int(request.args.get("hours") or 24), 24 * 7)
    t0 = now() - hours * 3600
    rows = q("SELECT * FROM items WHERE events != '' AND events IS NOT NULL AND published >= ? "
             "ORDER BY published DESC LIMIT 600", (t0,))
    pts = []
    for r in rows:
        loc = locate(r)
        if not loc:
            continue
        evs = [e for e in r["events"].strip("|").split("|") if e]
        pts.append({"id": r["id"], "lat": round(loc[0], 4), "lon": round(loc[1], 4), "place": loc[2], "exact": loc[3],
                    "events": evs, "color": EVENT_COLORS.get(evs[0], "#EF4444"), "title": r["title_ar"] or r["title"],
                    "source": r["source_ar"], "published": r["published"], "nsrc": r["nsrc"] or 1})
    dens = Counter()
    for r in q("SELECT countries FROM items WHERE published >= ? AND countries != ''", (t0,)):
        dens.update(c for c in r["countries"].strip("|").split("|") if c in CENTROIDS)
    net = []
    for r in q("SELECT iso, name, MAX(CASE level WHEN 'critical' THEN 2 WHEN 'warning' THEN 1 ELSE 0 END) lv, MAX(ts) ts "
               "FROM net_alerts WHERE ts >= ? AND level != 'normal' GROUP BY iso", (now() - 3 * 3600,)):
        if r["name"] in CENTROIDS:
            net.append({"name": r["name"], "lat": CENTROIDS[r["name"]][0], "lon": CENTROIDS[r["name"]][1],
                        "level": "critical" if r["lv"] == 2 else "warning", "ts": r["ts"]})
    return jsonify(net=net, points=pts, density=[{"name": c, "lat": CENTROIDS[c][0], "lon": CENTROIDS[c][1], "count": n}
                                        for c, n in dens.most_common(60)])


# ───────────────────────── الأرشيف ─────────────────────────
def archive_store(row, link, paras, via, reason):
    try:
        x("""INSERT OR IGNORE INTO archive(item_id, link, title, title_ar, source, cat, published, captured, paras, via, reason)
             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (row["id"], link, row["title"], row["title_ar"], row["source_ar"], row["cat"], row["published"], now(),
           json.dumps(paras, ensure_ascii=False), via, reason))
    except Exception as e:
        log.warning("archive: %s", e)


def wayback_save(link):
    """نسخة عامة دائمة في أرشيف الإنترنت (Wayback Machine)."""
    try:
        r = requests.get("https://web.archive.org/save/" + link, headers=HEADERS, timeout=90, allow_redirects=True)
        if r.status_code in (200, 302) and "web.archive.org/web/" in r.url:
            x("UPDATE archive SET wayback=? WHERE link=?", (r.url, link))
    except Exception:
        pass


def archive_item(iid, reason, public=False):
    row = q("SELECT * FROM items WHERE id=?", (iid,), one=True)
    if not row:
        return False
    if row["kind"] in ("tweet", "video"):
        x("""INSERT OR IGNORE INTO archive(item_id, link, title, title_ar, source, cat, published, captured, paras, via, reason)
             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (iid, row["link"], row["title"], row["title_ar"], row["source_ar"], row["cat"], row["published"], now(),
           json.dumps([row["title"]], ensure_ascii=False), "نص المنشور", reason))
    else:
        if not q("SELECT 1 FROM archive WHERE item_id=?", (iid,), one=True):
            get_article(row)
        x("UPDATE archive SET reason=? WHERE item_id=? AND reason='فتح المقال'", (reason, iid))
    if public:
        link = (q("SELECT link FROM items WHERE id=?", (iid,), one=True) or {"link": ""})["link"]
        if link.startswith("http") and not is_gnews(link):
            threading.Thread(target=wayback_save, args=(link,), daemon=True).start()
    return True


def archiver_loop():
    """يؤرشف الأخبار النوعية تلقائياً لحظة رصدها (النص الأصلي فقط)."""
    time.sleep(60)
    while True:
        try:
            rows = q("SELECT id FROM items WHERE events != '' AND events IS NOT NULL AND kind NOT IN ('tweet','video') "
                     "AND published >= ? AND id NOT IN (SELECT item_id FROM archive) ORDER BY published DESC LIMIT 5",
                     (now() - 86400,))
            for r in rows:
                safe(archive_item)(r["id"], "خبر نوعي")
                time.sleep(3)
        except Exception:
            log.exception("archiver")
        time.sleep(120)


@app.post("/api/archive/<iid>")
def api_archive_add(iid):
    ok = archive_item(iid, (request.get_json(silent=True) or {}).get("reason") or "يدوي", public=True)
    return jsonify(ok=ok)


@app.get("/api/archive")
def api_archive():
    a = request.args
    qtext = (a.get("q") or "").strip()
    hours = int(a.get("hours") or 24)
    page, per = max(1, int(a.get("page") or 1)), min(50, int(a.get("per") or 20))
    where, args = ["1=1"], []
    if qtext:                         # البحث يشمل الأرشيف كله
        for w in qtext.split()[:5]:
            where.append("(title LIKE ? OR title_ar LIKE ? OR source LIKE ? OR paras LIKE ? OR paras_ar LIKE ?)")
            args += [f"%{w}%"] * 5
    elif hours:
        where.append("captured >= ?"); args.append(now() - hours * 3600)
    wsql = " AND ".join(where)
    n = q(f"SELECT COUNT(*) c FROM archive WHERE {wsql}", args, one=True)["c"]
    rows = q(f"SELECT item_id, link, title, title_ar, source, cat, published, captured, via, wayback, reason FROM archive "
             f"WHERE {wsql} ORDER BY captured DESC LIMIT ? OFFSET ?", args + [per, (page - 1) * per])
    return jsonify(items=[dict(r) for r in rows], count=n, page=page, pages=max(1, -(-n // per)),
                   total=q("SELECT COUNT(*) c FROM archive", one=True)["c"],
                   day=q("SELECT COUNT(*) c FROM archive WHERE captured >= ?", (now() - 86400,), one=True)["c"])


@app.delete("/api/archive/<iid>")
def api_archive_del(iid):
    x("DELETE FROM archive WHERE item_id=?", (iid,))
    return jsonify(ok=True)


@app.delete("/api/archive")
def api_archive_del_many():
    hours = int(request.args.get("older_hours") or 0)
    if hours:
        x("DELETE FROM archive WHERE captured < ?", (now() - hours * 3600,))
    else:
        x("DELETE FROM archive")
    return jsonify(ok=True)


@app.get("/api/archive/<iid>")
def api_archive_get(iid):
    r = q("SELECT * FROM archive WHERE item_id=?", (iid,), one=True)
    if not r:
        return jsonify(ok=False), 404
    d = dict(r)
    d["paras"] = json.loads(d["paras"] or "[]")
    d["paras_ar"] = json.loads(d["paras_ar"] or "[]")
    return jsonify(ok=True, item=d)


# ───────────────────────── العناوين المعدّلة ─────────────────────────
@app.get("/api/edits")
def api_edits():
    a = request.args
    qtext = (a.get("q") or "").strip()
    hours = int(a.get("hours") or 24)
    page, per = max(1, int(a.get("page") or 1)), 20
    where, args = ["1=1"], []
    if qtext:
        for w in qtext.split()[:5]:
            where.append("(c.old_title LIKE ? OR c.new_title LIKE ? OR i.source_ar LIKE ?)"); args += [f"%{w}%"] * 3
    elif hours:
        where.append("c.changed >= ?"); args.append(now() - hours * 3600)
    wsql = " AND ".join(where)
    n = q(f"SELECT COUNT(*) c FROM title_changes c LEFT JOIN items i ON i.id = c.item_id WHERE {wsql}", args, one=True)["c"]
    rows = q(f"""SELECT c.rowid AS rid, c.*, i.title_ar AS new_ar, i.source_ar, i.cat, i.link FROM title_changes c
                LEFT JOIN items i ON i.id = c.item_id WHERE {wsql} ORDER BY c.changed DESC LIMIT ? OFFSET ?""",
             args + [per, (page - 1) * per])
    return jsonify(items=[dict(r) for r in rows], count=n, page=page, pages=max(1, -(-n // per)))


@app.delete("/api/edits/<int:rid>")
def api_edits_del(rid):
    x("DELETE FROM title_changes WHERE rowid=?", (rid,))
    return jsonify(ok=True)


@app.get("/api/edits/<iid>")
def api_edits_item(iid):
    rows = q("SELECT * FROM title_changes WHERE item_id=? ORDER BY changed", (iid,))
    return jsonify(items=[dict(r) for r in rows])


# ───────────────────────── قوائم العقوبات والتصنيفات الإرهابية ─────────────────────────
OFAC_CSV = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
UN_XML = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
PROGRAM_AR = {
    "SDGT": "إرهابي عالمي مصنّف", "FTO": "منظمة إرهابية أجنبية", "IRGC": "الحرس الثوري الإيراني", "IFSR": "إيران",
    "IRAN": "إيران", "IRAN-EO13902": "إيران", "SYRIA": "سوريا", "SYRIA-EO13894": "سوريا", "CAESAR": "قانون قيصر",
    "HIZBALLAH": "حزب الله", "RUSSIA-EO14024": "روسيا", "UKRAINE-EO13660": "أوكرانيا وروسيا", "YEMEN": "اليمن",
    "LIBYA3": "ليبيا", "SUDAN-EO14098": "السودان", "IRAQ3": "العراق", "LEBANON": "لبنان", "ILLICIT-DRUGS-EO14059": "المخدرات",
    "SDNTK": "تهريب المخدرات", "TCO": "جريمة منظمة عابرة", "GLOMAG": "قانون ماغنيتسكي", "CYBER2": "جرائم إلكترونية",
    "QDi": "قائمة داعش والقاعدة (أفراد)", "QDe": "قائمة داعش والقاعدة (كيانات)", "TAi": "قائمة طالبان", "TAe": "طالبان (كيانات)",
}
TERROR_PROGRAMS = ("SDGT", "FTO", "IRGC", "HIZBALLAH", "QDi", "QDe", "TAi", "TAe")
SANC = {"running": False, "last": 0, "error": "", "counts": {}}


SANC_GROUPS = [
    ("داعش", r"\bisil\b|\bisis\b|islamic state|da'?esh|\bdaesh\b|wilayat|iswap|isis-k|\bis-k\b|khorasan province"),
    ("القاعدة", r"al[- ]?qa'?ida|al[- ]?qaeda|\baqap\b|\baqim\b|\bjnim\b|nusrat al-islam"),
    ("هيئة تحرير الشام والنصرة", r"hay'?at tahrir|tahrir al-sham|\bhts\b|nusrah front|al-nusrah|jabhat al-nusra"),
    ("حراس الدين", r"hurras al-?din|hurras ad-?din"),
    ("حزب الله", r"hizballah|hezbollah|hizbollah"),
    ("الحرس الثوري وفيلق القدس", r"\birgc\b|revolutionary guard|qods force|quds force"),
    ("طالبان وشبكة حقاني", r"taliban|haqqani|\btai\.|\btae\."),
    ("حركة الشباب", r"al[- ]?shabaa?b"),
    ("بوكو حرام", r"boko haram|ansaru"),
    ("الحوثيون (أنصار الله)", r"ansarallah|ansar allah|houthi"),
    ("حماس", r"\bhamas\b|qassam brigades|izz al-din al-qassam"),
    ("الجهاد الإسلامي", r"palestinian islamic jihad|\bpij\b"),
    ("لشكر طيبة وجيش محمد", r"lashkar|jaish-e-mohammed|jaish-e-muhammad|jaish-i-mohammed"),
]
_SG_RES = [(n, re.compile(p_, re.I)) for n, p_ in SANC_GROUPS]


def sanc_groups(name, program, remarks):
    rem = re.sub(r"^\s*Al-Qaida\s*\|", "", remarks or "")       # اسم القائمة الأممية ليس دليلاً على الانتماء
    t = " ".join(filter(None, [name, program, rem]))
    out = [n for n, rx in _SG_RES if rx.search(t)]
    if not out and re.search(r"\bQD[ie]\b", program or ""):
        out.append("قائمة داعش والقاعدة الأممية")
    return ("|" + "|".join(out) + "|") if out else ""


def _sanc_upsert(rows, baseline):
    t = now()
    ex = {r["uid"] for r in q("SELECT uid FROM sanctions")}
    new = [r for r in rows if r[0] not in ex]
    if new:
        x("""INSERT OR IGNORE INTO sanctions(uid, list, name, type, program, remarks, listed, first_seen, is_new, groups)
             VALUES(?,?,?,?,?,?,?,?,?,?)""",
          [r + (t, 0 if baseline else 1, sanc_groups(r[2], r[4], r[5])) for r in new], many=True)
    return len(new)


def fetch_opensanctions(dataset, list_name, baseline):
    """مصدر احتياطي مجاني (OpenSanctions، للاستخدام غير التجاري) إن تعذّر الموقع الرسمي."""
    import csv
    content = http_get_big([f"https://data.opensanctions.org/datasets/latest/{dataset}/targets.simple.csv"], 50000,
                           valid=lambda c: b"schema" in c[:400] and b"name" in c[:400] and b"<html" not in c[:2000].lower())
    text = content.decode("utf-8-sig", errors="replace")
    rows = []
    typ = {"Person": "individual", "Vessel": "vessel", "Airplane": "aircraft"}
    for rec in csv.DictReader(io.StringIO(text)):
        prog = (rec.get("sanctions") or "")[:300]
        remarks = " | ".join(filter(None, [rec.get("countries") and "الدول: " + rec["countries"],
                                           rec.get("aliases") and "أسماء أخرى: " + rec["aliases"][:250]]))
        rows.append(("os:" + rec.get("id", ""), list_name, rec.get("name", ""), typ.get(rec.get("schema", ""), "entity"),
                     prog, remarks[:600], (rec.get("first_seen") or "")[:10]))
    return _sanc_upsert(rows, baseline), len(rows)


def http_get_big(urls, min_size=10000, valid=None):
    """تنزيل ملف كبير بهوية متصفح (curl_cffi إن وُجد)، مع روابط بديلة."""
    last = ""
    for url_ in urls:
        for attempt in range(2):
            try:
                if cffi_requests is not None:
                    r = cffi_requests.get(url_, impersonate="chrome", timeout=180, allow_redirects=True)
                else:
                    r = requests.get(url_, headers={**BROWSER_HEADERS, "Accept": "*/*"}, timeout=180, allow_redirects=True)
                if r.status_code == 200 and len(r.content) >= min_size and (valid is None or valid(r.content)):
                    return r.content
                last = f"رمز {r.status_code}، الحجم {len(r.content)}" + ("، صفحة حماية بدل الملف" if r.status_code == 200 else "")
            except Exception as e:
                last = str(e)[:150]
            time.sleep(3)
    raise ValueError(f"تعذّر التنزيل ({last})")


def fetch_ofac(baseline):
    import csv
    content = http_get_big([OFAC_CSV, "https://www.treasury.gov/ofac/downloads/sdn.csv",
                            "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/sdn.csv"], 100000,
                           valid=lambda c: not c.lstrip()[:20].lower().startswith((b"<!doctype", b"<html")))
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    rows = []
    for rec in csv.reader(io.StringIO(text)):
        if len(rec) < 12 or not rec[0].strip().isdigit():
            continue
        clean_ = lambda v: "" if v.strip() == "-0-" else v.strip()
        rows.append(("ofac:" + rec[0].strip(), "OFAC", clean_(rec[1]), clean_(rec[2]) or "entity",
                     clean_(rec[3]).replace("] [", ", ").strip("[]"), clean_(rec[11])[:600], ""))
    return _sanc_upsert(rows, baseline), len(rows)


def fetch_un(baseline):
    import xml.etree.ElementTree as ET
    content = http_get_big([UN_XML, "https://scsanctions.un.org/resources/xml/en/consolidated.xml?v=1",
                            "https://scsanctions.un.org/consolidated/"], 50000,
                           valid=lambda c: b"<CONSOLIDATED_LIST" in c[:30000] or b"<INDIVIDUALS" in c[:60000])
    root = ET.fromstring(content)
    rows = []
    for tag, typ in (("INDIVIDUAL", "individual"), ("ENTITY", "entity")):
        for e in root.iter(tag):
            g = lambda k: (e.findtext(k) or "").strip()
            ref = g("REFERENCE_NUMBER")
            if not ref:
                continue
            name = " ".join(filter(None, [g("FIRST_NAME"), g("SECOND_NAME"), g("THIRD_NAME"), g("FOURTH_NAME")]))
            nat = ", ".join(v.text for v in e.findall("./NATIONALITY/VALUE") if v.text)
            prog = re.sub(r"[\d.]+$", "", ref.split(".")[0]) if "." in ref else g("UN_LIST_TYPE")
            remarks = " | ".join(filter(None, [g("UN_LIST_TYPE"), nat and "الجنسية: " + nat, g("COMMENTS1")[:400]]))
            rows.append(("un:" + ref, "الأمم المتحدة", name, typ, prog, remarks, g("LISTED_ON")))
    return _sanc_upsert(rows, baseline), len(rows)


def fetch_sanctions():
    if SANC["running"]:
        return
    SANC.update(running=True, error="")
    errs = []
    for key, fn, osds, lname in (("OFAC", fetch_ofac, "us_ofac_sdn", "OFAC"), ("UN", fetch_un, "un_sc_sanctions", "الأمم المتحدة")):
        baseline = not kv_get("sanc_base_" + key)
        try:
            try:
                n_new, total = fn(baseline)
            except Exception as e_off:          # الموقع الرسمي تعذّر: المصدر الاحتياطي
                log.info("قائمة %s الرسمية تعذّرت (%s)، تجربة المصدر الاحتياطي", key, str(e_off)[:80])
                n_new, total = fetch_opensanctions(osds, lname, baseline)
            SANC["counts"][key] = total
            if baseline:
                kv_set("sanc_base_" + key, now())
            set_status(f"قائمة عقوبات {key}", "official", True, total, "رسمي", "")
            if n_new and not baseline:
                log.info("تصنيفات جديدة في %s: %s", key, n_new)
        except Exception as e:
            errs.append(f"{key}: {str(e)[:120]}")
            set_status(f"قائمة عقوبات {key}", "official", False, 0, "رسمي", str(e)[:200])
    for r in q("SELECT uid, name, program, remarks FROM sanctions WHERE groups IS NULL"):   # تصنيف القديم
        x("UPDATE sanctions SET groups=? WHERE uid=?", (sanc_groups(r["name"], r["program"], r["remarks"]), r["uid"]))
    SANC.update(running=False, last=now(), error="؛ ".join(errs))
    if len(errs) < 2:                      # نجحت قائمة واحدة على الأقل: الموعد التالي بعد 6 ساعات
        kv_set("sanc_last", now())
    else:                                  # فشلت القائمتان: إعادة المحاولة بعد 15 دقيقة لا 6 ساعات
        kv_set("sanc_last", now() - 6 * 3600 + 900)


def sanctions_loop():
    time.sleep(40)
    while True:
        try:
            if now() - int(kv_get("sanc_last", 0)) > 6 * 3600:
                fetch_sanctions()
        except Exception:
            log.exception("sanctions")
            SANC["running"] = False
        time.sleep(900)


@app.get("/api/sanctions")
def api_sanctions():
    a = request.args
    mode = a.get("mode", "terror")
    page, per = max(1, int(a.get("page") or 1)), 50
    where, args = ["1=1"], []
    order = "first_seen DESC, name"
    terror_sql = "(" + " OR ".join(["program LIKE ?"] * len(TERROR_PROGRAMS)) + " OR (groups IS NOT NULL AND groups != ''))"
    terror_args = [f"%{p_}%" for p_ in TERROR_PROGRAMS]
    if mode == "terror":
        where.append(terror_sql); args += terror_args
        order = "COALESCE(NULLIF(listed,''), '0000') DESC, name"
        if a.get("group"):
            where.append("groups LIKE ?"); args.append(f"%|{a['group']}|%")
    if mode == "new":
        # الجديد منذ بدء الرصد، ومعه أحدث إدراجات الأمم المتحدة (لها تاريخ إدراج) خلال السنتين الأخيرتين
        where.append("(is_new=1 OR (listed != '' AND listed >= ?))")
        args.append(datetime.fromtimestamp(now() - 730 * 86400).strftime("%Y-%m-%d"))
        order = "is_new DESC, COALESCE(NULLIF(listed,''), '0000') DESC, first_seen DESC"
    if a.get("terror") == "1" and mode != "terror":
        where.append(terror_sql); args += terror_args
    for w in (a.get("q") or "").split()[:5]:
        where.append("(name LIKE ? OR remarks LIKE ? OR program LIKE ? OR groups LIKE ?)"); args += [f"%{w}%"] * 4
    wsql = " AND ".join(where)
    total = q(f"SELECT COUNT(*) c FROM sanctions WHERE {wsql}", args, one=True)["c"]
    rows = q(f"SELECT * FROM sanctions WHERE {wsql} ORDER BY {order} LIMIT ? OFFSET ?", args + [per, (page - 1) * per])
    gcount = Counter()
    for r in q(f"SELECT groups FROM sanctions WHERE {terror_sql}", terror_args):
        gcount.update(g for g in (r["groups"] or "").strip("|").split("|") if g)
    groups = [{"name": n, "count": gcount.get(n, 0)} for n, _ in SANC_GROUPS + [("قائمة داعش والقاعدة الأممية", "")] if gcount.get(n)]
    out = []
    for r in rows:
        d = dict(r)
        d["program_ar"] = "، ".join(PROGRAM_AR.get(p_.strip(), p_.strip()) for p_ in (d["program"] or "").split(",") if p_.strip())
        out.append(d)
    counts = {r["list"]: r["c"] for r in q("SELECT list, COUNT(*) c FROM sanctions GROUP BY list")}
    newc = q("SELECT COUNT(*) c FROM sanctions WHERE is_new=1 AND first_seen >= ?", (now() - 7 * 86400,), one=True)["c"]
    st_rows = {r["name"]: dict(r) for r in q("SELECT * FROM source_status WHERE name LIKE 'قائمة عقوبات %'")}
    lists = [{"key": k, "name": n, "count": counts.get(lname, 0),
              "ok": (st_rows.get(f"قائمة عقوبات {k}") or {}).get("ok"),
              "last_ok": (st_rows.get(f"قائمة عقوبات {k}") or {}).get("last_ok"),
              "error": (st_rows.get(f"قائمة عقوبات {k}") or {}).get("error", "")}
             for k, n, lname in (("OFAC", "قائمة OFAC الأمريكية", "OFAC"), ("UN", "قائمة مجلس الأمن الدولي", "الأمم المتحدة"))]
    return jsonify(items=out, counts=counts, new_week=newc, state=SANC, last=int(kv_get("sanc_last", 0)), lists=lists,
                   curl_cffi=cffi_requests is not None, total=total, page=page, pages=max(1, -(-total // per)),
                   groups=groups, terror_total=q(f"SELECT COUNT(*) c FROM sanctions WHERE {terror_sql}", terror_args, one=True)["c"])


@app.post("/api/sanctions/refresh")
def api_sanctions_refresh():
    kv_set("sanc_last", 0)
    threading.Thread(target=safe(fetch_sanctions), daemon=True).start()
    return jsonify(ok=True)


# ───────────────────────── اسأل المركز ─────────────────────────
ASK_SYSTEM = """أنت محلل في مركز رصد. تجيب عن أسئلة المستخدم اعتماداً على المواد المرصودة المرفقة فقط.
- أجب بالعربية بإيجاز ووضوح، في فقرات قصيرة، وابدأ بالجواب المباشر.
- بعد كل معلومة اذكر رقم المادة التي أخذتها منها بين قوسين مربعين مثل [3] أو [2، 5].
- لا تضف معلومات من خارج المواد. إن لم تكفِ المواد للإجابة فقل ذلك صراحة، واذكر ما هو متوفر فقط.
- إن تعارضت المصادر فاذكر التعارض ومن قال ماذا."""


@app.post("/api/ask")
def api_ask():
    b = request.get_json(silent=True) or {}
    qtext = (b.get("q") or "").strip()[:400]
    days = min(int(b.get("days") or 7), 31)
    if not qtext:
        return jsonify(ok=False, error="اكتب سؤالك"), 400
    refs = [r for r in related_items(qtext, limit=40) if r["published"] >= now() - days * 86400][:25]
    tw = q("SELECT * FROM items WHERE kind='tweet' AND published >= ? AND (title_ar LIKE ? OR title LIKE ?) "
           "ORDER BY published DESC LIMIT 5", (now() - days * 86400, f"%{qtext.split()[0]}%", f"%{qtext.split()[0]}%"))
    refs += [dict(r) for r in tw]
    return jsonify(ok=True, refs=[{k: r[k] for k in ("id", "title_ar", "title", "source_ar", "published", "cat", "link")}
                                  for r in refs])


@app.post("/api/ask/stream")
def api_ask_stream():
    b = request.get_json(silent=True) or {}
    qtext = (b.get("q") or "").strip()[:400]
    ids = b.get("ids") or []
    rows = []
    for i_ in ids[:30]:
        r = q("SELECT * FROM items WHERE id=?", (i_,), one=True)
        if r:
            rows.append(r)
    if not rows:
        return Response("[[ERROR]] لا توجد مواد مرصودة عن هذا السؤال في المدة المحددة. جرّب صياغة أخرى أو مدة أطول.",
                        mimetype="text/plain; charset=utf-8")
    parts = [f"السؤال: {qtext}", "", "المواد المرصودة:"]
    for n_, r in enumerate(rows, 1):
        date = datetime.fromtimestamp(r["published"]).strftime("%Y-%m-%d %H:%M")
        parts.append(f"[{n_}] {r['source_ar']} | {date} | {r['title_ar'] or r['title']}\n{(r['summary_ar'] or r['summary'] or '')[:350]}")
    prompt = "\n".join(parts)
    prov = writer_provider()
    fn = {"free": gen_free, "claude": gen_claude, "gemini": gen_gemini, "ollama": gen_ollama}[prov]

    def gen():
        try:
            yield from fn(prompt, 2500, system=ASK_SYSTEM, min_words=0)
        except Exception as e:
            yield f"\n[[ERROR]] تعذّر الاتصال: {str(e)[:150]}"
    return Response(gen(), mimetype="text/plain; charset=utf-8", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


# ───────────────────────── ملفات القضايا ─────────────────────────
def _snap(r):
    return json.dumps({k: r[k] for k in ("id", "cat", "source_ar", "title", "title_ar", "summary_ar", "link", "published",
                                          "countries", "events")}, ensure_ascii=False)


@app.get("/api/cases")
def api_cases():
    rows = q("""SELECT c.*, (SELECT COUNT(*) FROM case_items ci WHERE ci.case_id=c.id) n FROM cases c ORDER BY updated DESC""")
    return jsonify(items=[dict(r) for r in rows])


@app.post("/api/cases")
def api_cases_new():
    b = request.get_json(silent=True) or {}
    title = " ".join((b.get("title") or "").split())[:120]
    if not title:
        return jsonify(ok=False, error="اكتب عنوان القضية"), 400
    cid = hashlib.sha1((title + str(time.time())).encode("utf-8")).hexdigest()[:10]
    x("INSERT INTO cases(id, title, descr, created, updated) VALUES(?,?,?,?,?)", (cid, title, (b.get("descr") or "")[:2000], now(), now()))
    if b.get("item_id"):
        _case_add(cid, b["item_id"], b.get("note", ""))
    return jsonify(ok=True, id=cid)


def _case_add(cid, iid, note=""):
    r = q("SELECT * FROM items WHERE id=?", (iid,), one=True)
    if not r:
        return False
    x("INSERT OR IGNORE INTO case_items(case_id, item_id, note, added, snap) VALUES(?,?,?,?,?)", (cid, iid, note, now(), _snap(r)))
    x("UPDATE cases SET updated=? WHERE id=?", (now(), cid))
    threading.Thread(target=safe(archive_item), args=(iid, "ملف قضية", True), daemon=True).start()
    return True


@app.get("/api/cases/<cid>")
def api_case(cid):
    c = q("SELECT * FROM cases WHERE id=?", (cid,), one=True)
    if not c:
        return jsonify(ok=False), 404
    items = []
    for r in q("SELECT * FROM case_items WHERE case_id=? ORDER BY added DESC", (cid,)):
        d = json.loads(r["snap"])
        d.update(note=r["note"], added=r["added"], archived=bool(q("SELECT 1 FROM archive WHERE item_id=?", (r["item_id"],), one=True)))
        items.append(d)
    return jsonify(ok=True, case=dict(c), items=items)


@app.post("/api/cases/<cid>")
def api_case_update(cid):
    b = request.get_json(silent=True) or {}
    if "title" in b or "descr" in b:
        c = q("SELECT * FROM cases WHERE id=?", (cid,), one=True)
        x("UPDATE cases SET title=?, descr=?, updated=? WHERE id=?",
          ((b.get("title") or c["title"])[:120], b.get("descr", c["descr"])[:2000], now(), cid))
    if b.get("item_id"):
        _case_add(cid, b["item_id"], b.get("note", ""))
    return jsonify(ok=True)


@app.post("/api/cases/<cid>/note")
def api_case_note(cid):
    b = request.get_json(silent=True) or {}
    x("UPDATE case_items SET note=? WHERE case_id=? AND item_id=?", ((b.get("note") or "")[:3000], cid, b.get("item_id")))
    x("UPDATE cases SET updated=? WHERE id=?", (now(), cid))
    return jsonify(ok=True)


@app.delete("/api/cases/<cid>/<iid>")
def api_case_item_del(cid, iid):
    x("DELETE FROM case_items WHERE case_id=? AND item_id=?", (cid, iid))
    return jsonify(ok=True)


@app.delete("/api/cases/<cid>")
def api_case_del(cid):
    x("DELETE FROM case_items WHERE case_id=?", (cid,))
    x("DELETE FROM cases WHERE id=?", (cid,))
    return jsonify(ok=True)


@app.get("/print/case/<cid>")
def print_case(cid):
    c = q("SELECT * FROM cases WHERE id=?", (cid,), one=True)
    if not c:
        return Response("غير موجود", status=404)
    e = html.escape
    rows = q("SELECT * FROM case_items WHERE case_id=? ORDER BY added", (cid,))
    body = []
    for n_, r in enumerate(rows, 1):
        d = json.loads(r["snap"])
        date = datetime.fromtimestamp(d["published"]).strftime("%Y-%m-%d %H:%M")
        arch = q("SELECT wayback FROM archive WHERE item_id=?", (d["id"],), one=True)
        body.append(f"""<section><div class="n">{n_}</div><h2>{e(d['title_ar'] or d['title'])}</h2>
          <div class="m">{e(d['source_ar'])} — {date}</div>
          {f'<p>{e(d["summary_ar"])}</p>' if d.get('summary_ar') else ''}
          {f'<div class="note"><b>ملاحظة المحلل:</b> {e(r["note"])}</div>' if r['note'] else ''}
          <div class="l">{e(d['link'] or '')}{('<br>نسخة مؤرشفة: ' + e(arch['wayback'])) if arch and arch['wayback'] else ''}</div></section>""")
    page = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>{e(c['title'])}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;700&family=Noto+Kufi+Arabic:wght@700&display=swap" rel="stylesheet">
<style>@page{{size:A4;margin:18mm 16mm}}body{{font:12.5pt/1.9 "Noto Naskh Arabic",Arial,sans-serif;max-width:780px;margin:0 auto;padding:24px;color:#111}}
h1{{font:700 20pt/1.5 "Noto Kufi Arabic",Arial;margin:0}}.brand{{color:#8E6F35;font:700 11pt "Noto Kufi Arabic",Arial;border-bottom:2px solid #8E6F35;padding-bottom:6px;margin-bottom:12px}}
.d{{color:#444;margin:8px 0 18px}}section{{border-top:1px solid #ddd;padding:12px 0;break-inside:avoid;position:relative;padding-right:34px}}
.n{{position:absolute;right:0;top:14px;width:24px;height:24px;border-radius:50%;background:#111;color:#fff;text-align:center;font:700 11pt/24px Arial}}
h2{{font:700 13.5pt/1.6 "Noto Kufi Arabic",Arial;margin:0 0 2px}}.m{{color:#777;font-size:10pt}}p{{margin:6px 0}}
.note{{background:#f6f1e4;border-right:3px solid #8E6F35;padding:6px 10px;margin:6px 0}}.l{{font-size:9pt;color:#666;direction:ltr;text-align:left;word-break:break-all}}
.tools{{position:fixed;top:12px;left:12px}}.tools button{{font:600 14px Tahoma;padding:9px 18px;border:0;border-radius:6px;background:#8E6F35;color:#fff;cursor:pointer}}@media print{{.tools{{display:none}}}}</style></head>
<body><div class="tools"><button onclick="print()">حفظ PDF / طباعة</button></div>
<div class="brand">مركز أبو زبيدة للتتبع والرصد — ملف قضية</div><h1>{e(c['title'])}</h1>
<div class="d">{e(c['descr'] or '')}<br><small>{len(rows)} مادة — آخر تحديث {datetime.fromtimestamp(c['updated']).strftime('%Y-%m-%d %H:%M')}</small></div>
{''.join(body)}<script>addEventListener('load',()=>setTimeout(()=>print(),800))</script></body></html>"""
    return Response(page, mimetype="text/html; charset=utf-8")


# ───────────────────────── تطبيق الجوال (PWA) والوصول من الشبكة المحلية ─────────────────────────


@app.get("/manifest.webmanifest")
def pwa_manifest():
    return jsonify(name="مركز أبو زبيدة للتتبع والرصد", short_name="أبو زبيدة", start_url="/", display="standalone",
                   dir="rtl", lang="ar", background_color="#060B13", theme_color="#060B13",
                   icons=[{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                          {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}])


@app.get("/icon-192.png")
def pwa_icon192():
    return Response(_ui_file("icon-192.png") or b"", mimetype="image/png")


@app.get("/icon-512.png")
def pwa_icon512():
    return Response(_ui_file("icon-512.png") or b"", mimetype="image/png")


@app.get("/sw.js")
def pwa_sw():
    js = """const C='rased-v1';
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/icon-192.png'])));self.skipWaiting()});
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==location.origin)return;
 if(u.pathname==='/'){e.respondWith(fetch(e.request).then(r=>{caches.open(C).then(c=>c.put('/',r.clone()));return r}).catch(()=>caches.match('/')))}});"""
    return Response(js, mimetype="application/javascript", headers={"Service-Worker-Allowed": "/"})


def find_app_browser():
    """متصفح يدعم وضع «نافذة البرنامج» (Edge موجود في كل ويندوز 10 و11، ثم Chrome وBrave)."""
    import shutil
    rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe"]
    for base in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", ""), os.environ.get("LOCALAPPDATA", "")):
        for rel in rels:
            pth = os.path.join(base, rel)
            if base and os.path.exists(pth):
                return pth
    try:                                   # مسارات البرامج المسجلة في ويندوز
        import winreg
        for exe_ in ("msedge.exe", "chrome.exe", "brave.exe"):
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_}") as k:
                        pth = winreg.QueryValue(k, None).strip('"')
                        if pth and os.path.exists(pth):
                            return pth
                except OSError:
                    pass
    except ImportError:
        pass
    for name in ("msedge", "google-chrome", "chrome", "chromium", "chromium-browser", "brave-browser"):
        pth = shutil.which(name)
        if pth:
            return pth
    return None


def open_app_window(url):
    """يفتح المركز في نافذة مستقلة كبرنامج (بلا شريط عنوان ولا تبويبات). إغلاق النافذة يُغلق البرنامج."""
    import subprocess
    exe = find_app_browser()
    if not exe:
        webbrowser.open(url)
        return
    prof = os.path.join(BASE_DIR, "app_window_profile")
    try:
        proc = subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={prof}", "--window-size=1440,920",
                                 "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
                                 "--lang=ar"])
    except Exception as e:
        log.warning("app window failed: %s", e)
        webbrowser.open(url)
        return
    t0 = time.time()

    def watch():
        proc.wait()
        if time.time() - t0 < 6:          # أُغلقت فوراً (نسخة أخرى مفتوحة مثلاً): نبقي البرنامج يعمل
            return
        if kv_get("close_with_window", "1") == "1":
            log.info("أُغلقت نافذة البرنامج، يجري الإيقاف…")
            os._exit(0)
    threading.Thread(target=watch, daemon=True).start()


def hide_console():
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.GetConsoleWindow()
            if h:
                ctypes.windll.user32.ShowWindow(h, 0)
        except Exception:
            pass


def show_console():
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.GetConsoleWindow()
            if h:
                ctypes.windll.user32.ShowWindow(h, 5)
        except Exception:
            pass


def lan_ip():
    import socket
    try:
        s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_.connect(("8.8.8.8", 80))
        ip = s_.getsockname()[0]
        s_.close()
        return ip
    except Exception:
        return ""


@app.before_request
def lan_guard():
    """عند فتح البرنامج من جهاز آخر على الشبكة: يُطلب رمز الدخول (PIN) إن كان مضبوطاً."""
    if request.remote_addr in ("127.0.0.1", "::1"):
        return None
    pin = kv_get("lan_pin") or ""
    if not pin or request.path in ("/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/sw.js", "/pin"):
        return None
    if request.cookies.get("rpin") == hashlib.sha256(pin.encode()).hexdigest():
        return None
    return Response(PIN_PAGE, mimetype="text/html; charset=utf-8", status=401)


PIN_PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>رمز الدخول</title><style>body{background:#060B13;color:#E3ECF5;font:16px Tahoma,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0}
form{display:flex;flex-direction:column;gap:12px;width:min(320px,90vw);text-align:center}input{font-size:22px;padding:12px;border-radius:8px;border:1px solid #24405C;background:#0F1A29;color:#fff;text-align:center;letter-spacing:6px}
button{font-size:16px;padding:12px;border:0;border-radius:8px;background:#2DD4BF;color:#04110F;font-weight:700}</style></head>
<body><form method="post" action="/pin"><b>مركز أبو زبيدة للتتبع والرصد</b><span>أدخل رمز الدخول</span><input name="pin" type="password" inputmode="numeric" autofocus><button>دخول</button></form></body></html>"""


@app.post("/pin")
def pin_login():
    pin = kv_get("lan_pin") or ""
    if pin and request.form.get("pin") == pin:
        resp = redirect("/", code=302)
        resp.set_cookie("rpin", hashlib.sha256(pin.encode()).hexdigest(), max_age=90 * 86400, httponly=True, samesite="Lax")
        return resp
    return Response(PIN_PAGE.replace("أدخل رمز الدخول", "<span style='color:#F43F5E'>الرمز غير صحيح</span>"),
                    mimetype="text/html; charset=utf-8", status=401)


@app.get("/api/settings")
def api_settings():
    return jsonify(app_window=kv_get("app_window", "1") == "1", app_browser=bool(find_app_browser()),
                   close_with_window=kv_get("close_with_window", "1") == "1",
                   lan=kv_get("lan") == "1", pin=bool(kv_get("lan_pin")), ip=lan_ip(), port=PORT,
                   running_lan=RUN_HOST == "0.0.0.0")


@app.post("/api/settings")
def api_settings_set():
    b = request.get_json(silent=True) or {}
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify(ok=False, error="تُغيَّر هذه الإعدادات من الحاسوب نفسه فقط"), 403
    if "app_window" in b:
        kv_set("app_window", "1" if b["app_window"] else "0")
    if "close_with_window" in b:
        kv_set("close_with_window", "1" if b["close_with_window"] else "0")
    if "lan" in b:
        kv_set("lan", "1" if b["lan"] else "0")
    if "pin" in b:
        pin = re.sub(r"\D", "", str(b["pin"]))[:8]
        if b["pin"] and len(pin) < 4:
            return jsonify(ok=False, error="الرمز 4 أرقام على الأقل"), 400
        kv_set("lan_pin", pin)
    return jsonify(ok=True)


@app.get("/api/ticker")
def api_ticker():
    out = {}
    for key, cats in TICKERS.items():
        rows = q(f"SELECT id, title_ar, source_ar, published, cat FROM items "
                 f"WHERE cat IN ({','.join('?' * len(cats))}) AND translated=1 "
                 f"ORDER BY published DESC LIMIT 25", cats)
        out[key] = [dict(r) for r in rows]
    return jsonify(out)


@app.get("/api/sources")
def api_sources():
    src = load_sources()
    links = {}
    for f in src["feeds"]:
        site = f.get("site", "")
        if f.get("query"):
            feed = gnews_url(f"{f['query']} when:3d", f.get("lang", "en"))
        elif f.get("url"):
            feed = f["url"]
        else:
            feed = gnews_url(f"site:{site} when:7d", f.get("lang", "en")) if site else ""
        links[f["name_ar"]] = {"site": ("https://" + site) if site else "", "feed": feed}
    for c in src.get("telegram_channels", []):
        u = c["channel"].lstrip("@")
        links[f"تيليغرام: {c.get('name_ar') or u}"] = {"site": f"https://t.me/{u}", "feed": f"https://t.me/s/{u}"}
    for a_ in src.get("bluesky_accounts", []):
        links[f"Bluesky: {a_.get('name_ar') or a_['handle']}"] = {"site": f"https://bsky.app/profile/{a_['handle']}", "feed": ""}
    for w in get_keywords():
        links[f"كلمة مفتاحية: {w}"] = {"site": "", "feed": gnews_url(f'"{w}" when:2d', "ar")}
    links["مكتبة الكتب"] = {"site": "https://books.google.com", "feed": "https://www.googleapis.com/books/v1/volumes?q=subject:terrorism"}
    items = []
    for r in q("SELECT * FROM source_status ORDER BY ok, cat, name"):
        d = dict(r)
        d.update(links.get(d["name"], {"site": "", "feed": ""}))
        items.append(d)
    return jsonify(items=items)


@app.post("/api/refresh")
def api_refresh():
    if not STATE["running"]:
        WAKE.set()
    return jsonify(ok=True, running=STATE["running"])


@app.post("/api/keywords")
def api_add_keyword():
    word = " ".join(((request.get_json(silent=True) or {}).get("word") or "").split())[:60]
    if not word:
        return jsonify(ok=False, error="اكتب كلمة أولاً"), 400
    x("INSERT OR IGNORE INTO keywords(word, added) VALUES(?, ?)", (word, now()))
    threading.Thread(target=safe(fetch_keyword), args=(word,), daemon=True).start()
    return jsonify(ok=True, keywords=get_keywords())


@app.delete("/api/keywords/<path:word>")
def api_del_keyword(word):
    x("DELETE FROM keywords WHERE word=?", (word,))
    x("DELETE FROM source_status WHERE name=?", (f"كلمة مفتاحية: {word}",))
    return jsonify(ok=True, keywords=get_keywords())


@app.post("/api/telegram")
def api_add_channel():
    body = request.get_json(silent=True) or {}
    raw = (body.get("channel") or "").strip()
    m = re.search(r"(?:t\.me/(?:s/)?)?@?([A-Za-z0-9_]{4,40})/?$", raw)
    if not m:
        return jsonify(ok=False, error="اكتب اسم القناة مثل AJArabic أو رابطها t.me/AJArabic"), 400
    username = m.group(1)
    name_ar = " ".join((body.get("name_ar") or "").split())[:60] or username
    data = load_sources()
    chans = data.setdefault("telegram_channels", [])
    if any(c["channel"].lower() == username.lower() for c in chans):
        return jsonify(ok=False, error="القناة مضافة مسبقاً"), 400
    ch = {"channel": username, "name_ar": name_ar}
    chans.append(ch)
    save_sources(data)
    threading.Thread(target=safe(fetch_telegram), args=(ch,), daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/telegram/refresh")
def api_tg_refresh():
    TG_WAKE.set()
    return jsonify(ok=True)


@app.post("/api/bluesky")
def api_add_bsky():
    b = request.get_json(silent=True) or {}
    raw = (b.get("handle") or "").strip()
    m = re.search(r"(?:bsky\.app/profile/)?@?([A-Za-z0-9.\-]{3,80})/?$", raw)
    if not m or "." not in m.group(1):
        return jsonify(ok=False, error="اكتب الحساب مثل apnews.com أو name.bsky.social"), 400
    handle = m.group(1).lower()
    data = load_sources()
    accs = data.setdefault("bluesky_accounts", [])
    if any(a["handle"].lower() == handle for a in accs):
        return jsonify(ok=False, error="الحساب مضاف مسبقاً"), 400
    acc = {"handle": handle, "name_ar": " ".join((b.get("name_ar") or "").split())[:60] or handle}
    accs.append(acc)
    save_sources(data)
    threading.Thread(target=safe(fetch_bluesky), args=(acc,), daemon=True).start()
    return jsonify(ok=True)


@app.delete("/api/bluesky/<handle>")
def api_del_bsky(handle):
    data = load_sources()
    accs = data.get("bluesky_accounts", [])
    gone = [a for a in accs if a["handle"].lower() == handle.lower()]
    data["bluesky_accounts"] = [a for a in accs if a not in gone]
    save_sources(data)
    for a in gone:
        x("DELETE FROM source_status WHERE name=?", (f"Bluesky: {a.get('name_ar', a['handle'])}",))
        x("DELETE FROM items WHERE source=?", (f"bsky/{a['handle']}",))
    return jsonify(ok=True)


@app.delete("/api/telegram/<username>")
def api_del_channel(username):
    data = load_sources()
    chans = data.get("telegram_channels", [])
    gone = [c for c in chans if c["channel"].lower() == username.lower()]
    data["telegram_channels"] = [c for c in chans if c not in gone]
    save_sources(data)
    for c in gone:
        x("DELETE FROM source_status WHERE name=?", (f"تيليغرام: {c.get('name_ar', c['channel'])}",))
        x("DELETE FROM items WHERE source=?", (f"t.me/{c['channel'].lstrip('@')}",))
    return jsonify(ok=True)


LDJSON_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
OGDESC_RE = re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)', re.I)


def _find_body(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("articleBody"), str):
            return obj["articleBody"]
        for v in obj.values():
            r = _find_body(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_body(v)
            if r:
                return r
    return None


def extract_article(page, url=""):
    """يستخرج فقرات المقال: trafilatura إن وُجد، والبيانات المنظَّمة، ووسوم <p>، ويختار الأغنى."""
    cands = []
    if trafilatura is not None:
        try:
            txt = trafilatura.extract(page, url=url or None, include_comments=False, include_tables=False,
                                      favor_recall=True) or ""
            cands.append([p.strip() for p in txt.split("\n") if len(p.strip()) > 40])
        except Exception:
            pass
    for blob in LDJSON_RE.findall(page):
        try:
            body = _find_body(json.loads(blob.strip()))
        except Exception:
            continue
        if body and len(body) > 300:
            body = html.unescape(body)
            chunks = [c.strip() for c in re.split(r"\n+", body) if len(c.strip()) > 30]
            if len(chunks) <= 1:
                sents = re.split(r"(?<=[.!?؟])\s+", body)
                chunks = [" ".join(sents[i:i + 3]) for i in range(0, len(sents), 3)]
            cands.append(chunks)
            break
    parser = ParaExtractor()
    try:
        parser.feed(page)
        cands.append(parser.paras)
    except Exception:
        pass
    best = max(cands, key=lambda c: sum(map(len, c)), default=[])
    return best[:40]


def enough(paras):
    return sum(map(len, paras)) >= 700 or len(paras) >= 4


def fetch_page(url):
    """جلب صفحة بهوية متصفح حقيقي. curl_cffi (إن ثُبّت) يقلّد بصمة Chrome فيتجاوز حماية كثير من المواقع."""
    if cffi_requests is not None:
        r = cffi_requests.get(url, impersonate="chrome", timeout=25, allow_redirects=True)
        return r.status_code, r.text, str(r.url)
    r = requests.Session().get(url, headers=BROWSER_HEADERS, timeout=25, allow_redirects=True)
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.status_code, r.text, r.url


MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def fetch_via_jina(url):
    """قارئ Jina: يفتح الصفحة في متصفح حقيقي ويعيد نصها (يتعامل مع الجافاسكربت وكثير من الحمايات)."""
    headers = {**HEADERS, "Accept": "text/plain", "X-Timeout": "25"}
    if JINA_KEY:
        headers["Authorization"] = f"Bearer {JINA_KEY}"
    r = requests.get("https://r.jina.ai/" + url, headers=headers, timeout=45)
    if r.status_code != 200:
        return [], ""
    text = r.text
    real = re.search(r"^URL Source:\s*(\S+)", text, re.M)
    if "Markdown Content:" in text:
        text = text.split("Markdown Content:", 1)[1]
    paras = []
    for line in re.split(r"\n\s*\n|\n", text):
        line = line.strip()
        if not line or line.startswith(("#", "|", "---", "===", "* ", "- ", "+ ", ">", "Title:", "URL Source:")):
            continue
        if line.count("](") > 1:          # أسطر قوائم روابط
            continue
        line = MD_LINK.sub(r"\1", line).replace("**", "").replace("__", "").strip()
        if len(line) >= 60 and line not in paras:
            paras.append(line)
    return paras[:40], (real.group(1) if real else "")


def fetch_via_wayback(url):
    r = requests.get("https://archive.org/wayback/available", params={"url": url}, timeout=20)
    snap = ((r.json().get("archived_snapshots") or {}).get("closest") or {}).get("url")
    if not snap:
        return []
    code, page, _ = fetch_page(snap)
    return extract_article(page, url) if code == 200 else []


@app.get("/go/<iid>")
def go(iid):
    """يفتح المقال في موقعه الأصلي مباشرة، دون المرور بـ Google."""
    row = q("SELECT id, link FROM items WHERE id=?", (iid,), one=True)
    if not row:
        return Response("العنصر غير موجود", status=404)
    return redirect(resolve_item(row), code=302)


@app.get("/api/resolve/<iid>")
def api_resolve(iid):
    row = q("SELECT id, link FROM items WHERE id=?", (iid,), one=True)
    if not row:
        return jsonify(ok=False), 404
    return jsonify(ok=True, link=resolve_item(row))


def reset_providers():
    """زر «ترجم»: نمنح كل مزودي الترجمة فرصة جديدة فوراً."""
    for pv in PROV.values():
        pv["off_until"] = 0
        pv["streak"] = 0


def get_article(row, force=False):
    """يجلب نص المقال (أصلي + مترجم). force: يعيد محاولة ترجمة ما لم يُترجم."""
    iid = row["id"]
    link = resolve_item(row)
    ck = hashlib.sha1(("full3:" + link).encode("utf-8")).hexdigest()
    if not force:
        cached = q("SELECT ar FROM tcache WHERE h=?", (ck,), one=True)
        if cached:
            c = json.loads(cached["ar"])
            return {"ok": True, "paragraphs": c["p"], "orig": c["o"], "via": c.get("via", ""), "link": link,
                    "partial": False, "untranslated": 0}
    ok_key = "orig:" + hashlib.sha1(link.encode("utf-8")).hexdigest()
    stored = kv_get(ok_key)
    paras, via, why = [], "", ""
    if stored:
        st = json.loads(stored)
        paras, via = st["o"], st.get("via", "")
    else:
        if not is_gnews(link):                       # 1) الموقع مباشرة
            try:
                code, page, final = fetch_page(link)
                if code == 200:
                    paras = extract_article(page, final)
                    via = "الموقع مباشرة"
                    if not enough(paras):
                        og = OGDESC_RE.search(page)
                        why = "الصفحة تُحمَّل بجافاسكربت أو المقال خلف اشتراك"
                        if og and not paras:
                            paras = [html.unescape(og.group(1))]
                else:
                    why = f"الموقع رفض الطلب (رمز {code})"
            except Exception as e:
                why = "تعذّر الاتصال بالموقع"
                log.info("direct fetch failed %s: %s", link, str(e)[:120])
        if not enough(paras):                         # 2) قارئ Jina
            try:
                jp, real = fetch_via_jina(link)
                if real and is_gnews(link) and not is_gnews(real):
                    x("UPDATE items SET link=? WHERE id=?", (real, iid))
                    link = real
                if sum(map(len, jp)) > sum(map(len, paras)):
                    paras, via = jp, "قارئ Jina"
            except Exception as e:
                log.info("jina failed %s: %s", link, str(e)[:120])
        if not enough(paras) and not is_gnews(link):  # 3) أرشيف الإنترنت
            try:
                wp = fetch_via_wayback(link)
                if sum(map(len, wp)) > sum(map(len, paras)):
                    paras, via = wp, "أرشيف الإنترنت"
            except Exception as e:
                log.info("wayback failed %s: %s", link, str(e)[:120])
        if paras:
            kv_set(ok_key, json.dumps({"o": paras, "via": via}, ensure_ascii=False))
            archive_store(row, link, paras, via, "فتح المقال")
    if not paras:
        return {"ok": False, "link": link, "error": (why or "تعذّر استخراج نص المقال") +
                ". جرّبنا الموقع مباشرة وقارئ Jina وأرشيف الإنترنت دون نتيجة. افتح المقال في موقعه لقراءته."}
    if force:
        reset_providers()
    translated = translate_many(paras)
    out = [t or p for t, p in zip(translated, paras)]
    missing = sum(1 for t in translated if t is None)
    partial = not enough(paras)
    if not missing:
        x("UPDATE archive SET paras_ar=? WHERE item_id=? AND (paras_ar IS NULL OR paras_ar='')",
          (json.dumps(out, ensure_ascii=False), iid))
    if not missing and not partial:
        x("INSERT OR REPLACE INTO tcache(h, ar) VALUES(?, ?)",
          (ck, json.dumps({"p": out, "o": paras, "via": via}, ensure_ascii=False)))
    return {"ok": True, "paragraphs": out, "orig": paras, "link": link, "via": via,
            "partial": partial, "untranslated": missing}


@app.get("/api/article/<iid>")
def api_article(iid):
    row = q("SELECT * FROM items WHERE id=?", (iid,), one=True)
    if not row:
        return jsonify(ok=False, error="العنصر غير موجود"), 404
    return jsonify(get_article(row, force=request.args.get("force") == "1"))


# ───────────────────────── الحفظ بصيغة PDF (مترجم + أصلي في ملف واحد) ─────────────────────────
def export_data(iid):
    row = q("SELECT * FROM items WHERE id=?", (iid,), one=True)
    if not row:
        return None
    if row["translated"] != 1 or (row["summary"] and not row["summary_ar"] and row["lang"] != "ar"):
        translate_rows([row])
        row = q("SELECT * FROM items WHERE id=?", (iid,), one=True)
    art = get_article(row) if row["kind"] != "tweet" else {"ok": False}
    cat = dict((k, n) for k, n, _ in CATEGORIES).get(row["cat"], "")
    return {
        "ref": "REF-" + row["id"][:8].upper(), "cat": cat, "source": row["source_ar"],
        "date": datetime.fromtimestamp(row["published"]).strftime("%Y-%m-%d %H:%M"),
        "link": art.get("link") or row["link"], "kind": row["kind"],
        "title_ar": row["title_ar"] or row["title"], "summary_ar": row["summary_ar"] or "",
        "title": row["title"], "summary": row["summary"] or "",
        "paras_ar": art.get("paragraphs", []) if art.get("ok") else [],
        "paras": art.get("orig", []) if art.get("ok") else [],
        "via": art.get("via", ""), "lang": row["lang"],
    }


@app.get("/print/<iid>")
def export_print(iid):
    """صفحة جاهزة للطباعة تُفتح نافذة الحفظ بصيغة PDF تلقائياً."""
    d = export_data(iid)
    if not d:
        return Response("العنصر غير موجود", status=404)
    e = html.escape

    def paras(lst):
        return "".join(f'<p dir="auto">{e(t)}</p>' for t in lst)
    orig_dir = "rtl" if d["lang"] == "ar" else "ltr"
    orig = ""
    lead_o = f'<p class="lead">{e(d["summary"])}</p>' if d["summary"] else ""
    if d["lang"] != "ar" or d["paras"]:
        orig = (f'<section class="orig" dir="{orig_dir}"><div class="lbl" dir="rtl">النص الأصلي</div>'
                f'<h1>{e(d["title"])}</h1>{lead_o}'
                f'{paras(d["paras"])}</section>')
    missing = "" if d["paras_ar"] or d["kind"] == "tweet" else \
        '<p class="note">تعذّر جلب النص الكامل للمقال؛ حُفظ العنوان والملخص فقط.</p>'
    lead_ar = f'<p class="lead">{e(d["summary_ar"])}</p>' if d["summary_ar"] else ""
    via_line = f'<br>مصدر النص: {e(d["via"])}' if d["via"] else ""
    page = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{e(d['ref'])} - {e(d['title_ar'][:60])}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;700&family=Noto+Kufi+Arabic:wght@700&display=swap" rel="stylesheet">
<style>
@page{{size:A4;margin:18mm 16mm}}
body{{font:13pt/1.9 "Noto Naskh Arabic","Traditional Arabic",Arial,sans-serif;color:#111;margin:0 auto;max-width:780px;padding:24px}}
.bar{{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #8E6F35;padding-bottom:8px;margin-bottom:6px}}
.brand{{font:700 14pt "Noto Kufi Arabic",Arial;color:#8E6F35}}
.meta{{font-size:9.5pt;color:#555;margin-bottom:18px}}
.lbl{{font:700 10pt "Noto Kufi Arabic",Arial;color:#8E6F35;margin:6px 0}}
h1{{font:700 19pt/1.6 "Noto Kufi Arabic","Noto Naskh Arabic",Arial;margin:4px 0 10px}}
.lead{{color:#444}}
p{{margin:0 0 10px;text-align:justify}}
.orig{{break-before:page;margin-top:30px}}
.orig[dir=ltr]{{font-family:Georgia,"Times New Roman",serif;line-height:1.7}}
.orig[dir=ltr] h1{{font-family:Georgia,serif;text-align:left}}
.foot{{border-top:1px solid #ccc;margin-top:24px;padding-top:8px;font-size:9pt;color:#666;word-break:break-all}}
.note{{color:#888;font-size:10pt}}
.tools{{position:fixed;top:12px;left:12px;font-family:Tahoma}}
.tools button{{font:600 14px Tahoma;padding:9px 18px;border:0;border-radius:6px;background:#8E6F35;color:#fff;cursor:pointer}}
@media print{{.tools{{display:none}}body{{padding:0}}}}
</style></head><body>
<div class="tools"><button onclick="print()">حفظ PDF / طباعة</button></div>
<div class="bar"><span class="brand">مركز أبو زبيدة للتتبع والرصد</span><span class="meta" style="margin:0">{e(d['ref'])}</span></div>
<div class="meta">{e(d['cat'])} — {e(d['source'])} — {e(d['date'])}</div>
<section><div class="lbl">النص المترجم إلى العربية</div><h1>{e(d['title_ar'])}</h1>
{lead_ar}{paras(d['paras_ar'])}{missing}</section>
{orig}
<div class="foot">الرابط: {e(d['link'])}{via_line}</div>
<script>addEventListener('load',()=>setTimeout(()=>print(),800))</script>
</body></html>"""
    return Response(page, mimetype="text/html; charset=utf-8")


@app.get("/api/translate-test")
def api_translate_test():
    """يختبر كل مزود ترجمة على جملة قصيرة ويعرض النتيجة."""
    sample = "The ministry announced new security measures on the border today."
    res = []
    tests = [("microsoft", lambda t: p_microsoft([t])[0]), ("google_multi", lambda t: p_google_multi([t])[0])] + \
        [c for c in SINGLE_CHAIN if c[0] != "microsoft"] + ([("claude", lambda t: p_claude([t])[0])] if anthropic_key() else [])
    for name, fn in tests:
        if (name == "deep" and GoogleTranslator is None) or (name == "argos" and argos_tr is None):
            res.append({"name": PROVIDER_NAMES[name], "ok": False,
                        "out": "غير مثبت (اختياري)" + (": pip install argostranslate" if name == "argos" else "")})
            continue
        t0 = time.time()
        try:
            out = fn(sample)
            ok = has_ar(out)
            if ok:
                PROV[name]["off_until"] = 0
                PROV[name]["streak"] = 0
            res.append({"name": PROVIDER_NAMES[name], "ok": ok, "out": (out or "")[:120],
                        "ms": int((time.time() - t0) * 1000)})
        except Exception as e:
            res.append({"name": PROVIDER_NAMES[name], "ok": False, "out": str(e)[:120]})
    return jsonify(results=res, curl_cffi=cffi_requests is not None, trafilatura=trafilatura is not None)


# ───────────────────────── الواجهة ─────────────────────────
# الواجهة في مجلد ui/ بجانب البرنامج: index.html و style.css و app.js



# ───────────────────────── التشغيل ─────────────────────────
if __name__ == "__main__":
    init_db()
    threading.Thread(target=safe(ensure_ui), daemon=True).start()
    cleanup_removed()
    repair_translations()
    load_sources()
    threading.Thread(target=fetch_loop, daemon=True).start()
    threading.Thread(target=telegram_loop, daemon=True).start()
    threading.Thread(target=translator_loop, daemon=True).start()
    threading.Thread(target=resolver_loop, daemon=True).start()
    threading.Thread(target=safe(countries_backfill), daemon=True).start()
    threading.Thread(target=books_loop, daemon=True).start()
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=analysis_loop, daemon=True).start()
    threading.Thread(target=sanctions_loop, daemon=True).start()
    threading.Thread(target=archiver_loop, daemon=True).start()
    threading.Thread(target=net_loop, daemon=True).start()
    threading.Thread(target=update_loop, daemon=True).start()
    RUN_HOST = "0.0.0.0" if kv_get("lan") == "1" else "127.0.0.1"
    if RUN_HOST == "0.0.0.0":
        log.info("الوصول من الشبكة المحلية مفعّل: http://%s:%s", lan_ip(), PORT)
    url = f"http://127.0.0.1:{PORT}"
    log.info("مركز أبو زبيدة للتتبع والرصد يعمل على %s", url)
    import socket as _sk                    # بعد إعادة التشغيل: ننتظر تحرر المنفذ من النسخة السابقة
    for _ in range(40):
        _t = _sk.socket()
        try:
            _t.bind(("127.0.0.1", PORT))
            _t.close()
            break
        except OSError:
            _t.close()
            time.sleep(0.5)
    want_window = True                     # يفتح دائماً كبرنامج مستقل
    webview = None
    if want_window:
        try:
            import webview                 # نافذة برنامج حقيقية (pip install pywebview)
        except Exception:
            webview = None
    if webview is not None:
        # الخادم في الخلفية، والنافذة في الواجهة: إغلاقها يُغلق البرنامج
        threading.Thread(target=lambda: app.run(host=RUN_HOST, port=PORT, debug=False, threaded=True,
                                                use_reloader=False), daemon=True).start()
        import socket
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", PORT), timeout=0.3).close()
                break
            except OSError:
                time.sleep(0.2)
        log.info("الفتح في نافذة البرنامج الخاصة")
        try:
            try:
                webview.create_window("مركز أبو زبيدة للتتبع والرصد", url, width=1440, height=920, min_size=(1000, 650),
                                      text_select=True, background_color="#02060E", maximized=True)
            except TypeError:
                webview.create_window("مركز أبو زبيدة للتتبع والرصد", url, width=1440, height=920, min_size=(1000, 650),
                                      text_select=True, background_color="#02060E")
            hide_console()                 # النافذة السوداء تختفي: يبقى البرنامج وحده كأي برنامج
            try:
                webview.start(private_mode=False, storage_path=os.path.join(BASE_DIR, "app_window_profile"))
            except TypeError:
                webview.start()
            os._exit(0)                    # إغلاق النافذة يُغلق البرنامج
        except Exception as e:
            show_console()
            log.warning("تعذّر فتح نافذة البرنامج (%s)، سيُفتح بطريقة بديلة", e)
            open_app_window(url)
        while True:
            time.sleep(3600)
    else:
        if want_window and not find_app_browser():
            log.info("لم يُعثر على pywebview ولا Edge/Chrome، سيُفتح في المتصفح الافتراضي")
        threading.Timer(1.5, lambda: open_app_window(url)).start()
        app.run(host=RUN_HOST, port=PORT, debug=False, threaded=True)
