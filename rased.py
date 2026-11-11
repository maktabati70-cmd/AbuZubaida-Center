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

VERSION = "2026.11.11.2"

# التشغيل بلا نافذة سوداء (pythonw أو exe بلا وحدة تحكم): نوجّه المخرجات إلى «لا شيء» حتى لا تتعطل الطباعة
if sys.stdout is None or sys.stderr is None:
    _null = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null
SUPPORT_URL = ""                 # رابط الدعم/التبرع (اختياري). إن تُرك فارغاً يظهر زر التواصل مع المطور فقط
DEV_WHATSAPP = "963968744241"    # رقم واتساب المطور لزر «ادعم المشروع»
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
STUDY_DAYS = 31              # الدراسات والتحليلات: شهر كامل
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


def F(name_ar, cat, url, site="", lang="en", query=""):
    d = {"name_ar": name_ar, "cat": cat, "url": url, "site": site, "lang": lang}
    if query:
        d["query"] = query       # مصدر بحث: يجمع الأخبار من أخبار Google بهذه الكلمات
    return d


DEFAULT_FEEDS = [
    # ── الأخبار العالمية
    F("بي بي سي - العالم", "world", "https://feeds.bbci.co.uk/news/world/rss.xml", "bbc.com"),
    F("الجزيرة الإنجليزية", "world", "https://www.aljazeera.com/xml/rss/all.xml", "aljazeera.com"),
    F("الغارديان", "world", "https://www.theguardian.com/world/rss", "theguardian.com"),
    F("نيويورك تايمز", "world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "nytimes.com"),
    F("دويتشه فيله", "world", "https://rss.dw.com/rdf/rss-en-world", "dw.com"),
    F("فرانس 24", "world", "https://www.france24.com/en/rss", "france24.com"),
    F("إن بي آر", "world", "https://feeds.npr.org/1004/rss.xml", "npr.org"),
    F("رويترز", "world", "", "reuters.com"),
    F("أسوشيتد برس", "world", "", "apnews.com"),
    F("ميدل إيست آي", "world", "https://www.middleeasteye.net/rss", "middleeasteye.net"),
    F("بوليتيكو أوروبا", "world", "https://www.politico.eu/feed/", "politico.eu"),
    # ── الأخبار العربية
    F("الجزيرة نت", "arab", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9", "aljazeera.net", "ar"),
    F("بي بي سي عربي", "arab", "https://feeds.bbci.co.uk/arabic/rss.xml", "bbc.com", "ar"),
    F("فرانس 24 عربي", "arab", "https://www.france24.com/ar/rss", "france24.com", "ar"),
    F("دويتشه فيله عربي", "arab", "https://rss.dw.com/rdf/rss-ar-all", "dw.com", "ar"),
    F("العربية", "arab", "https://www.alarabiya.net/feed/rss2/ar.xml", "alarabiya.net", "ar"),
    F("سكاي نيوز عربية", "arab", "", "skynewsarabia.com", "ar"),
    F("الشرق الأوسط", "arab", "https://aawsat.com/feed", "aawsat.com", "ar"),
    F("إندبندنت عربية", "arab", "", "independentarabia.com", "ar"),
    F("العربي الجديد", "arab", "", "alaraby.co.uk", "ar"),
    F("عنب بلدي", "arab", "https://www.enabbaladi.net/feed", "enabbaladi.net", "ar"),
    F("روسيا اليوم عربي", "arab", "https://arabic.rt.com/rss/", "arabic.rt.com", "ar"),
    # ── مراكز الأبحاث الأجنبية
    F("معهد بروكينغز", "think_global", "https://www.brookings.edu/feed/", "brookings.edu"),
    F("مركز الدراسات الاستراتيجية والدولية CSIS", "think_global", "", "csis.org"),
    F("مؤسسة راند", "think_global", "", "rand.org"),
    F("مؤسسة كارنيغي", "think_global", "", "carnegieendowment.org"),
    F("تشاتام هاوس", "think_global", "", "chathamhouse.org"),
    F("مجلس العلاقات الخارجية CFR", "think_global", "", "cfr.org"),
    F("المجلس الأطلسي", "think_global", "https://www.atlanticcouncil.org/feed/", "atlanticcouncil.org"),
    F("مجموعة الأزمات الدولية", "think_global", "", "crisisgroup.org"),
    F("معهد واشنطن", "think_global", "", "washingtoninstitute.org"),
    F("فورين بوليسي", "think_global", "https://foreignpolicy.com/feed/", "foreignpolicy.com"),
    F("فورين أفيرز", "think_global", "https://www.foreignaffairs.com/rss.xml", "foreignaffairs.com"),
    F("معهد الشرق الأوسط MEI", "think_global", "", "mei.edu"),
    F("المجلس الأوروبي للعلاقات الخارجية", "think_global", "https://ecfr.eu/feed/", "ecfr.eu"),
    F("المعهد الدولي للدراسات الاستراتيجية IISS", "think_global", "", "iiss.org"),
    F("مركز ويلسون", "think_global", "", "wilsoncenter.org"),
    F("مركز ستيمسون", "think_global", "https://www.stimson.org/feed/", "stimson.org"),
    # ── مراكز الأبحاث العربية
    F("مركز الجزيرة للدراسات", "think_arab", "", "studies.aljazeera.net", "ar"),
    F("مركز مالكوم كير–كارنيغي", "think_arab", "", "carnegie-mec.org", "ar"),
    F("المركز العربي للأبحاث ودراسة السياسات", "think_arab", "", "dohainstitute.org", "ar"),
    F("مركز حرمون للدراسات المعاصرة", "think_arab", "https://www.harmoon.org/feed/", "harmoon.org", "ar"),
    F("مركز جسور للدراسات", "think_arab", "https://www.jusoor.co/feed/", "jusoor.co", "ar"),
    F("مركز عمران للدراسات الاستراتيجية", "think_arab", "https://www.omrandirasat.org/feed/", "omrandirasat.org", "ar"),
    F("مركز الإمارات للسياسات", "think_arab", "", "epc.ae", "ar"),
    F("مركز الأهرام للدراسات السياسية", "think_arab", "", "acpss.ahram.org.eg", "ar"),
    F("مركز المستقبل للأبحاث", "think_arab", "", "futureuae.com", "ar"),
    F("المعهد الدولي للدراسات الإيرانية رصانة", "think_arab", "", "rasanah-iiis.org", "ar"),
    F("مركز دراسات الوحدة العربية", "think_arab", "", "caus.org.lb", "ar"),
    F("المعهد المصري للدراسات", "think_arab", "https://eipss-eg.org/feed/", "eipss-eg.org", "ar"),
    # ── مكافحة الإرهاب والتطرف
    F("مركز مكافحة الإرهاب - ويست بوينت", "terror", "https://ctc.westpoint.edu/feed/", "ctc.westpoint.edu"),
    F("المركز الدولي لمكافحة الإرهاب ICCT", "terror", "", "icct.nl"),
    F("لونغ وور جورنال", "terror", "https://www.longwarjournal.org/feed", "longwarjournal.org"),
    F("الشبكة العالمية للتطرف والتكنولوجيا GNET", "terror", "https://gnet-research.org/feed/", "gnet-research.org"),
    F("مؤسسة جيمستاون", "terror", "https://jamestown.org/feed/", "jamestown.org"),
    F("مشروع مكافحة التطرف CEP", "terror", "", "counterextremism.com"),
    F("برنامج التطرف - جامعة جورج واشنطن", "terror", "", "extremism.gwu.edu"),
    F("معهد الحوار الاستراتيجي ISD", "terror", "", "isdglobal.org"),
    F("لوفير", "terror", "", "lawfaremedia.org"),
    F("مرصد الأزهر لمكافحة التطرف", "terror", "", "azhar.eg", "ar"),
    F("المركز الأوروبي لدراسات مكافحة الإرهاب", "terror", "https://www.europarabct.com/feed/", "europarabct.com", "ar"),
    # ── الحروب والنزاعات والدفاع
    F("معهد دراسة الحرب ISW", "war", "", "understandingwar.org"),
    F("وور أون ذا روكس", "war", "https://warontherocks.com/feed/", "warontherocks.com"),
    F("ديفنس ون", "war", "https://www.defenseone.com/rss/all/", "defenseone.com"),
    F("بريكينغ ديفنس", "war", "https://breakingdefense.com/feed/", "breakingdefense.com"),
    F("ذا وور زون", "war", "https://www.twz.com/feed", "twz.com"),
    F("ديفنس نيوز", "war", "", "defensenews.com"),
    F("بيلينغكات", "war", "https://www.bellingcat.com/feed/", "bellingcat.com"),
    F("أكليد لبيانات النزاعات", "war", "", "acleddata.com"),
    F("كييف إندبندنت", "war", "https://kyivindependent.com/rss/", "kyivindependent.com"),
    F("سمول وورز جورنال", "war", "", "smallwarsjournal.com"),
    F("جينز", "war", "", "janes.com"),
    F("إيروورز", "war", "", "airwars.org"),
]

DEFAULT_FEEDS += [
    # ── الأخبار الاقتصادية
    F("بي بي سي - اقتصاد", "economy", "https://feeds.bbci.co.uk/news/business/rss.xml", "bbc.com"),
    F("الغارديان - اقتصاد", "economy", "https://www.theguardian.com/business/rss", "theguardian.com"),
    F("سي إن بي سي", "economy", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cnbc.com"),
    F("ماركت ووتش", "economy", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "marketwatch.com"),
    F("الإيكونوميست - مال واقتصاد", "economy", "https://www.economist.com/finance-and-economics/rss.xml", "economist.com"),
    F("فايننشال تايمز", "economy", "", "ft.com"),
    F("بلومبرغ", "economy", "", "bloomberg.com"),
    F("أويل برايس", "economy", "https://oilprice.com/rss/main", "oilprice.com"),
    F("اقتصاد الشرق مع بلومبرغ", "economy", "", "asharqbusiness.com", "ar"),
    F("سي إن بي سي عربية", "economy", "", "cnbcarabia.com", "ar"),
    F("صحيفة الاقتصادية", "economy", "", "aleqt.com", "ar"),
    F("أرقام", "economy", "", "argaam.com", "ar"),
    F("العربي الجديد - اقتصاد", "economy", "", "alaraby.co.uk/economy", "ar"),
]
DEFAULT_FEEDS += [
    # ── إضافات منتقاة: مكافحة الإرهاب والتطرف
    F("المركز الوطني لدراسة الإرهاب START (أمريكا)", "terror", "", "start.umd.edu"),
    F("مركز صوفان (أمريكا)", "terror", "https://thesoufancenter.org/feed/", "thesoufancenter.org"),
    F("المركز الدولي لدراسة التطرف ICSR (بريطانيا)", "terror", "https://icsr.info/feed/", "icsr.info"),
    F("مركز أبحاث التطرف C-REX (النرويج)", "terror", "", "sv.uio.no/c-rex"),
    F("مركز أبحاث وأدلة التهديدات الأمنية CREST (بريطانيا)", "terror", "", "crestresearch.ac.uk"),
    # ── إضافات منتقاة: مراكز أجنبية
    F("مؤسسة الدفاع عن الديمقراطيات FDD (أمريكا)", "think_global", "", "fdd.org"),
    F("مركز بلفر - هارفارد (أمريكا)", "think_global", "", "belfercenter.org"),
    F("المعهد الفرنسي للعلاقات الدولية IFRI (فرنسا)", "think_global", "", "ifri.org"),
    F("مؤسسة الأبحاث الاستراتيجية FRS (فرنسا)", "think_global", "", "frstrategie.org"),
    F("معهد الاتحاد الأوروبي للدراسات الأمنية EUISS", "think_global", "", "iss.europa.eu"),
    F("معهد كلينغينديل (هولندا)", "think_global", "", "clingendael.org"),
    F("مركز الدراسات الأمنية CSS - زيورخ (سويسرا)", "think_global", "", "css.ethz.ch"),
    F("المعهد الملكي إلكانو (إسبانيا)", "think_global", "", "realinstitutoelcano.org"),
    F("المعهد النرويجي للشؤون الدولية NUPI", "think_global", "", "nupi.no"),
    F("المعهد الأسترالي للسياسات الاستراتيجية ASPI", "think_global", "https://www.aspistrategist.org.au/feed/", "aspistrategist.org.au"),
    F("المجلس الروسي للشؤون الدولية RIAC (روسيا)", "think_global", "", "russiancouncil.ru"),
    F("نادي فالداي للحوار (روسيا)", "think_global", "", "valdaiclub.com"),
    # ── إضافات منتقاة: الحروب والأمن
    F("المعهد الملكي للخدمات المتحدة RUSI (بريطانيا)", "war", "", "rusi.org"),
    F("معهد ستوكهولم لأبحاث السلام SIPRI", "war", "", "sipri.org"),
    F("معهد أبحاث السلام في أوسلو PRIO", "war", "", "prio.org"),
    F("مركز التقييمات الاستراتيجية والميزانية CSBA (أمريكا)", "war", "", "csbaonline.org"),
    F("معهد الدراسات الأمنية ISS Africa", "war", "", "issafrica.org"),
    F("المركز الأفريقي للدراسات الاستراتيجية", "war", "https://africacenter.org/feed/", "africacenter.org"),
    F("المركز الأفريقي لحل النزاعات ACCORD", "war", "https://www.accord.org.za/feed/", "accord.org.za"),
    # ── إضافات منتقاة: مراكز عربية وشرق أوسطية
    F("المجلس المصري للشؤون الخارجية (مصر)", "think_arab", "", "ecfa-eg.org", "ar"),
    F("مركز الإمارات للدراسات والبحوث الاستراتيجية (الإمارات)", "think_arab", "", "ecssr.ae", "ar"),
    F("مركز الملك فيصل للبحوث والدراسات الإسلامية (السعودية)", "think_arab", "", "kfcris.com", "ar"),
    F("مركز الخليج للأبحاث (السعودية)", "think_arab", "", "grc.net", "ar"),
    F("مركز البحرين للدراسات الاستراتيجية دراسات (البحرين)", "think_arab", "", "derasat.org.bh", "ar"),
    F("مركز القدس للدراسات السياسية (الأردن)", "think_arab", "", "alqudscenter.org", "ar"),
    F("مركز الرافدين للحوار (العراق)", "think_arab", "", "alrafidaincenter.com", "ar"),
    F("معهد الشرق الأوسط للبحوث MERI (العراق)", "think_arab", "", "meri-k.org"),
]
DEFAULT_FEEDS += [
    # ── الأمن والاستخبارات: منصات تحليل ودراسات
    F("جاست سكيوريتي", "intel", "https://www.justsecurity.org/feed/", "justsecurity.org"),
    F("ذا سايفر بريف", "intel", "", "thecipherbrief.com"),
    F("سباي توك", "intel", "https://www.spytalk.co/feed", "spytalk.co"),
    F("إنتليجنس أونلاين", "intel", "", "intelligenceonline.com"),
    F("غراي داينامكس للتحليل الاستخباراتي", "intel", "https://greydynamics.com/feed/", "greydynamics.com"),
    F("ذا ريكورد (استخبارات التهديدات)", "intel", "https://therecord.media/feed/", "therecord.media"),
    F("سايبر سكوب", "intel", "https://cyberscoop.com/feed/", "cyberscoop.com"),
    F("مشروع الاستخبارات - مركز بلفر", "intel", "", "belfercenter.org/project/intelligence-project"),
    F("مجلة الاستخبارات والأمن القومي", "intel", "", "tandfonline.com/toc/rint20"),
    # ── الأمن والاستخبارات: رصد الأخبار
    F("رصد: أخبار الاستخبارات والتجسس", "intel", "", "", "en",
      query='"intelligence agency" OR espionage OR "spy ring" OR counterintelligence'),
    F("رصد: الاستخبارات بالعربية", "intel", "", "", "ar", query="استخبارات OR تجسس OR المخابرات"),
    F("رصد: الأمن السيبراني والهجمات المدعومة من دول", "intel", "", "", "en",
      query='"state-sponsored" hackers OR cyberattack OR "cyber espionage"'),
    F("رصد: الأمن القومي", "intel", "", "", "en", query='"national security" OR "security services" OR "terror plot"'),
]
def YT(name_ar, cat, channel_id, lang="en"):
    return F(name_ar, cat, f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", "", lang)


DEFAULT_FEEDS += [
    # ── قنوات يوتيوب الإخبارية (روابط RSS مجانية)
    YT("يوتيوب: الجزيرة", "arab", "UCfiwzLy-8yKzIbsmZTzxDgw", "ar"),
    YT("يوتيوب: العربية", "arab", "UCahpxixMCwoANAftn6IxkTg", "ar"),
    YT("يوتيوب: سكاي نيوز عربية", "arab", "UCIJXOvggjKtCagMfxvcCzAA", "ar"),
    YT("يوتيوب: بي بي سي عربي", "arab", "UCelk6aHijZq-GJBBB9YpReA", "ar"),
    YT("يوتيوب: الجزيرة الإنجليزية", "world", "UCNye-wNBqNL5ZzHSJj3l8Bg"),
    YT("يوتيوب: رويترز", "world", "UChqUTb7kYRX8-EiaN3XFrSQ"),
    YT("يوتيوب: دويتشه فيله", "world", "UCknLrEdhRCp1aegoMqRaCZg"),
    YT("يوتيوب: فرانس 24", "world", "UCQfwfsi5VrQ8yKZ-UWmAEFg"),
]
# حسابات Bluesky (بديل X المجاني: واجهته عامة بلا مفتاح). أضف أو احذف من الصفحة مباشرة.
DEFAULT_BSKY = [
    {"handle": "apnews.com", "name_ar": "أسوشيتد برس"},
    {"handle": "reuters.com", "name_ar": "رويترز"},
    {"handle": "nytimes.com", "name_ar": "نيويورك تايمز"},
    {"handle": "washingtonpost.com", "name_ar": "واشنطن بوست"},
    {"handle": "theguardian.com", "name_ar": "الغارديان"},
    {"handle": "economist.com", "name_ar": "الإيكونوميست"},
    {"handle": "bellingcat.com", "name_ar": "بيلينغكات"},
    {"handle": "kyivindependent.com", "name_ar": "كييف إندبندنت"},
]
DEFAULT_FEEDS += [
    # ── البيانات الرسمية: وزارات وقيادات عسكرية ومنظمات دولية (المصدر الأول قبل الصحف)
    F("وزارة الدفاع الأمريكية: بيانات", "official",
      "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=9&Site=945&max=15", "defense.gov"),
    F("القيادة المركزية الأمريكية CENTCOM", "official", "", "centcom.mil"),
    F("وزارة الخارجية الأمريكية: بيانات صحفية", "official", "https://www.state.gov/rss-feed/press-releases/feed/", "state.gov"),
    F("وزارة العدل الأمريكية: قضايا الأمن القومي", "official", "https://www.justice.gov/feeds/opa/justice-news.xml", "justice.gov"),
    F("وزارة الخزانة الأمريكية: العقوبات", "official", "", "home.treasury.gov"),
    F("أخبار الأمم المتحدة: الشرق الأوسط", "official",
      "https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml", "news.un.org"),
    F("مجلس الأمن الدولي: بيانات صحفية", "official", "", "press.un.org"),
    F("حلف الناتو: أخبار", "official", "https://www.nato.int/cps/rss/en/natohq/rssFeed.xsl/rssFeed.xml", "nato.int"),
    F("الخارجية البريطانية", "official",
      "https://www.gov.uk/government/organisations/foreign-commonwealth-development-office.atom", "gov.uk"),
    F("الاتحاد الأوروبي: الخدمة الخارجية", "official", "", "eeas.europa.eu"),
    F("أخبار الأمم المتحدة بالعربية", "official", "https://news.un.org/feed/subscribe/ar/news/all/rss.xml", "news.un.org", "ar"),
    F("وزارة الدفاع التركية", "official", "", "msb.gov.tr", "ar"),
]
DEFAULT_FEEDS += [
    # ── مراكز ومنصات متخصصة في الإرهاب والجماعات الإسلامية
    F("جهادولوجي: أرشيف إصدارات الجماعات (هارون زيلين)", "terror", "https://jihadology.net/feed/", "jihadology.net"),
    F("ميليتانت واير: رصد الجماعات المسلحة", "terror", "https://www.militantwire.com/feed", "militantwire.com"),
    F("كريتيكال ثريتس: مشروع التهديدات الحرجة", "terror", "", "criticalthreats.org"),
    F("مجموعة سايت للاستخبارات SITE", "terror", "", "siteintelgroup.com"),
    F("ميمري: مراقبة التهديد الجهادي JTTM", "terror", "", "memri.org"),
    F("التقنية ضد الإرهاب", "terror", "https://techagainstterrorism.org/feed/", "techagainstterrorism.org"),
    F("فوكس بول: شبكة أبحاث التطرف العنيف", "terror", "https://voxpol.eu/feed/", "voxpol.eu"),
    F("كونسورتيوم أبحاث الإرهاب TRAC", "terror", "", "trackingterrorism.org"),
    F("منتدى الشرق الأوسط: رصد الإسلاموية", "terror", "", "meforum.org"),
    F("عين أوروبية على التطرف", "terror", "", "eeradicalization.com", "ar"),
    F("مركز المسبار للدراسات والبحوث", "terror", "https://www.almesbar.net/feed/", "almesbar.net", "ar"),
    F("حفريات: الجماعات والتيارات الإسلامية", "terror", "", "hafryat.com", "ar"),
    F("تريندز للبحوث والاستشارات", "terror", "", "trendsresearch.org", "ar"),
    F("مرصد الفتاوى التكفيرية - دار الإفتاء المصرية", "terror", "", "dar-alifta.org", "ar"),
    # ── رصد أخبار الجماعات
    F("رصد: أخبار الجماعات الجهادية", "terror", "", "", "ar",
      query='داعش OR "تنظيم الدولة" OR القاعدة OR "هيئة تحرير الشام" OR "حركة الشباب" OR "بوكو حرام"'),
    F("رصد: Jihadist groups news", "terror", "", "", "en",
      query='"Islamic State" OR al-Qaeda OR al-Shabaab OR JNIM OR ISWAP OR "ISIS-K" OR "Hayat Tahrir"'),
    F("رصد: عمليات مكافحة الإرهاب", "terror", "", "", "en",
      query='counterterrorism operation OR "terror cell" OR "jihadist arrested" OR "ISIS cell"'),
]
SOURCES_VERSION = 8

# قنوات تيليغرام العامة (تعمل مجاناً بلا مفتاح). أضف أو احذف من الصفحة مباشرة.
DEFAULT_TG_CHANNELS = [
    {"channel": "arabicpost_me", "name_ar": "عربي بوست"},
    {"channel": "AJArabic", "name_ar": "الجزيرة"},
    {"channel": "alarabiya", "name_ar": "العربية"},
    {"channel": "skynewsarabia", "name_ar": "سكاي نيوز عربية"},
    {"channel": "bbcarabic", "name_ar": "بي بي سي عربي"},
    {"channel": "EnabBaladi", "name_ar": "عنب بلدي"},
    {"channel": "insiderpaper", "name_ar": "إنسايدر بيبر"},
    {"channel": "QudsNen", "name_ar": "شبكة قدس الإخبارية"},
    {"channel": "ClashReport", "name_ar": "كلاش ريبورت"},
    {"channel": "nanafrica", "name_ar": "أخبار شمال أفريقيا"},
    {"channel": "thejerusalempost", "name_ar": "جيروزاليم بوست"},
    {"channel": "Middle_East_Spectator", "name_ar": "مراقب الشرق الأوسط"},
    {"channel": "AJENews", "name_ar": "الجزيرة الإنجليزية"},
    {"channel": "asharqnews", "name_ar": "الشرق للأخبار"},
    {"channel": "AlHadath", "name_ar": "الحدث"},
    {"channel": "rtarabic", "name_ar": "آر تي عربي"},
    {"channel": "france24_ar", "name_ar": "فرانس 24 عربي"},
    {"channel": "Alaraby_Aljadeed", "name_ar": "العربي الجديد"},
    {"channel": "SyriaTV", "name_ar": "تلفزيون سوريا"},
    {"channel": "rudawarabic", "name_ar": "روداو عربية"},
    {"channel": "kurdistan24arabic", "name_ar": "كردستان 24 عربي"},
    {"channel": "BNONews", "name_ar": "بي إن أو نيوز"},
    {"channel": "WarMonitors", "name_ar": "وور مونيتورز"},
    {"channel": "OSINTdefender", "name_ar": "أوسينت ديفندر"},
]

DEFAULT_X_ACCOUNTS = [
    {"handle": "Reuters", "name_ar": "رويترز"},
    {"handle": "AP", "name_ar": "أسوشيتد برس"},
    {"handle": "BBCBreaking", "name_ar": "بي بي سي عاجل"},
    {"handle": "AJEnglish", "name_ar": "الجزيرة الإنجليزية"},
    {"handle": "AJArabic", "name_ar": "الجزيرة"},
    {"handle": "AlArabiya", "name_ar": "العربية"},
    {"handle": "skynewsarabia", "name_ar": "سكاي نيوز عربية"},
    {"handle": "TheStudyofWar", "name_ar": "معهد دراسة الحرب"},
    {"handle": "CTCWestPoint", "name_ar": "مركز مكافحة الإرهاب - ويست بوينت"},
    {"handle": "LongWarJournal", "name_ar": "لونغ وور جورنال"},
    {"handle": "bellingcat", "name_ar": "بيلينغكات"},
    {"handle": "CrisisGroup", "name_ar": "مجموعة الأزمات الدولية"},
    {"handle": "NATO", "name_ar": "حلف الناتو"},
    {"handle": "CENTCOM", "name_ar": "القيادة المركزية الأمريكية"},
    {"handle": "UN", "name_ar": "الأمم المتحدة"},
    {"handle": "KyivIndependent", "name_ar": "كييف إندبندنت"},
]

TOPIC_TAGS = {
    "داعش": ["داعش", "تنظيم الدولة", "isis", "isil", "islamic state"],
    "القاعدة": ["القاعدة", "al-qaeda", "al qaeda", "alqaeda", "aqap", "jnim"],
    "الإرهاب والتطرف": ["terror", "إرهاب", "extremis", "تطرف", "jihad"],
    "سوريا": ["سوريا", "سورية", "السوري", "دمشق", "syria", "damascus"],
    "غزة وفلسطين": ["غزة", "فلسطين", "الضفة", "gaza", "palestin", "west bank"],
    "أوكرانيا وروسيا": ["ukrain", "أوكران", "russia", "روسيا", "الروسي", "kremlin", "الكرملين"],
    "إيران": ["iran", "إيران", "الإيراني", "tehran", "طهران"],
    "اليمن": ["yemen", "houthi", "اليمن", "الحوثي"],
    "العراق": ["iraq", "العراق", "بغداد", "baghdad"],
    "لبنان": ["lebanon", "لبنان", "hezbollah", "حزب الله"],
    "السودان": ["sudan", "السودان", "الدعم السريع"],
    "ليبيا": ["libya", "ليبيا"],
    "تركيا": ["turkey", "türkiye", "turkiye", "تركيا", "أنقرة", "ankara"],
    "الساحل الإفريقي": ["sahel", "الساحل الإفريقي", "mali", "مالي", "niger", "النيجر", "burkina"],
    "الصين وتايوان": ["china", "الصين", "taiwan", "تايوان", "beijing", "بكين"],
    "المسيّرات": ["drone", "مسيّر", "مسيرة", "مسيرات", "uav"],
    "النووي": ["nuclear", "نووي"],
    "الصواريخ": ["missile", "صاروخ", "صواريخ"],
    "الاستخبارات": ["intelligence", "استخبار", "espionage", "تجسس", "spy", "mossad", "الموساد", "cia", "mi6", "fsb", "المخابرات"],
    "الأمن السيبراني": ["cyber", "سيبران", "hacker", "قراصنة", "ransomware", "اختراق"],
    "النفط والطاقة": ["oil price", "crude", "opec", "النفط", "أوبك", "الغاز الطبيعي", "lng"],
    "الفائدة والتضخم": ["interest rate", "inflation", "federal reserve", "الفائدة", "التضخم", "الفيدرالي"],
    "الذهب والعملات": ["gold price", "الذهب", "dollar", "الدولار", "الليرة", "lira", "currency"],
}

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
    CREATE TABLE IF NOT EXISTS tg_sent2(ch TEXT, id TEXT, sent INTEGER, title TEXT, PRIMARY KEY(ch, id));
    CREATE INDEX IF NOT EXISTS ix_tg2_sent ON tg_sent2(sent DESC);
    CREATE TABLE IF NOT EXISTS daily_reports(day TEXT PRIMARY KEY, created INTEGER, html TEXT, tg TEXT, n INTEGER, ai INTEGER);
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
LINGVA = ["https://lingva.ml", "https://lingva.lunar.icu", "https://translate.plausibility.cloud"]
TR_SESSION = requests.Session()
TR_SESSION.headers.update(HEADERS)
PIECE_CHARS = 1200          # أقصى طول للقطعة الواحدة
BATCH_CHARS = 3500          # أقصى مجموع أحرف في الدفعة
BATCH_ITEMS = 40
TRANSLATE_WORKERS = 2
PROVIDER_NAMES = {"microsoft": "Microsoft (مترجم Edge)", "google_multi": "Google (دفعات)", "google": "Google",
                  "lingva": "Lingva", "mymemory": "MyMemory", "deep": "deep-translator",
                  "claude": "Claude", "argos": "Argos (محلي بلا إنترنت)"}
# أقل فاصل زمني بين طلبين لكل مزود (ثوانٍ) — يمنع حظر Google وغيره بسبب كثرة الطلبات
MIN_GAP = {"microsoft": 0.4, "google_multi": 1.2, "google": 0.8, "lingva": 0.8, "mymemory": 1.5, "deep": 1.0}
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
            r.raise_for_status()
            _MS_TOKEN.update(t=r.text.strip(), exp=time.time() + 480)
        return _MS_TOKEN["t"]


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
        try:
            throttle("lingva")
            r = TR_SESSION.get(f"{base}/api/v1/auto/ar/{quote(text, safe='')}", timeout=20)
            _check(r)
            return r.json().get("translation", "")
        except RateLimited:
            raise
        except Exception as e:
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


SINGLE_CHAIN = [("google", p_google), ("microsoft", lambda t: p_microsoft([t])[0]), ("lingva", p_lingva),
                ("deep", p_deep), ("mymemory", p_mymemory), ("argos", p_argos)]


def _fail(name, e):
    if isinstance(e, RateLimited):
        PROV[name]["off_until"] = time.time() + 900      # حظر مؤقت: نريحه ربع ساعة
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
    else:
        loc = "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&{loc}"


def fetch_rss(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return feedparser.parse(r.content).entries or []


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
            entries = fetch_rss(gnews_url(f"{src['query']} when:3d", lang))
            via = "Google News (بحث)"
        except Exception as e:
            err = str(e)[:200]
    elif not entries and src.get("site"):
        try:
            entries = fetch_rss(gnews_url(f"site:{src['site']} when:{'30d' if long_cat else '7d'}", lang))
            via = "Google News"
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
    """جلب أرشيف الشهر الأخير لمراكز الدراسات (مرة يومياً)."""
    name, cat, lang = src["name_ar"], src["cat"], src.get("lang", "en")
    items, url = [], src.get("url", "")
    if url and re.search(r"/feed/?$", url):          # مواقع ووردبريس: صفحات الأرشيف 2 و3 و4
        for pg in (2, 3, 4):
            try:
                entries = fetch_rss(url.rstrip("/") + f"/?paged={pg}")
            except Exception:
                break
            if not entries:
                break
            items += [make_item(e, cat, src.get("site") or name, name, lang) for e in entries]
    have = q("SELECT MIN(published) m FROM items WHERE source_ar=?", (name,), one=True)["m"]
    covered = have and have < now() - 25 * 86400
    if src.get("site") and not covered:
        try:
            entries = fetch_rss(gnews_url(f"site:{src['site']} when:30d", lang))
            items += [make_item(e, cat, src.get("site") or name, name, lang, gnews=True) for e in entries[:100]]
        except Exception:
            pass
    store_items([i for i in items if i])


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
        r.raise_for_status()
        blocks = r.text.split('class="tgme_widget_message_wrap')[1:]
        if not blocks:
            err = "القناة غير موجودة أو ليست عامة أو اسمها مختلف"
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
    do_backfill = now() - int(kv_get("last_backfill", 0)) > 86400
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(safe(fetch_source), s) for s in src["feeds"]]
        if X_BEARER:
            futures.append(ex.submit(safe(fetch_tweets_api), src["x_accounts"]))
        else:
            set_status("X (تويتر)", "tweets", False, 0, "X API",
                       "منصة X أوقفت الوصول المجاني؛ ضع مفتاح X_BEARER_TOKEN لتفعيل التغريدات. "
                       "قنوات تيليغرام تعمل بدونه.")
        futures += [ex.submit(safe(fetch_keyword), w) for w in get_keywords()]
        for f in futures:
            f.result()
        if do_backfill:
            log.info("جلب أرشيف الشهر الأخير لمراكز الدراسات…")
            list(ex.map(safe(backfill_source), [s for s in src["feeds"] if s["cat"] in LONG_CATS]))
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


@app.get("/")
def index():
    page = PAGE.replace("__SUPPORT_URL__", json.dumps(SUPPORT_URL)).replace("__DEV_WA__", json.dumps(DEV_WHATSAPP))
    return Response(page, mimetype="text/html; charset=utf-8")


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
    if cat and cat != "all":
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
              "csbaonline.org acleddata.com justsecurity.org thecipherbrief.com spytalk.co therecord.media "
              "cyberscoop.com belfercenter.org/project/intelligence-project jihadology.net militantwire.com "
              "criticalthreats.org siteintelgroup.com memri.org trackingterrorism.org meforum.org",
    "أوروبا": "chathamhouse.org crisisgroup.org ecfr.eu iiss.org icct.nl gnet-research.org isdglobal.org "
              "bellingcat.com janes.com airwars.org icsr.info sv.uio.no/c-rex crestresearch.ac.uk ifri.org "
              "frstrategie.org iss.europa.eu clingendael.org css.ethz.ch realinstitutoelcano.org nupi.no rusi.org "
              "sipri.org prio.org kyivindependent.com europarabct.com intelligenceonline.com greydynamics.com "
              "tandfonline.com/toc/rint20 techagainstterrorism.org voxpol.eu eeradicalization.com",
    "أفريقيا": "issafrica.org africacenter.org accord.org.za",
    "آسيا وأستراليا": "aspistrategist.org.au",
    "روسيا": "russiancouncil.ru valdaiclub.com",
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
             args + [now() - 31 * 86400])
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
BOT = {"last_sent": 0, "next_due": 0, "last_error": "", "last_instant": 0, "bot_name": "", "running": False,
       "next": {}, "errors": {}, "cmd_error": "", "cmd_last": 0, "requests": []}
BOT_LOCK = threading.Lock()
BOT_CHATS = {}                    # المحادثات التي راسلت البوت (للاكتشاف التلقائي)
CH_DEFAULTS = {"name": "قناة", "chat": "", "on": True, "cats": BOT_DEFAULT_CATS, "interval": 60, "max_day": 0,
               "hours_from": 0, "hours_to": 24, "inc": [], "exc": [], "scope": "title", "fresh_h": 168,
               "preview": True, "photo": False}


def _ch_norm(ch):
    for k, v in CH_DEFAULTS.items():
        if k not in ch:
            ch[k] = list(v) if isinstance(v, list) else v
    ch["id"] = str(ch.get("id") or hashlib.sha1(f"{time.time()}{ch.get('chat')}".encode()).hexdigest()[:8])
    ch["cats"] = [k for k in ch["cats"] if k in BOT_ALLOWED_CATS] or list(BOT_DEFAULT_CATS)
    ch["prio_qual"] = False
    return ch


def bot_cfg():
    try:
        c = json.loads(kv_get("bot_cfg") or "{}")
    except Exception:
        c = {}
    c.setdefault("token", ""); c.setdefault("enabled", False)
    c.setdefault("cmd_on", False); c.setdefault("cmd_mode", "allow"); c.setdefault("cmd_users", [])
    if not c.get("v2"):          # سياسة جديدة: لا أخبار نوعية ولا إنذارات على تيليغرام
        c["cats"] = BOT_DEFAULT_CATS
        c["v2"] = True
    if not isinstance(c.get("channels"), list) or not c["channels"]:
        # الترحيل من الإعداد القديم (قناة واحدة) إلى قنوات متعددة
        main = {"id": "main", "name": "القناة الرئيسية"}
        for k in CH_DEFAULTS:
            if k in c and k not in ("name", "on"):
                main[k] = c[k]
        c["channels"] = [main]
        try:
            x("INSERT OR IGNORE INTO tg_sent2(ch, id, sent, title) SELECT 'main', id, sent, title FROM tg_sent")
        except Exception:
            pass
    c["channels"] = [_ch_norm(ch) for ch in c["channels"]]
    c["chat"] = next((ch["chat"] for ch in c["channels"] if ch["chat"]), "")
    c["instant_qual"] = c["prio_qual"] = c["send_alerts"] = False
    return c


def bot_save(c):
    c = {k: v for k, v in c.items() if k not in ("chat", "instant_qual", "prio_qual", "send_alerts")}
    kv_set("bot_cfg", json.dumps(c, ensure_ascii=False))


def bot_channel(cfg, ch_id):
    return next((ch for ch in cfg["channels"] if ch["id"] == ch_id), None)


def tg_api(token, method, _files=None, _timeout=25, **params):
    for _ in range(3):
        if _files:
            data = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, bool)) else v) for k, v in params.items()}
            r = requests.post(f"https://api.telegram.org/bot{token}/{method}", data=data, files=_files, timeout=_timeout + 30)
        else:
            r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=_timeout)
        d = r.json()
        if d.get("ok"):
            return d["result"]
        if r.status_code == 429:
            time.sleep(int((d.get("parameters") or {}).get("retry_after", 5)) + 1)
            continue
        raise ValueError(d.get("description") or f"رمز {r.status_code}")
    raise ValueError("تيليغرام يطلب الانتظار (حد الرسائل)")


def tg_send_long(token, chat, text, **kw):
    """يقسم النص الطويل على عدة رسائل (حد تيليغرام 4096 حرفاً) عند حدود الأسطر."""
    parts, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > 3900 and cur:
            parts.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        parts.append(cur)
    for p_ in parts:
        tg_api(token, "sendMessage", chat_id=chat, text=p_, parse_mode="HTML",
               link_preview_options={"is_disabled": True}, **kw)


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


def bot_message(row, summary, link, limit=4000):
    e = html.escape
    cat = dict((k, n) for k, n, _ in CATEGORIES).get(row["cat"], "")
    evs = [x for x in (row["events"] or "").strip("|").split("|") if x]
    ctry = [x for x in (row["countries"] or "").strip("|").split("|") if x][:4]
    when = datetime.fromtimestamp(row["published"]).strftime("%Y-%m-%d %H:%M")

    def build(summ):
        lines = []
        if evs:
            lines.append("🔴 <b>خبر نوعي: " + e("، ".join(evs)) + "</b>")
        lines.append(f"<b>{e(row['title_ar'] or row['title'])}</b>")
        if summ:
            lines += ["", e(summ)]
        lines += ["", f"🏛 {e(row['source_ar'])}  |  🗂 {e(cat)}"]
        if ctry:
            lines.append("📍 " + e("، ".join(ctry)))
        lines.append(f"🕒 {when}")
        if link:
            lines += ["", f'🔗 <a href="{e(link, quote=True)}">قراءة المقال في موقعه</a>']
        lines += ["", "<i>مركز أبو زبيدة للتتبع والرصد</i>"]
        return "\n".join(lines)

    txt = build(summary)
    s_ = summary or ""
    while len(txt) > limit and s_:              # تقصير الملخص حتى يتسع (مهم لتعليق الصورة: 1024 حرفاً)
        s_ = s_[:max(0, len(s_) - max(60, len(txt) - limit))].rstrip()
        k = max(s_.rfind("."), s_.rfind("؟"), s_.rfind("،"))
        s_ = (s_[:k + 1] if k > 80 else s_) + "…" if s_ else ""
        txt = build(s_ if len(s_) > 3 else "")
    return txt[:limit]


# ── صورة المقال ──
_IMG_CACHE = {}


def item_image(row, link):
    """يستخرج صورة المقال (og:image) من صفحته، ويخزّنها في الذاكرة."""
    iid = row["id"]
    if iid in _IMG_CACHE:
        return _IMG_CACHE[iid]
    img = ""
    if link and link.startswith("http"):
        try:
            if cffi_requests is not None:
                r = cffi_requests.get(link, impersonate="chrome", timeout=15)
            else:
                r = requests.get(link, headers=BROWSER_HEADERS, timeout=15)
            t = r.text[:400000]
            for pat in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)',
                        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)'):
                m = re.search(pat, t, re.I)
                if m:
                    from urllib.parse import urljoin
                    img = urljoin(link, html.unescape(m.group(1)).strip())
                    break
        except Exception:
            img = ""
    if img and re.search(r"(logo|favicon|placeholder|default)[^/]*\.(png|svg|ico)", img, re.I):
        img = ""
    if len(_IMG_CACHE) > 500:
        _IMG_CACHE.clear()
    _IMG_CACHE[iid] = img
    return img


def _norm_bot(t):
    t = norm_ar(t or "").lower().replace("ة", "ه")
    return re.sub(r"\s+", " ", t)


_bot_norm = _norm_bot


def _bot_terms(lst):
    """كل سطر شرط: الكلمات المفصولة بـ + يجب أن تجتمع كلها (مثل: سوريا + انتخابات)."""
    out = []
    for line in lst or []:
        parts = [_norm_bot(x).strip() for x in str(line).split("+")]
        # سوريا/سورية، تركيا/تركية، روسيا/روسية: تُطابق كلها
        parts = [re.sub(r"(?<=\w{2})ي[اه](?=\s|$)", "ي", x) for x in parts if x]
        if parts:
            out.append(parts)
    return out


def bot_match(row, cfg):
    inc, exc = _bot_terms(cfg.get("inc")), _bot_terms(cfg.get("exc"))
    if not inc and not exc:
        return True
    txt = " ".join(filter(None, [row["title_ar"], row["title"]]))
    if cfg.get("scope") == "all":
        txt += " " + " ".join(filter(None, [row["summary_ar"], row["summary"], row["source_ar"]]))
    txt = _norm_bot(txt)
    if any(all(w in txt for w in g) for g in exc):
        return False
    return not inc or any(all(w in txt for w in g) for g in inc)


def _bot_candidates(ch, limit=400, unsent=True):
    cats = [c for c in ch["cats"] if c in dict((k, 1) for k, _, _ in CATEGORIES)] or BOT_DEFAULT_CATS
    ph = ",".join("?" * len(cats))
    where = [f"cat IN ({ph})", "translated=1", "kind NOT IN ('tweet', 'video')", "published >= ?",
             "(events = '' OR events IS NULL)"]
    args = cats + [now() - max(1, int(ch.get("fresh_h") or 168)) * 3600]
    if unsent:
        where.append("id NOT IN (SELECT id FROM tg_sent2 WHERE ch=?)")
        args.append(ch["id"])
    return q(f"SELECT * FROM items WHERE {' AND '.join(where)} ORDER BY published DESC LIMIT {int(limit)}", args)


def bot_pick(ch):
    for row in _bot_candidates(ch):
        if bot_match(row, ch):
            return row
    return None


def _day0():
    return int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def bot_sent_today(ch_id=None):
    if ch_id:
        return q("SELECT COUNT(*) c FROM tg_sent2 WHERE ch=? AND sent >= ?", (ch_id, _day0()), one=True)["c"]
    return q("SELECT COUNT(*) c FROM tg_sent2 WHERE sent >= ?", (_day0(),), one=True)["c"]


def bot_in_hours(ch):
    a, b = int(ch.get("hours_from") or 0) % 24, int(ch.get("hours_to") if ch.get("hours_to") is not None else 24)
    b = 24 if b in (0, 24) and a == 0 else b % 24
    if a == 0 and b == 24:
        return True
    h = datetime.now().hour
    return a <= h < b if a < b else (h >= a or h < b)


def bot_hold_reason(ch):
    if not bot_in_hours(ch):
        return f"خارج ساعات النشر ({int(ch['hours_from']):02d}:00 – {int(ch['hours_to']) % 24:02d}:00)"
    if int(ch.get("max_day") or 0) and bot_sent_today(ch["id"]) >= int(ch["max_day"]):
        return f"بلغ الحد اليومي ({int(ch['max_day'])} رسالة)"
    return ""


def bot_send(row, cfg, ch, mark=True):
    link = resolve_item(row)
    row = q("SELECT * FROM items WHERE id=?", (row["id"],), one=True) or row
    summ = bot_summary(row)
    markup = {"inline_keyboard": [[{"text": "📖 اقرأ المقال", "url": link}]]} if link.startswith("http") else None
    sent = False
    if ch.get("photo"):
        img = item_image(row, link)
        if img:
            cap = bot_message(row, summ, link, limit=1024)
            extra = {"reply_markup": markup} if markup else {}
            try:                                     # أولاً: رابط الصورة مباشرة
                tg_api(cfg["token"], "sendPhoto", chat_id=ch["chat"], photo=img, caption=cap, parse_mode="HTML", **extra)
                sent = True
            except Exception:
                try:                                 # ثانياً: تنزيل الصورة ورفعها (مواقع تمنع تيليغرام من جلبها)
                    data, ct = _img_get(img)
                    if data and len(data) < 9_000_000 and "svg" not in (ct or ""):
                        tg_api(cfg["token"], "sendPhoto", _files={"photo": ("image.jpg", data, ct or "image/jpeg")},
                               chat_id=ch["chat"], caption=cap, parse_mode="HTML", **extra)
                        sent = True
                except Exception as e:
                    log.info("telegram photo failed: %s", e)
    if not sent:
        params = {"chat_id": ch["chat"], "text": bot_message(row, summ, link), "parse_mode": "HTML",
                  "link_preview_options": {"is_disabled": not ch["preview"], "url": link} if link else {"is_disabled": True}}
        if markup:
            params["reply_markup"] = markup
        tg_api(cfg["token"], "sendMessage", **params)
    if mark:
        x("INSERT OR REPLACE INTO tg_sent2(ch, id, sent, title) VALUES(?, ?, ?, ?)",
          (ch["id"], row["id"], now(), row["title_ar"] or row["title"]))
    BOT.update(last_sent=now(), last_error="")
    BOT["errors"].pop(ch["id"], None)


def bot_tick(force=False, ch_id=None):
    cfg = bot_cfg()
    if not cfg["token"] or (not cfg["enabled"] and not force):
        return False
    sent = False
    with BOT_LOCK:
        for ch in cfg["channels"]:
            if not ch["chat"]:
                continue
            if force:
                if ch_id and ch["id"] != ch_id:
                    continue
            else:
                if not ch["on"] or now() < BOT["next"].get(ch["id"], 0):
                    continue
                BOT["next"][ch["id"]] = now() + int(ch["interval"])
                if bot_hold_reason(ch):
                    continue
            try:
                row = bot_pick(ch)
                if row:
                    bot_send(row, cfg, ch)
                    sent = True
            except Exception as e:
                BOT["errors"][ch["id"]] = str(e)[:200]
                BOT["last_error"] = f"{ch['name']}: {str(e)[:180]}"
                log.warning("telegram bot [%s]: %s", ch["name"], e)
                if force:
                    raise
            if force:
                break
    return sent


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


# ── أوامر البوت: يسألك البوت وأنت بعيد عن الكمبيوتر ──
def _ago_ar(ts):
    d = max(0, now() - int(ts or 0))
    if d < 3600:
        return f"قبل {max(1, d // 60)} دقيقة"
    if d < 86400:
        return f"قبل {d // 3600} ساعة"
    return f"قبل {d // 86400} يوم"


def _tg_list(rows, limit=8):
    e = html.escape
    out = []
    for r in rows[:limit]:
        t = e((r["title_ar"] or r["title"] or "")[:180])
        link = r["link"] or ""
        t = f'<a href="{e(link, quote=True)}">{t}</a>' if link.startswith("http") else t
        out.append(f"• {t}\n   <i>{e(r['source_ar'] or '')} · {_ago_ar(r['published'])}</i>")
    return "\n".join(out)


def bot_search_rows(query, days=7, limit=8):
    words = [w for w in _norm_bot(query).split() if len(w) >= 2]
    words = [re.sub(r"(?<=\w{2})ي[اه]$", "ي", w) for w in words]
    if not words:
        return []
    out = []
    for r in q("SELECT * FROM items WHERE translated=1 AND published >= ? ORDER BY published DESC LIMIT 6000",
               (now() - days * 86400,)):
        txt = _norm_bot(" ".join(filter(None, [r["title_ar"], r["title"], r["summary_ar"]])))
        if all(w in txt for w in words):
            out.append(r)
            if len(out) >= limit:
                break
    return out


def find_country(name):
    n = _norm_bot(name).strip()
    if not n:
        return None
    for c in COUNTRY_INFO:
        if _norm_bot(c) == n:
            return c
    for c in COUNTRY_INFO:
        cn = _norm_bot(c)
        if n in cn or cn in n:
            return c
    return None


BOT_HELP = ("🤖 <b>أوامر مركز أبو زبيدة</b>\n\n"
            "/ابحث <i>كلمة</i> — آخر الأخبار عن موضوع (مثل: /ابحث داعش البادية)\n"
            "/دولة <i>اسم</i> — آخر أخبار دولة (مثل: /دولة العراق)\n"
            "/ملخص — الملخص اليومي\n"
            "/آخر — أحدث الأخبار\n"
            "/نوعي — الأخبار النوعية خلال 24 ساعة\n"
            "/انذارات — آخر الإنذارات المبكرة\n\n"
            "تعمل الأوامر بالإنجليزية أيضاً: /search /country /summary /latest /qual /alerts")


def bot_cmd_allowed(cfg, msg):
    if cfg.get("cmd_mode") == "all":
        return True
    chat = msg.get("chat") or {}
    if any(str(chat.get("id")) == str(ch["chat"]) or (chat.get("username") and ("@" + chat["username"]).lower() == str(ch["chat"]).lower())
           for ch in cfg["channels"]):
        return True                  # قنواتك أنت
    u = msg.get("from") or {}
    allowed = {str(a).strip().lower().lstrip("@") for a in cfg.get("cmd_users") or [] if str(a).strip()}
    return str(u.get("id", "")) in allowed or (u.get("username") or "").lower() in allowed


def bot_handle_update(cfg, u):
    msg = u.get("message") or u.get("channel_post") or {}
    chat = msg.get("chat") or (u.get("my_chat_member") or {}).get("chat")
    if chat:
        BOT_CHATS[chat["id"]] = {"id": chat["id"], "type": chat.get("type", ""),
                                 "name": chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])) or chat.get("username", "")}
    text = (msg.get("text") or "").strip()
    if not text.startswith("/") or not chat:
        return
    head, _, arg = text.partition(" ")
    cmd = head[1:].split("@")[0].lower().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")
    arg = arg.strip()
    token = cfg["token"]

    def reply(t):
        tg_send_long(token, chat["id"], t)

    if not bot_cmd_allowed(cfg, msg):
        u = msg.get("from") or {}
        if u:
            rq = {"id": u.get("id"), "name": " ".join(filter(None, [u.get("first_name"), u.get("last_name")])),
                  "username": u.get("username", ""), "t": now()}
            BOT["requests"] = [r for r in BOT["requests"] if r["id"] != rq["id"]][-9:] + [rq]
            reply(f"⛔ غير مسموح لك باستخدام أوامر المركز.\nمعرّفك: <code>{u.get('id')}</code>\nاطلب من صاحب المركز إضافتك.")
        return
    BOT["cmd_last"] = now()
    if cmd in ("start", "help", "مساعده", "اوامر", "الاوامر"):
        return reply(BOT_HELP)
    if cmd in ("search", "s", "ابحث", "بحث"):
        if not arg:
            return reply("اكتب ما تبحث عنه بعد الأمر، مثل: /ابحث هيئة تحرير الشام")
        rows = bot_search_rows(arg)
        return reply(f"🔎 <b>نتائج: {html.escape(arg)}</b> (آخر 7 أيام)\n\n" + (_tg_list(rows) or "لا توجد نتائج."))
    if cmd in ("country", "دوله", "دولة", "بلد"):
        c = find_country(arg)
        if not c:
            return reply("لم أتعرف على الدولة. مثال: /دولة سوريا")
        rows = q("SELECT * FROM items WHERE countries LIKE ? AND translated=1 ORDER BY published DESC LIMIT 8", (f"%|{c}|%",))
        n24 = q("SELECT COUNT(*) c FROM items WHERE countries LIKE ? AND published >= ?", (f"%|{c}|%", now() - 86400), one=True)["c"]
        n7 = q("SELECT COUNT(*) c FROM items WHERE countries LIKE ? AND published >= ?", (f"%|{c}|%", now() - 7 * 86400), one=True)["c"]
        return reply(f"📍 <b>{html.escape(c)}</b>\nخلال 24 ساعة: {n24} مادة · خلال أسبوع: {n7}\n\n" + (_tg_list(rows) or "لا أخبار."))
    if cmd in ("summary", "daily", "ملخص", "تقرير"):
        rep = daily_get(datetime.now().strftime("%Y-%m-%d")) or daily_build(save=False)
        return reply(rep["tg"])
    if cmd in ("latest", "news", "اخر", "جديد", "الاخبار"):
        rows = q("SELECT * FROM items WHERE translated=1 AND kind NOT IN ('tweet','video') ORDER BY published DESC LIMIT 8")
        return reply("🆕 <b>أحدث الأخبار</b>\n\n" + (_tg_list(rows) or "لا أخبار."))
    if cmd in ("qual", "نوعي", "عاجل"):
        rows = q("SELECT * FROM items WHERE events != '' AND events IS NOT NULL AND published >= ? ORDER BY published DESC LIMIT 10",
                 (now() - 86400,))
        return reply("🔴 <b>الأخبار النوعية (24 ساعة)</b>\n\n" + (_tg_list(rows, 10) or "لا أحداث نوعية."))
    if cmd in ("alerts", "انذارات", "انذار"):
        rows = q("SELECT * FROM alerts ORDER BY created DESC LIMIT 8")
        t = "\n".join(f"{'🚨' if r['level'] >= 3 else '⚠️'} {html.escape(r['msg'])}\n   <i>{_ago_ar(r['created'])}</i>" for r in rows)
        return reply("🔔 <b>آخر الإنذارات</b>\n\n" + (t or "لا إنذارات."))
    return reply("أمر غير معروف.\n\n" + BOT_HELP)


def bot_cmd_loop():
    time.sleep(15)
    registered = ""
    while True:
        cfg = bot_cfg()
        if not (cfg["token"] and cfg["cmd_on"]):
            time.sleep(8)
            continue
        if registered != cfg["token"]:          # قائمة الأوامر تظهر عند كتابة / في تيليغرام
            try:
                tg_api(cfg["token"], "setMyCommands", commands=[
                    {"command": "search", "description": "ابحث في الأخبار: /search كلمة"},
                    {"command": "country", "description": "أخبار دولة: /country العراق"},
                    {"command": "summary", "description": "الملخص اليومي"},
                    {"command": "latest", "description": "أحدث الأخبار"},
                    {"command": "qual", "description": "الأخبار النوعية"},
                    {"command": "alerts", "description": "آخر الإنذارات"},
                    {"command": "help", "description": "قائمة الأوامر"}])
                registered = cfg["token"]
            except Exception:
                pass
        try:
            off = int(kv_get("tg_upd_off") or 0)
            r = requests.post(f"https://api.telegram.org/bot{cfg['token']}/getUpdates", timeout=40,
                              json={"offset": off, "timeout": 25,
                                    "allowed_updates": ["message", "channel_post", "my_chat_member"]})
            d = r.json()
            if not d.get("ok"):
                BOT["cmd_error"] = d.get("description") or f"رمز {r.status_code}"
                time.sleep(20)
                continue
            BOT["cmd_error"] = ""
            for u in d["result"]:
                kv_set("tg_upd_off", str(u["update_id"] + 1))
                try:
                    bot_handle_update(cfg, u)
                except Exception as e:
                    log.warning("bot command: %s", e)
        except Exception as e:
            BOT["cmd_error"] = str(e)[:200]
            time.sleep(15)


# ── الملخص اليومي ──
def daily_cfg():
    try:
        c = json.loads(kv_get("daily_cfg") or "{}")
    except Exception:
        c = {}
    c.setdefault("on", True); c.setdefault("hour", 8); c.setdefault("tg", False)
    c.setdefault("chs", []); c.setdefault("ai", False)
    return c


def daily_get(day):
    r = q("SELECT * FROM daily_reports WHERE day=?", (day,), one=True)
    return dict(r) if r else None


def _daily_ai(rows):
    """فقرة «الصورة العامة» بمحرك الكتابة المختار (اختيارية)."""
    heads = "\n".join(f"- {r['title_ar'] or r['title']} ({r['source_ar']})" for r in rows[:60])
    prompt = ("هذه أبرز العناوين التي رصدها المركز خلال آخر 24 ساعة:\n" + heads +
              "\n\nاكتب فقرتين قصيرتين (120 إلى 180 كلمة) بالعربية تلخّصان الصورة العامة لليوم: أهم التطورات وأين تتركز، "
              "بلغة تقرير استخباراتي موضوعي، دون عناوين ولا تعداد نقطي، ودون اختراع معلومات غير موجودة في العناوين.")
    fn = {"free": gen_free, "claude": gen_claude, "gemini": gen_gemini, "ollama": gen_ollama}[writer_provider()]
    out = ""
    for piece in fn(prompt, 900, system="أنت محلل في مركز رصد. تكتب بالعربية الفصحى بإيجاز ودقة.", min_words=0):
        if "[[ERROR]]" in piece:
            break
        out += piece
    out = out.replace("[[WAIT]]", "").replace("[[END]]", "").strip()
    return out if len(out) > 80 else ""


def daily_build(save=True, ai=None):
    """يبني الملخص اليومي لآخر 24 ساعة: HTML للعرض والطباعة، ونص لتيليغرام."""
    cfg = daily_cfg()
    ai = cfg["ai"] if ai is None else ai
    t1 = now()
    t0 = t1 - 86400
    day = datetime.now().strftime("%Y-%m-%d")
    rows = q("SELECT * FROM items WHERE translated=1 AND published >= ? AND published < ? ORDER BY published DESC", (t0, t1))
    catn = dict((k, n) for k, n, _ in CATEGORIES)
    cats = Counter(r["cat"] for r in rows)
    ctry = Counter()
    for r in rows:
        ctry.update(c for c in (r["countries"] or "").strip("|").split("|") if c)
    tags = Counter()
    for r in rows:
        tags.update(t for t in (r["tags"] or "").strip("|").split("|") if t and not t.startswith("★") and t not in ctry)
    qual = sorted([r for r in rows if r["events"]], key=lambda r: (-(r["nsrc"] or 1), -r["published"]))[:10]
    studies = [r for r in rows if r["cat"] in ("think_global", "think_arab")][:6]
    alerts = q("SELECT * FROM alerts WHERE created >= ? ORDER BY created DESC LIMIT 8", (t0,))
    top_c = [c for c, _ in ctry.most_common(6)]
    by_c = {}
    for c in top_c:
        lst = [r for r in rows if f"|{c}|" in (r["countries"] or "")]
        by_c[c] = sorted(lst, key=lambda r: (-(r["nsrc"] or 1), -r["published"]))[:3]
    intro = ""
    if ai and rows:
        try:
            pool = qual + [r for r in sorted(rows, key=lambda r: -(r["nsrc"] or 1)) if r not in qual]
            intro = _daily_ai(pool)
        except Exception as e:
            log.info("daily ai: %s", e)
    e = html.escape
    dstr = datetime.now().strftime("%Y-%m-%d")

    def li(r):
        link = r["link"] or ""
        t = e(r["title_ar"] or r["title"] or "")
        a = f'<a href="{e(link, quote=True)}" target="_blank" rel="noopener">{t}</a>' if link.startswith("http") else t
        return f'<li>{a}<span> — {e(r["source_ar"] or "")}{" · ✓ " + str(r["nsrc"]) + " مصادر" if (r["nsrc"] or 1) >= 3 else ""}</span></li>'

    h = [f'<div class="dstat"><span><b>{len(rows)}</b>مادة مرصودة</span><span><b>{len(qual)}</b>خبراً نوعياً</span>'
         f'<span><b>{len(ctry)}</b>دولة</span><span><b>{len(alerts)}</b>إنذاراً</span></div>']
    if intro:
        h.append("<h2>الصورة العامة</h2>" + "".join(f"<p>{e(p_)}</p>" for p_ in intro.split("\n") if p_.strip()))
    if qual:
        h.append("<h2>أبرز الأحداث النوعية</h2><ol>" + "".join(li(r) for r in qual) + "</ol>")
    if top_c:
        h.append("<h2>الدول الأكثر حضوراً</h2>")
        for c in top_c:
            h.append(f'<h3>{e(c)} <small>({ctry[c]} مادة)</small></h3><ul>' + "".join(li(r) for r in by_c[c]) + "</ul>")
    if alerts:
        h.append("<h2>الإنذارات المبكرة</h2><ul>" + "".join(f"<li>{e(a['msg'])}</li>" for a in alerts) + "</ul>")
    if studies:
        h.append("<h2>دراسات ومقالات مختارة</h2><ul>" + "".join(li(r) for r in studies) + "</ul>")
    if tags:
        h.append("<h2>المواضيع الأكثر تداولاً</h2><p>" + "، ".join(f"{e(t)} ({n})" for t, n in tags.most_common(12)) + "</p>")
    if cats:
        h.append("<h2>توزيع المواد على الأقسام</h2><p>" + "، ".join(f"{e(catn.get(k, k))}: {n}" for k, n in cats.most_common()) + "</p>")
    if not rows:
        h.append("<p>لم تُرصد مواد مترجمة خلال آخر 24 ساعة.</p>")
    html_body = "".join(h)

    def tl(r):
        link = r["link"] or ""
        t = e((r["title_ar"] or r["title"] or "")[:170])
        return f'• <a href="{e(link, quote=True)}">{t}</a>' if link.startswith("http") else f"• {t}"

    g = [f"📋 <b>الملخص اليومي — {dstr}</b>",
         f"<i>{len(rows)} مادة · {len(qual)} خبراً نوعياً · {len(ctry)} دولة · {len(alerts)} إنذاراً</i>"]
    if intro:
        g += ["", "🧭 <b>الصورة العامة</b>", e(intro)]
    if qual:
        g += ["", "🔴 <b>أبرز الأحداث النوعية</b>"] + [tl(r) for r in qual[:7]]
    if top_c:
        g += ["", "📍 <b>الدول الأكثر حضوراً</b>"]
        for c in top_c[:5]:
            g.append(f"<b>{e(c)}</b> ({ctry[c]})")
            g += [tl(r) for r in by_c[c][:2]]
    if alerts:
        g += ["", "🔔 <b>الإنذارات</b>"] + [f"• {e(a['msg'])}" for a in alerts[:5]]
    if studies:
        g += ["", "📚 <b>دراسات مختارة</b>"] + [tl(r) for r in studies[:4]]
    g += ["", "<i>مركز أبو زبيدة للتتبع والرصد</i>"]
    rep = {"day": day, "created": t1, "html": html_body, "tg": "\n".join(g), "n": len(rows), "ai": 1 if intro else 0}
    if save:
        x("INSERT OR REPLACE INTO daily_reports(day, created, html, tg, n, ai) VALUES(?,?,?,?,?,?)",
          (rep["day"], rep["created"], rep["html"], rep["tg"], rep["n"], rep["ai"]))
        x("DELETE FROM daily_reports WHERE day NOT IN (SELECT day FROM daily_reports ORDER BY day DESC LIMIT 90)")
    return rep


def daily_send(rep, ch_ids=None):
    cfg = bot_cfg()
    if not cfg["token"]:
        raise ValueError("أضف رمز البوت أولاً من صفحة البوت")
    dc = daily_cfg()
    ids = ch_ids if ch_ids is not None else dc["chs"]
    targets = [ch for ch in cfg["channels"] if ch["chat"] and (not ids or ch["id"] in ids)]
    if not targets:
        raise ValueError("لا توجد قناة محددة لإرسال الملخص")
    for ch in targets:
        tg_send_long(cfg["token"], ch["chat"], rep["tg"])
    return len(targets)


def daily_loop():
    time.sleep(60)
    while True:
        try:
            c = daily_cfg()
            day = datetime.now().strftime("%Y-%m-%d")
            if c["on"] and datetime.now().hour >= int(c["hour"]) and not daily_get(day):
                rep = daily_build()
                log.info("أُنشئ الملخص اليومي (%s مادة)", rep["n"])
                if c["tg"]:
                    try:
                        daily_send(rep)
                    except Exception as e:
                        log.warning("daily to telegram: %s", e)
        except Exception:
            log.exception("daily")
        time.sleep(120)


@app.get("/api/daily")
def api_daily():
    days = [dict(r) for r in q("SELECT day, created, n, ai FROM daily_reports ORDER BY day DESC LIMIT 60")]
    day = request.args.get("day") or (days[0]["day"] if days else "")
    rep = daily_get(day) if day else None
    cfg = bot_cfg()
    return jsonify(cfg=daily_cfg(), days=days, report=rep, provider=writer_provider(),
                   channels=[{"id": ch["id"], "name": ch["name"], "ready": bool(ch["chat"])} for ch in cfg["channels"]],
                   has_token=bool(cfg["token"]))


@app.post("/api/daily")
def api_daily_set():
    b = request.get_json(silent=True) or {}
    c = daily_cfg()
    for k in ("on", "tg", "ai"):
        if k in b:
            c[k] = bool(b[k])
    if "hour" in b:
        c["hour"] = min(23, max(0, int(b["hour"])))
    if isinstance(b.get("chs"), list):
        c["chs"] = [str(v) for v in b["chs"]]
    kv_set("daily_cfg", json.dumps(c, ensure_ascii=False))
    return jsonify(ok=True)


@app.post("/api/daily/build")
def api_daily_build():
    b = request.get_json(silent=True) or {}
    rep = daily_build(ai=b.get("ai"))
    return jsonify(ok=True, day=rep["day"])


@app.post("/api/daily/send")
def api_daily_send():
    b = request.get_json(silent=True) or {}
    rep = daily_get(b.get("day") or "") or daily_build()
    try:
        n = daily_send(rep)
        return jsonify(ok=True, n=n)
    except Exception as e:
        return jsonify(ok=False, error=str(e)[:200]), 400


@app.get("/print/daily/<day>")
def print_daily(day):
    rep = daily_get(day)
    if not rep:
        return Response("لا يوجد ملخص لهذا اليوم", status=404)
    page = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>الملخص اليومي {html.escape(day)}</title>
<style>@page{{size:A4;margin:16mm}}body{{font:13pt/1.9 Tahoma,Arial,sans-serif;color:#111;max-width:800px;margin:0 auto;padding:20px}}
h1{{font-size:21pt;margin:0 0 4px;border-bottom:3px solid #8E6F35;padding-bottom:8px}}.sub{{color:#666;font-size:11pt;margin-bottom:16px}}
h2{{font-size:14.5pt;margin:20px 0 6px;color:#0A3D7A}}h3{{font-size:12.5pt;margin:12px 0 4px}}h3 small{{color:#777;font-weight:400}}
li{{margin-bottom:5px}}li span{{color:#666;font-size:10.5pt}}a{{color:#111;text-decoration:none}}
.dstat{{display:flex;gap:10px;margin:10px 0}}.dstat span{{flex:1;border:1px solid #ccc;border-radius:6px;padding:6px;text-align:center;font-size:10.5pt;color:#555}}
.dstat b{{display:block;font-size:17pt;color:#111}}
.tools{{position:fixed;top:12px;left:12px}}.tools button{{font:600 14px Tahoma;padding:9px 18px;border:0;border-radius:6px;background:#8E6F35;color:#fff;cursor:pointer}}
@media print{{.tools{{display:none}}}}</style></head><body><div class="tools"><button onclick="print()">طباعة / حفظ PDF</button></div>
<h1>الملخص اليومي</h1><div class="sub">مركز أبو زبيدة للتتبع والرصد · {html.escape(day)} · آخر 24 ساعة حتى {datetime.fromtimestamp(rep['created']).strftime('%H:%M')}</div>
{rep['html']}<script>addEventListener('load',()=>setTimeout(()=>print(),600))</script></body></html>"""
    return Response(page, mimetype="text/html; charset=utf-8")


# ── واجهة إعداد البوت ──
@app.get("/api/bot")
def api_bot():
    cfg = bot_cfg()
    tok = cfg["token"]
    chans = []
    for ch in cfg["channels"]:
        chans.append({**ch, "sent_today": bot_sent_today(ch["id"]), "hold": bot_hold_reason(ch),
                      "next_due": BOT["next"].get(ch["id"], 0), "error": BOT["errors"].get(ch["id"], ""),
                      "recent": [dict(r) for r in q("SELECT * FROM tg_sent2 WHERE ch=? ORDER BY sent DESC LIMIT 10", (ch["id"],))]})
    pub = {k: v for k, v in cfg.items() if k not in ("token", "channels")}
    return jsonify(cfg={**pub, "has_token": bool(tok), "token_hint": (tok[:6] + "…" + tok[-4:]) if tok else ""},
                   channels=chans,
                   state={"now": now(), "bot_name": BOT["bot_name"], "last_sent": BOT["last_sent"], "last_error": BOT["last_error"],
                          "sent_today": bot_sent_today(), "cmd_error": BOT["cmd_error"], "cmd_last": BOT["cmd_last"],
                          "requests": BOT["requests"][::-1]},
                   cats=[{"key": k, "name": n} for k, n, _ in CATEGORIES if k in BOT_ALLOWED_CATS])


def _ch_update(ch, b):
    if "chat" in b:
        ch["chat"] = str(b["chat"]).strip()
    if "name" in b and str(b["name"]).strip():
        ch["name"] = str(b["name"]).strip()[:40]
    if "interval" in b:
        ch["interval"] = min(86400, max(30, int(b["interval"])))
        BOT["next"][ch["id"]] = min(BOT["next"].get(ch["id"], 0), now() + ch["interval"])
    for k, lo, hi in (("max_day", 0, 2000), ("hours_from", 0, 23), ("hours_to", 0, 24), ("fresh_h", 1, 720)):
        if k in b:
            try:
                ch[k] = min(hi, max(lo, int(b[k])))
            except (TypeError, ValueError):
                pass
    for k in ("inc", "exc"):
        if k in b:
            v = b[k]
            lines = v.splitlines() if isinstance(v, str) else list(v or [])
            ch[k] = [str(ln).strip() for ln in lines if str(ln).strip()][:200]
    if b.get("scope") in ("title", "all"):
        ch["scope"] = b["scope"]
    if isinstance(b.get("cats"), list):
        ch["cats"] = b["cats"]
    for k in ("on", "preview", "photo"):
        if k in b:
            ch[k] = bool(b[k])


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
    for k in ("enabled", "cmd_on"):
        if k in b:
            cfg[k] = bool(b[k])
    if b.get("cmd_mode") in ("allow", "all"):
        cfg["cmd_mode"] = b["cmd_mode"]
    if "cmd_users" in b:
        v = b["cmd_users"]
        lines = re.split(r"[\s,،]+", v) if isinstance(v, str) else list(v or [])
        cfg["cmd_users"] = [str(a).strip() for a in lines if str(a).strip()][:100]
    if b.get("cmd_add"):
        a = str(b["cmd_add"]).strip()
        if a and a not in cfg["cmd_users"]:
            cfg["cmd_users"].append(a)
        BOT["requests"] = [r for r in BOT["requests"] if str(r["id"]) != a]
    if b.get("ch"):
        ch = bot_channel(cfg, b["ch"])
        if not ch:
            return jsonify(ok=False, error="القناة غير موجودة"), 404
        _ch_update(ch, b)
    if cfg["enabled"] and not (cfg["token"] and any(ch["chat"] for ch in cfg["channels"])):
        return jsonify(ok=False, error="أضف رمز البوت ومعرّف قناة واحدة على الأقل"), 400
    bot_save(cfg)
    if b.get("enabled"):
        BOT["next"] = {}
    return jsonify(ok=True)


@app.post("/api/bot/channel")
def api_bot_channel_add():
    b = request.get_json(silent=True) or {}
    cfg = bot_cfg()
    if len(cfg["channels"]) >= 20:
        return jsonify(ok=False, error="الحد 20 قناة"), 400
    ch = _ch_norm({"name": (b.get("name") or f"قناة {len(cfg['channels']) + 1}").strip()[:40]})
    cfg["channels"].append(ch)
    bot_save(cfg)
    return jsonify(ok=True, id=ch["id"])


@app.delete("/api/bot/channel/<cid>")
def api_bot_channel_del(cid):
    cfg = bot_cfg()
    if len(cfg["channels"]) <= 1:
        return jsonify(ok=False, error="يجب أن تبقى قناة واحدة على الأقل"), 400
    cfg["channels"] = [ch for ch in cfg["channels"] if ch["id"] != cid]
    bot_save(cfg)
    x("DELETE FROM tg_sent2 WHERE ch=?", (cid,))
    return jsonify(ok=True)


@app.post("/api/bot/preview")
def api_bot_preview():
    """يعرض أحدث العناوين التي تطابق فلتر القناة (دون إرسال)."""
    cfg = bot_cfg()
    b = request.get_json(silent=True) or {}
    ch = dict(bot_channel(cfg, b.get("ch")) or cfg["channels"][0])
    for k in ("inc", "exc"):
        if k in b:
            ch[k] = [ln.strip() for ln in str(b[k]).splitlines() if ln.strip()]
    if b.get("scope") in ("title", "all"):
        ch["scope"] = b["scope"]
    rows = _bot_candidates(ch, limit=600, unsent=False)
    hit = [r for r in rows if bot_match(r, ch)]
    return jsonify(total=len(rows), matched=len(hit),
                   items=[{"id": r["id"], "title": r["title_ar"] or r["title"], "source": r["source_ar"], "published": r["published"]}
                          for r in hit[:8]])


@app.get("/api/bot/chats")
def api_bot_chats():
    cfg = bot_cfg()
    if not cfg["token"]:
        return jsonify(ok=False, error="أضف رمز البوت أولاً"), 400
    chats = dict(BOT_CHATS)
    if not cfg["cmd_on"]:                    # حين تعمل الأوامر يقرأ البوت الرسائل بنفسه فلا نكرر القراءة
        try:
            ups = tg_api(cfg["token"], "getUpdates", limit=100, allowed_updates=["message", "channel_post", "my_chat_member"])
        except Exception as e:
            return jsonify(ok=False, error=str(e)), 400
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
    b = request.get_json(silent=True) or {}
    ch = bot_channel(cfg, b.get("ch")) or cfg["channels"][0]
    if not (cfg["token"] and ch["chat"]):
        return jsonify(ok=False, error="أضف رمز البوت ومعرّف القناة أولاً"), 400
    try:
        tg_api(cfg["token"], "sendMessage", chat_id=ch["chat"], parse_mode="HTML",
               text=f"✅ <b>تم ربط البوت بنجاح</b>\nمركز أبو زبيدة للتتبع والرصد سيرسل هنا ({html.escape(ch['name'])}) ملخصات المقالات المترجمة.")
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400


@app.post("/api/bot/send-now")
def api_bot_send_now():
    b = request.get_json(silent=True) or {}
    try:
        sent = bot_tick(force=True, ch_id=b.get("ch"))
        return jsonify(ok=True, sent=sent)
    except Exception as e:
        BOT["last_error"] = str(e)[:200]
        return jsonify(ok=False, error=BOT["last_error"]), 400


@app.post("/api/bot/reset")
def api_bot_reset():
    b = request.get_json(silent=True) or {}
    if b.get("ch"):
        x("DELETE FROM tg_sent2 WHERE ch=?", (b["ch"],))
    else:
        x("DELETE FROM tg_sent2")
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
    trim_alerts()


ALERTS_KEEP = 15            # لا يُحتفظ إلا بآخر 15 إنذاراً، والأقدم يُحذف تلقائياً


def trim_alerts():
    x("DELETE FROM alerts WHERE id NOT IN (SELECT id FROM alerts ORDER BY created DESC LIMIT ?)", (ALERTS_KEEP,))


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
    rows = q("SELECT * FROM alerts WHERE created >= ? ORDER BY created DESC LIMIT ?", (now() - hours * 3600, ALERTS_KEEP))
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
    trim_alerts()
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
    # مصدر التحديث ثابت لا يُغيَّر من الواجهة
    return {"repo": DEFAULT_REPO, "branch": "main", "auto": kv_get("upd_auto", "1") == "1"}


def _ver_tuple(v):
    try:
        return tuple(int(x) for x in re.findall(r"\d+", v or ""))
    except Exception:
        return ()


def _local_hash():
    pth = os.path.join(BASE_DIR, "rased.py")
    if os.path.exists(pth):
        with open(pth, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    return kv_get("upd_hash", "")


def check_update(apply=True):
    if UPDATE["checking"]:
        return UPDATE
    UPDATE.update(checking=True, error="")
    try:
        c = update_cfg()
        url = f"https://raw.githubusercontent.com/{c['repo']}/{c['branch']}/rased.py"
        r = requests.get(url, headers={**HEADERS, "Cache-Control": "no-cache"}, timeout=60)
        if r.status_code == 404:
            raise ValueError("لم يُعثر على rased.py في المستودع (تأكد من الاسم وأن المستودع عام Public)")
        r.raise_for_status()
        code = r.content
        h = hashlib.sha256(code).hexdigest()
        m = re.search(rb'^VERSION\s*=\s*"([^"]+)"', code, re.M)
        rv = m.group(1).decode() if m else ""
        UPDATE.update(last=now(), remote_version=rv)
        if h == _local_hash() or (rv and _ver_tuple(rv) <= _ver_tuple(VERSION)):
            UPDATE.update(state="البرنامج محدَّث", ready=False)       # لا ننزل أبداً إلى إصدار أقدم أو مساوٍ
            return UPDATE
        try:
            compile(code.decode("utf-8"), "rased.py", "exec")
        except Exception as e:
            raise ValueError(f"الملف على GitHub فيه خطأ برمجي فلم يُطبَّق: {str(e)[:120]}")
        if "مركز أبو زبيدة".encode("utf-8") not in code:
            raise ValueError("الملف على GitHub ليس برنامج المركز، لم يُطبَّق")
        if not apply:
            UPDATE.update(state="يوجد تحديث جديد", ready=False)
            return UPDATE
        dst = os.path.join(BASE_DIR, "rased.py")
        if os.path.exists(dst):
            import shutil
            shutil.copy2(dst, dst + ".bak")
        with open(dst + ".new", "wb") as f:
            f.write(code)
        os.replace(dst + ".new", dst)
        kv_set("upd_hash", h)
        UPDATE.update(state="نُزِّل تحديث جديد، يُطبَّق عند إعادة التشغيل", ready=True)
        log.info("نُزِّل تحديث جديد من GitHub (الإصدار %s)", rv or "؟")
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
                           valid=lambda c: c[:3] == b"id," or c[:6] == b"\xef\xbb\xbfid,")
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
                           valid=lambda c: b"<CONSOLIDATED_LIST" in c[:3000])
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
ICON192 = "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"
ICON512 = "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"


@app.get("/manifest.webmanifest")
def pwa_manifest():
    return jsonify(name="مركز أبو زبيدة للتتبع والرصد", short_name="أبو زبيدة", start_url="/", display="standalone",
                   dir="rtl", lang="ar", background_color="#060B13", theme_color="#060B13",
                   icons=[{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                          {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}])


FLAG_SY = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600"><rect width="900" height="600" fill="#000"/><rect width="900" height="400" fill="#fff"/><rect width="900" height="200" fill="#007A3D"/><g fill="#CE1126"><polygon points="270.0,238.0 283.9,280.8 329.0,280.8 292.5,307.3 306.4,350.2 270.0,323.7 233.6,350.2 247.5,307.3 211.0,280.8 256.1,280.8"/><polygon points="450.0,238.0 463.9,280.8 509.0,280.8 472.5,307.3 486.4,350.2 450.0,323.7 413.6,350.2 427.5,307.3 391.0,280.8 436.1,280.8"/><polygon points="630.0,238.0 643.9,280.8 689.0,280.8 652.5,307.3 666.4,350.2 630.0,323.7 593.6,350.2 607.5,307.3 571.0,280.8 616.1,280.8"/></g></svg>'''          # علم سوريا الحالي (الأخضر والأبيض والأسود مع ثلاث نجوم حمراء)


@app.get("/flag/<code>")
def flag_img(code):
    """علم الدولة: يُجلب من flagcdn مرة واحدة ثم يُحفظ في مجلد flags بجانب البرنامج."""
    code = (code or "").lower()[:2]
    if not re.fullmatch(r"[a-z]{2}", code):
        return Response(status=404)
    if code == "sy":
        r_ = Response(FLAG_SY, mimetype="image/svg+xml")
        r_.headers["Cache-Control"] = "public, max-age=604800"
        return r_
    d = os.path.join(BASE_DIR, "flags")
    pth = os.path.join(d, code + ".png")
    if not os.path.exists(pth):
        try:
            r = requests.get(f"https://flagcdn.com/w80/{code}.png", headers=HEADERS, timeout=15)
            if r.status_code != 200 or not r.content.startswith(b"\x89PNG"):
                return Response(status=404)
            os.makedirs(d, exist_ok=True)
            with open(pth + ".tmp", "wb") as f:
                f.write(r.content)
            os.replace(pth + ".tmp", pth)
        except Exception:
            return Response(status=404)
    r_ = send_file(pth, mimetype="image/png", max_age=604800)
    return r_


@app.get("/icon-192.png")
def pwa_icon192():
    return Response(base64.b64decode(ICON192), mimetype="image/png")


@app.get("/icon-512.png")
def pwa_icon512():
    return Response(base64.b64decode(ICON512), mimetype="image/png")


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
PAGE = r"""<!doctype html>
<html lang="ar" dir="rtl" data-theme="neon">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>مركز أبو زبيدة للتتبع والرصد</title>
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#060B13">
<link rel="icon" href="/icon-192.png">
<link rel="apple-touch-icon" href="/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=Noto+Kufi+Arabic:wght@500;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --fd:"Noto Kufi Arabic","IBM Plex Sans Arabic",sans-serif;
  --fm:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  --r:6px;--r-lg:8px;
}
/* النمط الافتراضي: غرفة العمليات (كحلي + فيروزي) */
/* النمط الافتراضي الجديد: نيون أزرق */
[data-theme=neon]{
  --bg:#02060E;--bg2:#040B18;--surface:#061224;--surface2:#08182F;--hover:#0B2140;
  --border:rgba(40,160,255,.16);--border2:rgba(60,190,255,.42);--line:rgba(80,170,255,.08);
  --text:#E6F3FF;--muted:#8DB2D8;--faint:#587CA6;
  --acc:#1EA7FF;--acc2:#7AD7FF;--acc-ink:#00101F;--accbg:rgba(30,167,255,.12);
  --red:#FF3D71;--green:#2BF0B4;--gold:#FFD166;--focus:#7AD7FF;
  --grid:rgba(30,167,255,.07);--neon:0 0 0 1px rgba(30,167,255,.10),0 0 22px -6px rgba(30,167,255,.45);color-scheme:dark}
[data-theme=neon] body::before{background:
  radial-gradient(900px 480px at 85% -10%,rgba(30,140,255,.22),transparent 60%),
  radial-gradient(700px 420px at 0% 110%,rgba(0,220,255,.12),transparent 60%),
  linear-gradient(var(--grid) 1px,transparent 1px) 0 0/40px 40px,linear-gradient(90deg,var(--grid) 1px,transparent 1px) 0 0/40px 40px;
  mask-image:none}
[data-theme=neon] .box,[data-theme=neon] .item,[data-theme=neon] .ccard,[data-theme=neon] .ctycard,[data-theme=neon] .book,[data-theme=neon] .al{box-shadow:var(--neon)}
[data-theme=neon] .box:hover,[data-theme=neon] .ccard:hover,[data-theme=neon] .ctycard:hover{box-shadow:0 0 0 1px rgba(60,190,255,.25),0 0 28px -4px rgba(30,167,255,.6)}
[data-theme=neon] .chrome{border-bottom:1px solid rgba(60,190,255,.35);box-shadow:0 6px 30px -12px rgba(30,167,255,.55)}
[data-theme=neon] .chrome::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;
  background:linear-gradient(90deg,transparent,#1EA7FF 20%,#7AD7FF 50%,#1EA7FF 80%,transparent);background-size:200% 100%;
  animation:neonflow 6s linear infinite;filter:drop-shadow(0 0 6px #1EA7FF)}
@keyframes neonflow{to{background-position:-200% 0}}
[data-theme=neon] .brand b,[data-theme=neon] .pagehead h1{text-shadow:0 0 18px rgba(30,167,255,.55),0 0 2px rgba(122,215,255,.8)}
[data-theme=neon] .pagehead .code,[data-theme=neon] .brand small{text-shadow:0 0 10px rgba(30,167,255,.8)}
[data-theme=neon] .mark{box-shadow:0 0 16px rgba(30,167,255,.6),inset 0 0 12px rgba(30,167,255,.35)}
[data-theme=neon] .ibtn.primary{box-shadow:0 0 16px rgba(30,167,255,.65),0 0 2px #7AD7FF;text-shadow:none}
[data-theme=neon] .ibtn.primary:hover{box-shadow:0 0 26px rgba(30,167,255,.9),0 0 3px #7AD7FF}
[data-theme=neon] .navi.on{background:linear-gradient(270deg,rgba(30,167,255,.22),transparent);box-shadow:inset 0 0 0 1px rgba(60,190,255,.25)}
[data-theme=neon] .navi.on::before{box-shadow:0 0 10px var(--c),0 0 3px var(--c)}
[data-theme=neon] .navi:hover svg,[data-theme=neon] .navi.on svg{filter:drop-shadow(0 0 5px var(--c))}
[data-theme=neon] .sidenav{box-shadow:inset 1px 0 0 rgba(60,190,255,.25)}
[data-theme=neon] .ticker .lbl{box-shadow:0 0 18px -2px var(--tc)}
[data-theme=neon] .qualbox{box-shadow:0 0 0 1px rgba(255,61,113,.2),0 0 30px -6px rgba(255,61,113,.55)}
[data-theme=neon] .seg button.on{box-shadow:inset 0 -2px 0 var(--acc),0 0 12px -2px rgba(30,167,255,.7)}
[data-theme=neon] .search input:focus{box-shadow:0 0 0 1px var(--acc),0 0 18px rgba(30,167,255,.5)}
[data-theme=neon] .ev,[data-theme=neon] .badge.new{box-shadow:0 0 10px -1px var(--e,var(--red))}
[data-theme=neon] .item:hover{box-shadow:0 0 0 1px rgba(60,190,255,.3),0 0 26px -4px rgba(30,167,255,.65)}
[data-theme=neon] .item .when{border-color:var(--c);box-shadow:3px 0 12px -6px var(--c)}
[data-theme=neon] .live i,[data-theme=neon] .statusbar .dot{box-shadow:0 0 10px currentColor}
[data-theme=neon] dialog{box-shadow:0 0 0 1px rgba(60,190,255,.35),0 0 60px -10px rgba(30,167,255,.7)}
[data-theme=neon] .dlghead{border-top-color:#1EA7FF;box-shadow:0 -1px 18px rgba(30,167,255,.6)}
@media (prefers-reduced-motion:reduce){[data-theme=neon] .chrome::after{animation:none}}
[data-theme=ops]{
  --bg:#060B13;--bg2:#08101B;--surface:#0B1420;--surface2:#0F1A29;--hover:#132236;
  --border:#182638;--border2:#24405C;--line:rgba(120,170,220,.07);
  --text:#E3ECF5;--muted:#8D9DB2;--faint:#5A6C84;
  --acc:#2DD4BF;--acc2:#5EEAD4;--acc-ink:#04110F;--accbg:rgba(45,212,191,.09);
  --red:#F43F5E;--green:#34D399;--gold:#E0B95B;--focus:#5EEAD4;
  --grid:rgba(45,212,191,.045);color-scheme:dark}
/* النمط الذهبي */
[data-theme=gold]{
  --bg:#05070B;--bg2:#080B11;--surface:#0B0F17;--surface2:#10151F;--hover:#161C28;
  --border:#1E2330;--border2:#3A3220;--line:rgba(201,164,92,.06);
  --text:#ECE6D8;--muted:#9AA2AF;--faint:#646C7A;
  --acc:#C9A45C;--acc2:#EBCB8B;--acc-ink:#140F06;--accbg:rgba(201,164,92,.09);
  --red:#E5484D;--green:#3DD68C;--gold:#EBCB8B;--focus:#EBCB8B;
  --grid:rgba(201,164,92,.04);color-scheme:dark}
/* النمط النهاري */
[data-theme=light]{
  --bg:#EEF1F5;--bg2:#E6EAF0;--surface:#FFFFFF;--surface2:#F5F7FA;--hover:#EDF1F6;
  --border:#DCE2EA;--border2:#B9C6D6;--line:rgba(20,40,70,.05);
  --text:#0F1724;--muted:#526075;--faint:#8592A5;
  --acc:#0F766E;--acc2:#0D5F59;--acc-ink:#FFFFFF;--accbg:rgba(15,118,110,.08);
  --red:#D61F45;--green:#0F8A5F;--gold:#A16207;--focus:#0F766E;
  --grid:rgba(15,118,110,.05);color-scheme:light}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0}
body{background:var(--bg);color:var(--text);font:15px/1.75 "IBM Plex Sans Arabic",Tahoma,"Segoe UI",sans-serif;min-height:100vh}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:linear-gradient(var(--grid) 1px,transparent 1px) 0 0/40px 40px,linear-gradient(90deg,var(--grid) 1px,transparent 1px) 0 0/40px 40px;
  mask-image:linear-gradient(180deg,#000,transparent 70%)}
a{color:inherit}
button,input,select{font-family:inherit;font-size:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:1.5px solid var(--focus);outline-offset:2px}
svg.i{width:17px;height:17px;flex:none;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.mt{font-family:var(--fm);letter-spacing:.05em}

/* ── الرأس */
.chrome{position:sticky;top:0;z-index:40;background:var(--bg2);border-bottom:1px solid var(--border)}
.statusbar{display:flex;align-items:center;gap:18px;height:26px;padding:0 18px;font:500 10.5px var(--fm);letter-spacing:.08em;color:var(--faint);border-bottom:1px solid var(--border);background:var(--bg)}
.statusbar b{color:var(--acc);font-weight:600}
.statusbar .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-inline-end:6px;box-shadow:0 0 6px var(--green)}
.statusbar .sp{flex:1}
.top{display:flex;align-items:center;gap:16px;padding:10px 18px}
.brand{display:flex;align-items:center;gap:12px;white-space:nowrap;text-decoration:none}
.mark{width:40px;height:40px;flex:none;display:grid;place-items:center;border:1px solid var(--border2);border-radius:var(--r);background:var(--accbg);position:relative;overflow:hidden}
.mark svg{width:28px;height:28px}
.mark .rot{transform-origin:14px 14px;transform-box:view-box;animation:sweep 3.2s linear infinite}
@keyframes sweep{to{transform:rotate(360deg)}}
.brand b{display:block;font:800 18px/1.3 var(--fd)}
.brand small{display:block;font:500 9.5px var(--fm);letter-spacing:.2em;color:var(--acc);direction:ltr;text-align:right}
.search{flex:1 1 380px;min-width:300px;max-width:560px;margin-inline-start:18px;position:relative;display:flex;align-items:center}
.search svg{position:absolute;right:12px;color:var(--faint);pointer-events:none}
.search input{width:100%;min-width:0;height:38px;font-size:14px;text-overflow:ellipsis;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:0 38px 0 40px}
.search input:focus{outline:none;border-color:var(--acc)}
.search kbd{position:absolute;left:10px;font:11px var(--fm);color:var(--faint);border:1px solid var(--border);border-radius:4px;padding:0 6px}
.sp{flex:1}
.clocks{display:flex;gap:14px;min-width:0;overflow:hidden;font:500 10px var(--fm);color:var(--faint);letter-spacing:.04em}
.clock{text-align:center;line-height:1.3}
.clock b{display:block;font:600 13.5px var(--fm);color:var(--text)}
.ibtn{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:36px;min-width:36px;padding:0 12px;border-radius:var(--r);border:1px solid var(--border);background:var(--surface);white-space:nowrap;text-decoration:none;font-size:13.5px}
.ibtn:hover{border-color:var(--border2);background:var(--hover)}
.ibtn.primary{background:var(--acc);border-color:var(--acc);color:var(--acc-ink);font-weight:600}
.ibtn.primary:hover{filter:brightness(1.08)}
.ibtn.spin svg{animation:rot 1s linear infinite}
.skins{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.skins button{border:0;background:var(--surface);width:34px;height:34px;display:grid;place-items:center}
.skins button+button{border-inline-start:1px solid var(--border)}
.skins button i{width:14px;height:14px;border-radius:50%;display:block;border:1px solid var(--border2)}
.skins button.on{background:var(--hover);box-shadow:inset 0 -2px 0 var(--acc)}

/* ── التبويبات */
.tabs{display:flex;gap:2px;padding:0 12px;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{position:relative;display:inline-flex;align-items:center;gap:8px;height:42px;padding:0 13px;border:0;background:none;color:var(--muted);white-space:nowrap;font-size:14px}
.tab svg{color:var(--c)}
.tab:hover{color:var(--text)}
.tab .ct{font:500 10.5px var(--fm);color:var(--faint);padding:0 6px;border:1px solid var(--border);border-radius:3px}
.tab.on{color:var(--text)}
.tab.on::after{content:"";position:absolute;right:10px;left:10px;bottom:-1px;height:2px;background:var(--c)}
.tab.on .ct{color:var(--text);border-color:var(--border2)}
.tabsep{width:1px;margin:10px 6px;background:var(--border);flex:none}

/* ── الأشرطة */
.tickers{border-bottom:1px solid var(--border);background:var(--bg)}
.tickers.off{display:none}
.ticker{display:flex;align-items:center;height:32px;border-top:1px solid var(--line)}
.ticker:first-child{border-top:0}
.ticker .lbl{flex:none;display:inline-flex;align-items:center;gap:8px;height:100%;width:136px;padding:0 14px;font:700 12.5px var(--fd);color:#fff;background:var(--tc);clip-path:polygon(0 0,100% 0,100% 100%,0 100%,10px 50%)}
.ticker .lbl em{font:500 9.5px var(--fm);font-style:normal;opacity:.75;margin-inline-start:auto;letter-spacing:.1em}
.ticker .track{flex:1;position:relative;overflow:hidden;height:100%;mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent)}
.ticker .run{position:absolute;top:0;left:0;white-space:nowrap;line-height:32px;font-size:14px;animation:tick 160s linear infinite}
.ticker .run:hover{animation-play-state:paused}
.ticker .run button{all:unset;cursor:pointer;margin:0 18px}
.ticker .run button::before{content:"";display:inline-block;width:5px;height:5px;background:var(--tc);margin-inline-end:12px;vertical-align:2px}
.ticker .run button:hover{color:var(--acc2)}
.ticker .run button span{color:var(--faint);font-size:12px;margin-inline-start:8px}
@keyframes tick{from{transform:translateX(-100%)}to{transform:translateX(100vw)}}

/* ── القائمة الجانبية */
.layout{display:grid;grid-template-columns:252px minmax(0,1fr);align-items:start}
.sidenav{position:sticky;top:84px;height:calc(100vh - 84px);overflow-y:auto;display:flex;flex-direction:column;background:var(--bg2);border-left:1px solid var(--border);padding:10px 10px 12px;scrollbar-width:thin;scrollbar-color:var(--border2) transparent}
.navgrp{font:600 10px var(--fm);letter-spacing:.16em;color:var(--faint);padding:14px 10px 6px}
.navgrp:first-child{padding-top:6px}
.navi{position:relative;display:flex;align-items:center;gap:11px;width:100%;padding:8px 10px;border:0;border-radius:var(--r);background:none;color:var(--muted);text-align:right;font-size:14px;line-height:1.5}
.navi svg{color:var(--c);flex:none}
.navi .nm{flex:1}
.navi .ct{font:500 10.5px var(--fm);color:var(--faint);min-width:26px;text-align:center;padding:0 5px;border:1px solid var(--border);border-radius:3px}
.navi:hover{background:var(--hover);color:var(--text)}
.navi.on{background:var(--accbg);color:var(--text);font-weight:600}
.navi.on::before{content:"";position:absolute;right:0;top:7px;bottom:7px;width:3px;border-radius:2px;background:var(--c)}
.navi.on .ct{color:var(--text);border-color:var(--border2)}
.navi .bar{position:absolute;right:38px;left:46px;bottom:3px;height:1px;background:transparent}
.navi .bar i{display:block;height:100%;background:var(--c);opacity:.45}
.sidefoot{margin-top:auto;padding:12px 10px 2px;border-top:1px solid var(--border);font:500 10.5px/2 var(--fm);color:var(--faint);letter-spacing:.04em}
.sidefoot b{color:var(--text);font-weight:600}

/* ── الصفحة */
.wrap{min-width:0;max-width:1500px;width:100%;padding:22px 22px 60px}
.pagehead{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px;padding-bottom:16px;border-bottom:1px solid var(--border)}
.pagehead .code{display:block;font:500 11px var(--fm);letter-spacing:.2em;color:var(--acc);margin-bottom:2px}
.pagehead h1{font:800 28px/1.4 var(--fd);margin:0}
.pagehead p{margin:4px 0 0;color:var(--muted);max-width:70ch}
.live{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:var(--muted);white-space:nowrap}
.live i{width:8px;height:8px;border-radius:50%;background:var(--red);animation:pulse 2s infinite}
.live b{font:600 15px var(--fm);color:var(--text)}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(244,63,94,.6)}70%{box-shadow:0 0 0 9px rgba(244,63,94,0)}100%{box-shadow:0 0 0 0 rgba(244,63,94,0)}}
.box{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg)}
.boxh{display:flex;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid var(--border);font:700 14px var(--fd)}
.boxh svg{color:var(--c,var(--acc))}
.boxh .sub{font:500 10.5px var(--fm);color:var(--faint);letter-spacing:.08em}
.boxh .sp{flex:1}
.boxh .lnk{font:500 12.5px "IBM Plex Sans Arabic";color:var(--acc);background:none;border:0;padding:0}
.boxh .lnk:hover{text-decoration:underline}

/* لوحة القيادة */
.kpis{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:14px;margin-bottom:18px}
.kpi{padding:14px 16px}
.kpi .k{font:500 10.5px var(--fm);letter-spacing:.12em;color:var(--faint)}
.kpi .v{display:flex;align-items:baseline;gap:8px;margin-top:4px}
.kpi .v b{font:600 30px/1.2 var(--fm)}
.kpi .v span{font-size:13px;color:var(--muted)}
.kpi p{margin:6px 0 0;font-size:12.5px;color:var(--muted)}
.threat .v b{font:800 24px/1.3 var(--fd);color:var(--tl)}
.segs{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin-top:10px}
.segs i{height:6px;background:var(--surface2);border:1px solid var(--border)}
.segs i.on{background:var(--tl);border-color:var(--tl)}
.dashgrid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:18px;align-items:start}
.boards{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}
.board{display:flex;flex-direction:column;border-top:2px solid var(--c)}
.board ol{list-style:none;margin:0;padding:4px 0}
.board li{border-top:1px solid var(--line)}
.board li:first-child{border-top:0}
.bt{all:unset;box-sizing:border-box;cursor:pointer;display:grid;grid-template-columns:62px 1fr;gap:10px;width:100%;padding:9px 14px}
.bt:hover{background:var(--hover)}
.bt:focus-visible{outline:1.5px solid var(--focus);outline-offset:-2px}
.bt time{font:500 11px/1.9 var(--fm);color:var(--faint)}
.bt .t{font-size:14.5px;line-height:1.65}
.bt .s{display:block;font-size:11.5px;color:var(--faint);margin-top:2px}
.bt .pend{color:var(--faint)}
.board .empty-s{padding:24px 14px;color:var(--faint);font-size:13px}

/* صفحات الأقسام */
.secgrid{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;align-items:start}
.rail{position:sticky;top:100px;display:flex;flex-direction:column;gap:14px;max-height:calc(100vh - 116px);overflow:auto;scrollbar-width:thin}
.filters{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden;background:var(--surface)}
.seg button{border:0;background:none;padding:6px 12px;font-size:13px;color:var(--muted)}
.seg button+button{border-inline-start:1px solid var(--border)}
.seg button:hover{color:var(--text);background:var(--hover)}
.seg button.on{background:var(--accbg);color:var(--acc2);box-shadow:inset 0 -2px 0 var(--acc)}
select{height:34px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:0 10px;max-width:260px}
.count{font:500 12px var(--fm);color:var(--faint)}
.activetag{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:var(--r);border:1px solid var(--acc);color:var(--acc2);background:var(--accbg);font-size:13px}
.newpill{display:block;margin:0 auto 12px;background:var(--acc);color:var(--acc-ink);border:0;border-radius:var(--r);padding:7px 20px;font-weight:600}

/* المواد: صفوف تحريرية */
.feed{display:flex;flex-direction:column}
.feed.list{border:1px solid var(--border);border-radius:var(--r-lg);background:var(--surface);overflow:hidden}
.item{position:relative;display:grid;grid-template-columns:76px minmax(0,1fr);gap:16px;padding:16px 18px;border-top:1px solid var(--border)}
.item:first-child{border-top:0}
.item:hover{background:var(--hover)}
.item .when{font:500 11.5px/1.6 var(--fm);color:var(--faint);text-align:center;border-inline-end:2px solid var(--c);padding-inline-end:12px}
.item .when b{display:block;font:600 15px var(--fm);color:var(--text)}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;font-size:12px;color:var(--faint)}
.src{color:var(--c);font-weight:600;background:none;border:0;padding:0;font-size:12.5px;display:inline-flex;align-items:center;gap:6px}
.fav{width:16px;height:16px;border-radius:4px;background:#fff;object-fit:contain;flex:none;padding:1px;box-shadow:0 0 0 1px var(--border)}
.src:has(.fav)::before{display:none}
button.src:hover{text-decoration:underline;text-underline-offset:3px}
.ref{font:500 10.5px var(--fm);color:var(--faint);margin-inline-start:auto;direction:ltr}
.badge{font-size:10.5px;padding:0 7px;border-radius:3px;line-height:1.9;font-weight:600}
.badge.new{background:var(--red);color:#fff}
.badge.pend{border:1px dashed var(--faint);font-weight:400}
.badge.fail{border:1px solid var(--red);color:var(--red);font-weight:400}
.badge.seen{border:1px solid var(--border2);color:var(--faint);font-weight:400}
.item.seen h3 .ttl{color:var(--muted)}
.item.seen .when b{color:var(--faint)}
.bt.seen .t,.tgp.seen .t,.twl button.seen{color:var(--faint)}
.bt.seen time::after{content:" ✓";color:var(--acc)}
.dlgtools{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px;padding:10px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface2)}
.dlgtools .grp{display:flex;gap:6px;flex-wrap:wrap}
.dlgtools .sep{width:1px;align-self:stretch;background:var(--border)}
.dlgtools .ibtn{height:34px}
.ibtn.tr{background:var(--accbg);border-color:var(--acc);color:var(--acc2);font-weight:600}
.ibtn.tr[disabled]{opacity:.7;cursor:wait}
.ibtn.on{background:var(--hover);box-shadow:inset 0 -2px 0 var(--acc)}
.viewlbl{font:500 11px var(--fm);letter-spacing:.12em;color:var(--faint)}
.item h3{margin:4px 0 4px;font:700 17px/1.7 var(--fd)}
.ttl{all:unset;cursor:pointer}
.ttl:hover{color:var(--acc2)}
.ttl:focus-visible{outline:1.5px solid var(--focus);outline-offset:3px}
.item .orig{display:block;font-size:12px;color:var(--faint);direction:ltr;text-align:left;margin-bottom:4px}
.item p{margin:0;color:var(--muted);font-size:14.5px;max-width:95ch;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.foot{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:8px}
.tag{display:inline-flex;align-items:center;gap:5px;font-size:12px;padding:0 8px;border-radius:3px;border:1px solid var(--border);background:var(--surface2);color:var(--muted);line-height:1.9}
button.tag:hover{color:var(--text);border-color:var(--border2)}
.tag.kw{color:var(--gold);border-color:var(--gold)}
.tag.on{background:var(--acc);border-color:var(--acc);color:var(--acc-ink)}
.tag em{font:400 10.5px var(--fm);font-style:normal;opacity:.65}
.acts{display:flex;gap:2px;margin-inline-start:auto}
.acts button,.acts a{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:var(--r);border:0;background:none;color:var(--faint);text-decoration:none}
.acts button:hover,.acts a:hover{background:var(--surface2);color:var(--text)}
.acts .saved{color:var(--gold)}
.item.lead{grid-template-columns:76px minmax(0,1fr);padding:22px 18px;background:linear-gradient(270deg,var(--accbg),transparent 70%)}
.item.lead h3{font-size:22px;line-height:1.6}
.item.lead p{-webkit-line-clamp:3;font-size:15.5px}
.compact .item p,.compact .item .foot .tag,.compact .item .orig{display:none}
.compact .item{padding:10px 18px}
.compact .item h3{font-size:15.5px;margin:2px 0 0}
.compact .item .foot{margin-top:2px}
.more{display:flex;margin:18px auto 0}
.empty{padding:50px 20px;text-align:center;color:var(--muted)}
.empty b{display:block;color:var(--text);font:700 16px var(--fd);margin-bottom:6px}
.loading{color:var(--muted);padding:30px;text-align:center}

/* العمود الجانبي */
.tags{display:flex;flex-wrap:wrap;gap:6px;padding:12px 14px}
.rail .status{font-size:12.5px;color:var(--muted);padding:10px 14px;line-height:2.1}
.status b{color:var(--text);font:500 12.5px var(--fm)}
.ok{color:var(--green)}.bad,.warn{color:var(--red)}
.twl{list-style:none;margin:0;padding:0}
.twl li{border-top:1px solid var(--line)}
.twl li:first-child{border-top:0}
.twl button{all:unset;box-sizing:border-box;cursor:pointer;display:block;width:100%;padding:9px 14px;font-size:13.5px;line-height:1.7}
.twl button:hover{background:var(--hover)}
.twl .meta{font-size:11.5px}

/* تيليغرام: لوحة القنوات */
.tgtools{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.tgtools .count b{color:var(--acc2)}
.tgboard{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.tgc{display:flex;flex-direction:column}
.tgc .boxh{font-size:13.5px}
.tgc .av{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font:700 13px var(--fd);color:var(--acc-ink);background:var(--acc);flex:none}
.tgc .uh{display:block;font:500 10.5px var(--fm);color:var(--faint);direction:ltr;text-align:right}
.tgc .st{width:7px;height:7px;border-radius:50%;background:var(--faint)}
.tgc .st.ok{background:var(--green);box-shadow:0 0 6px var(--green)}
.tgc .st.bad{background:var(--red)}
.tgc ol{list-style:none;margin:0;padding:0}
.tgc li{border-top:1px solid var(--line)}
.tgc li:first-child{border-top:0}
.tgp{all:unset;box-sizing:border-box;cursor:pointer;display:block;width:100%;padding:10px 14px}
.tgp:hover{background:var(--hover)}
.tgp .meta{font-size:11px}
.tgp .t{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;font-size:14px;line-height:1.75;margin-top:2px}
.tgc .err{padding:14px;font-size:12.5px;color:var(--faint)}
.tgc .x{background:none;border:0;color:var(--faint);font-size:16px;padding:0 4px}
.tgc .x:hover{color:var(--red)}

/* إضافة كلمات وقنوات */
.addpanel{padding:12px;margin-bottom:14px}
.addrow{display:flex;gap:8px;flex-wrap:wrap}
.addrow input{flex:1;min-width:180px;height:36px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 12px}
.addrow input:focus{outline:none;border-color:var(--acc)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:1px 6px 1px 10px;border-radius:4px;font-size:13px;border:1px solid var(--cc);color:var(--cc)}
.chip button,.chip a{background:none;border:0;color:inherit;text-decoration:none;padding:0 3px}
.chip .x{font-size:15px;line-height:1;opacity:.7}

/* دليل المراكز */
.cfilters{display:flex;flex-direction:column;gap:10px;padding:12px;margin-bottom:14px}
.cfrow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.cfrow input{flex:1;min-width:200px;height:36px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 12px}
.cgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.ccard{all:unset;box-sizing:border-box;cursor:pointer;display:flex;flex-direction:column;gap:10px;padding:14px;background:var(--surface);border:1px solid var(--border);border-top:2px solid var(--c);border-radius:var(--r-lg);position:relative}
.ccard:hover{border-color:var(--border2);background:var(--hover)}
.ccard:focus-visible{outline:1.5px solid var(--focus)}
.chead{display:flex;gap:12px;align-items:center}
.mono{width:44px;height:44px;flex:none;border-radius:var(--r);display:grid;place-items:center;font:700 12.5px var(--fm);color:var(--c);border:1px solid var(--c);background:var(--surface2);position:relative;overflow:hidden}
.mono img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#fff;padding:7px}
.mono.big img{padding:10px}
.av{position:relative;overflow:hidden}
.av img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#fff}
.mono.big{width:68px;height:68px;font-size:18px}
.cname{font:700 14.5px/1.6 var(--fd)}
.cmeta{display:flex;flex-wrap:wrap;gap:6px 10px;font-size:12px;color:var(--faint);align-items:center}
.pill{padding:0 7px;border-radius:3px;border:1px solid var(--border2);color:var(--muted);font-size:11.5px}
.cstats{display:flex;justify-content:space-between;align-items:baseline;font-size:12px;color:var(--faint);border-top:1px solid var(--line);padding-top:8px}
.cstats b{font:600 20px var(--fm);color:var(--text);margin-inline-end:6px}
.ctags{display:flex;flex-wrap:wrap;gap:5px}
.cdot{position:absolute;top:14px;left:14px;width:7px;height:7px;border-radius:50%;background:var(--faint)}
.cdot.ok{background:var(--green)}.cdot.bad{background:var(--red)}
.back{display:inline-flex;align-items:center;gap:6px;margin-bottom:12px;background:none;border:0;color:var(--muted);padding:4px 0}
.back:hover{color:var(--acc2)}
.chero{display:flex;gap:18px;align-items:center;flex-wrap:wrap;padding:20px;margin-bottom:14px;border-top:2px solid var(--c)}
.chero h1{font:800 24px/1.5 var(--fd);margin:0 0 4px}
.chero .grow{flex:1;min-width:220px}
.chero .num{text-align:center;padding:8px 18px;border:1px solid var(--border);border-radius:var(--r)}
.chero .num b{display:block;font:600 28px var(--fm)}
.chero .num span{font-size:12px;color:var(--faint)}
.chero a{color:var(--acc2)}
.ctopics{padding:12px 14px;margin-bottom:14px}
.clbl{font:700 13px var(--fd);align-self:center;margin-inline-end:4px}

/* الدول */
.tag.cty{border-color:color-mix(in srgb,var(--acc) 40%,var(--border));color:var(--acc2)}
.tag.cty::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--acc)}
.cgrid2{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
.ctycard{all:unset;box-sizing:border-box;cursor:pointer;display:flex;flex-direction:column;gap:6px;padding:12px 14px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg)}
.ctycard:hover{border-color:var(--border2);background:var(--hover)}
.ctycard:focus-visible{outline:1.5px solid var(--focus)}
.ctycard .top2{display:flex;align-items:center;gap:10px}
.iso{width:38px;height:28px;flex:none;display:grid;place-items:center;border:1px solid var(--border2);border-radius:4px;font:600 12px var(--fm);color:var(--acc2);background:var(--surface2)}
.iso.big{width:72px;height:52px;font-size:20px}
.iso.flag{padding:0;overflow:hidden;background:var(--surface2)}.iso.flag img{width:100%;height:100%;object-fit:cover;display:block}
.ctycard b{font:700 14.5px var(--fd)}
.ctycard .nums{display:flex;justify-content:space-between;font-size:12px;color:var(--faint)}
.ctycard .nums em{font:600 15px var(--fm);font-style:normal;color:var(--text);margin-inline-end:4px}
.cbar{height:3px;background:var(--surface2);border-radius:2px;overflow:hidden}.cbar i{display:block;height:100%;background:var(--acc)}
.regionh{font:700 13px var(--fd);color:var(--muted);margin:18px 2px 8px}
.toplist{list-style:none;margin:0;padding:6px 0}
.toplist button{all:unset;box-sizing:border-box;cursor:pointer;display:grid;grid-template-columns:34px 1fr 40px;gap:8px;align-items:center;width:100%;padding:6px 14px;font-size:13.5px}
.toplist button:hover{background:var(--hover)}
.toplist .iso{width:30px;height:22px;font-size:10.5px}
.toplist .n{font:500 12px var(--fm);color:var(--faint);text-align:left}
.toplist .cbar{grid-column:2/4;margin-top:-2px}

/* مكتبة الكتب */
.bookgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:14px}
.book{display:grid;grid-template-columns:120px minmax(0,1fr);gap:16px;padding:14px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg)}
.book:hover{border-color:var(--border2)}
.cover{width:120px;aspect-ratio:2/3;border-radius:4px;overflow:hidden;background:var(--surface2);border:1px solid var(--border);box-shadow:0 8px 20px -10px rgba(0,0,0,.6)}
.cover img{width:100%;height:100%;object-fit:cover;display:block}
.cover .phx{display:none}
.cover.ph{padding:10px;background:linear-gradient(160deg,var(--c,var(--acc)),#111 140%);color:#fff}
.cover.ph .phx{display:flex;flex-direction:column;justify-content:space-between;height:100%;font:700 12px/1.5 var(--fd);overflow:hidden}
.cover.ph small{font:500 9px var(--fm);opacity:.8}
.binfo{display:flex;flex-direction:column;gap:4px;min-width:0}
.btopic{font:600 12px var(--fd);color:var(--c,var(--acc))}
.binfo h3{margin:0;font:700 16px/1.6 var(--fd)}
.borig{font-size:12px;color:var(--faint);direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bmeta{font-size:12px;color:var(--muted)}
.binfo p{margin:2px 0 0;font-size:13.5px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.bacts{display:flex;gap:6px;margin-top:auto;padding-top:8px;flex-wrap:wrap}
.bacts .ibtn{height:32px;font-size:13px}
.bookdlg{display:grid;grid-template-columns:170px minmax(0,1fr);gap:22px;margin-top:12px}
.bookdlg .cover{width:170px}
@media (max-width:820px){.bookgrid{grid-template-columns:1fr}.book{grid-template-columns:90px 1fr}.cover{width:90px}.bookdlg{grid-template-columns:1fr}}

/* الأخبار النوعية: شريط متقلب */
.qcar{position:relative}
.qslide{min-height:178px;padding:18px 22px 12px;display:grid;grid-template-columns:96px minmax(0,1fr) auto;gap:20px;align-items:center;cursor:pointer;
  background:linear-gradient(270deg,color-mix(in srgb,var(--e,var(--red)) 12%,transparent),transparent 70%);border-inline-start:4px solid var(--e,var(--red))}
.qslide.anim{animation:qin .45s ease}
@keyframes qin{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:none}}
.qslide .clock2{text-align:center;border-inline-end:1px solid var(--border);padding-inline-end:16px}
.qslide .clock2 b{display:block;font:600 26px var(--fm);color:var(--text)}
.qslide .clock2 small{font:500 11px var(--fm);color:var(--faint)}
.qslide .meta{gap:6px 10px}
.qslide .ev{font-size:12.5px;line-height:2.1;padding:0 10px}
.qslide h3{margin:8px 0 6px;font:800 22px/1.6 var(--fd)}
.qslide p{margin:0;color:var(--muted);font-size:14.5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;max-width:110ch}
.qslide .src2{font-size:12.5px;color:var(--faint);margin-top:6px}
.qslide .read{align-self:center}
.qslide:focus-visible{outline:1.5px solid var(--focus);outline-offset:-3px}
.qctl{display:flex;align-items:center;gap:10px;padding:6px 14px 8px}
.qnav{all:unset;cursor:pointer;width:28px;height:28px;display:grid;place-items:center;border:1px solid var(--border);border-radius:var(--r);color:var(--muted);font-size:18px;line-height:1}
.qnav:hover{border-color:var(--border2);color:var(--text)}
.qdots{display:flex;gap:5px;flex-wrap:wrap;flex:1;justify-content:center}
.qdots button{all:unset;cursor:pointer;width:8px;height:8px;border-radius:2px;background:var(--border2)}
.qdots button.on{background:var(--e,var(--red));width:22px}
.qpos{font-size:11px;color:var(--faint)}
.qprog{height:2px;background:var(--line)}
.qprog i{display:block;height:100%;width:0;background:var(--e,var(--red))}
.qprog i.run{animation:qbar 6s linear forwards}
.qcar:hover .qprog i.run,.qcar:focus-within .qprog i.run{animation-play-state:paused}
@keyframes qbar{to{width:100%}}
.qempty{padding:30px 14px;color:var(--faint);font-size:13.5px;text-align:center}
@media (max-width:820px){.qslide{grid-template-columns:1fr;gap:8px}.qslide .clock2{display:flex;gap:10px;align-items:baseline;border:0;padding:0;text-align:right}.qslide h3{font-size:18px}.qslide .read{justify-self:start}}

.sanclists{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-bottom:14px}
.sl{padding:12px 14px;display:flex;flex-direction:column;gap:4px}
.sl b{font:700 14px var(--fd)}
.sl .n{font:600 22px var(--fm)}
.sl .e{font-size:12px;color:var(--red)}
.pager{display:flex;align-items:center;justify-content:center;gap:10px;padding:12px;border-top:1px solid var(--border)}
.pager .mt{font-size:12.5px;color:var(--muted)}
.tbl .del{all:unset;cursor:pointer;color:var(--faint);font-size:18px;padding:0 6px;line-height:1}
.tbl .del:hover{color:var(--red)}
.updbar{display:flex;align-items:center;justify-content:center;gap:12px;padding:8px 16px;background:linear-gradient(90deg,#0A3D7A,#1EA7FF,#0A3D7A);color:#fff;font:700 14px var(--fd)}
.updbar .ibtn{height:30px}
/* انقطاع الإنترنت */
.netgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.netc{padding:12px 14px;display:flex;flex-direction:column;gap:4px;border-top:3px solid var(--nc)}
.netc b{font:700 15px var(--fd)}
.netc .st{font:700 12.5px var(--fd);color:var(--nc)}
.netc .st::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--nc);margin-inline-end:6px;box-shadow:0 0 8px var(--nc)}
.netc small{color:var(--faint);font-size:11.5px}
.netc a{font-size:12px;color:var(--acc2)}
/* الخط الزمني */
.tlchart{padding:14px 16px;margin:14px 0}
.tlbars{display:flex;align-items:flex-end;gap:4px;height:120px}
.tlbar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:stretch;gap:2px;min-width:6px;position:relative}
.tlbar i{display:block;background:var(--acc);opacity:.45;border-radius:2px 2px 0 0}
.tlbar i.q{background:var(--red);opacity:.9}
.tlbar span{position:absolute;bottom:-18px;left:0;right:0;text-align:center;font:500 9.5px var(--fm);color:var(--faint);white-space:nowrap}
.tllegend{display:flex;gap:16px;margin-top:24px;font-size:12px;color:var(--muted)}
.tllegend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-inline-end:6px;vertical-align:-1px}
.tl{position:relative;padding-inline-start:28px}
.tl::before{content:"";position:absolute;right:9px;top:0;bottom:0;width:2px;background:linear-gradient(var(--acc),transparent)}
.tlday{font:800 15px var(--fd);margin:18px 0 8px;position:relative}
.tlday::before{content:"";position:absolute;right:-24px;top:7px;width:12px;height:12px;border-radius:50%;background:var(--acc);box-shadow:0 0 10px var(--acc)}
.tlit{all:unset;box-sizing:border-box;cursor:pointer;display:grid;grid-template-columns:58px 1fr;gap:10px;width:100%;padding:9px 12px;margin-bottom:6px;border:1px solid var(--border);border-inline-start:3px solid var(--e,var(--border2));border-radius:var(--r);background:var(--surface)}
.tlit:hover{background:var(--hover)}
.tlit time{font:600 13px var(--fm);color:var(--text)}
.tlit .t{font:600 14px/1.65 var(--fd)}
/* ادعم المشروع */
.ibtn.support{color:#F43F5E;border-color:rgba(244,63,94,.45);font-weight:700}
.ibtn.support svg{fill:rgba(244,63,94,.25)}
.ibtn.support:hover{background:rgba(244,63,94,.12)}
.supdlg{width:min(420px,92vw);padding:0;border:1px solid var(--border2);border-radius:var(--r-lg);background:var(--bg2);color:var(--text)}
.supdlg::backdrop{background:rgba(2,6,14,.6)}
.suphead{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid var(--border)}
.suphead svg{color:#F43F5E;fill:rgba(244,63,94,.3)}.suphead b{flex:1;font:800 16px var(--fd)}
.suphead .x{background:none;border:0;color:var(--muted);font-size:22px;cursor:pointer}
.supdlg p{margin:14px 18px;line-height:1.9;font-size:14px;color:var(--muted)}
.supacts{display:flex;flex-direction:column;gap:10px;margin:0 18px}.supacts .ibtn{height:42px;font-size:14.5px}
.supdlg .supdev{font-size:12.5px;text-align:center;color:var(--faint)}
/* لوحة الأوامر */
#cmdk{position:fixed;inset:0;z-index:210;background:rgba(2,6,14,.6);backdrop-filter:blur(3px);display:flex;justify-content:center;align-items:flex-start;padding-top:12vh}
.cmdbox{width:min(640px,94vw);background:var(--surface);border:1px solid var(--border2);border-radius:12px;box-shadow:0 30px 80px -20px rgba(0,0,0,.8),0 0 30px -8px rgba(30,167,255,.5);overflow:hidden}
#cmdin{width:100%;height:54px;border:0;border-bottom:1px solid var(--border);background:transparent;color:var(--text);font:500 17px "IBM Plex Sans Arabic";padding:0 18px;outline:none}
#cmdlist{list-style:none;margin:0;padding:6px;max-height:50vh;overflow:auto}
#cmdlist li{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;cursor:pointer;font-size:14.5px}
#cmdlist li .k{margin-inline-start:auto;font:500 11px var(--fm);color:var(--faint)}
#cmdlist li.on{background:var(--accbg);box-shadow:inset 0 0 0 1px var(--border2)}
#cmdlist li svg{color:var(--acc)}
.cmdhint{padding:8px 14px;font-size:11px;color:var(--faint);border-top:1px solid var(--border)}
/* وسوم الإعلام والعناوين المعدّلة */
.ml{font:600 10.5px var(--fd);padding:0 7px;border-radius:3px;line-height:1.9;border:1px solid var(--border2);color:var(--muted);background:var(--surface2)}
.ml.gov{border-color:#E11D48;color:#FB7185}
.ed{all:unset;cursor:pointer;font:600 10.5px var(--fd);padding:0 7px;border-radius:3px;line-height:1.9;border:1px dashed var(--gold);color:var(--gold)}
.edlist{list-style:none;margin:0;padding:0;border:1px solid var(--border);border-radius:var(--r)}
.edlist li{padding:8px 12px;border-top:1px solid var(--line);font-size:13.5px}.edlist li:first-child{border:0}
.edlist del{color:var(--red);text-decoration-thickness:1px}.edlist ins{color:var(--green);text-decoration:none}
/* الصفحات الجديدة */
.tabs2{display:flex;gap:4px;margin-bottom:14px;border-bottom:1px solid var(--border)}
.tabs2 button{border:0;background:none;padding:9px 14px;color:var(--muted);font:600 13.5px var(--fd);border-bottom:2px solid transparent;margin-bottom:-1px}
.tabs2 button.on{color:var(--text);border-color:var(--acc)}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.tbl th,.tbl td{padding:9px 12px;border-bottom:1px solid var(--border);text-align:right;vertical-align:top}
.tbl th{color:var(--faint);font:600 12px var(--fd);background:var(--surface2)}
.tbl td .sub{display:block;color:var(--faint);font-size:12px;margin-top:2px}
.tbl tr:hover td{background:var(--hover)}
.sname{font:700 14px var(--fm);direction:ltr;text-align:right}
.pg{font:600 11px var(--fd);padding:1px 8px;border-radius:3px;border:1px solid var(--border2);color:var(--muted);white-space:nowrap;display:inline-block;margin:1px}
.pg.t{border-color:var(--red);color:#FB7185}
.newdot{display:inline-block;padding:0 7px;border-radius:3px;background:var(--red);color:#fff;font:700 10.5px var(--fd);line-height:1.9}
.askbox{padding:16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.askbox input{flex:1;min-width:260px;height:46px;font-size:16px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 14px}
.askbox input:focus{outline:none;border-color:var(--acc)}
.askgrid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:18px;align-items:start}
.askans{min-height:200px}
.askans .wdoc sup a{color:var(--acc2);text-decoration:none;font:600 11px var(--fm)}
.askref{list-style:none;margin:0;padding:0;counter-reset:r}
.askref li{border-top:1px solid var(--line)}.askref li:first-child{border:0}
.askref button{all:unset;box-sizing:border-box;cursor:pointer;display:grid;grid-template-columns:26px 1fr;gap:8px;width:100%;padding:8px 12px;font-size:13px}
.askref button:hover{background:var(--hover)}
.askref .k{font:600 11px var(--fm);color:var(--acc2);text-align:center;border:1px solid var(--border2);border-radius:3px;height:20px;line-height:20px}
.chipsq{display:flex;flex-wrap:wrap;gap:6px;flex-basis:100%}
.chipsq button{all:unset;cursor:pointer;font-size:12.5px;padding:3px 10px;border:1px solid var(--border);border-radius:14px;color:var(--muted)}
.chipsq button:hover{border-color:var(--acc);color:var(--text)}
.casegrid{display:grid;grid-template-columns:320px minmax(0,1fr);gap:18px;align-items:start}
.caselist{list-style:none;margin:0;padding:0}
.caselist li button{all:unset;box-sizing:border-box;cursor:pointer;display:block;width:100%;padding:10px 14px;border-top:1px solid var(--line)}
.caselist li button:hover,.caselist li button.on{background:var(--hover)}
.caselist li button.on{box-shadow:inset -3px 0 0 var(--acc)}
.caselist b{font:700 14px var(--fd);display:block}
.caselist small{color:var(--faint);font-size:12px}
.citem{padding:12px 16px;border-top:1px solid var(--line)}
.citem:first-child{border:0}
.citem h4{margin:4px 0;font:700 15px/1.6 var(--fd)}
.citem textarea{width:100%;min-height:54px;margin-top:6px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:8px 10px;font:14px "IBM Plex Sans Arabic";color:var(--text);resize:vertical}
.citem .row{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:6px}
.casepick{position:fixed;z-index:90;inset:0;display:grid;place-items:center;background:rgba(2,5,10,.6)}
.casepick .box{width:min(420px,92vw);padding:16px;display:flex;flex-direction:column;gap:10px}
.casepick input,.casepick textarea{background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:8px 12px;font:14px "IBM Plex Sans Arabic";color:var(--text)}
.casepick .opts{max-height:240px;overflow:auto;display:flex;flex-direction:column;gap:4px}
.casepick .opts button{all:unset;cursor:pointer;padding:8px 12px;border:1px solid var(--border);border-radius:var(--r);font-size:14px}
.casepick .opts button:hover{border-color:var(--acc)}
.arcsnap{border:1px solid var(--border);border-radius:var(--r);padding:12px 16px;background:var(--surface2);margin-top:10px}
.lanbox{padding:14px 16px;margin-bottom:16px;display:flex;flex-direction:column;gap:10px}
.lanbox .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.lanbox input[type=password]{height:34px;width:140px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 10px;color:var(--text)}
.lanbox code{font:13px var(--fm);direction:ltr;display:inline-block;background:var(--surface2);border:1px solid var(--border);padding:2px 8px;border-radius:4px}
@media (max-width:1100px){.askgrid,.casegrid{grid-template-columns:1fr}}

/* التحقق من الخبر */
.vf{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:4px;font:600 11px var(--fd);padding:0 8px;border-radius:3px;line-height:2;border:1px solid var(--border2);color:var(--muted)}
.vf.v3{border-color:var(--green);color:var(--green);background:color-mix(in srgb,var(--green) 10%,transparent)}
.vf.v2{border-color:var(--gold);color:var(--gold)}
.vf.v1{border-style:dashed}
.vf:hover{filter:brightness(1.2)}
.vf:focus-visible{outline:1.5px solid var(--focus)}
.vlist{list-style:none;margin:0;padding:0;border:1px solid var(--border);border-radius:var(--r)}
.vlist li{border-top:1px solid var(--line)}.vlist li:first-child{border:0}
.vlist button{all:unset;box-sizing:border-box;cursor:pointer;display:block;width:100%;padding:8px 12px;font-size:14px}
.vlist button:hover{background:var(--hover)}
.vlist .meta{font-size:11.5px}

/* الإنذار المبكر */
.bell{position:relative}
.bell .n{position:absolute;top:-5px;left:-5px;min-width:18px;height:18px;padding:0 4px;border-radius:9px;background:var(--red);color:#fff;font:700 11px/18px var(--fm);text-align:center}
.bell.hot svg{animation:ring 1.4s ease-in-out infinite}
@keyframes ring{0%,100%{transform:rotate(0)}10%{transform:rotate(14deg)}20%{transform:rotate(-12deg)}30%{transform:rotate(8deg)}40%{transform:rotate(0)}}
.alertbar{display:flex;flex-direction:column;gap:8px;margin-bottom:18px}
.al{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:14px;align-items:center;padding:12px 16px;border:1px solid var(--border);border-inline-start:4px solid var(--lc);border-radius:var(--r-lg);background:linear-gradient(270deg,color-mix(in srgb,var(--lc) 12%,var(--surface)),var(--surface) 60%)}
.al .lv{font:800 12px var(--fd);color:#fff;background:var(--lc);padding:2px 10px;border-radius:3px;white-space:nowrap}
.al b{font:700 15px/1.7 var(--fd)}
.al small{display:block;color:var(--faint);font:500 11.5px var(--fm)}
.al .acts2{display:flex;gap:6px}
.al .acts2 .ibtn{height:32px;font-size:13px}

/* الخريطة */
.mapwrap{position:relative;height:calc(100vh - 290px);min-height:480px;border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface2)}
#map{position:absolute;inset:0}
#map.mapdark .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9) saturate(.6)}
.mappanel{position:absolute;top:12px;right:12px;z-index:500;width:270px;padding:12px;display:flex;flex-direction:column;gap:10px;background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(6px);border:1px solid var(--border2);border-radius:var(--r-lg)}
.mappanel .t{font:700 13.5px var(--fd)}
.mappanel .seg button{padding:4px 9px;font-size:12px}
.maplegend{display:flex;flex-direction:column;gap:3px;max-height:200px;overflow:auto}
.maplegend label{display:flex;align-items:center;gap:7px;font-size:12.5px;cursor:pointer}
.maplegend i{width:10px;height:10px;border-radius:50%;background:var(--e);flex:none}
.maplegend em{margin-inline-start:auto;font:500 11px var(--fm);font-style:normal;color:var(--faint)}
.mapcount{font:500 11.5px var(--fm);color:var(--faint)}
.leaflet-popup-content{direction:rtl;text-align:right;font:13.5px/1.7 "IBM Plex Sans Arabic",sans-serif;min-width:230px}
.leaflet-popup-content .pt{font:700 14px/1.6 "Noto Kufi Arabic",sans-serif;margin:6px 0}
.leaflet-popup-content .ibtn{height:30px;font-size:12.5px;margin-top:6px}
.leaflet-container{background:var(--surface2);font-family:"IBM Plex Sans Arabic",sans-serif}
.mapnote{position:absolute;inset:0;display:grid;place-items:center;color:var(--muted);text-align:center;padding:30px}
.vidwrap{position:relative;aspect-ratio:16/9;margin-top:14px;border-radius:var(--r);overflow:hidden;border:1px solid var(--border)}
.vidwrap iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.badge.vid{background:#DC2626;color:#fff}
.plat{font:600 10px var(--fm);padding:0 6px;border-radius:3px;border:1px solid var(--border2);color:var(--muted);letter-spacing:.04em}

/* بوت تيليغرام */
.botgrid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:18px;align-items:start}
.bbody{padding:16px;display:flex;flex-direction:column;gap:14px}
.bbody label.f{display:flex;flex-direction:column;gap:6px;font:600 13px var(--fd)}
.bbody input[type=text],.bbody input[type=password],.bbody input[type=number],.bbody select{height:38px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 12px;font:400 14px "IBM Plex Sans Arabic";color:var(--text);max-width:none}
.bbody .ltr{direction:ltr;text-align:left}
.bbody .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.bbody .row input{flex:1;min-width:200px}
.bbody .hint{font:400 12.5px/1.9 "IBM Plex Sans Arabic";color:var(--faint)}
.bbody ol{margin:2px 0 0;padding-inline-start:20px}
.bbody code{font:12px var(--fm);background:var(--surface2);border:1px solid var(--border);border-radius:3px;padding:0 5px}
.cks{display:flex;flex-wrap:wrap;gap:8px}
.cks label{display:inline-flex;align-items:center;gap:6px;font:500 13px "IBM Plex Sans Arabic";padding:4px 10px;border:1px solid var(--border);border-radius:var(--r);cursor:pointer}
.cks label:has(input:checked){border-color:var(--acc);background:var(--accbg)}
.opt{display:flex;align-items:flex-start;gap:8px;font:500 13.5px "IBM Plex Sans Arabic"}
.opt small{display:block;color:var(--faint);font-size:12px}
.chatlist{display:flex;flex-direction:column;gap:6px}
.chatlist button{all:unset;cursor:pointer;padding:6px 10px;border:1px solid var(--border);border-radius:var(--r);font-size:13px}
.chatlist button:hover{border-color:var(--acc)}
.bigtoggle{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface2)}
.bigtoggle b{font:700 14.5px var(--fd)}
.sw{position:relative;width:46px;height:26px;flex:none}
.sw input{opacity:0;width:0;height:0}
.sw span{position:absolute;inset:0;border-radius:13px;background:var(--border2);cursor:pointer;transition:.2s}
.sw span::before{content:"";position:absolute;width:20px;height:20px;top:3px;right:3px;border-radius:50%;background:#fff;transition:.2s}
.sw input:checked+span{background:var(--green)}
.sw input:checked+span::before{right:23px}
.sw input:focus-visible+span{outline:1.5px solid var(--focus)}
.bflt{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0}.bflt b{display:block;font-size:13px;margin-bottom:6px}
.bflt textarea{width:100%;box-sizing:border-box;resize:vertical;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:8px 10px;color:var(--text);font:14px/1.8 var(--fb,inherit)}
.bprev{margin-top:8px;font-size:13px}.bprev ul{list-style:none;margin:8px 0 0;padding:0;display:flex;flex-direction:column;gap:6px}
.bprev li{display:flex;flex-direction:column;padding:6px 10px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface)}
.bprev li .t{all:unset;cursor:pointer;font-weight:600}.bprev li span{font-size:11.5px;color:var(--faint)}
@media (max-width:820px){.bflt{grid-template-columns:1fr}}
.dailygrid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:18px;align-items:start}
@media (max-width:1100px){.dailygrid{grid-template-columns:1fr}}
.dsel{height:34px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);color:var(--text);padding:0 8px}
.dailybody{padding:18px 22px;line-height:2}
.dailybody h2{font:800 17px var(--fd);margin:22px 0 8px;color:var(--acc)}
.dailybody h3{font:700 15px var(--fd);margin:14px 0 4px}.dailybody h3 small{color:var(--faint);font-weight:400}
.dailybody ol,.dailybody ul{margin:0;padding-inline-start:22px}.dailybody li{margin-bottom:6px}
.dailybody li a{color:var(--text);text-decoration:none}.dailybody li a:hover{color:var(--acc)}
.dailybody li span{color:var(--faint);font-size:12.5px}.dailybody p{margin:0 0 10px;color:var(--muted)}
.dailybody .dmeta{font-size:12px;color:var(--faint)}
.dstat{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}
.dstat span{border:1px solid var(--border);border-radius:var(--r);padding:10px;text-align:center;font-size:12.5px;color:var(--muted);background:var(--surface)}
.dstat b{display:block;font:700 22px var(--fm);color:var(--text)}
.chtabs{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chtabs button{all:unset;cursor:pointer;padding:7px 14px;border:1px solid var(--border);border-radius:var(--r);font:600 13px var(--fd);background:var(--surface)}
.chtabs button.on{border-color:var(--acc);background:var(--accbg);color:var(--acc)}
.chtabs button.add{border-style:dashed;color:var(--muted)}
.chbox{border:1px solid var(--border2);border-radius:var(--r-lg);padding:14px;display:flex;flex-direction:column;gap:14px;background:var(--surface)}
.chsum{display:flex;flex-direction:column;gap:4px;margin:10px 0}
.chsum button{all:unset;cursor:pointer;display:flex;align-items:center;gap:8px;padding:4px 10px;border-radius:var(--r);border:1px solid transparent}
.chsum button.on{border-color:var(--border2);background:var(--surface2)}
.chsum i{width:8px;height:8px;border-radius:50%;background:var(--faint)}.chsum i.g{background:var(--green)}.chsum i.w{background:#F59E0B}
.chsum b{flex:1;font-family:inherit}.chsum span{font-size:12px;color:var(--faint)}
.chst{border-top:1px solid var(--line);padding-top:8px;margin-top:4px}
.cmdbox2{display:flex;flex-direction:column;gap:10px;margin-top:6px}
.cmdbox2 textarea{width:100%;box-sizing:border-box;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:8px 10px;color:var(--text);font:14px/1.7 var(--fm)}
.cmdlist{display:flex;flex-wrap:wrap;gap:6px}.cmdlist code{font-size:12.5px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;background:var(--surface2)}
.bstat{padding:14px 16px;font-size:13.5px;line-height:2.1;color:var(--muted)}
.bstat b{color:var(--text);font:600 13.5px var(--fm)}
@media (max-width:1100px){.botgrid{grid-template-columns:1fr}}

/* كاتب المقالات */
.wgrid{display:grid;grid-template-columns:380px minmax(0,1fr);gap:18px;align-items:start}
.wform{padding:16px;display:flex;flex-direction:column;gap:12px;position:sticky;top:100px}
.wform label{display:flex;flex-direction:column;gap:6px;font:600 13px var(--fd)}
.wform textarea,.wform input,.wform select{font:400 14px "IBM Plex Sans Arabic";background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:9px 12px;color:var(--text);max-width:none;height:auto}
.wform textarea{min-height:84px;resize:vertical}
.wform textarea:focus,.wform input:focus,.wform select:focus{outline:none;border-color:var(--acc)}
.wform .row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.wform .chk{flex-direction:row;align-items:center;gap:8px;font:500 13px "IBM Plex Sans Arabic"}
.wform .hint{font:400 12px "IBM Plex Sans Arabic";color:var(--faint)}
.wform .go{height:44px;font-size:15px}
.wsrc{font-size:12.5px;color:var(--muted);max-height:180px;overflow:auto;border:1px solid var(--border);border-radius:var(--r);padding:6px 10px;background:var(--surface2)}
.wsrc div{padding:3px 0;border-top:1px solid var(--line)}.wsrc div:first-child{border:0}
.wkey{padding:12px 16px;margin-bottom:14px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.wkey input{flex:1;min-width:240px;height:36px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:0 12px;direction:ltr}
.wkey select{height:36px}
.wkey .full{flex-basis:100%;font-size:12.5px;color:var(--muted);line-height:1.9}
.wkey ol{margin:4px 0 0;padding-inline-start:20px}
.wkey code{font:12px var(--fm);background:var(--surface2);border:1px solid var(--border);border-radius:3px;padding:0 5px;direction:ltr;display:inline-block}
.wkey .badge2{font:600 11px var(--fd);padding:1px 8px;border-radius:3px;background:var(--accbg);color:var(--acc2)}
.wprog{flex-basis:100%;height:6px;background:var(--surface2);border-radius:3px;overflow:hidden}.wprog i{display:block;height:100%;background:var(--acc)}
.sugg{display:flex;flex-direction:column;gap:6px;flex-basis:100%}
.sugg div{display:flex;align-items:center;gap:10px;font-size:13px}
.wout{min-height:420px}
.wout .boxh .sp{flex:1}
.wdoc{padding:26px 34px 34px;font:16.5px/2.05 "IBM Plex Sans Arabic";max-width:820px}
.wdoc h1{font:800 28px/1.5 var(--fd);margin:0 0 18px}
.wdoc h2{font:700 20px/1.6 var(--fd);margin:28px 0 10px}
.wdoc h3{font:700 17px/1.6 var(--fd);margin:22px 0 8px}
.wdoc p{margin:0 0 16px}
.wdoc ul,.wdoc ol{margin:0 0 16px;padding-inline-start:22px}
.wdoc a{color:var(--acc2);word-break:break-all}
.wdoc .cursor{display:inline-block;width:8px;height:18px;background:var(--acc);vertical-align:-3px;animation:blink2 1s steps(2) infinite}
@keyframes blink2{50%{opacity:0}}
.wempty{padding:60px 30px;text-align:center;color:var(--faint)}
.wempty b{display:block;color:var(--text);font:700 17px var(--fd);margin-bottom:8px}
.wstat{font:500 11.5px var(--fm);color:var(--faint)}
.warts{list-style:none;margin:0;padding:0}
.warts li{display:flex;align-items:center;gap:8px;border-top:1px solid var(--line);padding:8px 14px}
.warts li:first-child{border:0}
.warts button.t{all:unset;cursor:pointer;flex:1;font-size:13.5px}
.warts button.t:hover{color:var(--acc2)}
.warts .x{background:none;border:0;color:var(--faint);font-size:16px}
@media (max-width:1100px){.wgrid{grid-template-columns:1fr}.wform{position:static}}

/* الأخبار النوعية */
.ev{display:inline-flex;align-items:center;gap:5px;font:700 11px var(--fd);padding:0 8px;border-radius:3px;line-height:2;color:#fff;background:var(--e)}
.ev::before{content:"";width:5px;height:5px;border-radius:50%;background:#fff;opacity:.85}
.qualbox{margin-bottom:18px;border-top:3px solid var(--red);position:relative;overflow:hidden}
.qualbox::before{content:"";position:absolute;inset:0 0 auto 0;height:60px;background:linear-gradient(180deg,rgba(244,63,94,.08),transparent);pointer-events:none}
.qualbox .boxh{font-size:15.5px}
.qualbox .boxh .pulse{width:9px;height:9px;border-radius:50%;background:var(--red);animation:pulse 2s infinite}
.qtypes{display:flex;flex-wrap:wrap;gap:6px;padding:10px 14px;border-bottom:1px solid var(--border)}
.qt{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:4px;border:1px solid var(--border);font-size:12.5px;color:var(--muted)}
.qt i{width:8px;height:8px;border-radius:2px;background:var(--e)}
.qt b{font:600 11.5px var(--fm);color:var(--text)}
.qt:hover{border-color:var(--e)}
.qt.on{border-color:var(--e);background:color-mix(in srgb,var(--e) 16%,transparent);color:var(--text)}
.qt:focus-visible{outline:1.5px solid var(--focus)}
.qlist{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr))}
.qlist li{border-top:1px solid var(--line)}
.qi{all:unset;box-sizing:border-box;cursor:pointer;display:grid;grid-template-columns:52px minmax(0,1fr);gap:12px;width:100%;padding:11px 14px;border-inline-start:3px solid var(--e)}
.qi:hover{background:var(--hover)}
.qi:focus-visible{outline:1.5px solid var(--focus);outline-offset:-2px}
.qi time{font:600 13px/1.4 var(--fm);color:var(--text);text-align:center}
.qi time small{display:block;font:500 10px var(--fm);color:var(--faint)}
.qi .t{display:block;font:600 14.5px/1.7 var(--fd);margin:3px 0 2px}
.qi.seen .t{color:var(--faint)}
.qi .s{font-size:11.5px;color:var(--faint)}
.qempty{padding:20px 14px;color:var(--faint);font-size:13px}
.qmore{display:flex;justify-content:center;padding:10px;border-top:1px solid var(--line)}

/* جدول صحة المصادر */
td.lnk a{color:var(--acc2);text-decoration:none;font-size:12.5px;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
td.lnk a:hover{text-decoration:underline}
td.lnk .u{display:block;font:400 11px var(--fm);color:var(--faint);direction:ltr;text-align:left;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
tr.broken td{background:rgba(244,63,94,.04)}
.htools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:10px}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:9px 12px;border-bottom:1px solid var(--border);text-align:right;vertical-align:top}
th{color:var(--faint);font:600 12px var(--fd);background:var(--surface2)}
tr:last-child td{border-bottom:0}
td.err{color:var(--faint);font-size:12px;max-width:340px;word-break:break-word}

.trbox{padding:4px 0;margin-bottom:16px}
.trrow{display:grid;grid-template-columns:150px 110px 1fr;gap:10px;padding:8px 14px;border-top:1px solid var(--line);font-size:13px;align-items:center}
.trrow .o{color:var(--faint);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* نافذة القراءة */
dialog{width:min(820px,calc(100% - 24px));max-height:90vh;padding:0;background:var(--surface);color:var(--text);border:1px solid var(--border2);border-radius:var(--r-lg);box-shadow:0 30px 90px -20px rgba(0,0,0,.7)}
dialog::backdrop{background:rgba(2,5,10,.7);backdrop-filter:blur(3px)}
.dlghead{position:sticky;top:0;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 24px;background:var(--surface);border-bottom:1px solid var(--border);border-top:3px solid var(--acc);z-index:1}
.dlgbody{padding:8px 28px 28px}
.dossier{margin-top:12px;font:500 11px var(--fm);letter-spacing:.14em;color:var(--acc)}
.dlgbody h2{font:800 22px/1.65 var(--fd);margin:6px 0 10px}
.dlgbody .lead{color:var(--muted);font-size:16px}
.dlgbody h4{font:700 14px var(--fd);color:var(--acc2);margin:24px 0 10px;display:flex;align-items:center;gap:10px}
.dlgbody h4::after{content:"";flex:1;height:1px;background:var(--border)}
.dlgbody #full p{font-size:16.5px;line-height:2.05;margin:0 0 14px;max-width:70ch}
.dlgbody .err{color:var(--muted);padding:12px 14px;border:1px solid var(--border);border-inline-start:3px solid var(--red);border-radius:var(--r);background:var(--surface2)}
.dlgbody .note{color:var(--faint);font-size:13px}
.dlgacts{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.spinner{color:var(--muted);padding:10px 0}
.spinner::before{content:"";display:inline-block;width:14px;height:14px;border:2px solid var(--border2);border-top-color:var(--acc);border-radius:50%;animation:rot 1s linear infinite;margin-inline-end:10px;vertical-align:-2px}
@keyframes rot{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:22px;left:50%;transform:translate(-50%,10px);background:var(--text);color:var(--bg);padding:9px 20px;border-radius:var(--r);font-weight:600;z-index:80;opacity:0;pointer-events:none;transition:opacity .2s,transform .2s}
.toast.show{opacity:1;transform:translate(-50%,0)}

@media (max-width:1400px){.dashgrid,.secgrid{grid-template-columns:minmax(0,1fr) 300px}}
@media (max-width:1250px){.dashgrid,.secgrid{grid-template-columns:1fr}.rail{position:static;max-height:none}.kpis{grid-template-columns:1fr 1fr}.clock:nth-child(n+4){display:none}}
@media (max-width:1600px){.clock:nth-child(n+3){display:none}.top .ibtn .lbltxt{display:none}}
@media (max-width:1250px){.clocks{display:none}}
@media (max-width:820px){
  .statusbar .hide-sm,.clocks{display:none}
  .top{flex-wrap:wrap;gap:10px;padding:10px 12px}.search{order:5;max-width:none;flex-basis:100%;margin:0}
  .ibtn .lbltxt{display:none}
  .wrap{padding:14px 12px 40px}
  .layout{grid-template-columns:1fr}
  .sidenav{position:static;height:auto;flex-direction:row;overflow-x:auto;border-left:0;border-bottom:1px solid var(--border);padding:6px}
  .sidenav nav{display:flex;gap:4px}.navgrp,.sidefoot,.navi .bar,.navi.on::before{display:none}.navi{width:auto;white-space:nowrap}.kpis{grid-template-columns:1fr}.boards{grid-template-columns:1fr}
  .item{grid-template-columns:1fr;gap:6px}.item .when{display:flex;gap:8px;text-align:right;border-inline-end:0;border-bottom:2px solid var(--c);padding:0 0 4px;width:max-content}
  .item.lead{grid-template-columns:1fr}.item.lead h3{font-size:19px}
  .ticker .lbl{width:auto}.ticker .lbl em{display:none}
  .pagehead h1{font-size:23px}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important}
  .ticker .run{position:static}.ticker .track{overflow-x:auto;mask-image:none}
}
</style>
</head>
<body>
<div class="chrome">
  <div class="statusbar">
    <span><span class="dot"></span><b>ONLINE</b></span>
    <span id="utcnow" class="mt"></span>
    <span class="hide-sm">OSINT MONITORING PLATFORM</span>
    <span class="sp"></span>
    <span class="hide-sm" id="sbSources"></span>
    <span class="hide-sm" id="sbTr"></span>
  </div>
  <header class="top">
    <a class="brand" href="#" data-cat="dash">
      <span class="mark" aria-hidden="true"><svg viewBox="0 0 28 28" fill="none" stroke="currentColor" style="color:var(--acc)">
        <circle cx="14" cy="14" r="11" stroke-width="1.2" opacity=".6"/><circle cx="14" cy="14" r="6.5" stroke-width="1" opacity=".45"/>
        <path d="M14 3v22M3 14h22" stroke-width=".8" opacity=".3"/>
        <g class="rot"><path d="M14 14L14 3A11 11 0 0 1 23.5 8.5Z" fill="currentColor" stroke="none" opacity=".35"/></g>
        <circle cx="19" cy="9" r="1.4" fill="var(--red)" stroke="none"/></svg></span>
      <span><b>مركز أبو زبيدة للتتبع والرصد</b><small>ABU ZUBAIDA · OSINT CENTER</small></span>
    </a>
    <label class="search"><svg class="i" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>
      <input id="q" type="search" placeholder="ابحث في الأخبار والدراسات والمصادر…" autocomplete="off" aria-label="بحث"><kbd>/</kbd></label>
    <span class="sp"></span>
    <div class="clocks" id="clocks" aria-label="التوقيت في عواصم العالم"></div>
    <button class="ibtn support" id="supportbtn" title="ادعم المشروع"><svg class="i" viewBox="0 0 24 24"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg><span>ادعم المشروع</span></button>
    <button class="ibtn primary" id="refresh"><svg class="i" viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7L20 8M20 3v5h-5"/></svg><span class="lbltxt">تحديث</span></button>
    <button class="ibtn" id="cmdbtn" title="لوحة الأوامر (Ctrl+K)" aria-label="لوحة الأوامر"><svg class="i" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><span class="mt lbltxt" style="font-size:11px">Ctrl K</span></button>
    <span id="bell" hidden><span id="belln" hidden></span></span>
    <button class="ibtn" id="tkToggle" aria-pressed="true" title="إظهار أو إخفاء الأشرطة"><svg class="i" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h10"/></svg><span class="lbltxt" id="tkTxt">الأشرطة</span></button>
    <div class="skins" role="group" aria-label="نمط التصميم">
      <button data-skin="neon" title="نيون أزرق"><i style="background:#1EA7FF;box-shadow:0 0 8px #1EA7FF"></i></button>
      <button data-skin="ops" title="غرفة العمليات"><i style="background:#2DD4BF"></i></button>
      <button data-skin="gold" title="ذهبي"><i style="background:#C9A45C"></i></button>
      <button data-skin="light" title="نهاري"><i style="background:#EEF1F5"></i></button>
    </div>
  </header>
</div>

<div class="tickers" id="tickers">
  <div class="ticker" style="--tc:#E11D48" aria-label="العناوين العاجلة"><span class="lbl">عاجل<em>01</em></span><div class="track"><div class="run" id="tk-breaking"></div></div></div>
  <div class="ticker" style="--tc:#C2410C" aria-label="أخبار الحروب"><span class="lbl">الحروب<em>02</em></span><div class="track"><div class="run" id="tk-war"></div></div></div>
  <div class="ticker" style="--tc:#6D28D9" aria-label="آخر المقالات"><span class="lbl">آخر المقالات<em>03</em></span><div class="track"><div class="run" id="tk-articles"></div></div></div>
  <div class="ticker" style="--tc:#047857" aria-label="الأخبار الاقتصادية"><span class="lbl">اقتصاد<em>04</em></span><div class="track"><div class="run" id="tk-economy"></div></div></div>
</div>

<div class="updbar" id="updbar" hidden><span id="updtxt"></span><button class="ibtn primary" id="updgo">إعادة التشغيل الآن</button><button class="ibtn" id="updlater">لاحقاً</button></div>
<div class="layout">
<aside class="sidenav" aria-label="الأقسام">
  <nav id="nav"></nav>
  <div class="sidefoot" id="sidefoot"></div>
</aside>
<div class="wrap">
  <div id="pagehead" class="pagehead">
    <div><span class="code" id="pcode"></span><h1 id="title"></h1><p id="desc"></p></div>
    <span class="live" id="live"><i></i>مباشر</span>
  </div>
  <div id="centerhead" hidden></div>
  <div id="countryhead" hidden></div>

  <!-- لوحة القيادة -->
  <section id="dash" hidden>
    <div class="alertbar" id="dashAlerts"></div>
    <section class="box qualbox" id="qualbox">
      <div class="boxh"><span class="pulse" aria-hidden="true"></span>أخبار نوعية<span class="sub">CRITICAL EVENTS / آخر 24 ساعة</span><span class="sp"></span><button class="lnk" data-cat="qual">عرض الكل</button></div>
      <div class="qtypes" id="qtypes"></div>
      <div class="qcar" id="qcar" aria-live="polite">
        <div class="qslide" id="qslide"></div>
        <div class="qctl">
          <button class="qnav" id="qprev" aria-label="الخبر السابق">›</button>
          <div class="qdots" id="qdots"></div>
          <span class="qpos mt" id="qpos"></span>
          <button class="qnav" id="qnext" aria-label="الخبر التالي">‹</button>
        </div>
        <div class="qprog"><i id="qprog"></i></div>
      </div>
    </section>
    <div class="kpis">
      <div class="box kpi threat" id="kThreat"></div>
      <div class="box kpi" id="kHour"></div>
      <div class="box kpi" id="kSrc"></div>
      <div class="box kpi" id="kTr"></div>
    </div>
    <div class="dashgrid">
      <div class="boards" id="boards"></div>
      <div class="rail">
        <div class="box"><div class="boxh" style="--c:#38BDF8"><svg class="i" viewBox="0 0 24 24"><path d="M21 4L3 11l6 2 2 6 3-4 5 4z"/></svg>آخر منشورات تيليغرام<span class="sp"></span><button class="lnk" data-cat="tweets">كل القنوات</button></div><ul class="twl" id="dashTg"></ul></div>
        <div class="box"><div class="boxh"><svg class="i" viewBox="0 0 24 24"><path d="M12 3c3 4 5 6 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-6 1-9z"/></svg>المواضيع الساخنة<span class="sp"></span><span class="sub">48H</span></div><div class="tags" id="dashTags"></div></div>
        <div class="box"><div class="boxh"><svg class="i" viewBox="0 0 24 24"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg>الدول الأكثر حضوراً<span class="sp"></span><button class="lnk" data-cat="countries">كل الدول</button></div><ul class="toplist" id="dashCty"></ul></div>
      </div>
    </div>
  </section>

  <section class="box addpanel" id="kwpanel" hidden>
    <div class="addrow">
      <input id="kwinput" placeholder="مثال: هيئة تحرير الشام، الحدود التركية، drone strike" maxlength="60">
      <button class="ibtn primary" id="kwadd">أضف كلمة</button>
    </div>
    <div class="chips" id="kwchips"></div>
  </section>

  <!-- تيليغرام -->
  <section id="tgview" hidden>
    <div class="box addpanel">
      <div class="addrow">
        <select id="tgplat" aria-label="المنصة"><option value="telegram">تيليغرام</option><option value="bluesky">Bluesky</option></select>
        <input id="tgch" placeholder="اسم القناة أو رابطها، مثل: t.me/AJArabic" maxlength="80" dir="auto">
        <input id="tgname" placeholder="الاسم الظاهر (اختياري)" maxlength="60" style="max-width:230px">
        <button class="ibtn primary" id="tgadd">أضف</button>
      </div>
    </div>
    <div class="tgtools"><span class="count" id="tgcount"></span><span class="sp" style="flex:1"></span><span class="count" id="tgnext"></span><button class="ibtn" id="tgrefresh"><svg class="i" viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7L20 8M20 3v5h-5"/></svg>تحديث القنوات الآن</button></div>
    <div class="tgboard" id="tgboard"></div>
  </section>

  <!-- دليل المراكز -->
  <!-- الدول -->
  <section id="countriesdir" hidden>
    <div class="box cfilters">
      <div class="cfrow"><input id="ctyq" type="search" placeholder="ابحث عن دولة…" aria-label="بحث في الدول"><span class="count" id="ctycount"></span></div>
      <div class="cfrow"><div class="seg" id="ctyregion"></div></div>
    </div>
    <div id="ctygrid"></div>
  </section>

  <!-- انقطاع الإنترنت -->
  <section id="netview" hidden>
    <div class="netgrid" id="netgrid"></div>
    <div class="box" style="margin-top:16px"><div class="boxh">آخر تنبيهات الانقطاع (48 ساعة)<span class="sp"></span><span class="wstat" id="netlast"></span></div><div class="tablewrap" id="netrecent"></div></div>
  </section>

  <!-- الإعدادات -->
  <section id="setview" hidden>
    <div class="box lanbox" id="updbox"></div>
    <div id="setlan"></div>
  </section>

  <!-- اسأل المركز -->
  <section id="askview" hidden>
    <div class="box askbox">
      <input id="askq" placeholder="اسأل عن أي شيء رصده المركز، مثل: ماذا جرى في درعا هذا الأسبوع؟" maxlength="400">
      <select id="askdays" aria-label="المدة"><option value="1">آخر يوم</option><option value="3">آخر 3 أيام</option><option value="7" selected>آخر أسبوع</option><option value="31">آخر شهر</option></select>
      <button class="ibtn primary" id="askgo" style="height:46px;padding:0 22px">اسأل</button>
      <div class="chipsq" id="askex"></div>
    </div>
    <div class="askgrid">
      <div class="box askans"><div class="boxh">الإجابة<span class="sp"></span><span class="wstat" id="askstat"></span><button class="ibtn" id="askcopy" disabled>نسخ</button></div><div class="wdoc" id="askout"><div class="wempty"><b>اكتب سؤالك واضغط «اسأل»</b>يبحث المركز في الأخبار والدراسات المخزنة، ثم يكتب الإجابة مع أرقام مصادرها، بمحرك الكتابة المختار في «كاتب المقالات».</div></div></div>
      <div class="box"><div class="boxh">المواد التي استُند إليها<span class="sp"></span><span class="wstat" id="askn"></span></div><ul class="askref" id="askrefs"></ul></div>
    </div>
  </section>

  <!-- العقوبات والتصنيفات -->
  <section id="sancview" hidden>
    <div class="sanclists" id="sanclists"></div>
    <div class="tabs2" id="sanctabs"><button data-stab="terror" class="on">قوائم الإرهاب</button><button data-stab="new">أحدث الإدراجات</button><button data-stab="all">البحث في القوائم كاملة</button></div>
    <div class="qtypes box" id="sancgroups" style="margin-bottom:12px"></div>
    <div class="filters">
      <input id="sancq" type="search" placeholder="ابحث باسم شخص أو كيان، أو بالجنسية…" style="flex:1;min-width:240px;height:36px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:0 12px">
      <label class="opt" style="font-size:13px" id="sancterrorlbl" hidden><input type="checkbox" id="sancterror" checked>الإرهاب فقط</label>
      <span class="count" id="sanccount"></span>
      <button class="ibtn" id="sancref">تحديث القوائم</button>
    </div>
    <div class="box"><div class="tablewrap" id="sanclist"></div><div class="pager" id="sancpager"></div></div>
  </section>

  <!-- ملفات القضايا -->
  <section id="casesview" hidden>
    <div class="casegrid">
      <div class="box"><div class="boxh">القضايا<span class="sp"></span><button class="ibtn primary" id="casenew" style="height:30px">قضية جديدة</button></div><ul class="caselist" id="caselist"></ul></div>
      <div class="box" id="casedetail"><div class="wempty"><b>اختر قضية أو أنشئ واحدة</b>أضف إليها الأخبار والدراسات من زر «ملف قضية» في نافذة أي مادة، واكتب ملاحظاتك عليها، ثم صدّرها تقريراً واحداً.</div></div>
    </div>
  </section>

  <!-- الأرشيف والعناوين المعدّلة -->
  <section id="archview" hidden>
    <div class="tabs2"><button data-atab="arch" class="on">الأرشيف</button><button data-atab="edits">العناوين المعدّلة</button></div>
    <div class="filters" id="archtools">
      <div class="seg" id="archhours"><button data-ah="24" class="on">آخر 24 ساعة</button><button data-ah="168">أسبوع</button><button data-ah="720">شهر</button><button data-ah="0">الكل</button></div>
      <input id="archq" type="search" placeholder="ابحث في الأرشيف كله…" style="flex:1;min-width:220px;height:36px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:0 12px">
      <span class="count" id="archcount"></span>
      <button class="ibtn" id="archclear" style="color:var(--red)">حذف الأرشيف</button>
    </div>
    <div class="box" id="archbox"><div class="tablewrap" id="archlist"></div><div class="pager" id="archpager"></div></div>
  </section>

  <!-- الخريطة -->
  <section id="mapview" hidden>
    <div class="mapwrap"><div id="map"></div>
      <div class="mappanel">
        <span class="t">الأحداث النوعية على الخريطة</span>
        <div class="seg" id="maphours"><button data-mh="6">6 ساعات</button><button data-mh="24" class="on">يوم</button><button data-mh="72">3 أيام</button><button data-mh="168">أسبوع</button></div>
        <label class="opt" style="font-size:12.5px;white-space:nowrap">نوع الخريطة <select id="mapstyle" class="dsel" style="height:30px"><option value="general">عامة</option><option value="detailed">تفصيلية (مدن وقرى وطرق)</option><option value="satellite">قمر صناعي مع الأسماء</option><option value="terrain">تضاريس</option></select></label>
        <div class="seg" id="mapzoom"><button data-mz="sy">سوريا</button><button data-mz="me">الشرق الأوسط</button><button data-mz="world">العالم</button></div>
        <label class="opt" style="font-size:12.5px"><input type="checkbox" id="mapdens" checked>كثافة الأخبار حسب الدولة</label>
        <div class="maplegend" id="maplegend"></div>
        <span class="mapcount" id="mapcount"></span>
      </div>
    </div>
  </section>

  <!-- الإنذارات -->
  <section id="alertsview" hidden>
    <div class="filters"><div class="seg" id="alhours"><button data-alh="6">6 ساعات</button><button data-alh="24">يوم</button><button data-alh="48" class="on">يومان</button><button data-alh="168">أسبوع</button></div><span class="sp" style="flex:1"></span><span class="count" id="alcount"></span></div>
    <div class="alertbar" id="allist"></div>
  </section>

  <!-- الملخص اليومي -->
  <section id="dailyview" hidden>
    <div class="dailygrid">
      <div class="box"><div class="boxh"><span>التقرير</span><span class="sp"></span><select id="dailyday" class="dsel"></select><button class="ibtn" id="dailypdf">PDF</button><button class="ibtn" id="dailysend">إرسال إلى تيليغرام</button><button class="ibtn primary" id="dailybuild">إنشاء الآن</button></div><div class="dailybody" id="dailybody"></div></div>
      <div class="box"><div class="boxh">إعدادات الملخص</div><div class="bbody" id="dailyset"></div></div>
    </div>
  </section>

  <!-- بوت تيليغرام -->
  <section id="botview" hidden>
    <div class="botgrid">
      <div class="box bform">
        <div class="boxh">إعداد البوت</div>
        <div class="bbody" id="bform"></div>
      </div>
      <div>
        <div class="box"><div class="boxh">حالة القنوات<span class="sp"></span><button class="ibtn" id="bsendnow">أرسل مقالة الآن</button></div><div class="bstat" id="bstat"></div></div>
        <div class="box" style="margin-top:14px"><div class="boxh"><span id="brecenth">آخر ما أُرسل</span><span class="sp"></span><button class="lnk" id="breset" title="يسمح بإعادة إرسال المقالات السابقة">مسح السجل</button></div><ul class="warts" id="brecent"></ul></div>
      </div>
    </div>
  </section>

  <!-- كاتب المقالات -->
  <section id="writerview" hidden>
    <div class="tabs2"><button data-wtab="write" class="on">الكتابة</button><button data-wtab="log">سجل المقالات <span class="mt" id="wlogn"></span></button></div>
    <div id="wlogview" hidden>
      <div class="filters"><input id="wlogq" type="search" placeholder="ابحث في المقالات المكتوبة…" style="flex:1;min-width:240px;height:36px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:0 12px"><span class="count" id="wlogcount"></span><button class="ibtn" id="wlogdelall" style="color:var(--red)">حذف الكل</button></div>
      <div class="box tablewrap" id="wloglist"></div>
    </div>
    <div id="wwriteview">
    <div class="box wkey" id="wkey"></div>
    <div class="wgrid">
      <div>
        <div class="box wform">
          <label>الموضوع<textarea id="wtopic" placeholder="مثال: مستقبل تنظيم داعش في البادية السورية بعد انسحاب القوات الأمريكية" maxlength="400"></textarea></label>
          <div class="row2">
            <label>النوع<select id="wtype"></select></label>
            <label>الطول<select id="wlen"></select></label>
          </div>
          <div class="row2">
            <label>النبرة<select id="wtone"></select></label>
            <label>اللغة<select id="wlang"><option value="ar">العربية</option><option value="en">English</option></select></label>
          </div>
          <label>زاوية أو ملاحظات (اختياري)<input id="wangle" placeholder="مثال: ركّز على دور العشائر، وقارن بعام 2019" maxlength="300"></label>
          <label class="chk"><input type="checkbox" id="wsrcuse" checked>استند إلى ما رصده المركز عن الموضوع</label>
          <div class="wsrc" id="wsrc" hidden></div>
          <button class="ibtn primary go" id="wgo">اكتب الآن</button>
          <span class="hint">يُكتب النص كاملاً تلقائياً بالمحرك المختار في الأعلى. يستغرق النص المتوسط دقيقة إلى دقيقتين (وأكثر مع Ollama على الأجهزة العادية).</span>
        </div>
        <div class="box" style="margin-top:14px"><div class="boxh">مقالاتي المحفوظة<span class="sp"></span></div><ul class="warts" id="warts"></ul></div>
      </div>
      <div class="box wout">
        <div class="boxh"><span id="wtitle">النص</span><span class="sp"></span><span class="wstat" id="wstat"></span>
          <button class="ibtn" id="wcopy" disabled>نسخ</button><button class="ibtn" id="wsave" disabled>حفظ</button><button class="ibtn" id="wpdf" disabled>حفظ PDF</button><button class="ibtn" id="wstop" hidden>إيقاف</button></div>
        <div id="wdoc" class="wdoc"><div class="wempty"><b>اكتب موضوعاً واضغط «اكتب الآن»</b>سيظهر النص هنا أثناء كتابته.</div></div>
      </div>
    </div>
    </div>
  </section>

  <!-- مكتبة الكتب -->
  <section id="booksview" hidden>
    <div class="box cfilters">
      <div class="cfrow"><input id="bq" type="search" placeholder="ابحث بعنوان الكتاب أو المؤلف…" aria-label="بحث في الكتب"><span class="count" id="bcount"></span><button class="ibtn" id="brefresh"><svg class="i" viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7L20 8M20 3v5h-5"/></svg>تحديث المكتبة</button></div>
      <div class="cfrow"><div class="seg" id="btopic"></div><div class="seg" id="blang"><button data-blang="" class="on">كل اللغات</button><button data-blang="ar">عربي</button><button data-blang="foreign">أجنبي</button></div></div>
    </div>
    <div class="bookgrid" id="bookgrid"></div>
  </section>

  <section id="centersdir" hidden>
    <div class="box cfilters">
      <div class="cfrow"><input id="cq" type="search" placeholder="ابحث باسم المركز أو موقعه…" aria-label="بحث في المراكز"><span class="count" id="ccount"></span></div>
      <div class="cfrow"><div class="seg" id="cregion"></div></div>
      <div class="cfrow"><div class="seg" id="ccat"></div></div>
    </div>
    <div class="cgrid" id="cgrid"></div>
  </section>

  <!-- صفحات الأقسام -->
  <section id="secview" class="secgrid" hidden>
    <div>
      <div class="qtypes box" id="qualfilter" hidden style="margin-bottom:14px"></div>
    <div class="filters" id="filters">
        <div class="seg" id="hours">
          <button class="on" data-hours="0">الكل</button>
          <button data-hours="1">ساعة</button>
          <button data-hours="6">6 ساعات</button>
          <button data-hours="24">يوم</button>
          <button data-hours="168">أسبوع</button>
          <button data-hours="744">شهر</button>
        </div>
        <select id="source" aria-label="تصفية حسب المصدر"><option value="">كل المصادر</option></select>
        <span id="activetag"></span>
        <span class="sp"></span>
        <span class="count" id="count"></span>
        <div class="seg"><button id="hideseen" title="إخفاء ما فتحته من قبل">غير المقروءة</button><button id="density" title="عرض مضغوط">مضغوط</button></div>
      </div>
      <button class="newpill" id="newpill" hidden></button>
      <div id="feed" class="feed list"></div>
      <button class="ibtn more" id="more" hidden>تحميل المزيد</button>
    </div>
    <aside class="rail" aria-label="معلومات جانبية">
      <div class="box"><div class="boxh"><svg class="i" viewBox="0 0 24 24"><path d="M12 3c3 4 5 6 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-6 1-9z"/></svg>المواضيع الساخنة<span class="sp"></span><span class="sub">48H</span></div><div class="tags" id="tags"></div></div>
      <div class="box"><div class="boxh" style="--c:#38BDF8"><svg class="i" viewBox="0 0 24 24"><path d="M21 4L3 11l6 2 2 6 3-4 5 4z"/></svg>تيليغرام الآن<span class="sp"></span><button class="lnk" data-cat="tweets">كل القنوات</button></div><ul class="twl" id="tweets"></ul></div>
      <div class="box"><div class="boxh"><svg class="i" viewBox="0 0 24 24"><path d="M3 12h4l3-7 4 14 3-7h4"/></svg>حالة الرصد<span class="sp"></span><span class="sub">SYS</span></div><div class="status" id="status"></div></div>
    </aside>
  </section>
</div>

</div>

<dialog id="dlg" aria-labelledby="dlgTitle">
  <div class="dlghead"><div class="meta" id="dlgMeta"></div><button class="ibtn" id="dlgClose" aria-label="إغلاق"><svg class="i" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
  <div class="dlgbody" id="dlgBody"></div>
</dialog>
<div class="toast" id="toast" role="status"></div>
<dialog id="supdlg" class="supdlg"><div class="suphead"><svg class="i" viewBox="0 0 24 24"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg><b>ادعم مركز أبو زبيدة</b><button class="x" id="supclose" aria-label="إغلاق">×</button></div>
 <p>المركز مجاني ويعمل على جهازك دون اشتراك. دعمك يساعد على استمرار تطويره وإضافة مصادر وميزات جديدة.</p>
 <div class="supacts" id="supacts"></div>
 <p class="supdev">تطوير أبو عبدالله الشامي</p></dialog>
<div id="cmdk" hidden><div class="cmdbox" role="dialog" aria-label="لوحة الأوامر"><input id="cmdin" placeholder="اكتب: قسماً، دولة، مركزاً، أو كلمة للبحث…" autocomplete="off"><ul id="cmdlist"></ul><div class="cmdhint mt">↑↓ للتنقل · Enter للفتح · Esc للإغلاق</div></div></div>

<script>
const $=s=>document.querySelector(s);
const CAT={};let META=null;let CENTERS=[];let CENTER_SET=new Set();
const ITEMS=new Map();
const S={cat:'dash',hours:0,source:'',tag:'',q:'',page:1,per:30,total:0,ids:new Set(),compact:false,openId:null,center:''};
const CF={q:'',region:'',cat:''};
const TITLE_DEFAULT='مركز أبو زبيدة للتتبع والرصد';
const DESC={
 daily:'تقرير من صفحة واحدة عن أهم ما رصده المركز خلال آخر 24 ساعة، مقسّم حسب الأحداث النوعية والدول. يُنشأ تلقائياً كل صباح، ويمكن إرساله إلى تيليغرام أو حفظه PDF.',
 net:'حالة الاتصال بالإنترنت في دول المنطقة لحظياً. انقطاع الإنترنت كثيراً ما يسبق عملية عسكرية أو يرافقها. المصدر: مرصد IODA في معهد جورجيا للتقنية.',
 settings:'التحديث التلقائي والفتح من الجوال.',
 ask:'اسأل سؤالاً عادياً، فيجيبك المركز من الأخبار والدراسات التي رصدها، مع أرقام مصادر كل معلومة.',
 sanctions:'كل المصنَّفين إرهابياً على قائمة العقوبات الأمريكية (OFAC) وقائمة مجلس الأمن الدولي، مرتبين حسب الجماعة: داعش والقاعدة والنصرة وحزب الله والحرس الثوري وطالبان والشباب وغيرها، مع أحدث الإدراجات وبحث في القوائم كاملة.',
 cases:'اجمع الأخبار والدراسات المتعلقة بقضية تتابعها في ملف واحد، مع ملاحظاتك، وصدّرها تقريراً. كل مادة تُضاف تُؤرشف تلقائياً.',
 archive:'نسخ محفوظة من نصوص المقالات لحظة رصدها، تبقى حتى لو حُذفت من موقعها أو عُدّلت. وسجل بكل عنوان غيّرته صحيفته بعد النشر.',
 official:'بيانات وزارات الدفاع والخارجية والعدل والقيادات العسكرية والأمم المتحدة والناتو، وهي المصدر الأول قبل أن تعيد الصحف صياغتها.',
 map:'كل خبر نوعي على الخريطة في موقعه: المدينة إن ذُكرت، أو الدولة. اضغط أي نقطة لتقرأ الخبر.',
 alerts:'ينبّهك المركز حين يقفز الحديث عن دولة أو موضوع فجأة فوق معدله المعتاد، أو حين تتوالى الأحداث النوعية في مكان واحد.',
 bot:'يرسل البوت إلى قناتك أو مجموعتك في تيليغرام ملخص مقالة أو دراسة أو خبر عالمي مترجم مع رابطه، بالسرعة والفلتر اللذين تختارهما.',
 writer:'اكتب مقالاً أو دراسة أو تقدير موقف عن أي موضوع، يُكتب كاملاً تلقائياً مستنداً إلى ما رصده المركز. يعمل مجاناً فوراً دون مفتاح، أو عبر Gemini أو Ollama أو Claude.',
 qual:'الأحداث الميدانية المهمة تُلتقط تلقائياً من كل الأخبار وقنوات تيليغرام: غارات، مسيّرات، انفجارات، اشتباكات، اعتقالات، توغلات، اغتيالات.',
 dash:'نظرة واحدة على كل الأقسام: آخر ما رصده المركز في كل قسم، ومؤشر التوتر الأمني، وآخر منشورات تيليغرام.',
 all:'كل ما رصده المركز من جميع الأقسام، الأحدث أولاً.',
 world:'وكالات الأنباء والصحف الدولية الكبرى.',
 arab:'الصحف والقنوات والمواقع الإخبارية العربية.',
 think_global:'دراسات وتحليلات وتقديرات موقف من مراكز بحث غربية ودولية، خلال الشهر الأخير.',
 think_arab:'أوراق ودراسات من مراكز الأبحاث العربية، خلال الشهر الأخير.',
 terror:'مراكز رصد الإرهاب والتطرف وتحليلات الجماعات المسلحة، خلال الشهر الأخير.',
 war:'تقارير ميدانية وتحليلات عسكرية ودفاعية وبيانات النزاعات.',
 economy:'الأسواق والنفط والعملات والسياسات المالية من مصادر عالمية وعربية.',
 tweets:'آخر 3 منشورات من كل قناة تيليغرام وحساب Bluesky، تتحدّث تلقائياً كل دقيقتين.',
 keywords:'أضف كلمات تهمك، ويبحث عنها المركز في أخبار Google بالعربية والإنجليزية في كل دورة.',
 centers:'تصفّح مراكز الأبحاث ومكافحة الإرهاب والدراسات العسكرية واحداً واحداً، مع أبرز مواضيع كل مركز.',
 saved:'العناصر التي حفظتها على هذا الجهاز.',
 intel:'دراسات ومقالات وأخبار الأمن والاستخبارات والتجسس والأمن السيبراني، خلال الشهر الأخير.',
 countries:'كل مادة مربوطة تلقائياً بالدول التي تتحدث عنها. اختر دولة لتتصفح كل ما يخصها خلال الشهر الأخير.',
 books:'كتب صدرت خلال آخر سنتين عن الإرهاب والحروب والسياسة والأمن والاستخبارات، مع غلافها وملخصها المترجم ورابطها.',
 health:'حالة كل مصدر في آخر دورة جلب. المصادر التي لا يعمل رابطها تُجلب عبر بحث أخبار Google لنفس الموقع.'
};
const CODES={daily:'DAILY / BRIEF',net:'SIGINT / INTERNET',settings:'SYSTEM / SETTINGS',ask:'QUERY / ASK',sanctions:'DESIGNATIONS / SANCTIONS',cases:'CASE FILES',archive:'EVIDENCE / ARCHIVE',official:'SEC-11 / OFFICIAL',map:'GEO / LIVE-MAP',alerts:'EARLY WARNING / ALERTS',bot:'RELAY / TELEGRAM-BOT',writer:'STUDIO / WRITER',qual:'CRITICAL / EVENTS',dash:'COMMAND / OVERVIEW',all:'ALL-SOURCES',world:'SEC-01 / GLOBAL',arab:'SEC-02 / ARAB',think_global:'SEC-03 / THINK-TANKS',think_arab:'SEC-04 / ARAB-RESEARCH',terror:'SEC-05 / COUNTER-TERRORISM',war:'SEC-06 / CONFLICT',economy:'SEC-07 / ECONOMY',tweets:'SEC-08 / TELEGRAM',keywords:'SEC-09 / WATCHLIST',intel:'SEC-10 / SECURITY-INTEL',countries:'GEO / COUNTRIES',books:'LIBRARY / BOOKS',centers:'DIRECTORY / CENTERS',saved:'ARCHIVE / SAVED',health:'SYSTEM / SOURCES'};
const EXTRA={daily:'الملخص اليومي',net:'رصد انقطاع الإنترنت',settings:'الإعدادات',ask:'اسأل المركز',sanctions:'العقوبات والتصنيفات',cases:'ملفات القضايا',archive:'الأرشيف والعناوين المعدّلة',map:'الخريطة التفاعلية',alerts:'الإنذار المبكر',bot:'بوت تيليغرام',writer:'كاتب المقالات والدراسات',qual:'أخبار نوعية',dash:'لوحة القيادة',all:'كل الأخبار',countries:'الدول',books:'مكتبة الكتب',centers:'دليل المراكز',saved:'المحفوظات',health:'صحة المصادر والترجمة'};
const P={
 radar:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l6.4-6.4"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
 news:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h6M7 13h10M7 16h7"/>',
 columns:'<path d="M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18"/>',
 building:'<path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6"/>',
 shield:'<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
 target:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
 chart:'<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
 send:'<path d="M21 4L3 11l6 2 2 6 3-4 5 4z"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
 centers:'<rect x="4" y="3" width="10" height="18" rx="1.5"/><path d="M14 9h5a1 1 0 0 1 1 1v11h-6M8 7h2M8 11h2M8 15h2"/>',
 lock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4M12 15v2"/>',
 flag:'<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
 bolt:'<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
 wifi:'<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
 screen:'<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
 cmd:'<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',
 bell:'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 0 0 4 0"/>',
 pen:'<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
 book:'<path d="M4 19V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zm0 0a2 2 0 0 0 2 2h13"/><path d="M9 7h6"/>',
 bookmark:'<path d="M6 3h12v18l-6-4-6 4z"/>',
 pulse:'<path d="M3 12h4l3-7 4 14 3-7h4"/>',
 open:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 link:'<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
 copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
 arrow:'<path d="M9 6l6 6-6 6"/>',
 lang:'<path d="M4 5h8M8 3v2M6 5c0 4 3 7 6 8M10 5c0 3-2 6-6 8M13 21l4-9 4 9M14.5 18h5"/>',
 word:'<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M8.5 12l1.2 5 1.8-4 1.8 4 1.2-5"/>',
 pdf:'<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M9 13h6M9 16h4"/>',
 swap:'<path d="M7 7h12l-3-3M17 17H5l3 3"/>'
};
const CICON={daily:'pdf',net:'wifi',settings:'gear',ask:'search',sanctions:'shield',cases:'centers',archive:'bookmark',official:'columns',map:'globe',alerts:'bell',bot:'send',writer:'pen',qual:'bolt',dash:'radar',all:'grid',world:'globe',arab:'news',think_global:'columns',think_arab:'building',terror:'shield',war:'target',economy:'chart',tweets:'send',keywords:'search',intel:'lock',countries:'flag',country:'flag',books:'book',centers:'centers',saved:'bookmark',health:'pulse'};
const ico=(n)=>`<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${P[n]||''}</svg>`;

function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function ago(ts){const d=Math.max(0,Date.now()/1000-ts);if(d<60)return'الآن';if(d<3600)return'قبل '+Math.floor(d/60)+' دقيقة';if(d<86400)return'قبل '+Math.floor(d/3600)+' ساعة';return'قبل '+Math.floor(d/86400)+' يوم'}
function hm(ts){return new Date(ts*1000).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})}
function dm(ts){const d=new Date(ts*1000);return d.toLocaleDateString('ar',{day:'numeric',month:'short'})}
function fmt(ts){return ts?new Date(ts*1000).toLocaleString('ar',{dateStyle:'medium',timeStyle:'short'}):'—'}
async function api(u,o){const r=await fetch(u,o);const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.status);return j}
function toast(t){}          /* الإشعارات المنبثقة ملغاة */
function lsGet(k,d){try{return localStorage.getItem(k)??d}catch(e){return d}}
function lsSet(k,v){try{localStorage.setItem(k,v)}catch(e){}}
function savedList(){try{return JSON.parse(lsGet('rased_saved','[]'))}catch(e){return[]}}
function setSaved(l){lsSet('rased_saved',JSON.stringify(l))}
function isSaved(id){return savedList().some(i=>i.id===id)}
const STOP=new Set(['مركز','المركز','معهد','المعهد','مؤسسة','المجلس','مجلس','برنامج','الشبكة','مشروع','مرصد','الجمعية','نادي','وكالة','كلية','دراسات','للدراسات','لدراسة','لدراسات','و','-','–']);
function mono(name){const m=name.match(/\b[A-Z][A-Za-z-]{1,6}\b/);if(m&&m[0].length<=6)return m[0].toUpperCase();
 const w=name.replace(/\(.*?\)/g,'').split(/\s+/).filter(x=>x&&!STOP.has(x));return w.slice(0,2).map(x=>x.replace(/^ال/,'')[0]||'').join(' ')||name[0]}
const T=it=>it.title_ar||it.title;
let VIS=new Set();try{VIS=new Set(JSON.parse(lsGet('rased_visited','[]')))}catch(e){}
const seen=id=>VIS.has(id);
function markVisited(id){
 if(!id||VIS.has(id))return;VIS.add(id);
 const arr=[...VIS];lsSet('rased_visited',JSON.stringify(arr.slice(-6000)));
 document.querySelectorAll(`#feed [data-id="${id}"]`).forEach(el=>{const it=ITEMS.get(id);if(it)el.outerHTML=card(it,el.classList.contains('lead'))});
 document.querySelectorAll(`.bt[data-open="${id}"],.tgp[data-open="${id}"],.twl button[data-open="${id}"]`).forEach(b=>b.classList.add('seen'))}

/* الساعات */
const ZONES=[['UTC','UTC'],['إسطنبول','Europe/Istanbul'],['القاهرة','Africa/Cairo'],['واشنطن','America/New_York'],['موسكو','Europe/Moscow'],['بكين','Asia/Shanghai']];
function clocks(){const n=new Date();$('#utcnow').textContent=n.toISOString().slice(0,19).replace('T',' ')+' UTC';
 if(n.getSeconds()%20===0||!$('#clocks').innerHTML)$('#clocks').innerHTML=ZONES.map(([nm,z])=>`<span class="clock"><b>${new Intl.DateTimeFormat('en-GB',{timeZone:z,hour:'2-digit',minute:'2-digit'}).format(n)}</b>${nm}</span>`).join('')}

/* عناصر الأخبار */
function tagsHtml(tags,max=99){return (tags||'').split('|').filter(Boolean).slice(0,max).map(t=>t.startsWith('★')?`<button class="tag kw" data-tag="${esc(t)}">${esc(t.slice(1))}</button>`:`<button class="tag" data-tag="${esc(t)}">${esc(t)}</button>`).join('')}
const VCATS=['world','arab','war','terror','intel','tweets','keywords','economy'];
function vfHtml(it){if(!it.cluster||!VCATS.includes(it.cat))return'';const n=it.nsrc||1;
 if(n>=3)return `<button class="vf v3" data-cluster="${esc(it.cluster)}" title="نقلته ${n} مصادر مستقلة">✓ مؤكد، ${n} مصادر</button>`;
 if(n===2)return `<button class="vf v2" data-cluster="${esc(it.cluster)}" title="نقله مصدران">مصدران</button>`;
 return (it.events?`<span class="vf v1" title="لم ينقله حتى الآن إلا مصدر واحد">مصدر واحد، غير مؤكد</span>`:'')}
function evHtml(e){return (e||'').split('|').filter(Boolean).map(n=>`<span class="ev" style="--e:${EVC[n]||'var(--red)'}">${esc(n)}</span>`).join('')}
function ctyHtml(c,max=6){return (c||'').split('|').filter(Boolean).slice(0,max).map(n=>`<button class="tag cty" data-country="${esc(n)}" title="كل ما يخص ${esc(n)}">${esc(n)}</button>`).join('')}
function state(it){if(it.translated===1)return'';if(it.translated<=-3)return'<span class="badge fail">تعذّرت الترجمة</span>';return'<span class="badge pend">قيد الترجمة</span>'}
function mlHtml(it){const m=META?.media||{};const l=m[(it.source_ar||'').toLowerCase()]||m[(it.source||'').replace('t.me/','').toLowerCase()];
 return l?`<span class="ml${l.startsWith('حكومي')?' gov':''}" title="ملكية أو تمويل وسيلة الإعلام">${esc(l)}</span>`:''}
function edHtml(it){return it.edits?`<button class="ed" data-edits="${it.id}" title="غيّرت الصحيفة عنوان هذا الخبر بعد نشره">✎ عُدِّل العنوان${it.edits>1?' '+it.edits+' مرات':''}</button>`:''}
function iconKey(src,link){src=(src||'').toLowerCase();
 if(src.startsWith('t.me/'))return 'tg/'+src.slice(5);
 if(src.startsWith('bsky/'))return 'bs/'+src.slice(5);
 if(/^[a-z0-9.-]+\.[a-z]{2,}/.test(src)&&!src.startsWith('news.google'))return src.split('/')[0];
 try{const h=new URL(link).hostname.replace(/^www\./,'');if(h&&!h.includes('news.google'))return h}catch(e){}return ''}
function favImg(key){return key?`<img class="fav" src="/icon/${esc(key)}" alt="" loading="lazy" onerror="this.remove()">`:''}
function srcHtml(it){const fv=favImg(iconKey(it.source,it.link));return mlHtml(it)+(CENTER_SET.has(it.source_ar)?`<button class="src" data-center="${esc(it.source_ar)}" title="تصفّح هذا المركز">${fv}${esc(it.source_ar)}</button>`:`<span class="src">${fv}${esc(it.source_ar)}</span>`)}
function card(it,lead){
 const c=CAT[it.cat]||{color:'var(--acc)',name:''};
 const fresh=Date.now()/1000-it.published<3600;
 const showOrig=it.translated===1&&it.lang!=='ar'&&it.title&&it.title!==T(it);
 const sv=isSaved(it.id);
 const recent=Date.now()/1000-it.published<86400;
 return `<article class="item${lead?' lead':''}${seen(it.id)?' seen':''}" data-id="${it.id}" style="--c:${c.color}">
  <div class="when"><b>${recent?hm(it.published):dm(it.published)}</b>${recent?'اليوم':''}</div>
  <div>
   <div class="meta">${evHtml(it.events)}${vfHtml(it)}${edHtml(it)}${it.kind==='video'?'<span class="badge vid">▶ فيديو</span>':''}${srcHtml(it)}${['all','center','saved','qual','country'].includes(S.cat)?`<span>${esc(c.name)}</span>`:''}<time title="${esc(fmt(it.published))}">${ago(it.published)}</time>${fresh&&!seen(it.id)?'<span class="badge new">جديد</span>':''}${seen(it.id)?'<span class="badge seen">✓ تمت زيارتها</span>':''}${state(it)}<span class="ref">REF-${it.id.slice(0,6).toUpperCase()}</span></div>
   <h3><button class="ttl" data-open="${it.id}">${esc(T(it))}</button></h3>
   ${showOrig&&lead?`<span class="orig">${esc(it.title)}</span>`:''}
   ${it.summary_ar?`<p>${esc(it.summary_ar)}</p>`:''}
   <div class="foot">${ctyHtml(it.countries,3)}${tagsHtml(it.tags,4)}<span class="acts">
    <button data-open="${it.id}" title="قراءة مترجمة" aria-label="قراءة مترجمة">${ico('open')}</button>
    ${it.link?`<a href="/go/${it.id}" target="_blank" rel="noopener" title="فتح في الموقع الأصلي" aria-label="فتح في الموقع الأصلي">${ico('link')}</a>`:''}
    <button data-save="${it.id}" class="${sv?'saved':''}" title="${sv?'محفوظ':'حفظ'}" aria-label="حفظ">${ico('bookmark')}</button>
    <button data-copy="${it.id}" title="نسخ" aria-label="نسخ">${ico('copy')}</button></span></div>
  </div>
 </article>`}
function emptyHtml(){
 if(META&&META.categories.every(c=>!c.total))return'<div class="empty"><b>يجري الجلب الأول من المصادر</b>ستظهر العناصر هنا خلال دقائق، وتُترجم تباعاً.</div>';
 if(S.cat==='keywords'&&!META?.keywords.length)return'<div class="empty"><b>لا توجد كلمات مراقَبة بعد</b>أضف كلمة في الحقل أعلاه ليبدأ المركز برصدها.</div>';
 if(S.cat==='center')return'<div class="empty"><b>لا توجد مواد لهذا المركز حالياً</b>قد لا يكون نشر شيئاً خلال الشهر الأخير، أو أن مصدره متعطل. راجع «صحة المصادر».</div>';
 return'<div class="empty"><b>لا توجد نتائج لهذه المرشحات</b>وسّع المدة الزمنية، أو اختر كل المصادر، أو امسح البحث.</div>'}

/* البيانات الوصفية */
async function loadMeta(){
 META=await api('/api/meta');
 META.categories.forEach(c=>CAT[c.key]=c);
 renderNav();renderTags();renderStatus();renderPanels();renderSources();
 $('#live').innerHTML=`<i></i>مباشر <b>${META.hour}</b> خبراً في آخر ساعة`;
 updBanner();
 $('#sbSources').textContent=`SOURCES ${META.health.ok}/${META.health.ok+META.health.fail}`;
 $('#sbTr').textContent=`TRANSLATION QUEUE ${META.pending}`;
 if(S.cat==='dash')renderKpis();
}
async function loadCenters(){const d=await api('/api/centers');CENTERS=d.items;CENTER_SET=new Set(CENTERS.map(c=>c.name))}
function navi(key,name,color,count,ratio){return `<button class="navi${S.cat===key||(key==='centers'&&S.cat==='center')?' on':''}" data-cat="${key}" style="--c:${color}">${ico(CICON[key])}<span class="nm">${esc(name)}</span>${count!==''&&count!=null?`<span class="ct" title="خلال آخر 24 ساعة">${esc(count)}</span>`:''}${ratio!=null?`<span class="bar"><i style="width:${Math.max(3,Math.round(ratio*100))}%"></i></span>`:''}</button>`}
function renderNav(){
 const sum=META.categories.reduce((a,c)=>a+c.day,0);
 const max=Math.max(1,...META.categories.map(c=>c.day));
 let h='<div class="navgrp">COMMAND</div>'+navi('dash','لوحة القيادة','var(--acc)','')+navi('daily','الملخص اليومي','var(--gold)','')+navi('qual','أخبار نوعية','var(--red)',QSTATS?QSTATS.total:'')+navi('alerts','الإنذار المبكر','#F59E0B','')+navi('map','الخريطة التفاعلية','var(--acc)','')+navi('net','انقطاع الإنترنت','#A78BFA',NETBAD||'')+navi('ask','اسأل المركز','var(--acc)','')+navi('all','كل الأخبار','var(--acc)',sum);
 h+='<div class="navgrp">SECTIONS / الأقسام</div>';
 META.categories.forEach(c=>h+=navi(c.key,c.name,c.color,c.day,c.key==='tweets'||c.key==='keywords'?null:c.day/max));
 h+='<div class="navgrp">TOOLS / الأدوات</div>'+navi('centers','دليل المراكز','var(--acc)',CENTERS.length||'')+navi('countries','الدول','var(--acc)',CTY.length||'')+navi('books','مكتبة الكتب','var(--gold)',BOOKS_N||'')+navi('writer','كاتب المقالات','var(--acc)','')+(S.cat==='bot'?navi('bot','بوت تيليغرام','#38BDF8',BOTON?'يعمل':''):'')+navi('sanctions','العقوبات والتصنيفات','#E11D48',META.sanc_new||'')+navi('cases','ملفات القضايا','var(--gold)','')+navi('archive','الأرشيف','var(--acc)','')+navi('saved','المحفوظات','var(--gold)',savedList().length||'')+navi('settings','الإعدادات','var(--muted)','')+navi('health','صحة المصادر والترجمة',META.health.fail||META.tr_stats.down?'var(--red)':'var(--green)',META.health.fail?META.health.fail+' متعطل':'');
 $('#nav').innerHTML=h;
 $('#sidefoot').innerHTML=`SOURCES <b>${META.health.ok}/${META.health.ok+META.health.fail}</b><br>TRANSLATION QUEUE <b>${META.pending}</b><br>LAST CYCLE <b>${META.state.last_cycle?ago(META.state.last_cycle):'…'}</b>`}
function renderTags(){const h=META.tags.length?META.tags.map(t=>`<button class="tag${S.tag===t.tag?' on':''}" data-tag="${esc(t.tag)}">${esc(t.tag)} <em>${t.count}</em></button>`).join(''):'<span class="count">تظهر بعد ترجمة العناصر.</span>';$('#tags').innerHTML=h;$('#dashTags').innerHTML=h}
function renderSources(){
 const uniq=[...new Set(META.sources.filter(s=>S.cat==='all'||s.cat===S.cat).map(s=>s.name))];
 $('#source').innerHTML='<option value="">كل المصادر</option>'+uniq.map(n=>`<option${n===S.source?' selected':''}>${esc(n)}</option>`).join('')}
function renderStatus(){
 const st=META.state;
 $('#status').innerHTML=
  `آخر دورة: <b>${st.last_cycle?ago(st.last_cycle):'جارية الآن'}</b><br>`+
  `الدورة القادمة: <b>${st.running?'جارية الآن':(st.next_cycle?ago(2*META.now-st.next_cycle).replace('قبل','بعد'):'—')}</b><br>`+
  `بانتظار الترجمة: <b>${META.pending}</b><br>`+
  `مصادر تعمل: <b class="ok">${META.health.ok}</b>، متعطلة: <b class="${META.health.fail?'bad':''}">${META.health.fail}</b><br>`+
  (META.tr_stats.down?`<span class="warn">الترجمة متوقفة مؤقتاً: ${esc(META.tr_stats.last_error)}</span>`:'');
 $('#refresh').classList.toggle('spin',!!st.running)}
function threatColor(l){return['#34D399','#A3E635','#FACC15','#FB923C','#F43F5E'][l-1]}
function renderKpis(){
 const t=META.threat;
 const k=$('#kThreat');k.style.setProperty('--tl',threatColor(t.level));
 k.innerHTML=`<div class="k">THREAT INDEX / مؤشر التوتر الأمني</div><div class="v"><b>${esc(t.label)}</b><span class="mt">LEVEL ${t.level}/5</span></div><div class="segs">${[1,2,3,4,5].map(i=>`<i class="${i<=t.level?'on':''}"></i>`).join('')}</div><p>${t.w6} خبراً عن الحروب والإرهاب في آخر 6 ساعات، مقابل متوسط ${t.avg} في الأسبوع.</p>`;
 $('#kHour').innerHTML=`<div class="k">LAST HOUR / آخر ساعة</div><div class="v"><b>${META.hour}</b><span>خبراً جديداً</span></div><p>${META.categories.reduce((a,c)=>a+c.day,0)} خبراً خلال 24 ساعة</p>`;
 $('#kSrc').innerHTML=`<div class="k">SOURCES / المصادر</div><div class="v"><b class="ok">${META.health.ok}</b><span>تعمل</span></div><p>${META.health.fail?`<button class="lnk" data-cat="health" style="all:unset;cursor:pointer;color:var(--red)">${META.health.fail} مصدراً متعطلاً، اعرضها</button>`:'كل المصادر تعمل'}</p>`;
 $('#kTr').innerHTML=`<div class="k">TRANSLATION / الترجمة</div><div class="v"><b>${META.pending}</b><span>بانتظار الترجمة</span></div><p>${META.tr_stats.down?'<button data-cat="health" style="all:unset;cursor:pointer;color:var(--red)">كل مزودي الترجمة متوقفون مؤقتاً، اعرض التفاصيل</button>':(META.tr_stats.providers||[]).filter(p=>p.ready).length+' مزودي ترجمة يعملون'}</p>`}
function renderPanels(){
 $('#kwpanel').hidden=S.cat!=='keywords';
 if(!META)return;
 $('#kwchips').innerHTML=META.keywords.map(w=>`<span class="chip" style="--cc:var(--gold)"><button data-tag="★${esc(w)}">${esc(w)}</button><button class="x" data-kwdel="${esc(w)}" aria-label="حذف ${esc(w)}">×</button></span>`).join('')}

/* التنقل */
function setView(cat){
 S.cat=cat;S.source='';S.tag='';S.page=1;if(cat!=='center')S.center='';if(cat!=='country')S.country='';
 $('#title').textContent=EXTRA[cat]||CAT[cat]?.name||'';
 $('#desc').textContent=DESC[cat]||'';$('#pcode').textContent=CODES[cat]||'';
 const feedViews=!['dash','tweets','centers','countries','books','writer','bot','map','alerts','ask','sanctions','cases','archive','net','settings','daily'].includes(cat);
 $('#mapview').hidden=cat!=='map';$('#alertsview').hidden=cat!=='alerts';
 $('#netview').hidden=cat!=='net';$('#setview').hidden=cat!=='settings';
 $('#askview').hidden=cat!=='ask';$('#sancview').hidden=cat!=='sanctions';$('#casesview').hidden=cat!=='cases';$('#archview').hidden=cat!=='archive';
 $('#writerview').hidden=cat!=='writer';
 $('#botview').hidden=cat!=='bot';$('#dailyview').hidden=cat!=='daily';
 $('#pagehead').hidden=cat==='center'||cat==='country';
 $('#centerhead').hidden=cat!=='center';
 $('#countryhead').hidden=cat!=='country';
 $('#countriesdir').hidden=cat!=='countries';
 $('#booksview').hidden=cat!=='books';
 $('#dash').hidden=cat!=='dash';
 $('#tgview').hidden=cat!=='tweets';
 $('#centersdir').hidden=cat!=='centers';
 $('#secview').hidden=!feedViews;
 $('#filters').hidden=cat==='health';
 $('#source').hidden=cat==='center'||cat==='country';
 $('#qualfilter').hidden=cat!=='qual';if(cat!=='qual')S.event='';
 $('#newpill').hidden=true;document.title=TITLE_DEFAULT;
 if(META){renderNav();renderSources();renderPanels();renderTags()}
 renderActiveTag();window.scrollTo({top:0});
 if(cat==='dash')return loadDash();
 if(cat==='tweets')return loadTgBoard();
 if(cat==='health')return renderHealth();
 if(cat==='saved')return renderSaved();
 if(cat==='centers')return renderCenters();
 if(cat==='countries')return renderCountries();
 if(cat==='books')return loadBooks();
 if(cat==='writer')return loadWriter();
 if(cat==='bot')return loadBot();
 if(cat==='daily')return loadDaily();
 if(cat==='map'){$('#mapstyle').value=MAPSTYLE;return loadMap()}
 if(cat==='ask')return initAsk();
 if(cat==='sanctions')return loadSanc();
 if(cat==='cases')return loadCases();
 if(cat==='archive')return loadArch();
 if(cat==='net')return loadNet();
 if(cat==='settings')return loadSettings();
 if(cat==='alerts')return loadAlerts();
 if(cat==='center')renderCenterHead();
 if(cat==='country')renderCountryHead();
 if(cat==='qual')renderQualFilter();
 load(true)}
function renderActiveTag(){$('#activetag').innerHTML=S.tag&&!['center','country'].includes(S.cat)?`<button class="activetag" id="cleartag" aria-label="إلغاء تصفية الموضوع">${esc(S.tag.replace('★',''))} ×</button>`:''}
function params(page,per){const c=S.cat==='center',k=S.cat==='country',ql=S.cat==='qual';return new URLSearchParams({cat:(c||k||ql)?'all':S.cat,hours:S.hours,source:c?S.center:S.source,tag:S.tag,q:S.q,country:k?S.country:'',qual:ql?'1':'',event:ql?(S.event||''):'',page,per})}
async function load(reset){
 const feed=$('#feed');feed.className='feed list'+(S.compact?' compact':'');
 if(reset){S.page=1;feed.innerHTML='<div class="loading spinner">جارٍ التحميل…</div>'}
 try{
  const d=await api('/api/items?'+params(S.page,S.per));
  S.total=d.total;d.items.forEach(i=>ITEMS.set(i.id,i));
  const shown=S.hideSeen?d.items.filter(i=>!seen(i.id)):d.items;
  const h=shown.map((it,k)=>card(it,reset&&k===0&&!S.compact)).join('');
  if(reset){feed.innerHTML=h||emptyHtml();S.ids=new Set(d.items.map(i=>i.id))}
  else{feed.insertAdjacentHTML('beforeend',h);d.items.forEach(i=>S.ids.add(i.id))}
  $('#more').hidden=S.page*S.per>=S.total;
  $('#count').textContent=S.total+' عنصر';
 }catch(e){feed.innerHTML='<div class="empty"><b>تعذّر الاتصال بالخادم</b>تأكد أن البرنامج ما زال يعمل ثم حدّث الصفحة.</div>'}}
function renderSaved(){
 const feed=$('#feed');feed.className='feed list'+(S.compact?' compact':'');
 let l=savedList();
 if(S.q)l=l.filter(i=>((i.title_ar||'')+(i.summary_ar||'')+i.title+i.source_ar).includes(S.q));
 l.forEach(i=>ITEMS.has(i.id)||ITEMS.set(i.id,i));
 if(S.hideSeen)l=l.filter(i=>!seen(i.id));
 feed.innerHTML=l.length?l.map(i=>card(i,false)).join(''):'<div class="empty"><b>لا توجد عناصر محفوظة</b>اضغط زر الحفظ على أي خبر أو دراسة لتجده هنا لاحقاً.</div>';
 $('#more').hidden=true;$('#count').textContent=l.length+' عنصر'}
function trHtml(){
 const pv=META?.tr_stats?.providers||[];
 const rd=META?.reader||{};
 return `<div class="box trbox"><div class="boxh"><svg class="i" viewBox="0 0 24 24">${P.lang}</svg>مزودو الترجمة<span class="sp"></span><button class="ibtn" id="trtest">اختبار الترجمة الآن</button></div>
  <div id="trrows">${pv.map(p=>`<div class="trrow"><span>${esc(p.name)}</span><span class="${p.ready?'ok':'bad'}">${p.ready?'يعمل':'متوقف مؤقتاً'}</span><span class="o">نجح ${p.ok}، فشل ${p.fail}${p.err?'، آخر خطأ: '+esc(p.err):''}</span></div>`).join('')}</div>
  <div class="trrow"><span>قارئ المقالات</span><span class="${rd.curl_cffi?'ok':'warn'}">${rd.curl_cffi?'محسّن':'أساسي'}</span><span class="o">${rd.curl_cffi?'curl_cffi مثبت':'لتحسين فتح المواقع المحمية: pip install curl_cffi'}${rd.trafilatura?'، trafilatura مثبت':'، ولاستخراج أدق: pip install trafilatura'}</span></div></div>`}
async function trTest(){
 $('#trrows').innerHTML='<div class="trrow"><span class="spinner">جارٍ الاختبار…</span></div>';
 try{const d=await api('/api/translate-test');
  $('#trrows').innerHTML=d.results.map(r=>`<div class="trrow"><span>${esc(r.name)}</span><span class="${r.ok?'ok':'bad'}">${r.ok?'يعمل':'لا يعمل'}${r.ms?` <span class="mt" style="color:var(--faint)">${r.ms}ms</span>`:''}</span><span class="o" dir="auto">${esc(r.out)}</span></div>`).join('')}
 catch(e){$('#trrows').innerHTML='<div class="trrow"><span class="bad">تعذّر الاختبار</span></div>'}}
let HEALTH=[],HONLY=false;
function hostOf(u){try{return new URL(u).hostname.replace(/^www\./,'')}catch(e){return ''}}
let LANS=null;
function lanHtml(){const l=LANS;if(!l)return'';
 return `<div class="box lanbox"><b style="font:700 14px var(--fd)">الفتح من الجوال وتثبيته كتطبيق</b>
  <div class="row"><label class="opt"><input type="checkbox" id="lanon"${l.lan?' checked':''}>السماح بفتح المركز من الأجهزة على نفس شبكة الإنترنت المنزلية</label></div>
  <div class="row"><span>رمز دخول للأجهزة الأخرى (4 أرقام أو أكثر):</span><input type="password" id="lanpin" placeholder="${l.pin?'محفوظ':'مثلاً 2580'}" inputmode="numeric"><button class="ibtn primary" id="lansave">حفظ</button></div>
  <span class="hint" style="font-size:12.5px;color:var(--muted);line-height:1.9">${l.running_lan?`مفعّل الآن. افتح على جوالك: <code>http://${esc(l.ip)}:${l.port}</code> ثم من قائمة المتصفح اختر «إضافة إلى الشاشة الرئيسية»، فتظهر أيقونة المركز كتطبيق.`:(l.lan?'سيُفعَّل بعد إعادة تشغيل البرنامج.':'بعد التفعيل وإعادة التشغيل يظهر هنا الرابط الذي تفتحه من جوالك.')}
  <br>ضع رمز دخول دائماً، فبدونه يستطيع أي جهاز على الشبكة نفسها فتح المركز. وقد يطلب ويندوز السماح للبرنامج في الجدار الناري عند أول تشغيل، فاختر «السماح».</span></div>`}
async function renderHealth(){
 const feed=$('#feed');feed.className='feed list';$('#more').hidden=true;
 try{LANS=await api('/api/settings')}catch(e){}
 const d=await api('/api/sources');HEALTH=d.items;
 if(!d.items.length){feed.innerHTML=trHtml()+'<div class="empty"><b>لم تكتمل أول دورة جلب بعد</b>انتظر قليلاً ثم عُد إلى هذه الصفحة.</div>';return}
 drawHealth()}
function drawHealth(){
 const bad=HEALTH.filter(s=>!s.ok);const rows=HONLY?bad:HEALTH;
 $('#feed').innerHTML=trHtml()+`<div class="htools"><div class="seg"><button id="hall" class="${HONLY?'':'on'}">كل المصادر (${HEALTH.length})</button><button id="hbad" class="${HONLY?'on':''}">المتعطلة فقط (${bad.length})</button></div><span class="sp" style="flex:1"></span>${bad.length?'<button class="ibtn" id="hcopy">'+ico('copy')+'نسخ روابط المتعطلة</button>':''}</div>
 <div class="tablewrap box"><table><thead><tr><th>المصدر</th><th>القسم</th><th>الحالة</th><th>الموقع والرابط</th><th>طريقة الجلب</th><th>العناصر</th><th>آخر نجاح</th><th>ملاحظة</th></tr></thead><tbody>${
  rows.map(s=>`<tr class="${s.ok?'':'broken'}"><td>${esc(s.name)}</td><td>${esc(CAT[s.cat]?.name||(s.cat==='books'?'مكتبة الكتب':s.cat))}</td><td class="${s.ok?'ok':'bad'}">${s.ok?'يعمل':'متعطل'}</td>
   <td class="lnk">${s.site?`<a href="${esc(s.site)}" target="_blank" rel="noopener">${ico('link')}${esc(hostOf(s.site))}</a>`:''}${s.feed?`<a href="${esc(s.feed)}" target="_blank" rel="noopener" title="${esc(s.feed)}">${ico('pulse')}رابط الخلاصة</a><span class="u">${esc(s.feed)}</span>`:''}${!s.site&&!s.feed?'—':''}</td>
   <td>${esc(s.via)}</td><td class="mt">${s.count}</td><td>${s.last_ok?ago(s.last_ok):'—'}</td><td class="err">${esc(s.error||'')}</td></tr>`).join('')}</tbody></table></div>`}
function copyBroken(){
 const t=HEALTH.filter(s=>!s.ok).map(s=>`${s.name}\n  الموقع: ${s.site||'—'}\n  الخلاصة: ${s.feed||'—'}\n  الخطأ: ${s.error||'—'}`).join('\n\n');
 navigator.clipboard.writeText(t).then(()=>toast('نُسخت روابط المصادر المتعطلة'),()=>toast('تعذّر النسخ'))}

/* لوحة القيادة */
async function loadDash(){
 if(META)renderKpis();
 try{
  const d=await api('/api/boards');
  $('#boards').innerHTML=d.boards.map(b=>{b.items.forEach(i=>ITEMS.set(i.id,i));
   return `<section class="box board" style="--c:${b.color}"><div class="boxh" style="--c:${b.color}">${ico(CICON[b.key])}${esc(b.name)}<span class="sp"></span><button class="lnk" data-cat="${b.key}">عرض الكل</button></div>
   ${b.items.length?`<ol>${b.items.map(i=>`<li><button class="bt${seen(i.id)?' seen':''}" data-open="${i.id}"><time>${Date.now()/1000-i.published<86400?hm(i.published):dm(i.published)}</time><span><span class="t${i.translated===1?'':' pend'}">${esc(T(i))}</span><span class="s">${esc(i.source_ar)}</span></span></button></li>`).join('')}</ol>`:'<div class="empty-s">لا مواد بعد.</div>'}</section>`}).join('');
 }catch(e){$('#boards').innerHTML='<div class="empty"><b>تعذّر الاتصال بالخادم</b>تأكد أن البرنامج ما زال يعمل.</div>'}
 loadTweets();loadCty().then(renderDashCty).catch(()=>{});loadQualBox()}

/* الأخبار النوعية */
let QSTATS=null;const EVC={};let QF='';
async function loadQStats(){QSTATS=await api('/api/qual/stats?hours=24');QSTATS.types.forEach(t=>EVC[t.name]=t.color);return QSTATS}
function qtypesHtml(cur,attr){return `<button class="qt${!cur?' on':''}" ${attr}="" style="--e:var(--red)">الكل <b>${QSTATS.total}</b></button>`+QSTATS.types.filter(t=>t.count||t.name===cur).map(t=>`<button class="qt${cur===t.name?' on':''}" ${attr}="${esc(t.name)}" style="--e:${t.color}"><i></i>${esc(t.name)} <b>${t.count}</b></button>`).join('')}
let QITEMS=[],QIDX=0,QTIMER=null;
async function loadQualBox(){
 try{await loadQStats();$('#qtypes').innerHTML=qtypesHtml(QF,'data-qf');
  let d=await api('/api/items?'+new URLSearchParams({cat:'all',qual:'1',event:QF,hours:24,per:20}));
  if(!d.items.length)d=await api('/api/items?'+new URLSearchParams({cat:'all',qual:'1',event:QF,hours:72,per:20}));
  d.items.forEach(i=>ITEMS.set(i.id,i));
  const cur=QITEMS[QIDX]?.id;QITEMS=d.items;
  const k=QITEMS.findIndex(i=>i.id===cur);QIDX=k>=0?k:0;
  showQ(QIDX,k<0);
 }catch(e){}}
function showQ(i,animate=true){
 const box=$('#qslide');if(!box)return;
 if(!QITEMS.length){box.style.removeProperty('--e');box.innerHTML='<div class="qempty" style="grid-column:1/-1">لا توجد أحداث نوعية من هذا النوع حالياً.</div>';$('#qdots').innerHTML='';$('#qpos').textContent='';$('#qprog').className='';clearTimeout(QTIMER);return}
 QIDX=(i+QITEMS.length)%QITEMS.length;const it=QITEMS[QIDX];
 const e1=(it.events||'').split('|').filter(Boolean)[0];const col=EVC[e1]||'var(--red)';
 $('#qcar').style.setProperty('--e',col);
 box.dataset.open=it.id;box.setAttribute('role','button');box.tabIndex=0;
 box.innerHTML=`<div class="clock2"><b>${hm(it.published)}</b><small>${ago(it.published)}</small></div>
  <div><div class="meta">${evHtml(it.events)}${vfHtml(it)}${(it.countries||'').split('|').filter(Boolean).slice(0,3).map(c=>`<span class="tag cty">${esc(c)}</span>`).join('')}${seen(it.id)?'<span class="badge seen">✓ تمت زيارتها</span>':''}</div>
   <h3>${esc(T(it))}</h3>${it.summary_ar?`<p>${esc(it.summary_ar)}</p>`:''}<div class="src2">${esc(it.source_ar)}، ${esc(CAT[it.cat]?.name||'')}</div></div>
  <span class="ibtn read">${ico('open')}اقرأ</span>`;
 if(animate){box.classList.remove('anim');void box.offsetWidth;box.classList.add('anim')}
 const n=Math.min(QITEMS.length,20);
 $('#qdots').innerHTML=QITEMS.slice(0,n).map((_,j)=>`<button data-qgo="${j}" class="${j===QIDX?'on':''}" aria-label="الخبر ${j+1}"></button>`).join('');
 $('#qpos').textContent=`${QIDX+1}/${QITEMS.length}`;
 const bar=$('#qprog');bar.className='';void bar.offsetWidth;bar.className='run';
 clearTimeout(QTIMER);QTIMER=null}
$('#qprog').addEventListener('animationend',()=>{if(S.cat==='dash')showQ(QIDX+1)});
$('#qprev').onclick=()=>showQ(QIDX-1);$('#qnext').onclick=()=>showQ(QIDX+1);
async function renderQualFilter(){try{await loadQStats();$('#qualfilter').innerHTML=qtypesHtml(S.event||'','data-qev')}catch(e){}}

/* الدول */
let CTY=[];const CTYF={q:'',region:''};let BOOKS_N=0;
async function loadCty(){const d=await api('/api/countries');CTY=d.items;return CTY}
function renderDashCty(){
 const top=CTY.slice().sort((a,b)=>b.day-a.day||b.count-a.count).slice(0,10);const max=Math.max(1,...top.map(c=>c.day||c.count));
 $('#dashCty').innerHTML=top.length?top.map(c=>`<li><button data-country="${esc(c.name)}">${flagHtml(c.iso)}<span>${esc(c.name)}</span><span class="n">${c.day}</span><span class="cbar"><i style="width:${Math.round((c.day||c.count)/max*100)}%"></i></span></button></li>`).join(''):'<li class="count" style="padding:12px 14px">تظهر بعد ترجمة المواد.</li>'}
async function renderCountries(){
 $('#ctygrid').innerHTML='<div class="loading spinner">جارٍ تحميل الدول…</div>';
 try{await loadCty()}catch(e){$('#ctygrid').innerHTML='<div class="empty"><b>تعذّر التحميل</b></div>';return}
 const regs=['',...new Set(CTY.map(c=>c.region).filter(Boolean))];
 $('#ctyregion').innerHTML=regs.map(r=>`<button data-ctyregion="${esc(r)}" class="${CTYF.region===r?'on':''}">${esc(r||'كل المناطق')}</button>`).join('');
 renderCtyGrid()}
function flagHtml(iso,cls){iso=(iso||'').trim();if(!/^[A-Za-z]{2}$/.test(iso))return `<span class="iso ${cls||''}">${esc(iso||'—')}</span>`;
 return `<span class="iso flag ${cls||''}" title="${esc(iso)}"><img src="/flag/${iso.toLowerCase()}" alt="${esc(iso)}" loading="lazy" onerror="this.parentNode.classList.remove('flag');this.replaceWith(this.alt)"></span>`}
function ctyCard(c,max){return `<button class="ctycard" data-country="${esc(c.name)}"><span class="top2">${flagHtml(c.iso)}<b>${esc(c.name)}</b></span><span class="nums"><span><em>${c.count}</em>مادة في الشهر</span><span><em>${c.day}</em>اليوم</span></span><span class="cbar"><i style="width:${Math.round(c.count/max*100)}%"></i></span></button>`}
function renderCtyGrid(){
 const l=CTY.filter(c=>(!CTYF.region||c.region===CTYF.region)&&(!CTYF.q||c.name.includes(CTYF.q)||c.iso.toLowerCase()===CTYF.q.toLowerCase()));
 $('#ctycount').textContent=l.length+' دولة';
 if(!l.length){$('#ctygrid').innerHTML='<div class="empty"><b>لا توجد دول مطابقة</b>ستظهر الدول بعد ربط المواد بها، وهذا يحدث تلقائياً مع وصول الأخبار وترجمتها.</div>';return}
 const max=Math.max(...l.map(c=>c.count));
 if(CTYF.region||CTYF.q){$('#ctygrid').innerHTML='<div class="cgrid2">'+l.map(c=>ctyCard(c,max)).join('')+'</div>';return}
 const groups={};l.forEach(c=>(groups[c.region||'أخرى']=groups[c.region||'أخرى']||[]).push(c));
 $('#ctygrid').innerHTML=Object.entries(groups).map(([r,cs])=>`<div class="regionh">${esc(r)}</div><div class="cgrid2">${cs.map(c=>ctyCard(c,max)).join('')}</div>`).join('')}
function openCountry(name){S.country=name;setView('country')}
async function renderCountryHead(){
 const name=S.country;document.title=name+' | '+TITLE_DEFAULT;
 $('#countryhead').innerHTML=`<button class="back" data-cat="countries">${ico('arrow')}كل الدول</button><div class="box chero"><span class="spinner">…</span></div>`;
 try{const d=await api('/api/country/'+encodeURIComponent(name));if(S.country!==name)return;
  $('#countryhead').innerHTML=`<button class="back" data-cat="countries">${ico('arrow')}كل الدول</button>
  <div class="box chero" style="--c:var(--acc)">${flagHtml(d.iso,'big')}
   <div class="grow"><h1>${esc(name)}</h1><div class="cmeta">${d.region?`<span class="pill">${esc(d.region)}</span>`:''}${d.cats.slice(0,4).map(c=>`<span>${esc(CAT[c.cat]?.name||c.cat)}: ${c.count}</span>`).join('')}</div></div>
   <div class="num"><b>${d.count}</b><span>مادة خلال الشهر</span></div></div>
  ${d.tags.length?`<div class="box ctopics"><div class="tags" style="padding:0"><span class="clbl">مواضيع مرتبطة:</span>
   <button class="tag${!S.tag?' on':''}" data-ctag="">كل المواضيع</button>
   ${d.tags.map(t=>`<button class="tag${S.tag===t.tag?' on':''}" data-ctag="${esc(t.tag)}">${esc(t.tag)} <em>${t.count}</em></button>`).join('')}</div></div>`:''}`}catch(e){}}

/* التحقق: فتح أول خبر من العنقود مع قائمة البقية */
async function openCluster(cid){try{const d=await api('/api/cluster/'+encodeURIComponent(cid));d.items.forEach(x=>ITEMS.set(x.id,x));if(d.items.length)openItem(d.items[0].id)}catch(e){}}

/* الإنذار المبكر */
let ALN=0,ALH=48,ALSEEN=+lsGet('rased_alseen','0');
const LVC={3:'#F43F5E',2:'#F59E0B',1:'#38BDF8'};
function alertHtml(a,now_){const tl=a.kind==='field'?'تصاعد ميداني':(a.kind==='country'?'ارتفاع مفاجئ':'موضوع صاعد');
 const btn=a.kind==='topic'?`<button class="ibtn" data-altopic="${esc(a.key)}">عرض الأخبار</button>`:`<button class="ibtn" data-alcountry="${esc(a.key)}">عرض ${esc(a.key)}</button>`;
 return `<div class="al" style="--lc:${LVC[a.level]||LVC[2]}"><span class="lv">${a.level>=3?'إنذار عالٍ':'إنذار'}</span><div><b>${esc(a.msg)}</b><small>${tl} · ${ago(a.created)}</small></div><div class="acts2">${btn}${a.kind!=='topic'?`<button class="ibtn" data-cat="map">الخريطة</button>`:''}</div></div>`}
async function loadAlertCount(){try{const d=await api('/api/alerts?hours=24');const fresh=d.items.filter(a=>a.created>ALSEEN);ALN=fresh.length;
 const b=$('#belln');b.hidden=true;
 const act=d.items.filter(a=>d.now-a.created<6*3600).slice(0,3);
 $('#dashAlerts').innerHTML=act.map(a=>alertHtml(a,d.now)).join('');return d}catch(e){}}
async function loadAlerts(){
 try{const d=await api('/api/alerts?hours='+ALH);
  $('#alcount').textContent=d.items.length+' إنذار';
  $('#allist').innerHTML=d.items.length?d.items.map(a=>alertHtml(a,d.now)).join(''):'<div class="empty"><b>لا توجد إنذارات في هذه المدة</b>يفحص المركز كل 5 دقائق: إذا قفز الحديث عن دولة أو موضوع إلى 3 أضعاف معدله المعتاد أو أكثر، أو توالت 3 أحداث نوعية في دولة خلال ساعتين، يظهر الإنذار هنا وفي الجرس أعلى الصفحة، ويُرسل إلى بوت تيليغرام إن كان مفعّلاً.</div>';
  ALSEEN=d.now;lsSet('rased_alseen',ALSEEN);ALN=0;$('#belln').hidden=true;$('#bell').classList.remove('hot');
 }catch(e){}}

/* الخريطة التفاعلية */
let MAP=null,MLAYER=null,DLAYER=null,MAPH=24,MAPOFF=new Set(),LEAF=null;
function loadLeaflet(){if(LEAF)return LEAF;LEAF=new Promise((ok,no)=>{const l=document.createElement('link');l.rel='stylesheet';l.href='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';document.head.appendChild(l);
 const sc=document.createElement('script');sc.src='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';sc.onload=ok;sc.onerror=()=>{LEAF=null;no()};document.head.appendChild(sc)});return LEAF}
const TILES=[
 {url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',attr:'&copy; OpenStreetMap',dark:'invert'},
 {url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',attr:'&copy; Esri',dark:'native',light:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'},
 {url:'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',attr:'&copy; OpenStreetMap France',dark:'invert'}];
let TIDX=0,TERR=0,TOK=0,LBL=null;
let MAPSTYLE=lsGet('rased_mapstyle','general');
const MSTYLES={detailed:{url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',attr:'&copy; OpenStreetMap',max:19},
 satellite:{url:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',attr:'&copy; Esri',max:19,labels:'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'},
 terrain:{url:'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',attr:'&copy; OpenTopoMap',max:17}};
const MZOOM={sy:[[35.0,38.6],7],me:[[30,40],5],world:[[25,20],2]};
function applyMapStyle(){if(!MAP||!TILE)return;const st=MSTYLES[MAPSTYLE];
 TILE.options.maxZoom=st?st.max:18;MAP.setMaxZoom(st?st.max:18);TILE.options.attribution=st?st.attr:TILES[TIDX].attr;TILE.setUrl(tileUrl());tileFilter();
 if(LBL){MAP.removeLayer(LBL);LBL=null}
 if(st&&st.labels){LBL=L.tileLayer(st.labels,{maxZoom:st.max,pane:'overlayPane',opacity:.95}).addTo(MAP)}
 if(MAP.attributionControl){MAP.attributionControl.removeAttribution(TILES[TIDX].attr);Object.values(MSTYLES).forEach(x=>MAP.attributionControl.removeAttribution(x.attr));MAP.attributionControl.addAttribution(st?st.attr:TILES[TIDX].attr)}}
function tileUrl(){if(MSTYLES[MAPSTYLE])return MSTYLES[MAPSTYLE].url;const t=TILES[TIDX];const light=document.documentElement.dataset.theme==='light';return (light&&t.light)?t.light:t.url}
function tileFilter(){const t=TILES[TIDX];const light=document.documentElement.dataset.theme==='light';
 $('#map').classList.toggle('mapdark',MAPSTYLE==='general'&&!light&&t.dark==='invert')}
function nextTiles(){if(MAPSTYLE!=='general'||TIDX>=TILES.length-1)return;TIDX++;TERR=0;TOK=0;TILE.setUrl(tileUrl());TILE.options.attribution=TILES[TIDX].attr;tileFilter()}
let TILE=null;
async function loadMap(refresh){
 try{await loadLeaflet()}catch(e){$('#map').innerHTML='<div class="mapnote">تعذّر تحميل مكتبة الخرائط. تأكد من اتصال الإنترنت ثم أعد فتح الصفحة.</div>';return}
 if(!MAP){MAP=L.map('map',{zoomControl:true,worldCopyJump:true,attributionControl:true}).setView([30,38],4);
  TILE=L.tileLayer(tileUrl(),{maxZoom:18,attribution:TILES[TIDX].attr,crossOrigin:true}).addTo(MAP);
  TILE.on('tileload',()=>{TOK++});
  TILE.on('tileerror',()=>{TERR++;if(TERR>=6&&TOK<3)nextTiles()});
  MLAYER=L.layerGroup().addTo(MAP);DLAYER=L.layerGroup().addTo(MAP);$('#mapstyle').value=MAPSTYLE;applyMapStyle();}
 TILE.setUrl(tileUrl());tileFilter();setTimeout(()=>MAP.invalidateSize(),60);
 let d;try{d=await api('/api/map?hours='+MAPH)}catch(e){return}
 MLAYER.clearLayers();DLAYER.clearLayers();
 (d.net||[]).forEach(n=>{const col=n.level==='critical'?'#A855F7':'#C4B5FD';
  L.circleMarker([n.lat,n.lon],{radius:16,color:col,weight:2,dashArray:'4 4',fill:true,fillColor:col,fillOpacity:.12}).bindTooltip(`انقطاع إنترنت ${n.level==='critical'?'حرج':'جزئي'}: ${n.name}`,{direction:'top'}).addTo(MLAYER)});
 if($('#mapdens').checked){const mx=Math.max(1,...d.density.map(x=>x.count));
  d.density.forEach(c=>L.circle([c.lat,c.lon],{radius:60000+340000*Math.sqrt(c.count/mx),color:'#38BDF8',weight:1,opacity:.5,fillOpacity:.12,interactive:true}).bindTooltip(`${c.name}: ${c.count} خبراً`,{direction:'top'}).addTo(DLAYER))}
 const counts={};
 d.points.forEach(p=>{const e1=p.events[0];counts[e1]=(counts[e1]||0)+1;if(MAPOFF.has(e1))return;
  const m=L.circleMarker([p.lat,p.lon],{radius:p.exact?8:6,color:'#fff',weight:p.exact?1.5:1,fillColor:p.color,fillOpacity:.9});
  m.bindPopup(`<div><span class="meta">${evHtml(p.events.join('|'))}</span><div class="pt">${esc(p.title)}</div><div style="color:#888;font-size:12px">${esc(p.place)}${p.exact?'':' (موقع تقريبي)'} · ${esc(p.source)} · ${ago(p.published)}${p.nsrc>=3?' · ✓ مؤكد':''}</div><button class="ibtn primary" data-open="${p.id}">اقرأ الخبر</button></div>`);
  m.addTo(MLAYER)});
 $('#maplegend').innerHTML=(QSTATS?QSTATS.types:[]).filter(t=>counts[t.name]).map(t=>`<label><input type="checkbox" data-mev="${esc(t.name)}"${MAPOFF.has(t.name)?'':' checked'}><i style="--e:${t.color}"></i>${esc(t.name)}<em>${counts[t.name]}</em></label>`).join('')||'<span class="mapcount">لا أحداث نوعية في هذه المدة.</span>';
 $('#mapcount').textContent=d.points.length+' حدثاً على الخريطة'}
document.addEventListener('change',e=>{if(e.target.id==='mapstyle'){MAPSTYLE=e.target.value;lsSet('rased_mapstyle',MAPSTYLE);applyMapStyle();if(MAPSTYLE!=='general'&&MAP.getZoom()<6&&MAP.getBounds().contains([35,38.6]))MAP.setView(MZOOM.sy[0],MZOOM.sy[1]);return}if(e.target.id==='mapdens')return loadMap();if(e.target.dataset.mev){e.target.checked?MAPOFF.delete(e.target.dataset.mev):MAPOFF.add(e.target.dataset.mev);loadMap()}});

document.addEventListener('click',e=>{const b=e.target.closest('[data-mz]');if(!b||!MAP)return;const z=MZOOM[b.dataset.mz];MAP.flyTo(z[0],z[1],{duration:.8})});

/* اسأل المركز */
let ASKTXT='',ASKREFS=[];
const ASKEX=['ماذا جرى في سوريا خلال آخر يومين؟','ما آخر ما نُشر عن تنظيم داعش في البادية؟','ما أبرز الأحداث في السودان هذا الأسبوع؟','ما موقف الولايات المتحدة من التصعيد في لبنان؟'];
function initAsk(){if(!$('#askex').innerHTML)$('#askex').innerHTML='<span class="hint" style="font-size:12px;color:var(--faint)">أمثلة:</span>'+ASKEX.map(x=>`<button data-askex="${esc(x)}">${esc(x)}</button>`).join('');setTimeout(()=>$('#askq').focus(),50)}
async function askGo(){
 const qq=$('#askq').value.trim();if(!qq)return;ASKTXT='';$('#askcopy').disabled=true;
 $('#askout').innerHTML='<div class="spinner">جارٍ البحث في المواد المرصودة…</div>';$('#askrefs').innerHTML='';
 let d;try{d=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:qq,days:$('#askdays').value})})}catch(e){$('#askout').innerHTML=`<div class="wempty">${esc(e.message)}</div>`;return}
 ASKREFS=d.refs;$('#askn').textContent=d.refs.length+' مادة';
 d.refs.forEach(r=>ITEMS.has(r.id)||ITEMS.set(r.id,r));
 $('#askrefs').innerHTML=d.refs.map((r,i)=>`<li><button data-open="${r.id}"><span class="k">${i+1}</span><span><span class="meta"><span class="src" style="--c:${CAT[r.cat]?.color||'var(--acc)'}">${esc(r.source_ar)}</span><span>${ago(r.published)}</span></span>${esc(r.title_ar||r.title)}</span></button></li>`).join('')||'<li class="count" style="padding:12px 14px">لم يُعثر على مواد.</li>';
 $('#askout').innerHTML='<div class="spinner">جارٍ كتابة الإجابة…</div>';
 try{const r=await fetch('/api/ask/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:qq,ids:d.refs.map(x=>x.id)})});
  const rd=r.body.getReader();const dec=new TextDecoder();
  while(true){const {done,value}=await rd.read();if(done)break;ASKTXT+=dec.decode(value,{stream:true});ASKTXT=ASKTXT.split('[[WAIT]]').join('').split('[[END]]').join('');
   const k=ASKTXT.indexOf('[[ERROR]]');if(k>=0){const err=ASKTXT.slice(k+9);ASKTXT=ASKTXT.slice(0,k);toast(err.slice(0,140));if(!ASKTXT.trim()){$('#askout').innerHTML=`<div class="wempty">${esc(err)}</div>`;break}}
   askRender()}
 }catch(e){toast('انقطع الاتصال')}
 askRender(true)}
function askRender(done){const h=md(ASKTXT).replace(/\[(\d+(?:\s*[،,]\s*\d+)*)\]/g,(m,g)=>'<sup>'+g.split(/\s*[،,]\s*/).map(n=>{const r=ASKREFS[+n-1];return r?`<a href="#" data-open="${r.id}" title="${esc(r.source_ar)}">[${n}]</a>`:`[${n}]`}).join('')+'</sup>');
 $('#askout').innerHTML=h+(done?'':'<span class="cursor"></span>');$('#askstat').textContent=ASKTXT.trim()?ASKTXT.trim().split(/\s+/).length+' كلمة':'';$('#askcopy').disabled=!ASKTXT.trim()}
$('#askq').addEventListener('keydown',e=>{if(e.key==='Enter')askGo()});

/* العقوبات والتصنيفات */
let SANCMODE='terror',SANCGROUP='',SANCPAGE=1,sqt;
async function loadSanc(){
 $('#sancterrorlbl').hidden=SANCMODE==='terror';$('#sancgroups').hidden=SANCMODE!=='terror';
 try{const d=await api('/api/sanctions?'+new URLSearchParams({mode:SANCMODE,group:SANCGROUP,page:SANCPAGE,q:$('#sancq').value.trim(),terror:$('#sancterror').checked?'1':''}));
  const st=d.state;
  $('#sanclists').innerHTML=d.lists.map(l=>`<div class="box sl"><b>${esc(l.name)}</b><span><span class="n">${l.count||0}</span> اسماً</span>
   <span class="wstat">${l.ok===1?'<span class="ok">● تعمل</span>':(l.ok===0?'<span class="bad">● متعطلة</span>':'● لم تُنزَّل بعد')}${l.last_ok?' · آخر نجاح '+ago(l.last_ok):''}</span>
   ${l.ok===0&&l.error?`<span class="e">${esc(l.error)}</span>`:''}</div>`).join('')+`<div class="box sl"><b>المصنَّفون إرهابياً في القائمتين</b><span><span class="n">${d.terror_total||0}</span> فرداً وكياناً</span><span class="wstat">داعش والقاعدة والنصرة وحزب الله والحرس الثوري وغيرها</span></div>`;
  $('#sanccount').textContent=st.running?'جارٍ تنزيل القوائم…':`${d.total} نتيجة`+(d.last?' · آخر تحديث '+ago(d.last):'');
  $('#sancref').disabled=!!st.running;
  if(st.running)setTimeout(()=>S.cat==='sanctions'&&loadSanc(),8000);
  $('#sancgroups').innerHTML=`<button class="qt${!SANCGROUP?' on':''}" data-sgroup="" style="--e:var(--red)">كل الجماعات <b>${d.terror_total||0}</b></button>`+d.groups.map(g=>`<button class="qt${SANCGROUP===g.name?' on':''}" data-sgroup="${esc(g.name)}" style="--e:#E11D48"><i></i>${esc(g.name)} <b>${g.count}</b></button>`).join('');
  if(!d.lists.some(l=>l.count)){$('#sanclist').innerHTML=`<div class="empty"><b>${st.running?'يجري تنزيل القوائم الآن، انتظر دقيقة':'لم تُنزَّل القوائم بعد'}</b>${st.running?'':'اضغط «تحديث القوائم».'}</div>`;$('#sancpager').innerHTML='';return}
  const typ=t=>t==='individual'?'فرد':(t==='vessel'?'سفينة':(t==='aircraft'?'طائرة':'كيان'));
  $('#sanclist').innerHTML=d.items.length?`<table class="tbl"><thead><tr><th>الاسم</th><th>النوع</th><th>الجماعة</th><th>القائمة والبرنامج</th><th>تفاصيل</th><th>تاريخ الإدراج</th></tr></thead><tbody>${d.items.map(r=>`<tr><td><span class="sname">${esc(r.name)}</span>${r.is_new?' <span class="newdot">جديد</span>':''}</td><td>${typ(r.type)}</td><td>${(r.groups||'').split('|').filter(Boolean).map(g=>`<span class="pg t">${esc(g)}</span>`).join('')||'—'}</td><td>${esc(r.list)}<span class="sub">${(r.program_ar||'').split('، ').filter(Boolean).slice(0,4).map(p=>`<span class="pg">${esc(p)}</span>`).join('')}</span></td><td style="max-width:380px"><span class="sub" dir="auto" style="margin:0">${esc((r.remarks||'').slice(0,240))}</span></td><td class="mt" style="white-space:nowrap">${r.listed?esc(r.listed):(r.is_new?'رُصد '+fmt(r.first_seen):'—')}</td></tr>`).join('')}</tbody></table>`
   :'<div class="empty"><b>لا نتائج</b>جرّب اسماً آخر أو جماعة أخرى.</div>';
  $('#sancpager').innerHTML=d.pages>1?`<button class="ibtn" data-spg="${d.page-1}" ${d.page<=1?'disabled':''}>السابق</button><span class="mt">صفحة ${d.page} من ${d.pages}</span><button class="ibtn" data-spg="${d.page+1}" ${d.page>=d.pages?'disabled':''}>التالي</button>`:'';
 }catch(e){$('#sanclist').innerHTML='<div class="empty"><b>تعذّر الاتصال بالبرنامج</b></div>'}}
$('#sancq').oninput=()=>{clearTimeout(sqt);sqt=setTimeout(()=>{SANCPAGE=1;loadSanc()},400)};$('#sancterror').onchange=()=>{SANCPAGE=1;loadSanc()};

/* ملفات القضايا */
let CASE=null,PICKITEM=null,CASES=[];
async function loadCases(){try{const d=await api('/api/cases');CASES=d.items;
 $('#caselist').innerHTML=d.items.length?d.items.map(c=>`<li><button data-case="${c.id}" class="${c.id===CASE?'on':''}"><b>${esc(c.title)}</b><small>${c.n} مادة · ${ago(c.updated)}</small></button></li>`).join(''):'<li class="count" style="padding:12px 14px">لا توجد قضايا بعد.</li>';
 if(CASE)openCase(CASE)}catch(e){}}
async function openCase(cid){CASE=cid;document.querySelectorAll('[data-case]').forEach(b=>b.classList.toggle('on',b.dataset.case===cid));
 try{const d=await api('/api/cases/'+cid);const c=d.case;
  d.items.forEach(i=>ITEMS.has(i.id)||ITEMS.set(i.id,i));
  $('#casedetail').innerHTML=`<div class="boxh"><input id="ctitle" value="${esc(c.title)}" style="flex:1;font:700 15px var(--fd);background:none;border:0;color:var(--text)"><a class="ibtn" href="/print/case/${cid}" target="_blank" rel="noopener">${ico('pdf')}تقرير PDF</a><button class="ibtn" id="casesave">حفظ</button><button class="ibtn" id="casedel" style="color:var(--red)">حذف</button></div>
   <div style="padding:10px 16px"><textarea id="cdescr" placeholder="وصف القضية أو فرضيتها…" style="width:100%;min-height:50px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:8px 10px;color:var(--text);font:14px 'IBM Plex Sans Arabic'">${esc(c.descr||'')}</textarea></div>
   ${d.items.length?d.items.map(i=>`<div class="citem"><div class="meta"><span class="src" style="--c:${CAT[i.cat]?.color||'var(--acc)'}">${esc(i.source_ar)}</span><span>${fmt(i.published)}</span>${i.archived?'<span class="badge seen">مؤرشف</span>':''}</div><h4><button class="ttl" data-open="${i.id}">${esc(i.title_ar||i.title)}</button></h4>
    <textarea data-noteof="${i.id}" placeholder="ملاحظتك على هذه المادة…">${esc(i.note||'')}</textarea>
    <div class="row"><button class="ibtn" data-cnote="${i.id}" style="height:30px">حفظ الملاحظة</button>${i.link?`<a class="ibtn" href="${esc(i.link)}" target="_blank" rel="noopener" style="height:30px">المصدر</a>`:''}<button class="ibtn" data-archopen="${i.id}" style="height:30px">النسخة المؤرشفة</button><button class="ibtn" data-cidel="${i.id}" style="height:30px;color:var(--red)">إزالة</button></div></div>`).join(''):'<div class="wempty">لا مواد في هذه القضية بعد. افتح أي خبر واضغط «ملف قضية».</div>'}`}catch(e){}}
async function pickCase(iid){PICKITEM=iid;let cs=[];try{cs=(await api('/api/cases')).items}catch(e){}
 const el=document.createElement('div');el.className='casepick';el.id='casepick';
 el.innerHTML=`<div class="box"><b style="font:700 15px var(--fd)">أضف المادة إلى ملف قضية</b>${cs.length?`<div class="opts">${cs.map(c=>`<button data-pickcase="${c.id}">${esc(c.title)} <span class="wstat">(${c.n})</span></button>`).join('')}</div><span class="hint" style="font-size:12px;color:var(--faint)">أو أنشئ قضية جديدة:</span>`:''}<input id="picktitle" placeholder="عنوان قضية جديدة"><div style="display:flex;gap:8px"><button class="ibtn primary" id="picknew">إنشاء وإضافة</button><button class="ibtn" id="pickclose">إلغاء</button></div></div>`;
 ($('#dlg').open?$('#dlg'):document.body).appendChild(el)}
function addToCase(cid,iid){api('/api/cases/'+cid,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:iid})}).then(()=>{$('#casepick')?.remove();toast('أُضيفت المادة إلى القضية وتُؤرشف الآن')})}

/* الأرشيف والعناوين المعدّلة */
let ATAB='arch',aqt,AH=24,APAGE=1;
function pagerHtml(p,pages){return pages>1?`<button class="ibtn" data-apg="${p-1}" ${p<=1?'disabled':''}>السابق</button><span class="mt">صفحة ${p} من ${pages}</span><button class="ibtn" data-apg="${p+1}" ${p>=pages?'disabled':''}>التالي</button>`:''}
async function loadArch(){
 const qq=$('#archq').value.trim();
 const prm=new URLSearchParams({q:qq,hours:AH,page:APAGE});
 $('#archclear').hidden=ATAB!=='arch';
 $('#archq').placeholder=ATAB==='arch'?'ابحث في الأرشيف كله…':'ابحث في كل العناوين المعدّلة…';
 if(ATAB==='edits'){try{const d=await api('/api/edits?'+prm);
  $('#archcount').textContent=(qq?'نتائج البحث: ':'')+d.count+' تعديل';
  $('#archlist').innerHTML=d.items.length?`<table class="tbl"><thead><tr><th>المصدر</th><th>العنوان السابق ← الجديد</th><th>وقت التعديل</th><th></th></tr></thead><tbody>${d.items.map(c=>`<tr><td style="white-space:nowrap">${esc(c.source_ar||'')}</td><td><del dir="auto" style="color:var(--red)">${esc(c.old_title)}</del><br><ins dir="auto" style="color:var(--green);text-decoration:none">${esc(c.new_title)}</ins>${c.new_ar?`<span class="sub">${esc(c.new_ar)}</span>`:''}<br><button data-open="${c.item_id}" style="all:unset;cursor:pointer;color:var(--acc2);font-size:12.5px">فتح الخبر</button></td><td class="mt" style="white-space:nowrap">${fmt(c.changed)}</td><td><button class="del" data-edel="${c.rid}" title="حذف من السجل" aria-label="حذف">×</button></td></tr>`).join('')}</tbody></table>`
   :`<div class="empty"><b>${qq?'لا نتائج':'لا تعديلات في هذه المدة'}</b>${qq?'جرّب كلمة أخرى.':'حين تغيّر صحيفة عنوان خبر بعد نشره يُسجَّل هنا. جرّب مدة أطول من الأزرار أعلاه.'}</div>`;
  $('#archpager').innerHTML=pagerHtml(d.page,d.pages)}catch(e){}return}
 try{const d=await api('/api/archive?'+prm);
  $('#archcount').textContent=(qq?`نتائج البحث في كل الأرشيف: ${d.count}`:`${d.count} مادة في هذه المدة`)+` · الأرشيف كله ${d.total}`;
  $('#archlist').innerHTML=d.items.length?`<table class="tbl"><thead><tr><th>المادة</th><th>سبب الأرشفة</th><th>وقت الأرشفة</th><th></th></tr></thead><tbody>${d.items.map(a=>`<tr><td><b dir="auto">${esc(a.title_ar||a.title)}</b><span class="sub">${esc(a.source||'')}، نُشر ${fmt(a.published)}</span></td><td style="white-space:nowrap">${esc(a.reason||'')}${a.wayback?'<span class="sub">+ أرشيف الإنترنت</span>':''}</td><td class="mt" style="white-space:nowrap">${fmt(a.captured)}</td><td style="white-space:nowrap"><button class="ibtn" data-archopen="${a.item_id}" style="height:30px">عرض</button>${a.wayback?` <a class="ibtn" href="${esc(a.wayback)}" target="_blank" rel="noopener" style="height:30px">Wayback</a>`:''} <button class="del" data-adel="${a.item_id}" title="حذف من الأرشيف" aria-label="حذف">×</button></td></tr>`).join('')}</tbody></table>`
   :`<div class="empty"><b>${qq?'لا نتائج في الأرشيف':'لا مواد مؤرشفة في آخر '+(AH==24?'24 ساعة':'مدة')}</b>${qq?'جرّب كلمة أخرى.':'تُؤرشف تلقائياً الأخبار النوعية وكل مقال تفتحه أو تحفظه أو تضيفه لقضية. اختر «الكل» لرؤية الأرشيف الأقدم.'}</div>`;
  $('#archpager').innerHTML=pagerHtml(d.page,d.pages)}catch(e){}}
$('#archq').oninput=()=>{clearTimeout(aqt);aqt=setTimeout(()=>{APAGE=1;loadArch()},400)};
$('#wlogq').oninput=renderWLog;
async function openArchived(iid){try{const d=await api('/api/archive/'+iid);const a=d.item;
 S.openId=null;CUR={id:null,full:null,showOrig:false};
 $('#dlgMeta').innerHTML=`<span class="src">${esc(a.source||'')}</span><span>نسخة محفوظة في ${esc(fmt(a.captured))}</span>`;
 $('#dlgBody').innerHTML=`<div class="dossier">ARCHIVED COPY / ${esc(a.reason||'')}</div><h2 dir="auto">${esc(a.title_ar||a.title)}</h2>
  <div class="dlgacts">${a.link?`<a class="ibtn" href="${esc(a.link)}" target="_blank" rel="noopener">${ico('link')}الرابط الأصلي</a>`:''}${a.wayback?`<a class="ibtn" href="${esc(a.wayback)}" target="_blank" rel="noopener">نسخة أرشيف الإنترنت</a>`:''}</div>
  ${a.paras_ar.length?'<h4>الترجمة</h4>'+a.paras_ar.map(p=>`<p dir="auto">${esc(p)}</p>`).join(''):''}
  <h4>النص الأصلي كما حُفظ</h4><div class="arcsnap">${a.paras.map(p=>`<p dir="auto">${esc(p)}</p>`).join('')||'<p class="note">لا يوجد نص.</p>'}</div>
  <p class="note">مصدر النص: ${esc(a.via||'')}</p>`;
 if(!$('#dlg').open)$('#dlg').showModal()}catch(e){toast('لا توجد نسخة مؤرشفة لهذه المادة بعد')}}

/* انقطاع الإنترنت */
let NETBAD=0;const NLV={critical:['#A855F7','انقطاع حرج'],warning:['#F59E0B','اضطراب جزئي'],normal:['#2BF0B4','طبيعي']};
async function loadNet(){try{const d=await api('/api/net');NETBAD=d.countries.filter(c=>c.level!=='normal').length;
 $('#netgrid').innerHTML=d.countries.map(c=>`<div class="box netc" style="--nc:${NLV[c.level][0]}"><b>${esc(c.name)}</b><span class="st">${NLV[c.level][1]}</span>${c.sources.length?`<small>${esc(c.sources.join('، '))}</small>`:''}<small>${c.last?'آخر تنبيه '+ago(c.last):'لا تنبيهات خلال 48 ساعة'}</small><a href="${esc(c.link)}" target="_blank" rel="noopener">المنحنى التفصيلي في IODA</a></div>`).join('');
 $('#netlast').textContent=d.error?'تعذّر التحديث: '+d.error:(d.last?'آخر تحديث '+ago(d.last):'أول تحديث بعد دقيقة من التشغيل');
 $('#netrecent').innerHTML=d.recent.length?`<table class="tbl"><thead><tr><th>الدولة</th><th>المستوى</th><th>المؤشر</th><th>الانخفاض</th><th>الوقت</th></tr></thead><tbody>${d.recent.map(r=>`<tr><td>${esc(r.name)}</td><td style="color:${NLV[r.level][0]};font-weight:700">${NLV[r.level][1]}</td><td>${esc(r.source_ar)}</td><td class="mt">${r.value!=null&&r.hist?Math.max(0,Math.round((1-r.value/r.hist)*100))+'%':'—'}</td><td class="mt" style="white-space:nowrap">${fmt(r.ts)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty"><b>لا انقطاعات مرصودة خلال 48 ساعة</b>يفحص المركز كل 10 دقائق. أي انقطاع حرج يظهر هنا وعلى الخريطة، ويُطلق إنذاراً مبكراً وإشعاراً.</div>'}catch(e){}}

/* الإعدادات */
async function loadSettings(){
 try{LANS=await api('/api/settings');$('#setlan').innerHTML=lanHtml()}catch(e){}
 loadUpdBox()}
async function loadUpdBox(){try{const d=await api('/api/update');const c=d.cfg,st=d.state;
 $('#updbox').innerHTML=`<b style="font:700 14px var(--fd)">التحديث التلقائي من GitHub</b>
  <span style="font-size:13px">الإصدار الحالي: <b class="mt">${esc(d.version)}</b>${st.remote_version?` · على GitHub: <b class="mt">${esc(st.remote_version)}</b>`:''}${st.last?` · آخر فحص ${ago(st.last)}`:''}</span>
  ${st.state?`<span style="font-size:13px" class="${st.ready?'ok':''}">${esc(st.state)}</span>`:''}${st.error?`<span class="warn" style="font-size:12.5px">${esc(st.error)}</span>`:''}
  <label class="opt"><input type="checkbox" id="updauto"${c.auto?' checked':''}>فحص التحديثات تلقائياً كل 3 ساعات وعند التشغيل</label>
  <div class="row"><button class="ibtn primary" id="updcheck">تحقق من التحديث الآن</button>${st.ready?'<button class="ibtn" id="updgo2">إعادة التشغيل لتطبيقه</button>':''}</div>`}catch(e){}}
function updBanner(){$('#updbar').hidden=true}          /* لا شريط إشعار بالتحديث: يُطبَّق عند التشغيل التالي */
document.addEventListener('change',e=>{if(e.target.id==='updauto')api('/api/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({auto:e.target.checked})}).then(()=>toast('حُفظ'))});

/* لوحة الأوامر */
let CMDI=[],CMDS=0;
function cmdOpen(){$('#cmdk').hidden=false;$('#cmdin').value='';cmdFill('');setTimeout(()=>$('#cmdin').focus(),20)}
function cmdClose(){$('#cmdk').hidden=true}
function nrm(t){return (t||'').replace(/[أإآ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').toLowerCase()}
function cmdFill(qq){const n=nrm(qq.trim());const out=[];
 const views=Object.keys(CICON).filter(k=>k!=='bot'&&(EXTRA[k]||CAT[k])).map(k=>({ic:CICON[k],t:EXTRA[k]||CAT[k].name,k:'قسم',run:()=>setView(k)}));
 const ctys=CTY.map(c=>({ic:'flag',t:c.name,k:'دولة',run:()=>openCountry(c.name)}));
 const ctrs=CENTERS.map(c=>({ic:'centers',t:c.name,k:'مركز',run:()=>openCenter(c.name)}));
 const pool=n?[...views,...ctys,...ctrs].filter(o=>nrm(o.t).includes(n)):views;
 out.push(...pool.slice(0,9));
 if(n){out.push({ic:'search',t:`ابحث في الأخبار عن: ${qq.trim()}`,k:'بحث',run:()=>{$('#q').value=qq.trim();S.q=qq.trim();setView('all')}});
  out.push({ic:'search',t:`اسأل المركز: ${qq.trim()}`,k:'سؤال',run:()=>{setView('ask');$('#askq').value=qq.trim();askGo()}});}
 CMDI=out;CMDS=0;cmdDraw()}
function cmdDraw(){$('#cmdlist').innerHTML=CMDI.map((o,i)=>`<li class="${i===CMDS?'on':''}" data-cmdi="${i}">${ico(o.ic)}<span>${esc(o.t)}</span><span class="k">${esc(o.k)}</span></li>`).join('');
 const el=$('#cmdlist .on');el&&el.scrollIntoView({block:'nearest'})}
function cmdRun(i){const o=CMDI[i];if(!o)return;cmdClose();o.run()}
$('#cmdin').addEventListener('input',e=>cmdFill(e.target.value));
$('#cmdin').addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();CMDS=Math.min(CMDI.length-1,CMDS+1);cmdDraw()}else if(e.key==='ArrowUp'){e.preventDefault();CMDS=Math.max(0,CMDS-1);cmdDraw()}else if(e.key==='Enter'){e.preventDefault();cmdRun(CMDS)}else if(e.key==='Escape'){cmdClose()}});
$('#cmdlist').addEventListener('click',e=>{const li=e.target.closest('[data-cmdi]');if(li)cmdRun(+li.dataset.cmdi)});
$('#cmdk').addEventListener('click',e=>{if(e.target.id==='cmdk')cmdClose()});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&(e.key==='k'||e.key==='K'||e.code==='KeyK')){e.preventDefault();$('#cmdk').hidden?cmdOpen():cmdClose()}});

/* بوت تيليغرام */
let BOTD=null,BOTON=false,BOTCH=null;
function bpost(body,msg){return api('/api/bot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(()=>{if(msg)toast(msg);return loadBot()}).catch(e=>{alert(e.message);loadBot()})}
function bch(body,msg){return bpost({...body,ch:BOTCH},msg)}
function bpostJ(url,body){return api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})})}
async function loadBot(statusOnly){
 try{BOTD=await api('/api/bot')}catch(e){return}
 const c=BOTD.cfg,st=BOTD.state;BOTON=c.enabled;
 if(!BOTCH||!BOTD.channels.some(x=>x.id===BOTCH))BOTCH=BOTD.channels[0].id;
 const ch=BOTD.channels.find(x=>x.id===BOTCH);
 const left=Math.max(0,(ch.next_due||0)-st.now);
 const nxt=left?(left>=120?'بعد '+Math.round(left/60)+' دقيقة':'بعد '+left+' ثانية'):'الآن';
 $('#bstat').innerHTML=`البوت: <b class="${c.enabled?'ok':''}">${c.enabled?'يعمل':'متوقف'}</b>${st.bot_name?` (@${esc(st.bot_name)})`:''} · أُرسل اليوم من كل القنوات: <b>${st.sent_today}</b>
  <div class="chsum">${BOTD.channels.map(x=>`<button class="${x.id===BOTCH?'on':''}" data-chsel="${esc(x.id)}"><i class="${x.on&&x.chat&&c.enabled?(x.hold||x.error?'w':'g'):''}"></i><b>${esc(x.name)}</b><span>${x.sent_today}${+x.max_day?'/'+x.max_day:''} اليوم</span></button>`).join('')}</div>
  <div class="chst"><b>${esc(ch.name)}</b><br>
  ${!ch.chat?'<span class="warn">لم يُحدد معرّف القناة بعد</span><br>':''}
  ${!ch.on?'<span class="warn">هذه القناة موقوفة</span><br>':''}
  ${ch.hold?`<span class="warn">متوقف مؤقتاً: ${esc(ch.hold)}</span><br>`:''}
  ${c.enabled&&ch.on&&ch.chat&&!ch.hold?`الإرسال القادم: <b>${nxt}</b><br>`:''}
  ${(ch.inc||[]).length?`الفلتر: <b>${ch.inc.length}</b> شرط${(ch.exc||[]).length?'، '+ch.exc.length+' مستبعدة':''}<br>`:''}
  ${ch.photo?'يرسل صورة المقال مع الخبر<br>':''}
  ${ch.error?`<span class="warn">آخر خطأ: ${esc(ch.error)}</span>`:''}</div>
  <div class="hint" style="margin-top:6px;color:var(--faint);font-size:12px">يعمل البوت ما دام البرنامج مفتوحاً على جهازك.</div>`;
 $('#brecent').innerHTML=ch.recent.length?ch.recent.map(r=>`<li><button class="t" data-open="${r.id}">${esc(r.title||'')}<span class="wstat" style="display:block">${fmt(r.sent)}</span></button></li>`).join(''):'<li class="count" style="padding:12px 14px">لم يُرسل شيء إلى هذه القناة بعد.</li>';
 $('#brecenth').textContent='آخر ما أُرسل إلى: '+ch.name;
 const cmdH=`<div class="cmdbox2"><div class="bigtoggle"><span><b>أوامر البوت</b><br><span class="hint">اسأل البوت من تيليغرام وأنت بعيد عن الكمبيوتر</span></span><label class="sw"><input type="checkbox" id="cmdon"${c.cmd_on?' checked':''}><span></span></label></div>
  ${c.cmd_on?`${st.cmd_error?`<span class="warn">${esc(st.cmd_error)}</span>`:`<span class="hint ok">يستمع للأوامر${st.cmd_last?' · آخر أمر '+ago(st.cmd_last):''}</span>`}
  <div class="row"><label class="opt"><input type="radio" name="cmdmode" value="allow"${c.cmd_mode!=='all'?' checked':''}>المسموح لهم فقط</label><label class="opt"><input type="radio" name="cmdmode" value="all"${c.cmd_mode==='all'?' checked':''}>أي شخص يراسل البوت</label></div>
  ${c.cmd_mode!=='all'?`<b style="font-size:13px">المسموح لهم (المعرّف الرقمي أو اسم المستخدم، واحد في كل سطر)</b>
  <textarea id="cmdusers" rows="3" class="ltr" placeholder="123456789&#10;@username">${esc((c.cmd_users||[]).join('\n'))}</textarea>
  <div class="row"><button class="ibtn" id="cmdsave">حفظ القائمة</button></div>
  ${st.requests.length?`<b style="font-size:13px">طلبوا استخدام البوت:</b><div class="chatlist">${st.requests.map(r=>`<button data-cmdallow="${esc(String(r.id))}">${esc(r.name||'')}${r.username?' @'+esc(r.username):''} <span class="mt" style="color:var(--faint)">${r.id}</span> <b style="color:var(--acc)">← سماح</b></button>`).join('')}</div>`:''}
  <span class="hint">لتعرف معرّفك: أرسل للبوت <code>/start</code> فيظهر اسمك هنا، اضغط «سماح». وأوامرك من داخل قنواتك مسموحة دائماً.</span>`:''}
  <div class="cmdlist"><code>/ابحث داعش البادية</code><code>/دولة العراق</code><code>/ملخص</code><code>/آخر</code><code>/نوعي</code><code>/انذارات</code></div>`:''}</div>`;
 if(statusOnly&&$('#bform').innerHTML){const cb=$('#bcmdwrap');if(cb&&!cb.contains(document.activeElement))cb.innerHTML=cmdH;return}
 const ck=(k,label,sub)=>`<label class="opt"><input type="checkbox" data-bopt="${k}"${ch[k]?' checked':''}><span>${label}${sub?`<small>${sub}</small>`:''}</span></label>`;
 const ready=c.has_token&&BOTD.channels.some(x=>x.chat);
 $('#bform').innerHTML=`
  <div class="bigtoggle"><span><b>تشغيل النشر الآلي</b><br><span class="hint">${ready?'كل شيء جاهز':'أضف رمز البوت وقناة واحدة على الأقل'}</span></span><label class="sw"><input type="checkbox" id="benabled"${c.enabled?' checked':''}><span></span></label></div>
  <label class="f">رمز البوت (Token)
   <div class="row"><input type="password" id="btoken" class="ltr" placeholder="${c.has_token?esc(c.token_hint)+' (محفوظ)':'123456789:AA...'}" autocomplete="off"><button class="ibtn primary" id="btokensave">حفظ</button></div>
   <span class="hint">أنشئ بوتاً من <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a> في تيليغرام: أرسل له <code>/newbot</code> واختر اسماً، فيعطيك الرمز.</span></label>
  <div class="f"><b style="font-size:14px">القنوات</b><span class="hint">لكل قناة إعداداتها: الأقسام والفلتر والسرعة والصورة.</span>
   <div class="chtabs">${BOTD.channels.map(x=>`<button class="${x.id===BOTCH?'on':''}" data-chsel="${esc(x.id)}">${esc(x.name)}${x.on?'':' (موقوفة)'}</button>`).join('')}<button class="add" id="chadd">+ قناة جديدة</button></div></div>
  <div class="chbox">
  <div class="row"><input type="text" id="chname" value="${esc(ch.name)}" style="flex:1" placeholder="اسم القناة (لك فقط)"><button class="ibtn" id="chnamesave">حفظ الاسم</button>
   <label class="opt"><input type="checkbox" id="chon"${ch.on?' checked':''}>نشطة</label>${BOTD.channels.length>1?'<button class="ibtn" id="chdel" style="color:var(--red)">حذف القناة</button>':''}</div>
  <label class="f">1. معرّف القناة أو المجموعة
   <div class="row"><input type="text" id="bchat" class="ltr" value="${esc(ch.chat)}" placeholder="@my_channel  أو  -1001234567890"><button class="ibtn" id="bchatsave">حفظ</button><button class="ibtn" id="bdetect">اكتشاف تلقائي</button><button class="ibtn" id="btest">رسالة تجريبية</button></div>
   <span class="hint"><ol><li>لقناة: أضف البوت مشرفاً في القناة، ثم اكتب معرّفها مثل <code>@my_channel</code>.</li><li>لمجموعة أو محادثة خاصة: أضف البوت أو أرسل له <code>/start</code>، ثم اضغط «اكتشاف تلقائي» واختر من القائمة.</li></ol></span>
   <div class="chatlist" id="bchats"></div></label>
  <label class="f">2. سرعة الإرسال
   <div class="row"><span>رسالة واحدة كل</span><select id="binterval">${(()=>{const P=[[30,'30 ثانية'],[60,'دقيقة'],[120,'دقيقتين'],[180,'3 دقائق'],[300,'5 دقائق'],[600,'10 دقائق'],[900,'15 دقيقة'],[1200,'20 دقيقة'],[1800,'30 دقيقة'],[2700,'45 دقيقة'],[3600,'ساعة'],[7200,'ساعتين'],[10800,'3 ساعات'],[21600,'6 ساعات'],[43200,'12 ساعة'],[86400,'يوم']];if(!P.some(x=>x[0]===+ch.interval))P.push([+ch.interval,Math.round(ch.interval/60)+' دقيقة']);return P.map(([v,n])=>`<option value="${v}"${+ch.interval===v?' selected':''}>${n}</option>`).join('')})()}</select>
    <span>أو</span><input type="number" id="bintmin" min="0.5" max="1440" step="0.5" placeholder="دقائق" style="width:90px;flex:none"><button class="ibtn" id="bintsave">تطبيق</button></div>
   <div class="row"><span>حد أقصى في اليوم:</span><input type="number" id="bmaxday" min="0" max="2000" value="${+ch.max_day||''}" placeholder="بلا حد" style="width:100px;flex:none"><span class="hint">رسالة (اتركه فارغاً لبلا حد)</span></div>
   <div class="row"><span>ساعات النشر من</span><select id="bhfrom">${Array.from({length:24},(_,h)=>`<option value="${h}"${+ch.hours_from===h?' selected':''}>${String(h).padStart(2,'0')}:00</option>`).join('')}</select><span>إلى</span><select id="bhto">${Array.from({length:24},(_,h)=>h+1).map(h=>`<option value="${h}"${(+ch.hours_to||24)===h?' selected':''}>${String(h%24).padStart(2,'0')}:00${h===24?' (منتصف الليل)':''}</option>`).join('')}</select><button class="ibtn" id="bhsave">حفظ</button></div>
   <span class="hint">00:00 إلى منتصف الليل = طوال اليوم. خارج هذه الساعات تتوقف القناة وتكمل تلقائياً بعدها.</span></label>
  <label class="f">3. فلترة العناوين
   <div class="bflt"><div><b>أرسل فقط ما يحتوي على</b><textarea id="binc" rows="5" placeholder="كلمة أو عبارة في كل سطر، مثلاً:&#10;سوريا&#10;هيئة تحرير الشام&#10;داعش + العراق">${esc((ch.inc||[]).join('\n'))}</textarea></div>
    <div><b>ولا ترسل ما يحتوي على</b><textarea id="bexc" rows="5" placeholder="مثلاً:&#10;كرة القدم&#10;مباراة&#10;أسعار الذهب">${esc((ch.exc||[]).join('\n'))}</textarea></div></div>
   <div class="row"><label class="opt"><input type="radio" name="bscope" value="title"${ch.scope!=='all'?' checked':''}>في العنوان فقط</label><label class="opt"><input type="radio" name="bscope" value="all"${ch.scope==='all'?' checked':''}>في العنوان والملخص</label>
    <span>عمر الخبر حتى</span><select id="bfresh">${[[1,'ساعة'],[3,'3 ساعات'],[6,'6 ساعات'],[12,'12 ساعة'],[24,'يوم'],[48,'يومين'],[72,'3 أيام'],[168,'أسبوع']].map(([v,n])=>`<option value="${v}"${(+ch.fresh_h||168)===v?' selected':''}>${n}</option>`).join('')}</select></div>
   <div class="row"><button class="ibtn primary" id="bfltsave">حفظ الفلتر</button><button class="ibtn" id="bfltprev">معاينة: ماذا سيُرسل؟</button></div>
   <span class="hint">كل سطر شرط مستقل يكفي تحقق أحدها. اجمع كلمات بعلامة <code>+</code> لتشترط وجودها معاً (مثل <code>داعش + العراق</code>). لا فرق بين أ وإ وا، ولا بين ة وه. اترك الخانة الأولى فارغة لإرسال كل الأخبار.</span>
   <div class="bprev" id="bprev"></div></label>
  <label class="f">4. الأقسام التي يُرسل منها
   <div class="cks">${BOTD.cats.map(k=>`<label><input type="checkbox" data-bcat="${k.key}"${ch.cats.includes(k.key)?' checked':''}>${esc(k.name)}</label>`).join('')}</div></label>
  <div class="f" style="display:flex;flex-direction:column;gap:10px">
   ${ck('photo','إرسال صورة المقال مع الخبر','يرسل صورة المقال من موقعه مع العنوان والملخص في رسالة واحدة. إن لم توجد صورة يُرسل نصاً كالمعتاد')}
   ${ck('preview','معاينة الرابط (للرسائل النصية)','يُظهر تيليغرام صورة المقال وعنوانه أسفل الرسالة')}
   <span class="hint">لا تُرسل الأخبار النوعية ولا الإنذارات ولا مقاطع الفيديو؛ يرسل البوت المقالات والدراسات والأخبار العالمية فقط.</span>
  </div></div>
  <div id="bcmdwrap">${cmdH}</div>`}
$('#botview').addEventListener('change',e=>{const t=e.target;
 if(t.id==='benabled')return bpost({enabled:t.checked},t.checked?'بدأ النشر الآلي':'توقف النشر الآلي');
 if(t.id==='cmdon')return bpost({cmd_on:t.checked});
 if(t.name==='cmdmode')return bpost({cmd_mode:t.value});
 if(t.id==='chon')return bch({on:t.checked});
 if(t.id==='binterval')return bch({interval:+t.value});
 if(t.id==='bfresh')return bch({fresh_h:+t.value});
 if(t.name==='bscope')return bch({scope:t.value});
 if(t.id==='bmaxday')return bch({max_day:+t.value||0});
 if(t.dataset.bcat)return bch({cats:[...document.querySelectorAll('[data-bcat]:checked')].map(x=>x.dataset.bcat)});
 if(t.dataset.bopt)return bch({[t.dataset.bopt]:t.checked})});
$('#botview').addEventListener('click',async e=>{const t=e.target.closest('button');if(!t)return;
 if(t.dataset.chsel){BOTCH=t.dataset.chsel;$('#bform').innerHTML='';return loadBot()}
 if(t.id==='chadd'){const n=prompt('اسم القناة الجديدة:','قناة '+(BOTD.channels.length+1));if(!n)return;try{const d=await bpostJ('/api/bot/channel',{name:n});BOTCH=d.id;$('#bform').innerHTML='';loadBot()}catch(err){alert(err.message)}return}
 if(t.id==='chdel'){if(!confirm('حذف هذه القناة وإعداداتها؟'))return;try{await api('/api/bot/channel/'+encodeURIComponent(BOTCH),{method:'DELETE'});BOTCH=null;$('#bform').innerHTML='';loadBot()}catch(err){alert(err.message)}return}
 if(t.id==='chnamesave')return bch({name:$('#chname').value.trim()});
 if(t.id==='btokensave'){const v=$('#btoken').value.trim();if(!v)return;return bpost({token:v})}
 if(t.id==='bchatsave')return bch({chat:$('#bchat').value.trim()});
 if(t.id==='bintsave'){const m=parseFloat($('#bintmin').value);if(!(m>0))return;return bch({interval:Math.round(m*60)})}
 if(t.id==='bhsave')return bch({hours_from:+$('#bhfrom').value,hours_to:+$('#bhto').value});
 if(t.id==='bfltsave'){await bch({inc:$('#binc').value,exc:$('#bexc').value});return}
 if(t.id==='bfltprev'){$('#bprev').innerHTML='<span class="spinner">…</span>';
  try{const d=await bpostJ('/api/bot/preview',{ch:BOTCH,inc:$('#binc').value,exc:$('#bexc').value,scope:(document.querySelector('[name=bscope]:checked')||{}).value});
   $('#bprev').innerHTML=`<b>يطابق الفلتر ${d.matched} من ${d.total} مادة في الأقسام والمدة المختارة</b>`+(d.items.length?'<ul>'+d.items.map(i=>`<li><button class="t" data-open="${i.id}">${esc(i.title)}</button><span>${esc(i.source||'')} · ${ago(i.published)}</span></li>`).join('')+'</ul>':'<div class="hint">لا يوجد ما يطابق حالياً.</div>')}
  catch(err){$('#bprev').innerHTML=`<span class="warn">${esc(err.message)}</span>`}return}
 if(t.id==='btest'){t.disabled=true;try{await bpostJ('/api/bot/test',{ch:BOTCH});t.textContent='✔ أُرسلت'}catch(err){alert(err.message)}t.disabled=false;return}
 if(t.id==='bsendnow'){t.disabled=true;try{const d=await bpostJ('/api/bot/send-now',{ch:BOTCH});t.textContent=d.sent?'✔ أُرسلت':'لا جديد يطابق';setTimeout(()=>t.textContent='أرسل مقالة الآن',2500)}catch(err){alert(err.message)}t.disabled=false;return loadBot(true)}
 if(t.id==='breset'){if(!confirm('مسح سجل الإرسال لهذه القناة؟ قد يُعاد إرسال مقالات سبق إرسالها.'))return;await bpostJ('/api/bot/reset',{ch:BOTCH});return loadBot(true)}
 if(t.id==='cmdsave')return bpost({cmd_users:$('#cmdusers').value});
 if(t.dataset.cmdallow)return bpost({cmd_add:t.dataset.cmdallow});
 if(t.id==='bdetect'){$('#bchats').innerHTML='<span class="spinner">جارٍ البحث…</span>';
  try{const d=await api('/api/bot/chats');$('#bchats').innerHTML=d.chats.length?d.chats.map(c=>`<button data-bchat="${c.id}">${esc(c.name||String(c.id))} <span class="mt" style="color:var(--faint)">${c.id} · ${esc(c.type)}</span></button>`).join(''):'<span class="hint">لم يُعثر على محادثات. أرسل للبوت رسالة أو اكتب في المجموعة بعد إضافته، ثم أعد المحاولة.</span>'}
  catch(err){$('#bchats').innerHTML=`<span class="warn">${esc(err.message)}</span>`}return}
 if(t.dataset.bchat){$('#bchat').value=t.dataset.bchat;return bch({chat:t.dataset.bchat})}});
setInterval(()=>{if(S.cat==='bot')loadBot(true)},5000);


/* الملخص اليومي */
let DAILY=null;
async function loadDaily(day){
 try{DAILY=await api('/api/daily'+(day?'?day='+encodeURIComponent(day):''))}catch(e){return}
 const d=DAILY,c=d.cfg;
 $('#dailyday').innerHTML=d.days.length?d.days.map(x=>`<option value="${esc(x.day)}"${d.report&&d.report.day===x.day?' selected':''}>${esc(x.day)} · ${x.n} مادة</option>`).join(''):'<option value="">لا ملخصات بعد</option>';
 $('#dailypdf').disabled=$('#dailysend').disabled=!d.report;
 $('#dailybody').innerHTML=d.report?`<div class="dmeta">أُنشئ ${fmt(d.report.created)} · يغطي آخر 24 ساعة${d.report.ai?' · مع فقرة بالذكاء الاصطناعي':''}</div>`+d.report.html
  :'<div class="empty"><b>لا يوجد ملخص بعد</b>يُنشأ تلقائياً كل يوم في الساعة المحددة، أو اضغط «إنشاء الآن».</div>';
 const PV={free:'المحرك المجاني',claude:'Claude',gemini:'Gemini',ollama:'Ollama'};
 $('#dailyset').innerHTML=`
  <label class="opt"><input type="checkbox" data-dset="on"${c.on?' checked':''}>إنشاء الملخص تلقائياً كل يوم</label>
  <label class="f">الساعة<select id="dhour" class="dsel">${Array.from({length:24},(_,h)=>`<option value="${h}"${+c.hour===h?' selected':''}>${String(h).padStart(2,'0')}:00</option>`).join('')}</select></label>
  <label class="opt"><input type="checkbox" data-dset="ai"${c.ai?' checked':''}><span>إضافة فقرة «الصورة العامة» بالذكاء الاصطناعي<small>تُكتب بمحرك الكتابة المختار حالياً (${PV[d.provider]||d.provider}) من صفحة كاتب المقالات</small></span></label>
  <label class="opt"><input type="checkbox" data-dset="tg"${c.tg?' checked':''}${d.has_token?'':' disabled'}><span>إرساله تلقائياً إلى تيليغرام${d.has_token?'':'<small>يحتاج إعداد البوت أولاً</small>'}</span></label>
  ${d.has_token?`<div class="cks">${d.channels.map(ch=>`<label><input type="checkbox" data-dch="${esc(ch.id)}"${(!c.chs.length||c.chs.includes(ch.id))?' checked':''}${ch.ready?'':' disabled'}>${esc(ch.name)}</label>`).join('')}</div><span class="hint">القنوات التي يُرسل إليها الملخص.</span>`:''}
  <span class="hint">يمكنك أيضاً طلب الملخص في أي وقت بإرسال <code>/ملخص</code> للبوت (بعد تفعيل أوامر البوت).</span>`}
function dset(b){return api('/api/daily',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(()=>loadDaily($('#dailyday').value))}
$('#dailyview').addEventListener('change',e=>{const t=e.target;
 if(t.id==='dailyday')return loadDaily(t.value);
 if(t.id==='dhour')return dset({hour:+t.value});
 if(t.dataset.dset)return dset({[t.dataset.dset]:t.checked});
 if(t.dataset.dch)return dset({chs:[...document.querySelectorAll('[data-dch]:checked')].map(x=>x.dataset.dch)})});
$('#dailyview').addEventListener('click',async e=>{const t=e.target.closest('button');if(!t)return;
 if(t.id==='dailybuild'){t.disabled=true;t.textContent='جارٍ الإنشاء…';try{const d=await api('/api/daily/build',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await loadDaily(d.day)}catch(err){alert(err.message)}t.disabled=false;t.textContent='إنشاء الآن';return}
 if(t.id==='dailypdf'){const dd=$('#dailyday').value;if(dd)window.open('/print/daily/'+encodeURIComponent(dd),'_blank');return}
 if(t.id==='dailysend'){t.disabled=true;try{const d=await api('/api/daily/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({day:$('#dailyday').value})});t.textContent='✔ أُرسل إلى '+d.n+' قناة'}catch(err){alert(err.message)}setTimeout(()=>{t.disabled=false;t.textContent='إرسال إلى تيليغرام'},2500);return}});

/* كاتب المقالات */
let WCFG=null,WBODY='',WABORT=null,WSAVED=null;
const MD_ESC=t=>esc(t).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/(https?:\/\/[^\s<)]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>');
function md(t){
 const out=[];let list=null;
 for(const raw of t.split('\n')){const l=raw.trim();
  if(/^[-*•]\s+/.test(l)||/^\d+[.)]\s+/.test(l)){const ol=/^\d/.test(l);if(!list||list.ol!==ol){if(list)out.push(list.ol?'</ol>':'</ul>');out.push(ol?'<ol>':'<ul>');list={ol}}out.push('<li>'+MD_ESC(l.replace(/^([-*•]|\d+[.)])\s+/,''))+'</li>');continue}
  if(list){out.push(list.ol?'</ol>':'</ul>');list=null}
  if(!l)continue;
  const h=l.match(/^(#{1,3})\s+(.*)/);
  if(h){out.push(`<h${h[1].length}>${MD_ESC(h[2])}</h${h[1].length}>`);continue}
  out.push(`<p dir="auto">${MD_ESC(l)}</p>`)}
 if(list)out.push(list.ol?'</ol>':'</ul>');return out.join('')}
const PROVS=[['free','مجاني فوري: بلا مفتاح ولا تثبيت'],['gemini','Gemini: مفتاح مجاني'],['ollama','Ollama: على جهازك'],['claude','Claude: مدفوع']];
async function loadWriter(){
 try{WCFG=await api('/api/writer/config')}catch(e){return}
 const opt=(l,cur)=>l.map(o=>`<option value="${esc(o.id)}"${o.id===cur?' selected':''}>${esc(o.name)}</option>`).join('');
 if(!$('#wtype').options.length){$('#wtype').innerHTML=opt(WCFG.types,'analysis');$('#wlen').innerHTML=opt(WCFG.lengths,'medium');$('#wtone').innerHTML=opt(WCFG.tones,'analytical')}
 renderWKey();loadArticles();
 if(WCFG.ollama.pull.running)setTimeout(()=>S.cat==='writer'&&loadWriter(),2000)}
function renderWKey(){
 const c=WCFG,p=c.provider;const opt=(l,cur)=>l.map(o=>typeof o==='string'?`<option${o===cur?' selected':''}>${esc(o)}</option>`:`<option value="${esc(o.id)}"${o.id===cur?' selected':''}>${esc(o.name)}</option>`).join('');
 let h=`<span style="font:700 13.5px var(--fd)">محرك الكتابة</span><div class="seg">${PROVS.map(([k,n])=>`<button data-wprov="${k}" class="${p===k?'on':''}">${n}</button>`).join('')}</div><span class="sp" style="flex:1"></span>${c.ready?'<span class="badge2">جاهز للكتابة</span>':'<span class="badge2" style="color:var(--red);background:rgba(244,63,94,.1)">غير جاهز</span>'}`;
 if(p==='free'){const f=c.free;
  h+=`<label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wfreemodel">${opt(f.models,f.model)}</select></label>
  <div class="full">يعمل فوراً دون مفتاح أو حساب أو تثبيت، عبر خدمة Pollinations المجانية المفتوحة. لاحظ أنها خدمة مجانية من طرف ثالث: قد تكون أبطأ أحياناً، وتسمح بطلب كل بضع ثوانٍ، وقد تغيّر شروطها مستقبلاً. والموضوع والمواد المرجعية تُرسل إليها لكتابة النص، فلا تضع فيها معلومات حساسة. للجودة الأعلى استخدم Gemini بمفتاحه المجاني.</div>`}
 if(p==='ollama'){const o=c.ollama,pl=o.pull;
  if(!o.running)h+=`<div class="full">Ollama برنامج مجاني يشغّل نموذج الكتابة على جهازك نفسه، بلا مفتاح ولا إنترنت ولا تكلفة.<ol><li>نزّله من <a href="https://ollama.com/download" target="_blank" rel="noopener">ollama.com/download</a> وثبّته مثل أي برنامج.</li><li>شغّله (يعمل في الخلفية بجانب الساعة).</li><li>اضغط «تحقق» هنا، ثم نزّل نموذجاً من القائمة التي ستظهر.</li></ol></div><button class="ibtn primary" id="wcheck">تحقق</button>`;
  else{
   if(o.models.length)h+=`<label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wollmodel">${opt(o.models,o.model)}</select></label>`;
   h+=`<div class="sugg"><span style="font:600 12.5px var(--fd)">${o.models.length?'نماذج أخرى يمكنك تنزيلها:':'Ollama يعمل. نزّل نموذجاً للكتابة (مرة واحدة):'}</span>${o.suggest.filter(m=>!o.models.includes(m.id)).map(m=>`<div><button class="ibtn" data-wpull="${esc(m.id)}" ${pl.running?'disabled':''} style="height:30px">تنزيل</button><span>${esc(m.name)}</span></div>`).join('')}</div>`;
   if(pl.running||pl.error)h+=`<div class="full">${pl.error?`<span class="warn">فشل التنزيل: ${esc(pl.error)}</span>`:`جارٍ تنزيل ${esc(pl.model)}: ${esc(pl.status)} ${pl.pct}%`}</div>${pl.running?`<div class="wprog"><i style="width:${pl.pct}%"></i></div>`:''}`;
   h+=`<div class="full">ملاحظة: النماذج المحلية أضعف من Gemini وClaude في العربية والنصوص الطويلة، وسرعتها تعتمد على جهازك.</div>`}}
 if(p==='gemini'){const g=c.gemini;
  if(!g.has_key)h+=`<div class="full">مفتاح Gemini مجاني من Google، يكفي لعدد جيد من المقالات يومياً. احصل عليه خلال دقيقة من <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a> (سجّل بحساب Google ثم «Create API key»).</div><input id="wgemkey" type="password" placeholder="AIza..." autocomplete="off"><button class="ibtn primary" id="wgemsave">حفظ المفتاح</button>`;
  else h+=`<span class="mt" style="color:var(--faint);font-size:12px">${esc(g.key_hint)}</span>${g.error?`<span class="warn" style="font-size:12.5px">${esc(g.error)}</span>`:`<label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wgemmodel">${opt(g.models,g.model)}</select></label>`}<button class="ibtn" id="wgemedit">تغيير المفتاح</button>`}
 if(p==='claude'){const k=c.claude;
  if(!k.has_key)h+=`<div class="full">Claude أعلى جودة في العربية، ويحتاج مفتاحاً مدفوعاً حسب الاستخدام من <a href="https://console.anthropic.com" target="_blank" rel="noopener">console.anthropic.com</a>.</div><input id="wkeyin" type="password" placeholder="sk-ant-..." autocomplete="off"><button class="ibtn primary" id="wkeysave">حفظ المفتاح</button>`;
  else h+=`<span class="mt" style="color:var(--faint);font-size:12px">${esc(k.key_hint)}</span><label style="display:flex;gap:8px;align-items:center;font-size:13px">النموذج<select id="wmodel">${opt(k.models,k.model)}</select></label><button class="ibtn" id="wkeyedit">تغيير المفتاح</button>`}
 h+=`<div class="full" style="color:var(--faint)">المفاتيح تُحفظ على جهازك فقط داخل قاعدة بيانات البرنامج.</div>`;
 $('#wkey').innerHTML=h}
function wcfg(body,msg){return api('/api/writer/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(()=>{if(msg)toast(msg);return loadWriter()}).catch(e=>toast(e.message))}
const ENG={free:'مجاني',gemini:'Gemini',ollama:'Ollama',claude:'Claude'};
function renderWLog(){const all=window._WARTS||[];const qq=($('#wlogq').value||'').trim();
 const l=qq?all.filter(a=>(a.title+' '+a.topic+' '+a.body).includes(qq)):all;
 $('#wlogcount').textContent=l.length+' مقالاً';$('#wlogn').textContent=all.length?'('+all.length+')':'';
 const TN={opinion:'مقال رأي',analysis:'تحليل',study:'دراسة',assessment:'تقدير موقف',report:'تقرير'};
 $('#wloglist').innerHTML=l.length?`<table class="tbl"><thead><tr><th>العنوان</th><th>النوع</th><th>الكلمات</th><th>المحرك</th><th>التاريخ</th><th></th></tr></thead><tbody>${l.map(a=>`<tr><td><b>${esc(a.title||a.topic)}</b><span class="sub">${esc(a.topic||'')}</span></td><td>${esc(TN[a.type]||a.type||'—')}</td><td class="mt">${a.words||(a.body||'').split(/\s+/).length}</td><td>${esc(ENG[a.engine]||a.engine||'—')}</td><td class="mt" style="white-space:nowrap">${fmt(a.created)}</td><td style="white-space:nowrap"><button class="ibtn" data-wlopen="${a.id}" style="height:30px">فتح</button> <button class="ibtn" data-wlcopy="${a.id}" style="height:30px">نسخ</button> <button class="ibtn" data-wlpdf="${a.id}" style="height:30px">PDF</button> <button class="ibtn" data-wdel="${a.id}" style="height:30px;color:var(--red)">حذف</button></td></tr>`).join('')}</tbody></table>`
  :'<div class="empty"><b>لا توجد مقالات في السجل</b>كل مقال يكتبه الكاتب يُحفظ هنا تلقائياً.</div>'}
async function loadArticles(){try{const d=await api('/api/articles');
 $('#warts').innerHTML=d.items.length?d.items.map(a=>`<li><button class="t" data-wart="${a.id}">${esc(a.title||a.topic)}<span class="wstat" style="display:block">${fmt(a.created)}</span></button><button class="x" data-wdel="${a.id}" aria-label="حذف">×</button></li>`).join(''):'<li class="count" style="padding:12px 14px">لا توجد مقالات محفوظة بعد.</li>';
 window._WARTS=d.items;$('#wlogn').textContent=d.items.length?'('+d.items.length+')':'';if(!$('#wlogview').hidden)renderWLog()}catch(e){}}
let wst;$('#wtopic').oninput=()=>{clearTimeout(wst);wst=setTimeout(wSources,600)};
async function wSources(){const t=$('#wtopic').value.trim();const box=$('#wsrc');
 if(!t||!$('#wsrcuse').checked){box.hidden=true;return}
 try{const d=await api('/api/writer/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:t})});
  box.hidden=false;box.innerHTML=d.items.length?`<b style="font:600 12.5px var(--fd)">${d.items.length} مادة مرصودة سيستند إليها:</b>`+d.items.slice(0,12).map(i=>`<div>${esc(i.source_ar)}: ${esc(i.title_ar||i.title)}</div>`).join(''):'لا توجد مواد مرصودة عن هذا الموضوع؛ سيكتب من معرفته العامة.'}catch(e){box.hidden=true}}
$('#wsrcuse').onchange=wSources;
document.addEventListener('change',e=>{const id=e.target.id;
 if(id==='wmodel')wcfg({model:e.target.value},'تم تغيير النموذج');
 if(id==='wgemmodel')wcfg({gemini_model:e.target.value},'تم تغيير النموذج');
 if(id==='wollmodel')wcfg({ollama_model:e.target.value},'تم تغيير النموذج');
 if(id==='wfreemodel')wcfg({free_model:e.target.value},'تم تغيير النموذج')});
let WCONT=false;
function wRender(done){$('#wdoc').innerHTML=md(WBODY)+(done?'':'<span class="cursor"></span>');
 const words=WBODY.trim()?WBODY.trim().split(/\s+/).length:0;$('#wstat').textContent=words+' كلمة'+(WCONT&&!done?'، جارٍ إكمال النص…':'');
 const m=WBODY.match(/^#\s*(.+)/m);$('#wtitle').textContent=m?m[1].slice(0,60):'النص'}
async function wGenerate(){
 const topic=$('#wtopic').value.trim();if(!topic){toast('اكتب الموضوع أولاً');return}
 if(!WCFG?.ready){toast('محرك الكتابة غير جاهز بعد؛ أكمل إعداده في أعلى الصفحة');window.scrollTo({top:0});return}
 WBODY='';WSAVED=null;wRender(false);
 ['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=true);$('#wgo').disabled=true;$('#wgo').textContent='جارٍ الكتابة…';$('#wstop').hidden=false;
 WABORT=new AbortController();
 try{
  const r=await fetch('/api/writer/generate',{method:'POST',signal:WABORT.signal,headers:{'Content-Type':'application/json'},
   body:JSON.stringify({topic,type:$('#wtype').value,length:$('#wlen').value,tone:$('#wtone').value,lang:$('#wlang').value,angle:$('#wangle').value.trim(),use_sources:$('#wsrcuse').checked})});
  const rd=r.body.getReader();const dec=new TextDecoder();
  while(true){const {done,value}=await rd.read();if(done)break;WBODY+=dec.decode(value,{stream:true});
   if(WBODY.includes('[[WAIT]]')){WBODY=WBODY.split('[[WAIT]]').join('');WCONT=true}else WCONT=false;
   if(WBODY.includes('[[END]]'))WBODY=WBODY.split('[[END]]').join('');
   const k=WBODY.indexOf('[[ERROR]]');if(k>=0){const err=WBODY.slice(k+9).trim();WBODY=WBODY.slice(0,k);wRender(true);toast(err);if(!WBODY.trim())$('#wdoc').innerHTML=`<div class="wempty"><b>تعذّرت الكتابة</b>${esc(err)}</div>`;break}
   wRender(false)}
 }catch(e){if(e.name!=='AbortError')toast('انقطع الاتصال أثناء الكتابة')}
 wRender(true);WABORT=null;$('#wgo').disabled=false;$('#wgo').textContent='اكتب الآن';$('#wstop').hidden=true;
 if(WBODY.trim()){['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=false);await wSave(true)}}
async function wSave(auto){if(!WBODY.trim())return;
 try{const d=await api('/api/articles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:WSAVED,topic:$('#wtopic').value.trim(),type:$('#wtype').value,length:$('#wlen').value,lang:$('#wlang').value,engine:WCFG?.provider,body:WBODY})});
  WSAVED=d.id;loadArticles();if(!auto)toast('حُفظ المقال')}catch(e){toast('تعذّر الحفظ')}}
function wPdf(){const m=WBODY.match(/^#\s*(.+)/m);const w=window.open('','_blank');
 w.document.write(`<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>${esc(m?m[1]:'مقال')}</title><link href="https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;700&family=Noto+Kufi+Arabic:wght@700&display=swap" rel="stylesheet"><style>@page{size:A4;margin:20mm 18mm}body{font:13pt/2 "Noto Naskh Arabic",Arial,sans-serif;color:#111;max-width:760px;margin:0 auto;padding:20px}h1{font:700 21pt/1.5 "Noto Kufi Arabic",Arial}h2{font:700 15pt/1.6 "Noto Kufi Arabic",Arial;margin-top:22px}h3{font:700 13pt "Noto Kufi Arabic",Arial}p{text-align:justify;margin:0 0 12px}a{color:#333;word-break:break-all}</style></head><body>${md(WBODY)}<script>addEventListener('load',()=>setTimeout(()=>print(),700))<\/script></body></html>`);w.document.close()}
$('#wgo').onclick=wGenerate;
$('#wstop').onclick=()=>{if(WABORT)WABORT.abort()};
$('#wcopy').onclick=()=>navigator.clipboard.writeText(WBODY).then(()=>toast('نُسخ النص'));
$('#wsave').onclick=()=>wSave(false);
$('#wpdf').onclick=wPdf;

/* مكتبة الكتب */
const BF={topic:'',lang:'',q:''};const BOOKS=new Map();const BCOL={terror:'#E5484D',war:'#E8774A',politics:'#5B9BD5',security:'#F472B6'};
function coverHtml(b){const col=BCOL[b.topic]||'var(--acc)';
 const ph=`<span class="phx">${esc((b.title||'').slice(0,70))}<small>${esc(b.year)}</small></span>`;
 return b.image?`<div class="cover" style="--c:${col}"><img src="${esc(b.image)}" alt="غلاف ${esc(b.title_ar||b.title)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.classList.add('ph');this.remove()">${ph}</div>`
  :`<div class="cover ph" style="--c:${col}">${ph}</div>`}
function bookCard(b,topics){
 const tname=(topics.find(t=>t.key===b.topic)||{}).name||'';
 return `<article class="book" style="--c:${BCOL[b.topic]||'var(--acc)'}">${coverHtml(b)}
  <div class="binfo"><span class="btopic">${esc(tname)}</span><h3>${esc(b.title_ar||b.title)}</h3>
   ${b.title_ar&&b.title_ar!==b.title?`<span class="borig" title="${esc(b.title)}">${esc(b.title)}</span>`:''}
   <span class="bmeta">${esc(b.authors||'مؤلف غير معروف')}، ${esc(b.published||b.year)}${b.publisher?'، '+esc(b.publisher):''}</span>
   ${(b.description_ar||b.description)?`<p dir="auto">${esc(b.description_ar||b.description)}</p>`:'<p>لا يتوفر ملخص لهذا الكتاب.</p>'}
   <div class="bacts"><button class="ibtn" data-book="${esc(b.id)}">${ico('open')}الملخص الكامل</button>${b.link?`<a class="ibtn primary" href="${esc(b.link)}" target="_blank" rel="noopener">${ico('link')}رابط الكتاب</a>`:''}</div></div></article>`}
let BTOPICS=[];
async function loadBooks(){
 const g=$('#bookgrid');g.innerHTML='<div class="loading spinner">جارٍ تحميل المكتبة…</div>';
 try{const d=await api('/api/books?'+new URLSearchParams(BF));BTOPICS=d.topics;
  BOOKS_N=d.topics.reduce((a,t)=>a+t.count,0);
  $('#btopic').innerHTML=`<button data-btopic="" class="${!BF.topic?'on':''}">كل المواضيع</button>`+d.topics.map(t=>`<button data-btopic="${t.key}" class="${BF.topic===t.key?'on':''}">${esc(t.name)} <span class="mt" style="opacity:.6">${t.count}</span></button>`).join('');
  d.items.forEach(b=>BOOKS.set(b.id,b));
  $('#bcount').textContent=d.items.length+' كتاباً';
  g.innerHTML=d.items.length?d.items.map(b=>bookCard(b,d.topics)).join(''):`<div class="empty"><b>${d.running||!BOOKS_N?'يجري تجهيز المكتبة':'لا توجد كتب مطابقة'}</b>${d.running||!BOOKS_N?'يبحث المركز عن الكتب الصادرة في آخر سنتين ويترجم ملخصاتها، وتظهر هنا خلال دقائق.':'غيّر الموضوع أو اللغة أو امسح البحث.'}</div>`;
  if(d.running)setTimeout(()=>S.cat==='books'&&loadBooks(),20000);
 }catch(e){g.innerHTML='<div class="empty"><b>تعذّر تحميل المكتبة</b>تأكد أن البرنامج ما زال يعمل.</div>'}}
function openBook(id){
 const b=BOOKS.get(id);if(!b)return;S.openId=null;CUR={id:null,full:null,showOrig:false};
 const tname=(BTOPICS.find(t=>t.key===b.topic)||{}).name||'';
 $('#dlgMeta').innerHTML=`<span class="src" style="--c:${BCOL[b.topic]||'var(--acc)'}">${esc(tname)}</span><span>${esc(b.published||b.year)}</span>${b.pages?`<span>${b.pages} صفحة</span>`:''}`;
 $('#dlgBody').innerHTML=`<div class="dossier">BOOK / ${esc(id.toUpperCase())}</div>
  <div class="bookdlg">${coverHtml(b)}<div>
   <h2 id="dlgTitle" style="margin-top:0">${esc(b.title_ar||b.title)}</h2>
   ${b.title_ar&&b.title_ar!==b.title?`<p class="note" dir="auto">${esc(b.title)}</p>`:''}
   <p class="lead">${esc(b.authors||'مؤلف غير معروف')}${b.publisher?'، '+esc(b.publisher):''}</p>
   <div class="dlgtools"><div class="grp">${b.link?`<a class="ibtn primary" href="${esc(b.link)}" target="_blank" rel="noopener">${ico('link')}رابط الكتاب</a>`:''}${b.translated!==1?`<button class="ibtn tr" data-booktr="${esc(b.id)}">${ico('lang')}ترجم</button>`:''}</div></div>
  </div></div>
  ${b.description_ar?`<h4>ملخص الكتاب</h4><p dir="auto" style="font-size:16px;line-height:2">${esc(b.description_ar)}</p>`:''}
  ${b.description&&b.description!==b.description_ar?`<h4>الملخص الأصلي</h4><p dir="auto" style="color:var(--muted)">${esc(b.description)}</p>`:''}
  ${!b.description?'<p class="note">لا يتوفر ملخص لهذا الكتاب.</p>':''}`;
 const dlg=$('#dlg');if(!dlg.open)dlg.showModal()}
async function translateBook(id){
 const btn=document.querySelector(`[data-booktr="${CSS.escape(id)}"]`);if(btn){btn.disabled=true;btn.innerHTML='<span class="spinner" style="padding:0">جارٍ الترجمة…</span>'}
 try{const d=await api('/api/books/translate/'+encodeURIComponent(id),{method:'POST'});if(d.item){BOOKS.set(id,d.item);openBook(id)}
  toast(d.ok?'تمت ترجمة الكتاب':'تعذّرت الترجمة الآن')}catch(e){toast('تعذّرت الترجمة الآن')}}

/* تيليغرام */
let TG_LAST=0,TG_INT=120,TG_LOADED=0;
async function loadTgBoard(){
 try{
  const d=await api('/api/telegram/board');TG_LOADED=Date.now();TG_LAST=d.last;TG_INT=d.interval;
  const okN=d.channels.filter(c=>c.posts.length).length;
  $('#tgcount').innerHTML=`<b>${okN}</b> قناة نشطة من ${d.channels.length}، وآخر 3 منشورات من كل قناة`;
  $('#tgboard').innerHTML=d.channels.map(c=>{c.posts.forEach(p=>ITEMS.set(p.id,p));
   const st=c.ok===1?'ok':(c.ok===0?'bad':'');
   return `<section class="box tgc"><div class="boxh"><span class="av" aria-hidden="true">${esc((c.name_ar||'?').replace(/^ال/,'')[0])}<img src="/icon/${c.platform==='bluesky'?'bs':'tg'}/${esc(c.channel)}" alt="" loading="lazy" onerror="this.remove()"></span><span style="min-width:0"><a href="${esc(c.url||'https://t.me/'+c.channel)}" target="_blank" rel="noopener" style="text-decoration:none">${esc(c.name_ar)}</a><span class="uh">@${esc(c.channel)}</span></span><span class="sp"></span><span class="plat">${c.platform==='bluesky'?'BLUESKY':'TELEGRAM'}</span><span class="st ${st}" title="${st==='ok'?'تعمل':(st==='bad'?'لا تستجيب':'لم تُفحص بعد')}"></span><button class="x" ${c.platform==='bluesky'?'data-bsdel':'data-tgdel'}="${esc(c.channel)}" aria-label="حذف ${esc(c.name_ar)}" title="حذف القناة">×</button></div>
   ${c.posts.length?`<ol>${c.posts.map(p=>`<li><button class="tgp${seen(p.id)?' seen':''}" data-open="${p.id}"><span class="meta"><time>${ago(p.published)}</time>${seen(p.id)?'<span>✓ تمت زيارتها</span>':''}${state(p)}</span><span class="t">${esc(T(p))}</span></button></li>`).join('')}</ol>`:`<div class="err">${c.ok===0?esc(c.error||'القناة لا تستجيب')+'. تأكد من اسمها في تطبيق تيليغرام، أو احذفها.':'بانتظار أول تحديث…'}</div>`}</section>`}).join('')||'<div class="empty"><b>لا توجد قنوات</b>أضف قناة من الحقل أعلاه.</div>';
  tgNext();
 }catch(e){$('#tgboard').innerHTML='<div class="empty"><b>تعذّر الاتصال بالخادم</b>تأكد أن البرنامج ما زال يعمل.</div>'}}
function tgNext(){if(!TG_LAST)return;const left=Math.max(0,Math.round(TG_LAST+TG_INT-Date.now()/1000));$('#tgnext').textContent=left?`التحديث القادم بعد ${left} ثانية`:'يجري التحديث…'}
async function addTg(){
 const ch=$('#tgch').value.trim();if(!ch)return;const bs=$('#tgplat').value==='bluesky';
 try{await api(bs?'/api/bluesky':'/api/telegram',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bs?{handle:ch,name_ar:$('#tgname').value.trim()}:{channel:ch,name_ar:$('#tgname').value.trim()})});
  $('#tgch').value='';$('#tgname').value='';toast('أُضيفت القناة، ويجري جلب منشوراتها');setTimeout(loadTgBoard,5000)}catch(e){toast(e.message)}}
async function loadTweets(){
 try{const d=await api('/api/items?'+new URLSearchParams({cat:'tweets',per:12}));
  d.items.forEach(i=>ITEMS.set(i.id,i));
  const h=d.items.length?d.items.map(i=>`<li><button data-open="${i.id}" class="${seen(i.id)?'seen':''}"><span class="meta"><span class="src" style="--c:#38BDF8">${esc(i.source_ar)}</span><span>${ago(i.published)}</span>${state(i)}</span>${esc(T(i))}</button></li>`).join(''):'<li style="padding:12px 14px" class="count">لا توجد منشورات بعد.</li>';
  $('#tweets').innerHTML=h;$('#dashTg').innerHTML=h}catch(e){}}

/* دليل المراكز */
const CCATS=[['','الكل'],['think_global','أبحاث أجنبية'],['think_arab','أبحاث عربية'],['terror','مكافحة الإرهاب'],['war','حروب ودفاع'],['intel','أمن واستخبارات']];
async function renderCenters(){
 $('#cgrid').innerHTML='<div class="loading spinner">جارٍ تحميل المراكز…</div>';
 try{await loadCenters()}catch(e){$('#cgrid').innerHTML='<div class="empty"><b>تعذّر تحميل المراكز</b>تأكد أن البرنامج ما زال يعمل.</div>';return}
 const regions=['',...new Set(CENTERS.map(c=>c.region))];
 $('#cregion').innerHTML=regions.map(r=>`<button data-cregion="${esc(r)}" class="${CF.region===r?'on':''}">${esc(r||'كل المناطق')}</button>`).join('');
 $('#ccat').innerHTML=CCATS.map(([k,n])=>`<button data-ccat="${k}" class="${CF.cat===k?'on':''}">${n}</button>`).join('');
 renderCenterGrid()}
function centerCard(c){
 const col=CAT[c.cat]?.color||'var(--acc)';
 return `<button class="ccard" data-center="${esc(c.name)}" style="--c:${col}">
  <span class="cdot ${c.ok===1?'ok':(c.ok===0?'bad':'')}" title="${c.ok===1?'المصدر يعمل':(c.ok===0?'المصدر متعطل':'لم يُفحص بعد')}"></span>
  <span class="chead"><span class="mono">${esc(mono(c.name))}${c.site?`<img src="/icon/${esc(c.site.split('/')[0])}" alt="" loading="lazy" onerror="this.remove()">`:''}</span><span><span class="cname">${esc(c.name)}</span><span class="cmeta"><span class="pill">${esc(c.region)}</span><span>${esc(CAT[c.cat]?.name||'')}</span></span></span></span>
  <span class="cstats"><span><b>${c.count}</b>مادة</span><span>${c.last?'آخر نشر '+ago(c.last):'لا مواد بعد'}</span></span>
  <span class="ctags">${c.tags.slice(0,4).map(t=>`<span class="tag">${esc(t.tag)}</span>`).join('')}</span>
 </button>`}
function renderCenterGrid(){
 const qq=CF.q.toLowerCase();
 const l=CENTERS.filter(c=>(!CF.region||c.region===CF.region)&&(!CF.cat||c.cat===CF.cat)&&(!qq||(c.name+' '+c.site).toLowerCase().includes(qq)));
 $('#ccount').textContent=l.length+' مركزاً';
 $('#cgrid').innerHTML=l.length?l.map(centerCard).join(''):'<div class="empty"><b>لا توجد مراكز مطابقة</b>غيّر المنطقة أو النوع أو امسح البحث.</div>'}
function openCenter(name){S.center=name;setView('center')}
function renderCenterHead(){
 const c=CENTERS.find(x=>x.name===S.center)||{name:S.center,region:'',cat:'',site:'',count:0,tags:[]};
 const col=CAT[c.cat]?.color||'var(--acc)';
 document.title=c.name+' | '+TITLE_DEFAULT;
 $('#centerhead').innerHTML=`<button class="back" data-cat="centers">${ico('arrow')}كل المراكز</button>
  <div class="box chero" style="--c:${col}"><span class="mono big" style="--c:${col}">${esc(mono(c.name))}${c.site?`<img src="/icon/${esc(c.site.split('/')[0])}" alt="" onerror="this.remove()">`:''}</span>
   <div class="grow"><h1>${esc(c.name)}</h1><div class="cmeta">${c.region?`<span class="pill">${esc(c.region)}</span>`:''}<span>${esc(CAT[c.cat]?.name||'')}</span>${c.site?`<a href="https://${esc(c.site)}" target="_blank" rel="noopener">${esc(c.site)}</a>`:''}${c.last?`<span>آخر نشر ${ago(c.last)}</span>`:''}</div></div>
   <div class="num"><b>${c.count}</b><span>مادة خلال الشهر</span></div></div>
  ${c.tags.length?`<div class="box ctopics"><div class="tags" style="padding:0"><span class="clbl">مواضيع المركز:</span>
   <button class="tag${!S.tag?' on':''}" data-ctag="">كل المواضيع</button>
   ${c.tags.map(t=>`<button class="tag${S.tag===t.tag?' on':''}" data-ctag="${esc(t.tag)}">${esc(t.tag)} <em>${t.count}</em></button>`).join('')}</div></div>`:''}`}

/* الكلمات المفتاحية */
async function addKw(){
 const w=$('#kwinput').value.trim();if(!w)return;
 try{await api('/api/keywords',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({word:w})});
  $('#kwinput').value='';toast('أُضيفت الكلمة، ويجري البحث عنها الآن');await loadMeta();setTimeout(()=>S.cat==='keywords'&&load(true),6000)}catch(e){toast(e.message)}}

/* الأشرطة */
const TK_SIG={};
async function loadTicker(){
 const d=await api('/api/ticker');
 for(const [key,items] of Object.entries(d)){
  items.forEach(i=>ITEMS.has(i.id)||ITEMS.set(i.id,i));
  const sig=items.map(i=>i.id).join();if(TK_SIG[key]===sig)continue;TK_SIG[key]=sig;
  const run=$('#tk-'+key);if(!run)continue;
  run.innerHTML=items.length?items.map(i=>`<button data-open="${i.id}">${esc(i.title_ar)}<span>${esc(i.source_ar)}، ${ago(i.published)}</span></button>`).join(''):'<span style="margin:0 20px;color:var(--faint)">بانتظار أول العناوين المترجمة…</span>';
  run.style.animationDuration=Math.max(60,(run.scrollWidth+innerWidth)/50)+'s';
 }}

/* التحديث الدوري */
async function poll(){
 try{
  await loadQStats().catch(()=>{});
  loadAlertCount();
  await loadMeta();loadTicker();
  if(S.cat==='dash')return loadDash();
  if(S.cat==='tweets')return loadTgBoard();
  loadTweets();
  if(S.cat==='health')return renderHealth();
  if(S.cat==='bot')return loadBot(true);
  if(S.cat==='map')return loadMap(true);
  if(S.cat==='net')return loadNet();
  if(['ask','sanctions','cases','archive','settings'].includes(S.cat))return;
  if(S.cat==='alerts')return loadAlerts();
  if(['saved','centers','countries','books','writer'].includes(S.cat))return;
  const d=await api('/api/items?'+params(1,50));
  d.items.forEach(i=>{const o=ITEMS.get(i.id);if(o&&o.translated!==1&&i.translated===1){ITEMS.set(i.id,i);const el=document.querySelector(`#feed [data-id="${i.id}"]`);if(el)el.outerHTML=card(i,el.classList.contains('lead'))}});
  if(!S.ids.size&&d.items.length)return load(true);
  const fresh=d.items.filter(i=>!S.ids.has(i.id));
  if(fresh.length&&window.scrollY<250&&!$('#dlg').open)load(true);          /* تظهر الأخبار الجديدة بصمت دون إشعار */
 }catch(e){}}

/* نافذة القراءة */
let CUR={id:null,full:null,showOrig:false};
function dlgHtml(it){
 const c=CAT[it.cat]||{color:'var(--acc)',name:''};
 const o=CUR.showOrig;
 $('#dlgMeta').innerHTML=`<span class="src" style="--c:${c.color}">${esc(it.source_ar)}</span><span>${esc(c.name)}</span><span>${esc(fmt(it.published))}</span>`;
 const title=o?it.title:T(it);
 const sum=o?(it.summary||''):(it.summary_ar||it.summary||'');
 const pending=(it.translated!==1||(it.summary&&!it.summary_ar))&&it.lang!=='ar';
 return `<div class="dossier">FILE REF-${it.id.slice(0,8).toUpperCase()} <span class="viewlbl">· ${o?'ORIGINAL / النص الأصلي':'ARABIC / الترجمة العربية'}</span></div>
  <h2 id="dlgTitle" dir="auto">${esc(title)}</h2>
  ${pending&&!o?'<p class="note" id="trnote">لم يُترجم هذا العنصر بعد. اضغط «ترجم» لترجمته الآن.</p>':''}
  ${sum?`<p class="lead" dir="auto">${esc(sum)}</p>`:''}
  <div class="tags" style="padding:0;margin-top:8px">${tagsHtml(it.tags)}</div>
  <div class="dlgtools">
   <div class="grp">
    <button class="ibtn tr" id="trbtn">${ico('lang')}ترجم</button>
    ${it.lang!=='ar'?`<button class="ibtn${o?' on':''}" id="origbtn">${ico('swap')}${o?'عرض الترجمة':'عرض النص الأصلي'}</button>`:''}
   </div><span class="sep"></span>
   <div class="grp">
    <a class="ibtn" href="/print/${it.id}" target="_blank" rel="noopener" title="صفحة جاهزة للحفظ بصيغة PDF فيها الترجمة والنص الأصلي">${ico('pdf')}حفظ PDF</a>
   </div><span class="sep"></span>
   <div class="grp">
    ${it.link?`<a class="ibtn primary" href="/go/${it.id}" target="_blank" rel="noopener">${ico('link')}فتح في موقعه</a>`:''}
    <button class="ibtn" data-save="${it.id}">${ico('bookmark')}${isSaved(it.id)?'محفوظ':'حفظ'}</button>
    <button class="ibtn" data-copy="${it.id}">${ico('copy')}نسخ</button>
    ${CENTER_SET.has(it.source_ar)?`<button class="ibtn" data-center="${esc(it.source_ar)}">${ico('centers')}مواد المركز</button>`:''}
   </div><span class="sep"></span>
   <div class="grp">
    <button class="ibtn" data-tocase="${it.id}">${ico('centers')}ملف قضية</button>
    <button class="ibtn" data-arch="${it.id}" title="يحفظ نسخة من النص على جهازك ونسخة عامة في أرشيف الإنترنت">${ico('bookmark')}أرشف</button>
   </div>
  </div>
  ${it.edits?'<div id="edsec"><h4>تعديلات العنوان</h4><div class="spinner">…</div></div>':''}
  ${it.cluster&&(it.nsrc||1)>1?'<div id="vsec"><h4>نقلته أيضاً مصادر أخرى</h4><div class="spinner">…</div></div>':''}
  ${it.kind==='video'&&ytId(it.link)?`<div class="vidwrap"><iframe src="https://www.youtube.com/embed/${ytId(it.link)}" title="${esc(T(it))}" allow="accelerometer; encrypted-media; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>`:''}
  ${it.kind==='tweet'||it.kind==='video'?'':'<div id="full"></div>'}`}
function ytId(u){const m=(u||'').match(/[?&]v=([\w-]{6,})/);return m?m[1]:''}
async function loadVSec(it){if(!$('#vsec'))return;
 try{const d=await api('/api/cluster/'+encodeURIComponent(it.cluster));if(CUR.id!==it.id||!$('#vsec'))return;
  const others=d.items.filter(x=>x.id!==it.id);others.forEach(x=>ITEMS.has(x.id)||ITEMS.set(x.id,x));
  $('#vsec').innerHTML=`<h4>نقلته أيضاً ${others.length} ${others.length>2?'مصادر أخرى':'مصدر آخر'}</h4><ul class="vlist">${others.map(x=>`<li><button data-open="${x.id}"><span class="meta"><span class="src" style="--c:${CAT[x.cat]?.color||'var(--acc)'}">${esc(x.source_ar)}</span><span>${ago(x.published)}</span></span>${esc(T(x))}</button></li>`).join('')}</ul>`}catch(e){}}
function renderDlg(){const it=ITEMS.get(CUR.id)||savedList().find(x=>x.id===CUR.id);if(!it)return;$('#dlgBody').innerHTML=dlgHtml(it);renderFull()}
function renderFull(){
 const box=$('#full');if(!box)return;const d=CUR.full;const id=CUR.id;
 if(!d){box.innerHTML='<div class="spinner">جارٍ جلب النص الكامل وترجمته…</div>';return}
 if(!d.ok){box.innerHTML=`<h4>النص الكامل</h4><p class="err">${esc(d.error)}</p><div class="dlgacts"><a class="ibtn primary" href="/go/${id}" target="_blank" rel="noopener">${ico('link')}فتح المقال في موقعه</a><button class="ibtn" id="retryfull">أعد المحاولة</button></div>`;return}
 let host='';try{host=new URL(d.link).hostname}catch(e){}
 const o=CUR.showOrig;const paras=o?(d.orig||d.paragraphs):d.paragraphs;
 box.innerHTML=`<h4>${o?'النص الكامل الأصلي':'النص الكامل مترجماً'}</h4>`
  +(d.partial?'<p class="note">تعذّر استخراج المقال كاملاً (قد يكون خلف اشتراك)، وهذا ما أمكن جلبه:</p>':'')
  +(!o&&d.untranslated?`<p class="note">${d.untranslated} فقرة لم تُترجم بعد. اضغط «ترجم» لإعادة المحاولة.</p>`:'')
  +`<div ${o?'dir="auto" lang="en"':''}>`+paras.map(p=>`<p dir="auto">${esc(p)}</p>`).join('')+'</div>'
  +`<p class="note">مصدر النص: ${esc(d.via||'')}، الموقع: <a href="/go/${id}" target="_blank" rel="noopener">${esc(host)}</a></p>`}
async function openItem(id){
 const it=ITEMS.get(id)||savedList().find(x=>x.id===id);if(!it)return;
 ITEMS.set(id,it);S.openId=id;CUR={id,full:null,showOrig:false};
 renderDlg();
 const dlg=$('#dlg');if(!dlg.open)dlg.showModal();
 markVisited(id);
 if((it.translated!==1||(it.summary&&!it.summary_ar))&&it.lang!=='ar')translateTitle(id,false);
 if(it.kind!=='tweet'&&it.kind!=='video')loadFull(id,false);
 loadVSec(it);if(it.edits)loadEdits(it)}
async function loadEdits(it){try{const d=await api('/api/edits/'+it.id);if(CUR.id!==it.id||!$('#edsec'))return;
 $('#edsec').innerHTML='<h4>تعديلات العنوان بعد النشر</h4><ul class="edlist">'+d.items.map(c=>`<li><span class="wstat">${fmt(c.changed)}</span><br><del dir="auto">${esc(c.old_title)}</del><br><ins dir="auto">${esc(c.new_title)}</ins>${c.old_ar?`<br><span class="note">الترجمة السابقة: ${esc(c.old_ar)}</span>`:''}</li>`).join('')+'</ul>'}catch(e){}}
async function translateTitle(id,force){
 try{const d=await api('/api/translate/'+id+(force?'?force=1':''),{method:'POST'});
  if(CUR.id!==id)return d;
  if(d.item){ITEMS.set(id,d.item);renderDlg();
   const el=document.querySelector(`#feed [data-id="${id}"]`);if(el)el.outerHTML=card(d.item,el.classList.contains('lead'))}
  return d}catch(e){return {ok:false}}}
async function loadFull(id,force){
 try{const d=await api('/api/article/'+id+(force?'?force=1':''));if(CUR.id!==id)return d;
  if(d.link&&ITEMS.get(id))ITEMS.get(id).link=d.link;
  CUR.full=d;renderFull();return d}
 catch(e){if(CUR.id===id){CUR.full={ok:false,error:e.message||'تعذّر جلب النص الكامل.'};renderFull()}return {ok:false}}}
async function translateNow(){
 const id=CUR.id;if(!id)return;const it=ITEMS.get(id);
 const btn=$('#trbtn');if(btn){btn.disabled=true;btn.innerHTML='<span class="spinner" style="padding:0">جارٍ الترجمة…</span>'}
 CUR.showOrig=false;
 const tasks=[translateTitle(id,true)];
 if(it&&it.kind!=='tweet'){CUR.full=null;renderFull();tasks.push(loadFull(id,true))}
 const [t,f]=await Promise.all(tasks);
 if(CUR.id!==id)return;
 renderDlg();
 const okT=(ITEMS.get(id)||{}).translated===1||(ITEMS.get(id)||{}).lang==='ar';
 const okF=!f||(f.ok&&!f.untranslated);
 if(okT&&okF)return toast('تمت الترجمة');
 try{await loadMeta()}catch(e){}
 const err=META?.tr_stats?.last_error||'';
 toast('تعذّرت ترجمة بعض الأجزاء'+(err?': '+err.slice(0,90):'')+'. راجع «صحة المصادر والترجمة»')}
function toggleSave(id){
 const it=ITEMS.get(id);let l=savedList();
 if(l.some(i=>i.id===id)){l=l.filter(i=>i.id!==id);toast('أُزيل من المحفوظات')}else if(it){l.unshift(it);toast('حُفظ في المحفوظات');api('/api/archive/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:'محفوظات'})}).catch(()=>{})}
 setSaved(l);const s=isSaved(id);
 document.querySelectorAll(`.acts [data-save="${id}"]`).forEach(b=>{b.classList.toggle('saved',s);b.title=s?'محفوظ':'حفظ'});
 document.querySelectorAll(`.dlgacts [data-save="${id}"]`).forEach(b=>b.innerHTML=ico('bookmark')+(s?'محفوظ':'حفظ'));
 if(META)renderNav();if(S.cat==='saved')renderSaved()}
async function copyItem(id){const it=ITEMS.get(id)||savedList().find(x=>x.id===id);if(!it)return;
 if((it.link||'').includes('news.google.com')){try{const d=await api('/api/resolve/'+id);it.link=d.link}catch(e){}}
 const t=[T(it),it.summary_ar,'المصدر: '+it.source_ar,it.link].filter(Boolean).join('\n');
 navigator.clipboard.writeText(t).then(()=>toast('نُسخ النص والرابط'),()=>toast('تعذّر النسخ'))}

/* الأحداث */
let SETCLK=0,SETCLK_T=0;
const SUPPORT={url:__SUPPORT_URL__,wa:__DEV_WA__};
$('#supdlg').addEventListener('click',e=>{if(e.target.id==='supdlg')$('#supdlg').close()});
document.addEventListener('click',e=>{
 const t=e.target.closest('button,a');if(!t)return;
 const ds=t.dataset;
 const gm=(t.getAttribute('href')||'').match(/^\/(?:go|print)\/([0-9a-f]+)/);if(gm)markVisited(gm[1]);
 if(ds.cat==='settings'){const n=Date.now();SETCLK=(n-SETCLK_T<3000)?SETCLK+1:1;SETCLK_T=n;
  if(SETCLK>=6){SETCLK=0;e.preventDefault();return setView('bot')}}
 if(ds.cat){e.preventDefault();$('#dlg').open&&$('#dlg').close();return setView(ds.cat)}
 if(t.id==='supportbtn'){$('#supacts').innerHTML=(SUPPORT.url?`<a class="ibtn primary" href="${esc(SUPPORT.url)}" target="_blank" rel="noopener">ادعم المشروع الآن</a>`:'')+(SUPPORT.wa?`<a class="ibtn${SUPPORT.url?'':' primary'}" href="https://wa.me/${esc(SUPPORT.wa)}?text=${encodeURIComponent('السلام عليكم، أرغب في دعم مشروع مركز أبو زبيدة للتتبع والرصد')}" target="_blank" rel="noopener">تواصل مع المطور (واتساب)</a>`:'');$('#supdlg').showModal();return}
 if(t.id==='supclose'){$('#supdlg').close();return}
 if(ds.center!==undefined){$('#dlg').open&&$('#dlg').close();return openCenter(ds.center)}
 if(ds.open)return openItem(ds.open);
 if(ds.save)return toggleSave(ds.save);
 if(ds.copy)return copyItem(ds.copy);
 if(ds.skin)return applySkin(ds.skin);
 if(ds.bsdel){if(!confirm('حذف هذا الحساب من المتابعة؟'))return;api('/api/bluesky/'+encodeURIComponent(ds.bsdel),{method:'DELETE'}).then(()=>{toast('حُذف الحساب');loadTgBoard()});return}
 if(ds.tgdel){if(!confirm('حذف هذه القناة من المتابعة؟'))return;api('/api/telegram/'+encodeURIComponent(ds.tgdel),{method:'DELETE'}).then(()=>{toast('حُذفت القناة');loadTgBoard()});return}
 if(ds.kwdel){api('/api/keywords/'+encodeURIComponent(ds.kwdel),{method:'DELETE'}).then(()=>{toast('حُذفت الكلمة');loadMeta()});return}
 if(ds.qf!==undefined){QF=ds.qf;QITEMS=[];return loadQualBox()}
 if(ds.qgo!==undefined)return showQ(+ds.qgo);
 if(ds.cluster){openCluster(ds.cluster);return}
 if(ds.nset!==undefined){return}
 if(ds.edits)return openItem(ds.edits);
 if(ds.arch){t.disabled=true;api('/api/archive/'+ds.arch,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:'يدوي'})}).then(()=>toast('أُرشف المقال، وتُرسل نسخة إلى أرشيف الإنترنت')).catch(()=>toast('تعذّرت الأرشفة'));return}
 if(ds.tocase)return pickCase(ds.tocase);
 if(ds.pickcase){addToCase(ds.pickcase,PICKITEM);return}
 if(ds.sgroup!==undefined){SANCGROUP=ds.sgroup;SANCPAGE=1;return loadSanc()}
 if(ds.spg){SANCPAGE=+ds.spg;$('#sanclist').scrollIntoView({block:'start'});return loadSanc()}
 if(ds.stab){SANCMODE=ds.stab;SANCPAGE=1;document.querySelectorAll('#sanctabs button').forEach(b=>b.classList.toggle('on',b===t));return loadSanc()}
 if(ds.atab){ATAB=ds.atab;APAGE=1;document.querySelectorAll('[data-atab]').forEach(b=>b.classList.toggle('on',b===t));return loadArch()}
 if(ds.ah!==undefined){AH=+ds.ah;APAGE=1;document.querySelectorAll('#archhours button').forEach(b=>b.classList.toggle('on',b===t));return loadArch()}
 if(ds.apg){APAGE=+ds.apg;$('#archbox').scrollIntoView({block:'start'});return loadArch()}
 if(ds.adel){api('/api/archive/'+ds.adel,{method:'DELETE'}).then(()=>{toast('حُذفت من الأرشيف');loadArch()});return}
 if(ds.edel){api('/api/edits/'+ds.edel,{method:'DELETE'}).then(()=>loadArch());return}
 if(ds.archopen)return openArchived(ds.archopen);
 if(ds.case)return openCase(ds.case);
 if(ds.cidel){if(!confirm('إزالة هذه المادة من القضية؟'))return;api(`/api/cases/${CASE}/${ds.cidel}`,{method:'DELETE'}).then(()=>openCase(CASE));return}
 if(ds.cnote){const v=document.querySelector(`[data-noteof="${ds.cnote}"]`).value;api(`/api/cases/${CASE}/note`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:ds.cnote,note:v})}).then(()=>toast('حُفظت الملاحظة'));return}
 if(ds.askex){$('#askq').value=ds.askex;return askGo()}
 if(ds.wtab){document.querySelectorAll('[data-wtab]').forEach(b=>b.classList.toggle('on',b===t));$('#wlogview').hidden=ds.wtab!=='log';$('#wwriteview').hidden=ds.wtab==='log';if(ds.wtab==='log')renderWLog();return}
 if(ds.wlopen){const a=(window._WARTS||[]).find(x=>x.id===ds.wlopen);if(a){WBODY=a.body;WSAVED=a.id;$('#wtopic').value=a.topic||'';wRender(true);['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=false);document.querySelector('[data-wtab="write"]').click();window.scrollTo({top:0})}return}
 if(ds.wlcopy){const a=(window._WARTS||[]).find(x=>x.id===ds.wlcopy);if(a)navigator.clipboard.writeText(a.body).then(()=>toast('نُسخ المقال'));return}
 if(ds.wlpdf){const a=(window._WARTS||[]).find(x=>x.id===ds.wlpdf);if(a){const keep=WBODY;WBODY=a.body;wPdf();WBODY=keep}return}
 if(ds.mh){MAPH=+ds.mh;document.querySelectorAll('#maphours button').forEach(b=>b.classList.toggle('on',b===t));return loadMap()}
 if(ds.alh){ALH=+ds.alh;document.querySelectorAll('#alhours button').forEach(b=>b.classList.toggle('on',b===t));return loadAlerts()}
 if(ds.alcountry!==undefined)return openCountry(ds.alcountry);
 if(ds.altopic!==undefined){setView('all');S.tag=ds.altopic;renderActiveTag();if(META)renderTags();return load(true)}
 if(ds.wart){const a=(window._WARTS||[]).find(x=>x.id===ds.wart);if(a){WBODY=a.body;WSAVED=a.id;$('#wtopic').value=a.topic||'';wRender(true);['wcopy','wsave','wpdf'].forEach(i=>$('#'+i).disabled=false);window.scrollTo({top:0})}return}
 if(ds.wdel){if(!confirm('حذف هذا المقال نهائياً؟'))return;api('/api/articles/'+ds.wdel,{method:'DELETE'}).then(()=>{toast('حُذف المقال');loadArticles()});return}
 if(ds.qev!==undefined){S.event=ds.qev;renderQualFilter();return load(true)}
 if(ds.ctag!==undefined){S.tag=ds.ctag;S.cat==='country'?renderCountryHead():renderCenterHead();load(true);return}
 if(ds.country!==undefined){$('#dlg').open&&$('#dlg').close();return openCountry(ds.country)}
 if(ds.ctyregion!==undefined){CTYF.region=ds.ctyregion;document.querySelectorAll('#ctyregion button').forEach(b=>b.classList.toggle('on',b===t));return renderCtyGrid()}
 if(ds.btopic!==undefined){BF.topic=ds.btopic;document.querySelectorAll('#btopic button').forEach(b=>b.classList.toggle('on',b===t));return loadBooks()}
 if(ds.blang!==undefined){BF.lang=ds.blang;document.querySelectorAll('#blang button').forEach(b=>b.classList.toggle('on',b===t));return loadBooks()}
 if(ds.book)return openBook(ds.book);
 if(ds.booktr)return translateBook(ds.booktr);
 if(ds.tag){$('#dlg').open&&$('#dlg').close();if(['saved','health','centers','dash','tweets','countries','books','writer','bot','map','alerts','ask','sanctions','cases','archive','net','settings','daily'].includes(S.cat))setView('all');S.tag=ds.tag;renderActiveTag();if(S.cat==='center')renderCenterHead();if(S.cat==='country')renderCountryHead();if(META)renderTags();load(true);return}
 if(ds.hours!==undefined){S.hours=+ds.hours;document.querySelectorAll('#hours button').forEach(b=>b.classList.toggle('on',b===t));if(S.cat!=='saved')load(true);return}
 if(ds.cregion!==undefined){CF.region=ds.cregion;document.querySelectorAll('#cregion button').forEach(b=>b.classList.toggle('on',b===t));return renderCenterGrid()}
 if(ds.ccat!==undefined){CF.cat=ds.ccat;document.querySelectorAll('#ccat button').forEach(b=>b.classList.toggle('on',b===t));return renderCenterGrid()}
 if(t.id==='trtest')return trTest();
 if(t.id==='updgo'||t.id==='updgo2'){toast('يجري إعادة التشغيل…');api('/api/update/restart',{method:'POST'}).catch(()=>{});setTimeout(()=>location.reload(),6000);return}
 if(t.id==='updlater'){sessionStorage.setItem('upd_later','1');$('#updbar').hidden=true;return}
 if(t.id==='updcheck'){t.disabled=true;t.textContent='جارٍ الفحص…';api('/api/update/check',{method:'POST'}).then(d=>{toast(d.state.error||d.state.state||'تم');loadUpdBox();loadMeta().then(updBanner)}).catch(()=>toast('تعذّر الفحص'));return}
 if(t.id==='cmdbtn')return cmdOpen();
 if(t.id==='askgo')return askGo();
 if(t.id==='askcopy')return navigator.clipboard.writeText(ASKTXT).then(()=>toast('نُسخت الإجابة'));
 if(t.id==='archclear'){const lbl=AH?`أرشيف آخر ${AH==24?'24 ساعة':AH==168?'أسبوع':'شهر'}`:'الأرشيف كله';
  if(!confirm('حذف الأرشيف نهائياً؟\nاضغط «موافق» لحذف كل المواد المؤرشفة.'))return;
  api('/api/archive',{method:'DELETE'}).then(()=>{toast('حُذف الأرشيف');APAGE=1;loadArch()});return}
 if(t.id==='sancref'){api('/api/sanctions/refresh',{method:'POST'}).then(()=>{toast('يجري تنزيل القوائم، قد يستغرق دقيقة');setTimeout(loadSanc,1500)});return}
 if(t.id==='casenew'){const tt=prompt('عنوان القضية الجديدة:');if(!tt)return;api('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:tt})}).then(d=>{CASE=d.id;loadCases()});return}
 if(t.id==='casedel'){if(!confirm('حذف القضية وكل ما فيها من ملاحظات؟'))return;api('/api/cases/'+CASE,{method:'DELETE'}).then(()=>{CASE=null;loadCases()});return}
 if(t.id==='casesave'){api('/api/cases/'+CASE,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:$('#ctitle').value,descr:$('#cdescr').value})}).then(()=>{toast('حُفظ');loadCases()});return}
 if(t.id==='pickclose'){$('#casepick')?.remove();return}
 if(t.id==='picknew'){const tt=$('#picktitle').value.trim();if(!tt)return;api('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:tt,item_id:PICKITEM})}).then(()=>{$('#casepick')?.remove();toast('أُنشئت القضية وأُضيفت المادة إليها')});return}
 if(t.id==='wlogdelall'){if(!confirm('حذف كل المقالات المكتوبة نهائياً؟'))return;api('/api/articles',{method:'DELETE'}).then(()=>{toast('حُذفت كل المقالات');loadArticles().then(renderWLog)});return}
 if(t.id==='lansave'){api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lan:$('#lanon').checked,pin:$('#lanpin').value})}).then(()=>{toast('حُفظ. أعد تشغيل البرنامج ليُطبَّق');renderHealth()}).catch(e=>toast(e.message));return}
 if(ds.wprov)return wcfg({provider:ds.wprov});
 if(ds.wpull){api('/api/writer/ollama/pull',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:ds.wpull})}).then(()=>{toast('بدأ التنزيل، قد يستغرق عدة دقائق');setTimeout(loadWriter,1500)}).catch(e=>toast(e.message));return}
 if(t.id==='wcheck')return loadWriter().then(()=>toast(WCFG.ollama.running?'Ollama يعمل':'لم يُعثر على Ollama؛ تأكد أنه مثبت ومشغّل'));
 if(t.id==='wkeyedit'){WCFG.claude.has_key=false;return renderWKey()}
 if(t.id==='wgemedit'){WCFG.gemini.has_key=false;return renderWKey()}
 if(t.id==='wkeysave')return wcfg({key:$('#wkeyin').value.trim()},'حُفظ المفتاح');
 if(t.id==='wgemsave'){toast('جارٍ التحقق من المفتاح…');return wcfg({gemini_key:$('#wgemkey').value.trim()},'حُفظ مفتاح Gemini')}
 if(t.id==='hall'){HONLY=false;return drawHealth()}
 if(t.id==='hbad'){HONLY=true;return drawHealth()}
 if(t.id==='hcopy')return copyBroken();
 if(t.id==='trbtn')return translateNow();
 if(t.id==='origbtn'){CUR.showOrig=!CUR.showOrig;return renderDlg()}
 if(t.id==='retryfull'){const id=CUR.id;if(id){CUR.full=null;renderFull();loadFull(id,true)}return}
 if(t.id==='cleartag'){S.tag='';renderActiveTag();if(META)renderTags();load(true)}
});
$('#source').onchange=e=>{S.source=e.target.value;load(true)};
$('#more').onclick=()=>{S.page++;load(false)};
$('#newpill').onclick=()=>{window.scrollTo({top:0});load(true);$('#newpill').hidden=true;document.title=TITLE_DEFAULT};
$('#hideseen').onclick=()=>{S.hideSeen=!S.hideSeen;$('#hideseen').classList.toggle('on',S.hideSeen);S.cat==='saved'?renderSaved():load(true)};
$('#density').onclick=()=>{S.compact=!S.compact;lsSet('rased_compact',S.compact?'1':'0');$('#density').classList.toggle('on',S.compact);S.cat==='saved'?renderSaved():load(true)};
$('#kwadd').onclick=addKw;$('#kwinput').onkeydown=e=>{if(e.key==='Enter')addKw()};
$('#tgadd').onclick=addTg;$('#tgplat').onchange=e=>{$('#tgch').placeholder=e.target.value==='bluesky'?'اسم الحساب أو رابطه، مثل: apnews.com أو name.bsky.social':'اسم القناة أو رابطها، مثل: t.me/AJArabic'};$('#tgch').onkeydown=e=>{if(e.key==='Enter')addTg()};
$('#tgrefresh').onclick=async()=>{await api('/api/telegram/refresh',{method:'POST'});toast('يجري تحديث كل القنوات');setTimeout(loadTgBoard,8000)};
$('#cq').oninput=e=>{CF.q=e.target.value.trim();renderCenterGrid()};
$('#ctyq').oninput=e=>{CTYF.q=e.target.value.trim();renderCtyGrid()};
let bqt;$('#bq').oninput=e=>{clearTimeout(bqt);bqt=setTimeout(()=>{BF.q=e.target.value.trim();loadBooks()},400)};
$('#brefresh').onclick=async()=>{await api('/api/books/refresh',{method:'POST'});toast('يجري البحث عن الكتب الجديدة، وستظهر خلال دقائق');setTimeout(loadBooks,15000)};
$('#dlgClose').onclick=()=>$('#dlg').close();
$('#dlg').addEventListener('click',e=>{if(e.target.id==='dlg')$('#dlg').close()});
$('#dlg').addEventListener('close',()=>{S.openId=null;CUR.id=null});
let qt;$('#q').oninput=e=>{clearTimeout(qt);qt=setTimeout(()=>{S.q=e.target.value.trim();if(['health','centers','dash','tweets','countries','books','writer','bot','map','alerts','ask','sanctions','cases','archive','net','settings','daily'].includes(S.cat))setView('all');else if(S.cat==='saved')renderSaved();else load(true)},400)};
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&document.activeElement?.id==='qslide'){openItem(document.activeElement.dataset.open);return}if(e.key==='/'&&!['INPUT','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('#q').focus()}});
$('#refresh').onclick=async()=>{const d=await api('/api/refresh',{method:'POST'});toast(d.running?'دورة جلب جارية بالفعل':'بدأ تحديث جميع المصادر');$('#refresh').classList.add('spin');setTimeout(poll,4000)};
function applySkin(t){if(!['neon','ops','gold','light'].includes(t))t='neon';document.documentElement.dataset.theme=t;document.querySelectorAll('[data-skin]').forEach(b=>b.classList.toggle('on',b.dataset.skin===t));lsSet('rased_skin',t)}
function applyTk(on){$('#tickers').classList.toggle('off',!on);$('#tkTxt').textContent=on?'إخفاء الأشرطة':'إظهار الأشرطة';$('#tkToggle').setAttribute('aria-pressed',on);lsSet('rased_tk',on?'1':'0')}
$('#tkToggle').onclick=()=>applyTk($('#tickers').classList.contains('off'));

if('serviceWorker' in navigator&&(location.protocol==='https:'||['localhost','127.0.0.1'].includes(location.hostname)))navigator.serviceWorker.register('/sw.js').catch(()=>{});
(async()=>{
 if(!lsGet('rased_skin_v2',''))lsSet('rased_skin','neon'),lsSet('rased_skin_v2','1');
 applySkin(lsGet('rased_skin','neon'));applyTk(lsGet('rased_tk','1')!=='0');
 S.compact=lsGet('rased_compact','0')==='1';$('#density').classList.toggle('on',S.compact);
 clocks();setInterval(clocks,1000);
 try{await loadCenters()}catch(e){}
 try{await loadCty()}catch(e){}
 try{await loadQStats()}catch(e){}
 try{const nt=await api('/api/net');NETBAD=nt.countries.filter(c=>c.level!=='normal').length}catch(e){}
 try{BOTON=(await api('/api/bot')).cfg.enabled}catch(e){}
 loadAlertCount();
 try{const b=await api('/api/books');BOOKS_N=b.topics.reduce((a,t)=>a+t.count,0)}catch(e){}
 try{await loadMeta()}catch(e){}
 setView('dash');loadTicker().catch(()=>{});
 setInterval(poll,45000);
 setInterval(()=>{if(S.cat==='tweets'){tgNext();if(TG_LAST&&Date.now()/1000>TG_LAST+TG_INT+15&&Date.now()-TG_LOADED>20000)loadTgBoard()}},1000);
 setInterval(()=>document.querySelectorAll('#feed time').forEach(t=>{const it=ITEMS.get(t.closest('[data-id]')?.dataset.id);if(it)t.textContent=ago(it.published)}),60000);
})();
</script>
</body>
</html>
"""


# ───────────────────────── التشغيل ─────────────────────────
if __name__ == "__main__":
    init_db()
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
    threading.Thread(target=bot_cmd_loop, daemon=True).start()
    threading.Thread(target=daily_loop, daemon=True).start()
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
