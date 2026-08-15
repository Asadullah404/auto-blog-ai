#!/usr/bin/env python3
"""
installer.py — frozen by build.py into "Install ContentPipeline.exe".

This is the file the user double-clicks. It carries the whole built app
(automation.exe, wordpress_publisher.exe, ContentPipeline.exe + support
files) bundled inside itself via PyInstaller --add-data, and on run:

  1. Copies that bundle to %LOCALAPPDATA%\\ContentPipeline
  2. Creates a Desktop + Start Menu shortcut to ContentPipeline.exe
  3. Registers an uninstaller in Windows "Apps & Features"
  4. Offers to launch the app immediately

Windows-only (uses ctypes.windll, winreg, PowerShell for .lnk creation).
"""
import os
import sys
import shutil
import ctypes
import subprocess
import winreg
from pathlib import Path

APP_NAME     = "ContentPipeline"
DISPLAY_NAME = "Content Pipeline"

MB_ICONINFO = 0x40
MB_ICONWARN = 0x30
MB_ICONERR  = 0x10
MB_YESNO    = 0x04
IDYES       = 6


def _bundled_app_dir() -> Path:
    """Where PyInstaller unpacked our --add-data 'app' folder at runtime."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / "app"


def _install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / APP_NAME


def _msgbox(text, icon=MB_ICONINFO):
    ctypes.windll.user32.MessageBoxW(0, text, DISPLAY_NAME, icon)


def _confirm(text) -> bool:
    return ctypes.windll.user32.MessageBoxW(0, text, DISPLAY_NAME, MB_YESNO | MB_ICONINFO) == IDYES


def _make_shortcut(target: Path, link_path: Path, workdir: Path, icon: Path):
    link_path.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{link_path}');"
        f"$s.TargetPath='{target}';"
        f"$s.WorkingDirectory='{workdir}';"
        f"$s.IconLocation='{icon}';"
        f"$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   check=True, creationflags=subprocess.CREATE_NO_WINDOW)


def _write_uninstaller(install_dir: Path) -> Path:
    bat = install_dir / "Uninstall.bat"
    # Self-deleting batch trick: spawn a detached helper that waits for this
    # process to exit, then removes the whole install folder (itself included).
    bat.write_text(f"""@echo off
echo Removing {DISPLAY_NAME} ...
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" /f >nul 2>nul
del "%USERPROFILE%\\Desktop\\{DISPLAY_NAME}.lnk" >nul 2>nul
del "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{DISPLAY_NAME}.lnk" >nul 2>nul
start "" /min cmd /c "timeout /t 1 >nul & rd /s /q \\"{install_dir}\\""
echo Done. This window will close shortly.
timeout /t 2 >nul
""", encoding="utf-8")
    return bat


def _register_uninstall(install_dir: Path, uninstaller: Path):
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, DISPLAY_NAME)
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, f'cmd /c "{uninstaller}"')
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)


def main():
    src = _bundled_app_dir()
    if not src.exists():
        _msgbox("Installer bundle is corrupt (the 'app' folder is missing inside it).\n"
               "Please rebuild with build.py.", icon=MB_ICONERR)
        sys.exit(1)

    dest = _install_dir()
    if dest.exists():
        if not _confirm(f"{DISPLAY_NAME} is already installed at:\n{dest}\n\nReinstall / update it?"):
            sys.exit(0)
        shutil.rmtree(dest, ignore_errors=True)

    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    exe = dest / "ContentPipeline.exe"
    if not exe.exists():
        _msgbox(f"Copied files, but {exe.name} is missing from the bundle.\n"
               "Please rebuild with build.py.", icon=MB_ICONERR)
        sys.exit(1)

    uninstaller = _write_uninstaller(dest)

    desktop = Path(os.environ["USERPROFILE"]) / "Desktop" / f"{DISPLAY_NAME}.lnk"
    start_menu = (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu"
                 / "Programs" / f"{DISPLAY_NAME}.lnk")
    try:
        _make_shortcut(exe, desktop, dest, exe)
        _make_shortcut(exe, start_menu, dest, exe)
        shortcuts_ok = True
    except Exception as e:
        shortcuts_ok = False
        shortcut_err = str(e)

    try:
        _register_uninstall(dest, uninstaller)
    except Exception:
        pass  # Add/Remove Programs entry is a nice-to-have, not required

    if not shortcuts_ok:
        _msgbox(f"Installed to:\n{dest}\n\n"
               f"Could not create shortcuts automatically:\n{shortcut_err}\n\n"
               f"You can run it directly from that folder.", icon=MB_ICONWARN)
        return

    if _confirm(f"{DISPLAY_NAME} installed to:\n{dest}\n\n"
               f"Shortcuts were added to your Desktop and Start Menu.\n\nLaunch it now?"):
        subprocess.Popen([str(exe)], cwd=str(dest))


if __name__ == "__main__":
    main()
