#!/bin/sh
# PowerTUI AppImage entrypoint.
# The powertui/ source package is bundled at $APPDIR/powertui (see build_appimage.sh -x).
# -s keeps the user site-packages out; PYTHONPATH points at the AppDir so
# `python -m powertui` resolves the bundled package. Do NOT add -E/-I here:
# they would ignore PYTHONPATH and the import would fail.
PYTHONPATH="${APPDIR}"
export PYTHONPATH
# shellcheck disable=SC1083  # the python-executable token below is a template
exec {{ python-executable }} -s -m powertui "$@"
