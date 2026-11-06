# -*- coding: utf-8 -*-
"""
مشغّل مركز أبو زبيدة للتتبع والرصد
يتحقق من المكتبات اللازمة ويثبّت الناقص منها تلقائياً، ثم يشغّل البرنامج.
"""
import os
import sys
import subprocess
import importlib.util

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))

# (اسم الاستيراد، اسم الحزمة في pip، ضرورية؟، الوصف)
PACKAGES = [
    ("flask", "flask", True, "خادم الواجهة"),
    ("feedparser", "feedparser", True, "قراءة خلاصات الأخبار"),
    ("requests", "requests", True, "الاتصال بالمصادر"),
    ("deep_translator", "deep-translator", False, "مزود ترجمة احتياطي"),
    ("curl_cffi", "curl_cffi", False, "فتح المواقع المحمية"),
    ("trafilatura", "trafilatura", False, "استخراج نص المقالات بدقة"),
    ("webview", "pywebview", False, "فتح المركز في نافذة برنامج مستقلة"),
]


def line(t=""):
    print(t, flush=True)


def has(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


def ensure_pip():
    if has("pip"):
        return True
    line("  pip غير موجود، يجري تثبيته…")
    try:
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
        return True
    except Exception:
        return False


def install(pkg):
    base = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location"]
    tries = [base + [pkg], base + ["--user", pkg]]          # الثانية: عند عدم وجود صلاحية للمجلد العام
    if os.name != "nt":
        tries.append(base + ["--user", "--break-system-packages", pkg])
    for cmd in tries:
        try:
            if subprocess.call(cmd) == 0:
                importlib.invalidate_caches()
                return True
        except Exception:
            pass
    return False


def main():
    line("=" * 60)
    line("  مركز أبو زبيدة للتتبع والرصد")
    line("=" * 60)
    if sys.version_info < (3, 9):
        line(f"  نسخة بايثون عندك قديمة ({sys.version.split()[0]}). يلزم 3.9 أو أحدث.")
        line("  نزّل أحدث نسخة من: https://www.python.org/downloads/")
        return 1
    line(f"  بايثون {sys.version.split()[0]}  ({sys.executable})")
    line("")
    line("  فحص المكتبات…")
    missing = [p for p in PACKAGES if not has(p[0])]
    for mod, pkg, req, desc in PACKAGES:
        line(f"   {'✔' if (mod, pkg, req, desc) not in missing else '✘'}  {pkg:<16} {desc}")
    if missing:
        line("")
        line(f"  تثبيت {len(missing)} مكتبة ناقصة (مرة واحدة فقط، قد يستغرق دقائق)…")
        if not ensure_pip():
            line("  تعذّر تجهيز pip. أعد تثبيت بايثون من python.org مع تفعيل خيار pip.")
            return 1
        failed_required = []
        for mod, pkg, req, desc in missing:
            line("")
            line(f"  ← تثبيت {pkg} ({desc})")
            ok = install(pkg)
            if not ok or not has(mod):
                if req:
                    failed_required.append(pkg)
                    line(f"  ✘ فشل تثبيت {pkg} وهي ضرورية.")
                else:
                    line(f"  ! تعذّر تثبيت {pkg} (اختيارية)، سيعمل البرنامج بدونها بقدرة أقل.")
        if failed_required:
            line("")
            line("  لم تُثبَّت مكتبات ضرورية: " + "، ".join(failed_required))
            line("  تأكد من اتصال الإنترنت ثم شغّل الملف مرة أخرى.")
            return 1
        line("")
        line("  ✔ اكتمل تثبيت المكتبات.")
    line("")
    line("  تشغيل البرنامج… ستُفتح الصفحة في المتصفح على: http://127.0.0.1:5050")
    line("  لإيقاف البرنامج أغلق هذه النافذة.")
    line("=" * 60)
    os.chdir(HERE)
    return subprocess.call([sys.executable, os.path.join(HERE, "rased.py")])


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        code = 0
    sys.exit(code or 0)
