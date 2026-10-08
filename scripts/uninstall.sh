#!/bin/sh
# PowerTUI uninstaller - POSIX sh (dash / busybox ash compatible).
set -e

SYSTEM=0
DEST=""
PURGE=0

usage() {
    cat <<'EOF'
Usage: uninstall.sh [options]

Options:
  --system     Remove a system-wide install (default: per-user).
  --dir <path> Install root of the source tree to (optionally) purge.
  --purge      Also delete the source tree.
  -h, --help   Show this help.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --system)  SYSTEM=1 ;;
        --dir)     shift; DEST="$1" ;;
        --dir=*)   DEST="${1#--dir=}" ;;
        --purge)   PURGE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$SYSTEM" = "1" ]; then
    [ -n "$DEST" ] || DEST="/usr/local/share/powertui"
    BIN_DIR="/usr/local/bin"
    APPS_DIR="/usr/local/share/applications"
    ICON_DIR="/usr/local/share/icons/hicolor/scalable/apps"
    ICON_THEME="/usr/local/share/icons/hicolor"
else
    DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
    [ -n "$DEST" ] || DEST="$DATA_HOME/powertui"
    BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
    APPS_DIR="$DATA_HOME/applications"
    ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
    ICON_THEME="$DATA_HOME/icons/hicolor"
fi

WRAPPER="$BIN_DIR/powertui"
DESKTOP="$APPS_DIR/powertui.desktop"
ICON="$ICON_DIR/powertui.svg"

priv() {
    if [ "$SYSTEM" = "1" ] && [ "$(id -u)" != "0" ]; then
        if command -v sudo >/dev/null 2>&1; then sudo -E "$@"
        elif command -v doas >/dev/null 2>&1; then doas "$@"
        elif command -v pkexec >/dev/null 2>&1; then pkexec "$@"
        else
            echo "ERROR: --system needs root; install sudo/doas/pkexec." >&2
            return 1
        fi
    else
        "$@"
    fi
}

echo "Removing PowerTUI ($([ "$SYSTEM" = 1 ] && echo system || echo user) scope)..."
priv rm -f "$WRAPPER" "$DESKTOP" "$ICON"

if command -v update-desktop-database >/dev/null 2>&1; then
    priv update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    priv gtk-update-icon-cache -f -t "$ICON_THEME" 2>/dev/null || true
fi

if [ "$PURGE" = "1" ]; then
    case "$DEST" in
        ""|"/"|"$HOME")
            echo "ERROR: refusing to purge unsafe path: '$DEST'" >&2
            exit 1
            ;;
    esac
    echo "Purging source tree: $DEST"
    priv rm -rf "$DEST"
fi

echo "Uninstalled."
