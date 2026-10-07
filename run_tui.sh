#!/bin/sh
# PowerTUI launcher - POSIX sh (works under dash/busybox ash).
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
PYTHONPATH="$DIR"
export PYTHONPATH

# Diagnostics mode is read-only: no root, no third-party packages required.
if [ "$1" = "--diagnostics" ]; then
    if [ -x "$DIR/.venv/bin/python3" ]; then
        exec "$DIR/.venv/bin/python3" -m powertui --diagnostics
    fi
    exec python3 -m powertui --diagnostics
fi

distro_hint() {
    id=""
    like=""
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        id="${ID:-}"
        like="${ID_LIKE:-}"
    fi
    case " $id $like " in
        *debian*|*ubuntu*)         echo "  Debian/Ubuntu: sudo apt install python3-venv" >&2 ;;
        *rhel*|*fedora*|*centos*)  echo "  RHEL/Fedora: sudo dnf install python3" >&2 ;;
        *arch*)                    echo "  Arch: sudo pacman -S python" >&2 ;;
        *suse*)                    echo "  openSUSE/SUSE: sudo zypper install python3" >&2 ;;
        *alpine*)                  echo "  Alpine: sudo apk add python3 py3-pip" >&2 ;;
        *gentoo*)                  echo "  Gentoo: sudo emerge dev-lang/python" >&2 ;;
        *void*)                    echo "  Void: sudo xbps-install python3" >&2 ;;
        *nixos*)                   echo "  NixOS: use 'nix develop' or 'nix run .'" >&2 ;;
        *)                         echo "  Install python3 with venv + pip for your distribution." >&2 ;;
    esac
}

# Ensure a virtual environment exists.
if [ ! -x "$DIR/.venv/bin/python3" ]; then
    echo "Creating python virtual environment..."
    if ! python3 -m venv "$DIR/.venv" 2>/dev/null; then
        echo "ERROR: could not create a virtual environment (python3 venv/pip unavailable)." >&2
        distro_hint
        exit 1
    fi
fi

# Install dependencies only when actually missing (offline / air-gapped safe).
if ! "$DIR/.venv/bin/python3" -c "import textual" >/dev/null 2>&1; then
    echo "Installing dependencies..."
    if ! "$DIR/.venv/bin/python3" -m pip install -q -r "$DIR/requirements.txt"; then
        echo "ERROR: failed to install dependencies (pip unavailable or no network)." >&2
        distro_hint
        exit 1
    fi
fi

# Pick an available privilege-escalation tool (portable across distributions).
if command -v sudo >/dev/null 2>&1; then
    PRIV="sudo -E"
elif command -v doas >/dev/null 2>&1; then
    PRIV="doas"
elif command -v pkexec >/dev/null 2>&1; then
    PRIV="pkexec"
else
    echo "ERROR: none of sudo/doas/pkexec was found." >&2
    echo "Run the application directly as root, or install one of those tools." >&2
    exit 1
fi

echo "Starting PowerTUI via '${PRIV}' for core and GPU power management..."
# Intentional word-splitting of $PRIV (e.g. "sudo -E").
# shellcheck disable=SC2086
exec $PRIV "$DIR/.venv/bin/python3" -m powertui "$@"
