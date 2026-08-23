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
import json
import os
import sys
import shutil
import subprocess
import importlib
import importlib.util
from pathlib import Path

if sys.platform != "win32":
    print("build.py only produces Windows .exe files — run it on Windows.")
    sys.exit(1)

ROOT     = Path(__file__).parent.resolve()
OUT      = ROOT / os.environ.get("BUILD_OUTPUT_DIR", "build_output")
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


def _winpty_binary_args() -> list:
    """
    `winpty` (pulled in by agy_headless_bridge on Windows) ships two native
    helper executables — OpenConsole.exe (ConPTY backend) and
    winpty-agent.exe (legacy backend) — that its compiled _winpty extension
    spawns at runtime by looking next to itself. Nothing imports them as
    Python modules, so PyInstaller's automatic dependency scan never finds
    them: it only picks up conpty.dll/winpty.dll/_winpty*.pyd because those
    are linked binaries. Without these two .exe files, every pseudo-console
    spawn silently produces zero captured output — agy runs to completion in
    a black hole and the frozen app sees nothing, even though the exact same
    code works fine unfrozen (site-packages/winpty has both files sitting
    right there). Bundle them explicitly, next to the auto-detected DLLs
    (same "winpty" destination folder), so the frozen exe has what the
    extension expects to find beside it.
    """
    try:
        spec = importlib.util.find_spec("winpty")
    except (ImportError, ValueError):
        spec = None
    if not spec or not spec.origin:
        print("  ⚠  winpty package not found — agy calls will likely fail in the frozen exe.")
        return []
    pkg_dir = Path(spec.origin).parent
    args = []
    for name in ("OpenConsole.exe", "winpty-agent.exe"):
        src = pkg_dir / name
        if src.exists():
            args += ["--add-binary", f"{src}{os.pathsep}winpty"]
        else:
            print(f"  ⚠  {src} not found — agy calls will likely fail in the frozen exe.")
    return args


def build_app():
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    APP_DIR.mkdir(parents=True, exist_ok=True)

    _assert_no_service_account_keys()

    # 1) automation.exe — the pipeline itself (kept console: rich UI + prompts)
    # --collect-all newspaper/nltk sweeps in unrelated ML packages that happen to be
    # installed in this dev environment (torch, tensorflow, transformers, sklearn,
    # cupy, numba, ...). The app never calls Article.nlp() or imports any of them —
    # only .download()/.parse() (HTML fetch + lxml extraction) — so they're dead
    # weight that bloats the exe past GitHub's release size limit. Exclude them.
    _pyinstaller(ROOT / "automation.py", "automation", windowed=False, distpath=APP_DIR,
                extra=["--collect-all", "newspaper", "--collect-all", "nltk",
                       "--exclude-module", "torch",
                       "--exclude-module", "torchvision",
                       "--exclude-module", "torchaudio",
                       "--exclude-module", "tensorflow",
                       "--exclude-module", "tensorboard",
                       "--exclude-module", "transformers",
                       "--exclude-module", "sklearn",
                       "--exclude-module", "scipy",
                       "--exclude-module", "pandas",
                       "--exclude-module", "matplotlib",
                       "--exclude-module", "sympy",
                       "--exclude-module", "huggingface_hub",
                       "--exclude-module", "IPython",
                       "--exclude-module", "jieba",
                       "--exclude-module", "cupy",
                       "--exclude-module", "cupyx",
                       "--exclude-module", "cupy_backends",
                       "--exclude-module", "numba",
                       "--exclude-module", "llvmlite",
                       "--exclude-module", "nvidia",
                       "--exclude-module", "triton",
                       "--exclude-module", "graphviz",
                       "--exclude-module", "lief"] + _winpty_binary_args())

    # 2) wordpress_publisher.exe — standalone publisher / connection test
    _pyinstaller(ROOT / "wordpress_publisher.py", "wordpress_publisher",
                windowed=False, distpath=APP_DIR)

    # 3) ContentPipeline.exe — the control panel (no console window)
    _pyinstaller(ROOT / "pipeline_gui.py", "ContentPipeline", windowed=True, distpath=APP_DIR,
                extra=["--collect-all", "customtkinter"])

    # Support files the running app expects to find next to it. firebase_config.json
    # (public web config — see firebase_config.example.json for why this isn't
    # a secret) must ship with every install so end users can sign in.
    for name in ("Skills", "rank-math-rest-meta.php", "README_SETUP.md",
                "firebase_config.json"):
        src = ROOT / name
        if not src.exists():
            if name == "firebase_config.json":
                print(f"  ⚠  {name} not found — sign-in won't work in this build. "
                      f"See firebase_config.example.json / README.md.")
            continue
        dst = APP_DIR / name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    print(f"\nApp bundle ready -> {APP_DIR}")


def _assert_no_service_account_keys():
    """
    Build-time guard: a Firebase/GCP service-account key (Admin SDK) would
    bypass Firestore Security Rules entirely and must never ship in the
    built app — unlike firebase_config.json's public web API key, which is
    safe to ship (see firebase_config.example.json). Nothing in this app's
    design creates or needs a service-account key; this just makes that an
    enforced build-time check instead of only a convention.
    """
    suspects = []
    for path in ROOT.glob("*.json"):
        if "service" in path.stem.lower() and "account" in path.stem.lower():
            suspects.append(path)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and "private_key" in data:
            suspects.append(path)
    if suspects:
        names = ", ".join(p.name for p in suspects)
        print(f"\n✗ Refusing to build: found what looks like a service-account "
              f"key ({names}) in {ROOT}. This must never be bundled into the "
              f"app — delete or move it out of this folder and rebuild.")
        sys.exit(1)


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
