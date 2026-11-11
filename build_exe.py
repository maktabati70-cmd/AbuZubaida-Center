# -*- coding: utf-8 -*-
"""
بناء ملف exe لمركز أبو زبيدة للتتبع والرصد (يُشغَّل مرة واحدة على ويندوز).
يثبّت الأدوات اللازمة، ثم يبني AbuZubaida-Center.exe في هذا المجلد، وينشئ اختصاراً على سطح المكتب.
"""
import os
import sys
import shutil
import subprocess
import importlib.util

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "AbuZubaida-Center"
REQUIRED = ["flask", "feedparser", "requests", "pyinstaller"]
OPTIONAL = [("deep_translator", "deep-translator"), ("curl_cffi", "curl_cffi"), ("trafilatura", "trafilatura"),
            ("webview", "pywebview")]


def say(t=""):
    print(t, flush=True)


def has(mod):
    importlib.invalidate_caches()
    return importlib.util.find_spec(mod) is not None


def pip(*pkgs):
    base = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location", "--upgrade"]
    if subprocess.call(base + list(pkgs)) == 0:
        return True
    return subprocess.call(base + ["--user"] + list(pkgs)) == 0


def main():
    say("=" * 60)
    say("  بناء برنامج مركز أبو زبيدة بصيغة exe")
    say("=" * 60)
    if sys.version_info < (3, 9):
        say("  يلزم بايثون 3.9 أو أحدث: https://www.python.org/downloads/")
        return 1
    say("\n  1) تثبيت الأدوات اللازمة للبناء (قد يستغرق دقائق)…")
    if not pip(*REQUIRED):
        say("  ✘ تعذّر تثبيت الأدوات. تأكد من الإنترنت ثم أعد المحاولة.")
        return 1
    for mod, pkg in OPTIONAL:
        if not has(mod):
            say(f"  ← {pkg} (اختيارية)")
            pip(pkg)
    say("\n  2) بناء الملف التنفيذي…")
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
            "--name", NAME, "--icon", os.path.join(HERE, "icon.ico"),
            "--distpath", os.path.join(HERE, "dist"), "--workpath", os.path.join(HERE, "build"),
            "--specpath", os.path.join(HERE, "build")]
    for mod in ("trafilatura", "justext", "htmldate", "courlan", "curl_cffi", "deep_translator", "feedparser",
                "webview", "clr_loader", "pythonnet"):
        if has(mod):
            args += ["--collect-all", mod]
    args.append(os.path.join(HERE, "rased.py"))
    if subprocess.call(args) != 0:
        say("  ✘ فشل البناء. أرسل آخر الأسطر الظاهرة أعلاه لمعرفة السبب.")
        return 1
    built = os.path.join(HERE, "dist", NAME + ".exe")
    target = os.path.join(HERE, NAME + ".exe")
    shutil.copy2(built, target)
    for d in ("build", "dist"):
        shutil.rmtree(os.path.join(HERE, d), ignore_errors=True)
    say(f"\n  ✔ تم البناء: {target}")
    say("\n  3) إنشاء اختصار على سطح المكتب…")
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\{NAME}.lnk');"
          f"$s.TargetPath='{target}';$s.WorkingDirectory='{HERE}';$s.IconLocation='{target},0';$s.Save()")
    if subprocess.call(["powershell", "-NoProfile", "-Command", ps]) == 0:
        say("  ✔ أُنشئ اختصار «AbuZubaida-Center» على سطح المكتب.")
    say("\n  من الآن شغّل البرنامج بالنقر المزدوج على AbuZubaida-Center.exe أو اختصار سطح المكتب.")
    say("  ابقِ الملف في هذا المجلد: قاعدة البيانات والإعدادات تُحفظ بجانبه.")
    return 0


if __name__ == "__main__":
    code = main()
    input("\n  اضغط Enter للإغلاق…")
    sys.exit(code)
