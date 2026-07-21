"""Build a single-file Windows executable for Prizma Studio.

Usage:
    python build_exe.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_NAME_DISPLAY = "Prizma Studio"
EXE_NAME = "PrizmaStudio"          # final .exe stem
ENTRY = HERE / "main.py"
ICON = HERE / "assets" / "icon.ico"
DIST = HERE / "dist"
BUILD = HERE / "build"
SPEC = HERE / f"{EXE_NAME}.spec"


HIDDEN_IMPORTS = [
    # third-party
    "fitz",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "sv_ttk",
    "darkdetect",
    "win32com",
    "win32com.client",
    "pythoncom",
    # local packages – force-include so PyInstaller never drops them
    "core",
    "core.config",
    "core.i18n",
    "core.theme",
    "modules",
    "modules.pdf_tools_tab",
    "modules.psd_tools_tab",
]


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd)


def preflight() -> None:
    print("== Preflight: fix_unicode ==")
    run([sys.executable, str(HERE / "fix_unicode.py")])


def install_deps() -> None:
    print("== Installing dependencies ==")
    req = HERE / "requirements.txt"
    if req.exists():
        run([sys.executable, "-m", "pip", "install", "-r", str(req)])
    run([sys.executable, "-m", "pip", "install", "-U", "pyinstaller"])


def clean_previous() -> None:
    """Remove leftovers from previous builds so PyInstaller starts fresh."""
    print("== Cleaning previous build artifacts ==")
    for path in (BUILD, DIST, SPEC):
        if path.exists():
            print(f"removing: {path}")
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    path.unlink()
                except OSError:
                    pass
    # Drop stale bytecode too – prevents PyInstaller from picking old .pyc files.
    for pyc_dir in HERE.rglob("__pycache__"):
        shutil.rmtree(pyc_dir, ignore_errors=True)


def build() -> None:
    print("== Building executable ==")
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--name={EXE_NAME}",
        f"--distpath={DIST}",
        f"--workpath={BUILD}",
        f"--specpath={HERE}",
        # Make PyInstaller look for local packages relative to the entry script.
        f"--paths={HERE}",
        "--collect-submodules=core",
        "--collect-submodules=modules",
    ]
    if ICON.exists():
        args.append(f"--icon={ICON}")
    assets_dir = HERE / "assets"
    if assets_dir.exists():
        sep = ";" if os.name == "nt" else ":"
        args.append(f"--add-data={assets_dir}{sep}assets")
    for h in HIDDEN_IMPORTS:
        args.append(f"--hidden-import={h}")
    args.append(str(ENTRY))
    run(args)


def create_shortcut() -> None:
    """Place a shortcut on the current user's Desktop (Windows only)."""
    if os.name != "nt":
        print("Skipping desktop shortcut (non-Windows).")
        return
    exe_path = DIST / f"{EXE_NAME}.exe"
    if not exe_path.exists():
        print(f"Executable not found at {exe_path}, cannot create shortcut.")
        return
    try:
        from win32com.client import Dispatch  # type: ignore
        shell = Dispatch("WScript.Shell")
        desktop = Path(shell.SpecialFolders("Desktop"))
        lnk = desktop / f"{APP_NAME_DISPLAY}.lnk"
        shortcut = shell.CreateShortcut(str(lnk))
        shortcut.TargetPath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_path.parent)
        if ICON.exists():
            shortcut.IconLocation = str(ICON)
        shortcut.Description = APP_NAME_DISPLAY
        shortcut.save()
        print(f"Shortcut created: {lnk}")
    except Exception as exc:
        print(f"Failed to create shortcut: {exc}")


def main() -> None:
    preflight()
    install_deps()
    clean_previous()
    build()
    create_shortcut()
    print("\n== Done ==")
    print(f"Executable: {DIST / (EXE_NAME + '.exe')}")


if __name__ == "__main__":
    main()
