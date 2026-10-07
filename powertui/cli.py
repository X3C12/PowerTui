"""Command-line entry point.

The ``--diagnostics`` fast path is handled before importing :mod:`powertui.app`
so that diagnostics keep working with no Textual installed.
"""

import sys


def main(argv=None) -> int:
    if "--diagnostics" in (argv or sys.argv[1:]):
        from .capabilities import Capabilities

        print(Capabilities().report_text())
        return 0

    from .app import PowerTUI

    PowerTUI().run()
    return 0
