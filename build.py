#!/usr/bin/env python3
"""
build.py — packages the Content Pipeline into a double-click Windows installer.

    python build.py

Produces, under build_output/:
    ContentPipeline/                 the frozen app (3 .exe + support files)
    Install ContentPipeline.exe      <- double-click THIS to install the app

The installer copies the app to %LOCALAPPDATA%\\ContentPipeline, creates a
Desktop + Start Menu shortcut, and registers an uninstaller. See installer.py.

This is a big build (opencv, lxml, newspaper, customtkinter all get bundled),
so expect it to take several minutes and produce several hundred MB of output.
Windows only.
"""
import os
import sys
import shutil
import subprocess
import importlib
from pathlib import Path

if sys.platform != "win32":
    print("build.py only produces Windows .exe files — run it on Windows.")
    sys.exit(1)

ROOT     = Path(__file__).parent.resolve()
OUT      = ROOT / "build_output"
APP_DIR  = OUT / "ContentPipeline"
APP_NAME = "ContentPipeline"


def _ensure(pkg, imp=None):
    imp = imp or pkg
    try:
        return importlib.import_module(imp)
    except ImportError:
        print(f"Installing {pkg} ...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)
        return importlib.import_module(imp)


def _pyinstaller(entry: Path, name: str, windowed: bool, distpath: Path, extra=None):
    extra = extra or []
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", name,
        "--distpath", str(distpath),
        "--workpath", str(OUT / "build" / name),
        "--specpath", str(OUT / "specs"),
        "--noconfirm",
        "--clean",
    ]
    if windowed:
        cmd.append("--windowed")
    cmd += extra
    cmd.append(str(entry))
    print(f"\n=== Building {name}.exe ===")
    subprocess.run(cmd, check=True, cwd=ROOT)


def build_app():
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    APP_DIR.mkdir(parents=True, exist_ok=True)

    # 1) automation.exe — the pipeline itself (kept console: rich UI + prompts)
    _pyinstaller(ROOT / "automation.py", "automation", windowed=False, distpath=APP_DIR,
                extra=["--collect-all", "newspaper", "--collect-all", "nltk"])

    # 2) wordpress_publisher.exe — standalone publisher / connection test
    _pyinstaller(ROOT / "wordpress_publisher.py", "wordpress_publisher",
                windowed=False, distpath=APP_DIR)

    # 3) ContentPipeline.exe — the control panel (no console window)
    _pyinstaller(ROOT / "pipeline_gui.py", "ContentPipeline", windowed=True, distpath=APP_DIR,
                extra=["--collect-all", "customtkinter"])

    # Support files the running app expects to find next to it
    for name in ("Skills", "rank-math-rest-meta.php", "README_SETUP.md"):
        src = ROOT / name
        if not src.exists():
            continue
        dst = APP_DIR / name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    print(f"\nApp bundle ready -> {APP_DIR}")


def build_installer() -> Path:
    installer_distpath = OUT / "_installer_dist"
    _pyinstaller(
        ROOT / "installer.py", f"Install {APP_NAME}", windowed=True,
        distpath=installer_distpath,
        extra=["--add-data", f"{APP_DIR}{os.pathsep}app"],
    )
    built = installer_distpath / f"Install {APP_NAME}.exe"
    final = OUT / f"Install {APP_NAME}.exe"
    shutil.move(str(built), str(final))
    shutil.rmtree(installer_distpath, ignore_errors=True)
    return final


def main():
    _ensure("pyinstaller", "PyInstaller")
    build_app()
    installer_exe = build_installer()
    print("\n" + "=" * 64)
    print("Done! Double-click this file to install Content Pipeline:")
    print(f"  {installer_exe}")
    print("=" * 64)


if __name__ == "__main__":
    main()
