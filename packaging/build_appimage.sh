#!/bin/sh
# Build PowerTUI-x86_64.AppImage with python-appimage.
#
# Usage: sh packaging/build_appimage.sh
# Output: packaging/dist/PowerTUI-x86_64.AppImage (path printed on success).
#
# The powertui/ source tree is bundled with `-x` (NOT installed from PyPI, it
# is not published); see packaging/appimage/entrypoint.sh for how it is run.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
RECIPE="$ROOT/packaging/appimage"
DIST="$ROOT/packaging/dist"
PYTHON_VERSION=${PYTHON_VERSION:-3.13}

command -v python3 >/dev/null 2>&1 || {
    echo "error: python3 is required to build the AppImage" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

if command -v python-appimage >/dev/null 2>&1; then
    pyapp=python-appimage
else
    echo "python-appimage not found, installing into a temporary venv..."
    python3 -m venv "$tmp/venv"
    "$tmp/venv/bin/pip" install --quiet --upgrade pip
    "$tmp/venv/bin/pip" install --quiet python-appimage
    pyapp="$tmp/venv/bin/python-appimage"
fi

mkdir -p "$DIST" "$tmp/build"
cd "$tmp/build"

# Build with the recipe; -x bundles the powertui package into $APPDIR/powertui.
# Keep the recipe path before -x: -x takes one-or-more paths and would otherwise
# swallow the positional recipe argument.
"$pyapp" build app -p "$PYTHON_VERSION" "$RECIPE" -x "$ROOT/powertui"

set -- ./*.AppImage
[ -e "$1" ] || {
    echo "error: python-appimage produced no .AppImage" >&2
    exit 1
}

mv "$1" "$DIST/PowerTUI-x86_64.AppImage"
echo "$DIST/PowerTUI-x86_64.AppImage"
