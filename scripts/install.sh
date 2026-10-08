#!/bin/sh
# PowerTUI installer - POSIX sh (dash / busybox ash compatible).
set -e

SYSTEM=0
DEST=""
NO_DESKTOP=0

usage() {
    cat <<'EOF'
Usage: install.sh [options]

Options:
  --system        Install system-wide (default: per-user).
  --dir <path>    Install root for the source tree.
  --no-desktop    Do not install the .desktop entry or icon.
  -h, --help      Show this help.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --system)    SYSTEM=1 ;;
        --dir)       shift; DEST="$1" ;;
        --dir=*)     DEST="${1#--dir=}" ;;
        --no-desktop) NO_DESKTOP=1 ;;
        -h|--help)   usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

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
RUN_TUI="$ROOT/scripts/run_tui.sh"

# Run a command with escalate-if-needed for system installs.
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

echo "Installing PowerTUI ($([ "$SYSTEM" = 1 ] && echo system || echo user) scope)..."

priv mkdir -p "$BIN_DIR"
[ "$NO_DESKTOP" = "1" ] || priv mkdir -p "$APPS_DIR" "$ICON_DIR"

# Command wrapper: absolute path to run_tui.sh baked in, no symlink resolution.
cat <<EOF | priv tee "$WRAPPER" >/dev/null
#!/bin/sh
exec "$RUN_TUI" "\$@"
EOF
priv chmod 0755 "$WRAPPER"

if [ "$NO_DESKTOP" != "1" ]; then
    cat <<EOF | priv tee "$DESKTOP" >/dev/null
[Desktop Entry]
Type=Application
Name=PowerTUI
Comment=Cross-distribution hardware power control
Exec="$WRAPPER"
Path=$ROOT
TryExec=$WRAPPER
Terminal=true
Icon=powertui
Categories=System;Monitor;
Keywords=power;battery;cpu;gpu;fan;turbo;
StartupNotify=true
EOF
    priv cp "$ROOT/assets/powertui.svg" "$ICON"
    priv chmod 0644 "$DESKTOP" "$ICON"
fi

# Refresh desktop/icon caches only when the tools are available; ignore failure.
if [ "$NO_DESKTOP" != "1" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        priv update-desktop-database "$APPS_DIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        priv gtk-update-icon-cache -f -t "$ICON_THEME" 2>/dev/null || true
    fi
    if command -v desktop-file-validate >/dev/null 2>&1; then
        desktop-file-validate "$DESKTOP" || true
    fi
fi

if [ "$SYSTEM" != "1" ]; then
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) echo "WARNING: $HOME/.local/bin is not in PATH; add it to use 'powertui'." >&2 ;;
    esac
fi

echo "Installed:"
echo "  command: $WRAPPER"
[ "$NO_DESKTOP" = "1" ] || echo "  desktop: $DESKTOP"
echo "Run 'powertui' or launch PowerTUI from your menu."
