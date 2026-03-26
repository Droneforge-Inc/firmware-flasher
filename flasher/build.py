#!/usr/bin/env python3

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_VENV_DIR = ROOT_DIR / ".venv"
DEFAULT_PYINSTALLER_CONFIG_DIR = ROOT_DIR / ".pyinstaller"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build the flash-helper PyInstaller binary."
    )
    parser.add_argument(
        "--mode",
        choices=("native", "universal", "universal2"),
        default="native",
        help="Build a native binary or a macOS universal2 binary.",
    )
    parser.add_argument(
        "--python",
        dest="python_bin",
        default=None,
        help="Python interpreter to use when creating the venv.",
    )
    parser.add_argument(
        "--venv",
        dest="venv_dir",
        default=str(DEFAULT_VENV_DIR),
        help="Venv directory to create/use.",
    )
    parser.add_argument(
        "--pyinstaller-config-dir",
        default=str(DEFAULT_PYINSTALLER_CONFIG_DIR),
        help="PyInstaller config directory.",
    )
    return parser.parse_args()


def resolve_python_bin(value):
    if not value:
        return Path(sys.executable).resolve()

    candidate = Path(value).expanduser()
    if candidate.parent != Path("."):
        resolved = candidate.resolve()
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise FileNotFoundError(f"Python not found or not executable: {value}")
        return resolved

    resolved_cmd = shutil.which(value)
    if not resolved_cmd:
        raise FileNotFoundError(f"Python not found or not executable: {value}")
    return Path(resolved_cmd).resolve()


def validate_mode(mode, system_name=None):
    normalized = "universal2" if mode == "universal" else mode
    if system_name is None:
        system_name = platform.system()
    if normalized == "universal2" and system_name != "Darwin":
        raise ValueError("--mode universal is only supported on macOS")
    return normalized


def venv_python_path(venv_dir, os_name=None):
    if os_name is None:
        os_name = os.name
    if os_name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def build_pythonpath():
    current = os.environ.get("PYTHONPATH")
    root = str(ROOT_DIR)
    return root if not current else os.pathsep.join((root, current))


def run(cmd, env=None):
    subprocess.run(cmd, check=True, cwd=ROOT_DIR, env=env)


def artifact_path(os_name=None):
    if os_name is None:
        os_name = os.name
    name = "flash-helper.exe" if os_name == "nt" else "flash-helper"
    return ROOT_DIR / "dist" / name


def main():
    args = parse_args()
    mode = validate_mode(args.mode)
    python_bin = resolve_python_bin(args.python_bin)
    venv_dir = Path(args.venv_dir).expanduser().resolve()
    pyinstaller_config_dir = Path(args.pyinstaller_config_dir).expanduser().resolve()

    print(f"Mode: {mode}")
    print(f"Python: {python_bin}")
    print(f"Venv: {venv_dir}")
    print(f"PyInstaller config: {pyinstaller_config_dir}")

    pyinstaller_config_dir.mkdir(parents=True, exist_ok=True)

    run([str(python_bin), "-m", "venv", str(venv_dir)])

    venv_python = venv_python_path(venv_dir)
    if not venv_python.exists():
        raise FileNotFoundError(f"Venv Python not found: {venv_python}")

    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(pyinstaller_config_dir)
    env["PYTHONPATH"] = build_pythonpath()

    if mode == "universal2":
        env["FLASH_HELPER_TARGET_ARCH"] = "universal2"
    else:
        env.pop("FLASH_HELPER_TARGET_ARCH", None)

    run([str(venv_python), "-m", "pip", "install", "-U", "pip"], env=env)
    run([str(venv_python), "-m", "pip", "install", "-r", "requirements-build.txt"], env=env)
    run([str(venv_python), "-m", "PyInstaller", "--clean", "--noconfirm", "flash-helper.spec"], env=env)

    print(f"Built: {artifact_path()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
