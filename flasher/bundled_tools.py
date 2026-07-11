import os
import platform
import shutil
import sys
from pathlib import Path


def first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None


def normalized_machine(machine_name=None):
    if machine_name is None:
        machine_name = platform.machine()
    machine = machine_name.lower()
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "aarch64": "arm64",
    }
    return aliases.get(machine, machine)


def dfu_search_paths(resource_root, platform_name=None, machine_name=None, os_name=None):
    if platform_name is None:
        platform_name = platform.system().lower()
    else:
        platform_name = platform_name.lower()
    if os_name is None:
        os_name = os.name

    executable = "dfu-util.exe" if os_name == "nt" else "dfu-util"
    machine = normalized_machine(machine_name)
    base = Path(resource_root)
    variants = [f"{platform_name}-{machine}"]
    if platform_name == "darwin":
        variants.insert(0, f"macos-{machine}")
    return [base / variant / executable for variant in variants] + [base / executable]


def resolve_dfu_util(path_arg, resource_root):
    if path_arg is not None:
        path = Path(path_arg).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"dfu-util not found: {path}")
        return path

    bundled = first_existing(dfu_search_paths(resource_root))
    if bundled is not None:
        return bundled

    system_path = shutil.which("dfu-util")
    if system_path:
        return Path(system_path).resolve()

    searched = ", ".join(str(path) for path in dfu_search_paths(resource_root))
    raise FileNotFoundError(
        "dfu-util not found. Pass --dfu-util or bundle it under one of: "
        + searched
    )


def prepend_env_path(env, key, value):
    current = env.get(key)
    env[key] = value if not current else value + os.pathsep + current


def dfu_library_dirs(dfu_util):
    """Directories that must be searched for the staged/vendored libusb.

    Supported layouts:

    1. Nimbus stage (cmake --install / backend-stage)::

           stage/bin/dfu-util[.exe]
           stage/lib/libusb-1.0.so* | libusb-1.0*.dylib

    2. Vendored flasher bundle (next to the tool)::

           vendor/dfu-util/<platform>/dfu-util
           vendor/dfu-util/<platform>/libusb-1.0.0.dylib
           vendor/dfu-util/<platform>/libusb-1.0.so.0
           vendor/dfu-util/<platform>/libusb-1.0.dll

    Older build_dfu_env only put the tool directory on LD_LIBRARY_PATH, so
    Nimbus stage builds still resolved ambient host/Nix libusb via RUNPATH
    + LD_LIBRARY_PATH order. Always prefer sibling lib/ then the tool dir.
    """
    tool_dir = Path(dfu_util).resolve().parent
    lib_dir = tool_dir.parent / "lib"
    dirs = []
    # Prefer the sibling lib tree first (Nimbus stage layout).
    if lib_dir.is_dir():
        dirs.append(str(lib_dir))
    # Then the tool directory itself (vendored layout + Windows DLL-next-to-exe).
    dirs.append(str(tool_dir))
    return dirs


def build_dfu_env(dfu_util, platform_name=None, os_name=None):
    """Environment for launching dfu-util with bundled libusb preferred.

    Prepends library search paths so ambient host libraries cannot steal
    libusb-1.0 from the staged or vendored bundle.
    """
    env = os.environ.copy()
    if platform_name is None:
        platform_name = sys.platform
    if os_name is None:
        os_name = os.name

    # Prepend in reverse so the first library dir ends up first.
    for directory in reversed(dfu_library_dirs(dfu_util)):
        if platform_name == "darwin":
            prepend_env_path(env, "DYLD_LIBRARY_PATH", directory)
        elif os_name == "nt":
            prepend_env_path(env, "PATH", directory)
        else:
            prepend_env_path(env, "LD_LIBRARY_PATH", directory)
    return env
