# Contributing to PowerTUI

Thanks for helping improve PowerTUI. This project is a Linux hardware/power TUI,
so contributions usually fall into one of four buckets: a new **backend**, a new
**distribution**, a **bug fix**, or **docs**.

## Development setup

No packaging required for development — the package runs from a checkout:

```sh
git clone https://github.com/X3C12/PowerTui.git
cd PowerTui
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m powertui --diagnostics   # read-only, no root
```

To run the TUI against real hardware you need elevated access; use the launcher
(which picks `sudo`/`doas`/`pkexec`):

```sh
./run_tui.sh
```

## Tests

All tests are hermetic (they mock `/proc`, `/sys` and PCI trees in temp dirs and
never require root). Run them before opening a PR:

```sh
python3 -m unittest discover -p "test_*.py"
```

If you change a shell script, also run:

```sh
shellcheck -s sh run_tui.sh install.sh uninstall.sh get.sh
```

## Adding a backend or distribution

1. Probe it in `powertui/capabilities.py` (return a `Capability` with a `reason`
   and, when applicable, an install hint) and register it in `_probe_all`.
2. If tool availability depends on the distribution, add/adjust a `DISTRO_RULES`
   entry using the shared order constants in the same file.
3. Dispatch to the backend in `powertui/sys_controller.py`, routing privileged
   writes through `_write_file_or_sudo` (which has a short timeout and must never
   block the UI).
4. Gate any new UI action by adding its capability key to `BUTTON_CAPABILITY` in
   `powertui/app.py`.
5. Add tests for the probe and the dispatch.

## Pull requests

- Keep changes focused; one concern per PR.
- Update `CHANGELOG.md` under `[Unreleased]`.
- Make sure CI is green (tests on Python 3.10–3.13, shellcheck, desktop validation).
- Describe the hardware/distro you tested on and paste the relevant
  `powertui --diagnostics` lines.

## Reporting a hardware issue

Include your distribution, kernel, CPU and GPU, and the output of
`powertui --diagnostics` — it lists exactly which backends PowerTUI detected.
