#!/bin/sh
# ---------------------------------------------------------------------------
# PowerTUI bootstrap installer.
#
# Owner/repo is X3C12/powertui (override with POWERTUI_REPO if you fork it).
#
# Safe to run as:  curl -fsSL https://raw.githubusercontent.com/X3C12/powertui/main/get.sh | sh
# Must NOT rely on $0 or its own path.
# ---------------------------------------------------------------------------
set -e

REPO="${POWERTUI_REPO:-X3C12/powertui}"
REF="main"
DIR="${XDG_DATA_HOME:-$HOME/.local/share}/powertui"
DIR_GIVEN=0
SYSTEM=0
VERIFY=0

usage() {
    cat <<'EOF'
Usage: get.sh [options]

Options:
  --ref <ref>  Git ref/branch to fall back to (default: main).
  --dir <path> Install root (default: $HOME/.local/share/powertui).
  --system     Install system-wide (forwarded to install.sh).
  --verify     Verify the downloaded tarball against the release SHA256SUMS.
  -h, --help   Show this help.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --ref)    shift; REF="$1" ;;
        --ref=*)  REF="${1#--ref=}" ;;
        --dir)    shift; DIR="$1"; DIR_GIVEN=1 ;;
        --dir=*)  DIR="${1#--dir=}"; DIR_GIVEN=1 ;;
        --system) SYSTEM=1 ;;
        --verify) VERIFY=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# --- dependency detection ---------------------------------------------------
if command -v curl >/dev/null 2>&1; then
    DL="curl"
elif command -v wget >/dev/null 2>&1; then
    DL="wget"
else
    echo "ERROR: need 'curl' or 'wget' to download PowerTUI." >&2
    echo "  Debian/Ubuntu: sudo apt install curl   Alpine: sudo apk add curl" >&2
    exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
    echo "ERROR: need 'tar' to extract PowerTUI." >&2
    exit 1
fi

fetch() { # $1=url $2=outfile
    if [ "$DL" = "curl" ]; then
        curl -fsSL "$1" -o "$2"
    else
        wget -q -O "$2" "$1"
    fi
}

TMP="$(mktemp -d)" || { echo "ERROR: mktemp failed." >&2; exit 1; }
trap 'rm -rf "$TMP"' 0 HUP INT TERM

RELEASE_BASE="https://github.com/$REPO/releases/latest/download"
RELEASE_URL="$RELEASE_BASE/powertui.tar.gz"
ARCHIVE_URL="https://github.com/$REPO/archive/refs/heads/$REF.tar.gz"

echo "Downloading PowerTUI from $REPO ..."
if ! fetch "$RELEASE_URL" "$TMP/powertui.tar.gz" 2>/dev/null; then
    echo "No release asset found; falling back to branch '$REF' ..."
    if ! fetch "$ARCHIVE_URL" "$TMP/powertui.tar.gz"; then
        echo "ERROR: download failed. Check the repo name and your network." >&2
        exit 1
    fi
fi

# --- optional checksum verification (fails closed) -------------------------
if [ "$VERIFY" = "1" ]; then
    if ! fetch "$RELEASE_BASE/SHA256SUMS" "$TMP/SHA256SUMS" 2>/dev/null; then
        echo "ERROR: --verify requested but the latest release has no SHA256SUMS." >&2
        exit 1
    fi
    expected="$(awk '/powertui\.tar\.gz/ {print $1; exit}' "$TMP/SHA256SUMS")"
    if [ -z "$expected" ]; then
        echo "ERROR: --verify requested but powertui.tar.gz is not listed in SHA256SUMS." >&2
        exit 1
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        actual="$(sha256sum "$TMP/powertui.tar.gz" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
        actual="$(shasum -a 256 "$TMP/powertui.tar.gz" | awk '{print $1}')"
    else
        echo "ERROR: --verify requested but neither sha256sum nor shasum is available." >&2
        exit 1
    fi
    if [ "$expected" != "$actual" ]; then
        echo "ERROR: checksum mismatch — refusing to install." >&2
        exit 1
    fi
    echo "Checksum verified."
fi

# --- extract ----------------------------------------------------------------
echo "Extracting ..."
mkdir -p "$TMP/extract"
tar -xzf "$TMP/powertui.tar.gz" -C "$TMP/extract"
SRC="$(find "$TMP/extract" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "$SRC" ]; then
    echo "ERROR: archive did not contain a top-level directory." >&2
    exit 1
fi

if [ -e "$DIR" ]; then
    echo "Replacing existing install at $DIR ..."
    rm -rf "$DIR"
fi
mkdir -p "$(dirname "$DIR")"
mv "$SRC" "$DIR"

# Forward only the flags install.sh understands.
set --
[ "$SYSTEM" = "1" ] && set -- "$@" --system
[ "$DIR_GIVEN" = "1" ] && set -- "$@" --dir "$DIR"

echo "Running installer from $DIR ..."
# Not exec'd: the EXIT trap above must run to remove $TMP.
sh "$DIR/install.sh" "$@"
