# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-10-08

### Added

- Portable **AppImage** (`PowerTUI-x86_64.AppImage`) built with `python-appimage`,
  bundling a relocatable CPython 3.13 + Textual; run it directly, no install and no
  dependencies. Built and attached to GitHub Releases by CI
  (`.github/workflows/release.yml`).
- `packaging/build_appimage.sh` for reproducing the AppImage locally.
- Automatic GitHub **Release** on `v*` tags (`powertui.tar.gz` + `SHA256SUMS`).
- README badges (CI, release, license, Python) and community health files
  (`CONTRIBUTING.md`, `SECURITY.md`, issue forms, PR template).
- `docs/PROMOTION.md` promotion kit.

### Changed

- Packaged as the installable `powertui` module (`pip`/`pipx`) with a `powertui`
  console entry point; `python -m powertui` runs the app.

## [0.1.0] - 2026-10-07

### Added

- Cross-distribution detection layer (`platform_detect.py`): parses `/etc/os-release`
  with fallbacks and classifies debian / rhel / arch / suse / alpine / gentoo / void /
  nixos families, plus package manager, init system and privilege tool.
- Capability layer (`capabilities.py`): probes 12 subsystems and reports
  `supported`, backend, reason and a package-manager install hint for each.
- Controller dispatch (`sys_controller.py`) across backends:
  - CPU P-core/E-core topology and sysfs online/offline hotplug.
  - Turbo Boost (`intel_pstate/no_turbo` or generic `cpufreq/boost`) and CPU EPP
    validated against the CPU's advertised values.
  - Power profiles via `powerprofilesctl`, `tuned-adm` or `cpupower`.
  - NVIDIA Optimus GPU switching via `supergfxctl`, `envycontrol`, `optimus-manager`,
    `prime-select` or `system76-power`.
  - NVIDIA power cap (`nvidia-smi -pl`), AMD GPU DPM performance level, AMD Ryzen
    limits (`ryzenadj`), ASUS / ACPI platform profiles, fans (`nbfc`/`asusctl`),
    battery telemetry and background container/daemon cleanup.
- Textual TUI (`app.py`) with a platform/capability panel, one-click presets
  (Max Battery / Balanced / Max Performance / Reset), per-core controls, GPU and
  extended-hardware controls, and capability gating (unsupported actions disabled
  with a reason).
- `--diagnostics` mode: read-only detection report that needs neither root nor Textual.
- Install tooling: `run_tui.sh` launcher (POSIX `sh`, `sudo`/`doas`/`pkexec`),
  `install.sh` / `uninstall.sh` (desktop entry + `powertui` command + icon),
  `get.sh` one-command GitHub bootstrap with optional `--verify`.
- `powertui` console entry point and `pyproject.toml` for `pip`/`pipx` installs.
- NixOS `flake.nix`.
- 49 hermetic `unittest` tests (temp-dir mocks; no root, no real `/proc`/`/sys`).
- CI workflow: tests on Python 3.10–3.13, `shellcheck` on the shell scripts,
  and `.desktop` validation.

[Unreleased]: https://github.com/X3C12/PowerTui/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/X3C12/PowerTui/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/X3C12/PowerTui/releases/tag/v0.1.0
