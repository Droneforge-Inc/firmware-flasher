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


def build_dfu_env(dfu_util, platform_name=None, os_name=None):
    env = os.environ.copy()
    tool_dir = str(Path(dfu_util).parent)
    if platform_name is None:
        platform_name = sys.platform
    if os_name is None:
        os_name = os.name

    if platform_name == "darwin":
        prepend_env_path(env, "DYLD_LIBRARY_PATH", tool_dir)
    elif os_name == "nt":
        prepend_env_path(env, "PATH", tool_dir)
    else:
        prepend_env_path(env, "LD_LIBRARY_PATH", tool_dir)
    return env
