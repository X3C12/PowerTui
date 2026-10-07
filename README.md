# PowerTUI

A cross-distribution terminal UI for live CPU core, Turbo/EPP, GPU, platform-profile, fan and battery control on Linux.

PowerTUI detects the host distribution and probes each hardware subsystem before acting. It performs the correct backend-specific action where one exists, and grey-out + reports the reason (with a package-manager install hint) where it does not.

## Install

One command, straight from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/X3C12/powertui/main/get.sh | sh
```

or, with `wget`:

```bash
wget -qO- https://raw.githubusercontent.com/X3C12/powertui/main/get.sh | sh
```

`get.sh` downloads the source into `$HOME/.local/share/powertui` (override with `--dir <path>`), installs the `powertui` command and desktop entry, and can fetch a specific branch or tag with `--ref <ref>` (default `main`). Add `--system` for a system-wide install and `--verify` to verify the download before installing.

### Install from a local clone

```bash
git clone https://github.com/X3C12/powertui.git
cd powertui
sh install.sh
```

`install.sh` is a POSIX `sh` script (busybox-ash compatible — no bash needed, so it runs on Alpine and Void). It installs to your user scope by default:

| Flag | Effect |
|---|---|
| `--system` | Install system-wide under `/usr/local` instead of the user home. |
| `--dir <path>` | Install the source into `<path>` (default `$HOME/.local/share/powertui`). |
| `--no-desktop` | Skip creating the desktop menu entry. |
| `--help` | Show usage. |

### Distribution prerequisites

PowerTUI needs Python 3 with virtual-environment support, plus a privilege tool. Install the packages for your distribution first:

| Distribution | Python | Privilege tool |
|---|---|---|
| debian / ubuntu | `python3`, `python3-venv` | `sudo` |
| rhel / fedora | `python3` | `sudo` |
| arch / manjaro | `python3` | `sudo` |
| suse / opensuse | `python3` | `sudo` |
| alpine | `python3`, `py3-pip` | `doas` |
| gentoo | `dev-lang/python` | `sudo` |
| void | `python3` | `doas` |
| nixos | `flake.nix` (`nix develop` / `nix run`) | `sudo` |

On NixOS use the provided `flake.nix`; the virtual-environment path also works.

## Features

- **CPU core control** — hybrid P-core/E-core topology discovery and online/offline toggling via sysfs.
- **Turbo Boost and EPP** — `intel_pstate/no_turbo` or generic `cpufreq/boost`; EPP validated against the CPU's advertised values (`map_epp`).
- **Power profiles** — `powerprofilesctl`, `tuned-adm` or `cpupower`, chosen per distribution family.
- **GPU switching (NVIDIA Optimus)** — `supergfxctl`, `envycontrol`, `optimus-manager`, `prime-select` or `system76-power`.
- **NVIDIA power cap** — `nvidia-smi -pl`, only when a live GPU probe succeeds.
- **AMD GPU DPM level** — amdgpu `power_dpm_force_performance_level` (`low`/`high`/`auto`).
- **AMD Ryzen power** — `ryzenadj` STAPM/FAST/SLOW presets.
- **Platform profiles and fans** — generic ACPI `platform_profile` or `asusctl`; `nbfc` or `asusctl` fans.
- **Battery telemetry** — live wattage and runtime estimate from `/sys/class/power_supply`.
- **Background cleanup** — stop docker/podman containers and systemd AI daemons.
- **One-click presets** — Max Battery, Balanced, Max Performance, and Reset to Default.
- **Capability gating** — unsupported actions are disabled with a reason and install hint; final sysfs writes fall back to `sudo -n`/`doas`/`pkexec` under a 3-second timeout so the UI never blocks on a password prompt.
- **`--diagnostics` mode** — read-only detection report that needs neither root nor Textual.

## Hardware Support Matrix

"Monitor" is telemetry only; "Control" can change state.

| Hardware | Monitor | Control | Notes |
|---|---|---|---|
| **Intel CPU** | yes | yes | Topology and hotplug via sysfs; Turbo via `intel_pstate/no_turbo` or `cpufreq/boost`; EPP validated against advertised values. |
| **AMD CPU** | yes | yes | Topology and `cpufreq/boost`; power limits via `ryzenadj` (STAPM/FAST/SLOW). |
| **NVIDIA GPU** | yes | yes | Runtime PCI status; `nvidia-smi` telemetry and power cap (`-pl`), only when a live `--query-gpu` probe reaches a GPU. Optimus switching via the detected tool. |
| **AMD GPU** | yes | partial | DPM **performance level** only (`power_dpm_force_performance_level` low/high/auto). **Not a power cap** — no clocks, voltages or fan curves. `lact`/`corectrl` are detected for awareness only and never driven. |
| **Intel iGPU** | no | no | Not supported; there is no backend. |
| **Laptop fans** | yes | partial | `nbfc` and `asusctl fan-curve` are writable; `thinkfan` is read-only/config-only and reported unsupported. |
| **Battery** | yes | no | Telemetry only; no charge-threshold control. |

## Supported Distributions

PowerTUI is distribution-agnostic. It classifies the host into a family from `ID`/`ID_LIKE` and applies per-family backend preference orders:

| Family | Example IDs | Preference override |
|---|---|---|
| debian | debian, ubuntu, kali, linuxmint, pop, raspbian, devuan | power profiles: `PP_NO_TUNED` |
| rhel | fedora, rhel, centos, rocky, alma, ol | power: `tuned-adm` first; GPU: drops `system76-power` |
| arch | arch, manjaro, endeavouros, garuda, artix, cachyos | power: `PP_NO_TUNED` |
| suse | opensuse, sles, sled | power: `PP_NO_TLP`; GPU: `GPU_CORE` |
| alpine | alpine | power: minimal; GPU: `GPU_BASIC` |
| gentoo | gentoo | power: minimal |
| void | void | power: minimal |
| nixos | nixos | power: `PP_NO_TLP` |
| other | unknown IDs | falls back to the shared default orders |

Unknown families fall back to `DEFAULT_POWER_PROFILE_ORDER` and `DEFAULT_GPU_ORDER`.

## Requirements

- Linux with `sysfs` and `/proc` (any modern distribution).
- Python 3 with the `textual` package (`textual>=0.70.0`; `rich` is pulled in transitively).
- A privilege-escalation tool for hardware changes: `sudo`, `doas` or `pkexec`.
- Optional vendor tools, only for the features you want: `powerprofilesctl`/`tuned-adm`/`cpupower`, `supergfxctl`/`envycontrol`/`optimus-manager`/`prime-select`/`system76-power`, `nvidia-smi`, amdgpu sysfs, `ryzenadj`, `asusctl`, `nbfc`, `docker`/`podman`.

## Run

After installing, launch PowerTUI with:

```bash
powertui
```

or pick **PowerTUI** in your desktop application menu. The menu entry opens a terminal (`Terminal=true`) because the TUI needs a TTY and elevation; the launcher picks the first available privilege tool — `sudo`, then `doas`, then `pkexec`.

On first launch the launcher creates `.venv` and installs `textual` only if it is missing (offline-friendly), then runs elevated.

From a local clone without installing, the launcher can be run directly:

```bash
./run_tui.sh
```

### Diagnostics

`powertui --diagnostics` prints a read-only detection report — no root and no Textual needed:

```bash
powertui --diagnostics
# or from a local clone
./run_tui.sh --diagnostics
python3 app.py --diagnostics
```

Example diagnostics output:

```
PowerTUI platform diagnostics
================================
Distribution : Kali GNU/Linux 2026.3 (id=kali, family=debian)
ID_LIKE      : debian
Package mgr  : apt
Init system  : systemd
Privilege    : sudo
Privilege now: user

Capabilities:
  [OK]   cpu_online       via sysfs
  [OK]   turbo            via intel_pstate
  [OK]   epp              via intel_pstate
  [OK]   power_profile    via powerprofilesctl
  [OK]   gpu_switch       via supergfxctl
  [OK]   nvidia_power     via nvidia-smi
  [--]   amd_gpu          no AMD GPU detected
  [--]   amd_power        no AMD CPU detected
  [OK]   asus_platform    via platform_profile_sysfs
  [OK]   fan_control      via asusctl
  [OK]   battery          via sysfs_power_supply
  [OK]   cleanup          via docker
```

## Uninstall

Remove the `powertui` command, desktop entry and icon:

```bash
sh uninstall.sh
```

| Flag | Effect |
|---|---|
| `--system` | Remove the system-wide install under `/usr/local`. |
| `--dir <path>` | Source tree to purge (only used with `--purge`); default `~/.local/share/powertui`. |
| `--purge` | Also delete the source tree (for a `get.sh` install this removes the virtual environment too). |

## Controls

Keyboard bindings:

| Key | Action |
|---|---|
| `b` | Max Battery preset (2 P-cores + 2 E-cores, Turbo off, power profile, integrated GPU, cleanup, quiet platform/fans) |
| `p` | Max Performance preset (all cores, Turbo on, performance profile, hybrid GPU, performance platform/fans) |
| `r` | Reset to defaults |
| `u` | Refresh status now |
| `q` | Quit |

On-screen buttons mirror the bindings and add:

- **Balanced Work** — 4 P-cores + 4 E-cores, Turbo on, balanced profile, hybrid GPU.
- **Custom CPU core control** — `-`/`+` for P-cores and E-cores.
- **GPU mode** — switch to Integrated or Hybrid.
- **Clean background containers** — docker/podman + systemd daemons.
- **Extended hardware** — NVIDIA Eco/Max, AMD GPU Low/Auto, Ryzen Eco/Perf, Platform/Fan Quiet/Performance.

Buttons whose capability is unavailable are disabled automatically.

## Architecture

PowerTUI flows detection -> capability -> dispatch -> TUI:

1. **Detection** — `platform_detect.py` parses `/etc/os-release` (fallbacks `/usr/lib/os-release`, `/etc/lsb-release`) into a `DistroInfo` (id, name, version, `id_like`, family, package manager, init system, privilege tool). `classify_family` maps the distro id/`ID_LIKE` into a family case-insensitively.
2. **Capability** — `capabilities.py` probes 12 subsystem keys once and returns a `Capability(supported, backend, reason, hint, meta)` for each: `cpu_online`, `turbo`, `epp`, `power_profile`, `gpu_switch`, `nvidia_power`, `amd_gpu`, `amd_power`, `asus_platform`, `fan_control`, `battery`, `cleanup`. Hardware presence comes from PCI vendor IDs (NVIDIA `0x10de`, AMD `0x1002`) and `/proc/cpuinfo` (`AuthenticAMD`). `DISTRO_RULES` holds per-family preference orders built from shared constants.
3. **Dispatch** — `sys_controller.py` (`SystemController`, `CPUCore`) reads and writes sysfs and shells out to whichever backend was detected. All privileged writes funnel through `_write_file_or_sudo`, which skips no-op writes and escalates via `sudo -n`/`doas`/`pkexec` under a 3-second timeout.
4. **TUI** — `app.py` (Textual) renders the dashboard and maps buttons to capabilities via `BUTTON_CAPABILITY`; unsupported buttons are disabled. A 1-second timer refreshes the core dashboard and extended telemetry refreshes roughly every 5 seconds.

## Testing

49 hermetic `unittest` tests run against temporary-directory mocks — they never touch the real `/proc`, `/sys` or `nvidia-smi`, and need no root:

```bash
python3 -m unittest discover -p "test_*.py"
```

- `test_topology.py` — CPU discovery/classification, single-thread high-frequency P-core heuristic, topology caching.
- `test_platform_detect.py` — os-release parsing, family classification, package-manager/init/privilege detection.
- `test_capabilities.py` — backend selection and unsupported/hint behaviour across all 12 capability keys, `map_epp`, and hardening regressions (generic ACPI platform profile, unwritable `thinkfan`, malformed vendor lines).

## Honest Limitations

- **Intel iGPU** is unsupported: there is no control backend.
- **AMD GPU** control is DPM performance level only — no power cap, power monitoring, clock/voltage or fan control.
- **LACT** and **CoreCtrl** are detected and reported, never driven; **TuxClocker** is unsupported.
- **TLP** is detected but has no runtime profile switching (configure `/etc/tlp.conf`).
- **thinkfan** is read-only/config-only and reported unsupported.
- **Battery** is telemetry-only; there is no charge-threshold control.
- The app runs **elevated**; a narrow polkit helper is the recommended future hardening.
- `nvidia_power` needs `nvidia-smi` present *and* a live probe; `gpu_switch` needs an NVIDIA GPU.
- There is no automatic package installation; missing tools produce a hint only.

## Extending

To add a device or backend:

1. Add a probe in `capabilities.py` (return a `Capability`; include a reason and, when applicable, an install hint) and register it in `_probe_all`.
2. If the tool availability depends on the distribution, add or adjust a `DISTRO_RULES` entry using the shared order constants.
3. Add a dispatch branch in `sys_controller.py` for the new backend, routing privileged writes through `_write_file_or_sudo`.
4. Gate any new UI action by adding the capability key to `BUTTON_CAPABILITY` in `app.py`.

## License

[MIT](LICENSE) © 2026 X3C12

