#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
MODE="native"
PYTHON_BIN="${PYTHON_BIN:-}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$ROOT_DIR/.pyinstaller}"

usage() {
    cat <<'EOF'
Usage:
  ./build.sh [--mode native|universal] [--python /path/to/python3] [--venv /path/to/venv]

Options:
  --mode native|universal   Build a native binary or a macOS universal2 binary.
  --python PATH             Python interpreter to use when creating the venv.
  --venv PATH               Venv directory to create/use. Default: ./.venv
  -h, --help                Show this help text.

Env overrides:
  PYTHON_BIN                Same as --python
  VENV_DIR                  Same as --venv
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --python)
            PYTHON_BIN="$2"
            shift 2
            ;;
        --venv)
            VENV_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

PYINSTALLER_ARGS=(
    --clean
    --noconfirm
)

case "$MODE" in
    native)
        if [[ -z "$PYTHON_BIN" ]]; then
            PYTHON_BIN="python3"
        fi
        unset FLASH_HELPER_TARGET_ARCH || true
        ;;
    universal|universal2)
        if [[ -z "$PYTHON_BIN" ]]; then
            PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
        fi
        export FLASH_HELPER_TARGET_ARCH="universal2"
        ;;
    *)
        echo "Invalid mode: $MODE" >&2
        usage >&2
        exit 1
        ;;
esac

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python not found or not executable: $PYTHON_BIN" >&2
    exit 1
fi

echo "Mode: $MODE"
echo "Python: $PYTHON_BIN"
echo "Venv: $VENV_DIR"
echo "PyInstaller config: $PYINSTALLER_CONFIG_DIR"

cd "$ROOT_DIR"

mkdir -p "$PYINSTALLER_CONFIG_DIR"

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install -U pip
python -m pip install -r requirements-build.txt

PYINSTALLER_CONFIG_DIR="$PYINSTALLER_CONFIG_DIR" \
PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    pyinstaller "${PYINSTALLER_ARGS[@]}" flash-helper.spec

echo "Built: $ROOT_DIR/dist/flash-helper"
