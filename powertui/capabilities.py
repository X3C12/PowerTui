"""Capability probing for PowerTUI.

Each Linux subsystem PowerTUI can touch (CPU topology, Turbo Boost, EPP,
power profiles, GPU switching, battery telemetry, background cleanup) is
probed once and described by a :class:`Capability`. The controller then
dispatches on the detected backend or reports that the action is not
supported on the current distribution, including an install hint.

The design is data-driven: distribution preferences and package names live
in the tables below so new distros/tools can be added without touching logic.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .platform_detect import DistroInfo, detect_distro

# Backend preference order (first available tool wins), shared to avoid repeating
# identical lists per family.
PP_DEFAULT = ["powerprofilesctl", "tuned-adm", "tlp", "cpupower"]
PP_TUNED_FIRST = ["tuned-adm", "powerprofilesctl", "cpupower"]
PP_NO_TLP = ["powerprofilesctl", "tuned-adm", "cpupower"]
PP_NO_TUNED = ["powerprofilesctl", "tlp", "cpupower"]
PP_MINIMAL = ["powerprofilesctl", "cpupower"]
GPU_DEFAULT = ["supergfxctl", "envycontrol", "optimus-manager", "prime-select", "system76-power"]
GPU_NO_S76 = ["supergfxctl", "envycontrol", "optimus-manager", "prime-select"]
GPU_CORE = ["supergfxctl", "envycontrol", "optimus-manager"]
GPU_BASIC = ["supergfxctl", "envycontrol"]

# Families absent from DISTRO_RULES use these defaults.
DEFAULT_POWER_PROFILE_ORDER = PP_DEFAULT
DEFAULT_GPU_ORDER = GPU_DEFAULT

# Per-family overrides, only where the order differs from the defaults.
DISTRO_RULES: Dict[str, Dict[str, List[str]]] = {
    "rhel": {"power_profile": PP_TUNED_FIRST, "gpu_switch": GPU_NO_S76},
    "arch": {"power_profile": PP_NO_TUNED},
    "debian": {"power_profile": PP_NO_TUNED},
    "gentoo": {"power_profile": PP_MINIMAL},
    "void": {"power_profile": PP_MINIMAL},
    "suse": {"power_profile": PP_NO_TLP, "gpu_switch": GPU_CORE},
    "nixos": {"power_profile": PP_NO_TLP},
    "alpine": {"power_profile": PP_MINIMAL, "gpu_switch": GPU_BASIC},
}

# Install command templates keyed by the detected package manager.
INSTALL_TEMPLATES: Dict[str, str] = {
    "apt": "apt install {pkg}",
    "dnf": "dnf install {pkg}",
    "pacman": "pacman -S {pkg}",
    "zypper": "zypper install {pkg}",
    "apk": "apk add {pkg}",
}

# Package name per backend (only backends that actually emit an install hint).
BACKEND_PACKAGES: Dict[str, Dict[str, str]] = {
    "powerprofilesctl": {
        "apt": "power-profiles-daemon", "dnf": "power-profiles-daemon",
        "pacman": "power-profiles-daemon", "zypper": "power-profiles-daemon",
        "apk": "power-profiles-daemon",
    },
    "supergfxctl": {"apt": "supergfxctl", "dnf": "supergfxctl", "pacman": "supergfxctl"},
    "docker": {"apt": "docker.io", "dnf": "docker", "pacman": "docker", "zypper": "docker"},
    "asusctl": {"apt": "asusctl", "dnf": "asusctl", "pacman": "asusctl"},
    "ryzenadj": {"apt": "ryzenadj", "dnf": "ryzenadj", "pacman": "ryzenadj", "zypper": "ryzenadj"},
    "nvidia-smi": {"apt": "nvidia-driver", "dnf": "akmod-nvidia", "pacman": "nvidia", "zypper": "nvidia-video-G06"},
}

# Vendor / device IDs used for hardware presence probing.
NVIDIA_VENDOR_IDS = ("0x10de", "10de")
AMD_VENDOR_IDS = ("0x1002", "1002")



def install_hint(pkg_manager: str, backend: str, privilege_tool: str = "sudo") -> str:
    """Build a package-manager specific installation hint, or an empty string."""
    template = INSTALL_TEMPLATES.get(pkg_manager)
    package = BACKEND_PACKAGES.get(backend, {}).get(pkg_manager)
    if not template or not package:
        return ""
    command = template.format(pkg=package)
    if privilege_tool in ("sudo", "doas", "pkexec"):
        return f"{privilege_tool} {command}"
    return command


KNOWN_EPP_VALUES = ("power", "balance_power", "balance_performance", "performance", "default")


def map_epp(logical: str, allowed: List[str]) -> Optional[str]:
    """Map a logical EPP request onto a value the CPU actually advertises.

    Returns ``None`` for an unrecognised logical value so callers never write a
    bogus string into sysfs.
    """
    if logical not in KNOWN_EPP_VALUES:
        return None
    if not allowed:
        return logical
    if logical in allowed:
        return logical
    fallbacks = {
        "power": ["power", "balance_power", "powersave", "balance_performance"],
        "balance_performance": ["balance_performance", "balance_power", "performance", "power"],
        "performance": ["performance", "balance_performance", "balance_power"],
    }
    for candidate in fallbacks.get(logical, []):
        if candidate in allowed:
            return candidate
    # Never return "default" unless it is the only option left.
    real = [v for v in allowed if v != "default"]
    return real[0] if real else "default"


@dataclass
class Capability:
    key: str
    supported: bool
    backend: str = "none"
    reason: str = ""
    hint: str = ""
    meta: Dict[str, object] = field(default_factory=dict)

    def line(self) -> str:
        if self.supported:
            return f"[OK]   {self.key:<16} via {self.backend}"
        detail = self.reason or "not supported"
        if self.hint:
            detail = f"{detail} | try: {self.hint}"
        return f"[--]   {self.key:<16} {detail}"


def _read_list(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read().split()
    except OSError:
        return []


def _first_available(order: List[str], which: Callable[[str], Optional[str]]) -> Optional[str]:
    for tool in order:
        if which(tool):
            return tool
    return None


class Capabilities:
    """Probe the host once and expose every subsystem PowerTUI may control."""

    def __init__(
        self,
        distro: Optional[DistroInfo] = None,
        sys_cpu_dir: str = "/sys/devices/system/cpu",
        power_supply_dir: str = "/sys/class/power_supply",
        pci_dir: str = "/sys/bus/pci/devices",
        drm_dir: str = "/sys/class/drm",
        cpuinfo_path: str = "/proc/cpuinfo",
        acpi_profile_path: str = "/sys/firmware/acpi/platform_profile",
        acpi_profile_choices_path: str = "/sys/firmware/acpi/platform_profile_choices",
        which: Callable[[str], Optional[str]] = shutil.which,
        is_root: Optional[bool] = None,
    ):
        self.distro = distro or detect_distro(which=which)
        self.sys_cpu_dir = sys_cpu_dir
        self.power_supply_dir = power_supply_dir
        self.pci_dir = pci_dir
        self.drm_dir = drm_dir
        self.cpuinfo_path = cpuinfo_path
        self.acpi_profile_path = acpi_profile_path
        self.acpi_profile_choices_path = acpi_profile_choices_path
        self._which = which
        self.is_root = (os.geteuid() == 0) if is_root is None else is_root
        self.caps: Dict[str, Capability] = {}
        self._probe_all()

    # -- public helpers -------------------------------------------------
    def get(self, key: str) -> Capability:
        return self.caps.get(key, Capability(key, False, reason="unknown capability"))

    def supported(self, key: str) -> bool:
        return self.get(key).supported

    # -- probing --------------------------------------------------------
    def _probe_all(self) -> None:
        self.caps["cpu_online"] = self._probe_cpu_online()
        self.caps["turbo"] = self._probe_turbo()
        self.caps["epp"] = self._probe_epp()
        self.caps["power_profile"] = self._probe_power_profile()
        self.caps["gpu_switch"] = self._probe_gpu_switch()
        self.caps["nvidia_power"] = self._probe_nvidia_power()
        self.caps["amd_gpu"] = self._probe_amd_gpu()
        self.caps["amd_power"] = self._probe_amd_power()
        self.caps["asus_platform"] = self._probe_asus_platform()
        self.caps["fan_control"] = self._probe_fan_control()
        self.caps["battery"] = self._probe_battery()
        self.caps["cleanup"] = self._probe_cleanup()

    def _probe_cpu_online(self) -> Capability:
        probe = os.path.join(self.sys_cpu_dir, "cpu1", "online")
        if not os.path.exists(probe):
            return Capability("cpu_online", False, reason="sysfs CPU hotplug interface not exposed")
        if self.is_root or self.distro.privilege_tool != "none":
            return Capability("cpu_online", True, backend="sysfs", meta={"path": self.sys_cpu_dir})
        return Capability("cpu_online", False, reason="requires root and no sudo/doas/pkexec found")

    def _probe_turbo(self) -> Capability:
        intel = os.path.join(self.sys_cpu_dir, "intel_pstate", "no_turbo")
        generic = os.path.join(self.sys_cpu_dir, "cpufreq", "boost")
        if os.path.exists(intel):
            return Capability("turbo", True, backend="intel_pstate",
                              meta={"path": intel, "on": "0", "off": "1"})
        if os.path.exists(generic):
            return Capability("turbo", True, backend="cpufreq_boost",
                              meta={"path": generic, "on": "1", "off": "0"})
        return Capability("turbo", False,
                          reason="no intel_pstate/no_turbo or cpufreq/boost interface found")

    def _probe_epp(self) -> Capability:
        epp = os.path.join(self.sys_cpu_dir, "cpu0", "cpufreq", "energy_performance_preference")
        if not os.path.exists(epp):
            return Capability("epp", False, reason="CPU EPP sysfs interface not present")
        allowed = _read_list(os.path.join(self.sys_cpu_dir, "cpu0", "cpufreq",
                                          "energy_performance_available_preferences"))
        driver = ""
        try:
            with open(os.path.join(self.sys_cpu_dir, "cpu0", "cpufreq", "scaling_driver"), "r") as handle:
                driver = handle.read().strip()
        except OSError:
            pass
        return Capability("epp", True, backend=driver or "cpufreq", meta={"allowed": allowed})

    def _probe_power_profile(self) -> Capability:
        family = self.distro.family
        order = DISTRO_RULES.get(family, {}).get("power_profile", DEFAULT_POWER_PROFILE_ORDER)
        tool = _first_available(order, self._which)
        if tool is None:
            hint = install_hint(self.distro.package_manager, "powerprofilesctl", self.distro.privilege_tool)
            return Capability("power_profile", False,
                              reason="no power-profiles-daemon / tuned / cpupower found", hint=hint)
        if tool == "tlp":
            return Capability("power_profile", False, backend="tlp",
                              reason="TLP has no runtime profile switching (configure /etc/tlp.conf)")
        return Capability("power_profile", True, backend=tool)

    def _pci_devices_with_vendor(self, vendor_ids) -> List[str]:
        found = []
        if not os.path.isdir(self.pci_dir):
            return found
        for entry in sorted(os.listdir(self.pci_dir)):
            vendor_path = os.path.join(self.pci_dir, entry, "vendor")
            try:
                with open(vendor_path, "r") as handle:
                    if handle.read().strip().lower() in vendor_ids:
                        found.append(os.path.join(self.pci_dir, entry))
            except OSError:
                continue
        return found

    def _nvidia_present(self) -> bool:
        return bool(self._pci_devices_with_vendor(NVIDIA_VENDOR_IDS))

    def _amd_gpu_present(self) -> bool:
        return bool(self._pci_devices_with_vendor(AMD_VENDOR_IDS))

    def _cpu_vendor(self) -> str:
        try:
            with open(self.cpuinfo_path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.lower().startswith("vendor_id"):
                        parts = line.split(":", 1)
                        return parts[1].strip() if len(parts) == 2 else ""
                    if line.strip() == "":
                        break
        except OSError:
            pass
        return ""

    def _nvidia_smi_present(self) -> bool:
        """True only when nvidia-smi exists AND actually talks to a GPU."""
        path = self._which("nvidia-smi")
        if not path or not os.path.exists(path):
            return False
        try:
            res = subprocess.run(
                [path, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=4)
            return res.returncode == 0 and bool(res.stdout.strip())
        except Exception:
            return False

    def _amd_gpu_perflevel_path(self) -> Optional[str]:
        """Locate the amdgpu power_dpm_force_performance_level sysfs file."""
        for device in self._pci_devices_with_vendor(AMD_VENDOR_IDS):
            candidate = os.path.join(device, "power_dpm_force_performance_level")
            if os.path.exists(candidate):
                return candidate
        # Fallback: search DRM card devices.
        if os.path.isdir(self.drm_dir):
            for entry in sorted(os.listdir(self.drm_dir)):
                candidate = os.path.join(self.drm_dir, entry, "device",
                                         "power_dpm_force_performance_level")
                if os.path.exists(candidate):
                    return candidate
        return None

    def _probe_gpu_switch(self) -> Capability:
        if not self._nvidia_present():
            return Capability("gpu_switch", False, reason="no NVIDIA GPU detected")
        family = self.distro.family
        order = DISTRO_RULES.get(family, {}).get("gpu_switch", DEFAULT_GPU_ORDER)
        tool = _first_available(order, self._which)
        if tool is None:
            hint = install_hint(self.distro.package_manager, "supergfxctl", self.distro.privilege_tool)
            return Capability("gpu_switch", False,
                              reason="NVIDIA present but no switching tool found", hint=hint)
        return Capability("gpu_switch", True, backend=tool)

    def _probe_nvidia_power(self) -> Capability:
        if not self._nvidia_present():
            return Capability("nvidia_power", False, reason="no NVIDIA GPU detected")
        if not self._nvidia_smi_present():
            hint = install_hint(self.distro.package_manager, "nvidia-smi", self.distro.privilege_tool)
            return Capability("nvidia_power", False,
                              reason="nvidia-smi missing or not talking to a GPU", hint=hint)
        return Capability("nvidia_power", True, backend="nvidia-smi")

    def _probe_amd_gpu(self) -> Capability:
        if not self._amd_gpu_present():
            return Capability("amd_gpu", False, reason="no AMD GPU detected")
        path = self._amd_gpu_perflevel_path()
        if path is None:
            return Capability("amd_gpu", False,
                              reason="AMD GPU present but no amdgpu power_dpm interface")
        # Control is always exercised through amdgpu sysfs; LACT/CoreCtrl are
        # only reported for the operator's awareness (no stable CLI is driven).
        tools = [t for t in ("lact", "corectrl") if self._which(t)]
        reason = f"controls DPM performance level (auto/low/high); detected: {', '.join(tools)}" if tools else \
            "controls DPM performance level (auto/low/high)"
        return Capability("amd_gpu", True, backend="amdgpu_sysfs",
                          meta={"path": path, "tools": tools}, reason=reason)

    def _probe_amd_power(self) -> Capability:
        if "AuthenticAMD" not in self._cpu_vendor():
            return Capability("amd_power", False, reason="no AMD CPU detected")
        if not self._which("ryzenadj"):
            hint = install_hint(self.distro.package_manager, "ryzenadj", self.distro.privilege_tool)
            return Capability("amd_power", False, reason="AMD CPU but ryzenadj not found", hint=hint)
        return Capability("amd_power", True, backend="ryzenadj")

    def _probe_asus_platform(self) -> Capability:
        # Generic ACPI platform profile (kernel >= 5.18) works on many laptops,
        # not just ASUS. Prefer it; fall back to asusctl.
        if os.path.exists(self.acpi_profile_path):
            choices = _read_list(self.acpi_profile_choices_path)
            return Capability("asus_platform", True, backend="platform_profile_sysfs",
                              meta={"path": self.acpi_profile_path, "choices": choices})
        if self._which("asusctl"):
            return Capability("asus_platform", True, backend="asusctl")
        hint = install_hint(self.distro.package_manager, "asusctl", self.distro.privilege_tool)
        return Capability("asus_platform", False,
                          reason="no ACPI platform_profile and asusctl not found", hint=hint)

    def _probe_fan_control(self) -> Capability:
        # Only nbfc exposes a usable runtime write path. thinkfan is config-only,
        # so it is NOT advertised as supported (its write path returns an error).
        if self._which("nbfc"):
            return Capability("fan_control", True, backend="nbfc")
        if self._which("asusctl"):
            return Capability("fan_control", True, backend="asusctl")
        if self._which("thinkfan"):
            return Capability("fan_control", False, backend="thinkfan",
                              reason="thinkfan is read-only (configure /etc/thinkfan.conf)")
        return Capability("fan_control", False, reason="no nbfc / asusctl found")

    def _probe_battery(self) -> Capability:
        if not os.path.isdir(self.power_supply_dir):
            return Capability("battery", False, reason="no /sys/class/power_supply")
        batteries = []
        mains_name = None
        for entry in sorted(os.listdir(self.power_supply_dir)):
            base = os.path.join(self.power_supply_dir, entry)
            try:
                with open(os.path.join(base, "type"), "r") as handle:
                    kind = handle.read().strip().lower()
            except OSError:
                continue
            if kind == "battery":
                batteries.append({
                    "name": entry,
                    "power_now": os.path.exists(os.path.join(base, "power_now")),
                    "current_voltage": os.path.exists(os.path.join(base, "current_now"))
                    and os.path.exists(os.path.join(base, "voltage_now")),
                    "energy_now": os.path.exists(os.path.join(base, "energy_now")),
                    "charge_now": os.path.exists(os.path.join(base, "charge_now")),
                    "capacity": os.path.exists(os.path.join(base, "capacity")),
                })
            elif kind == "mains":
                mains_name = entry
        if not batteries:
            return Capability("battery", False, reason="no battery device found (desktop?)")
        return Capability("battery", True, backend="sysfs_power_supply",
                          meta={"batteries": batteries, "mains": mains_name})

    def _probe_cleanup(self) -> Capability:
        container = _first_available(["docker", "podman"], self._which)
        supports_systemd = self.distro.init_system == "systemd"
        if container is None and not supports_systemd:
            return Capability("cleanup", False, reason="no docker/podman and non-systemd init")
        if container is None:
            hint = install_hint(self.distro.package_manager, "docker", self.distro.privilege_tool)
            return Capability("cleanup", True, backend="systemd",
                              meta={"container": None, "systemd": True}, hint=hint)
        return Capability("cleanup", True, backend=container,
                          meta={"container": container, "systemd": supports_systemd})

    # -- reporting ------------------------------------------------------
    def report_lines(self) -> List[str]:
        lines = ["PowerTUI platform diagnostics", "=" * 32]
        lines.extend(self.distro.as_lines())
        lines.append(f"Privilege now: {'root' if self.is_root else 'user'}")
        lines.append("")
        lines.append("Capabilities:")
        for cap in self.caps.values():
            lines.append("  " + cap.line())
        return lines

    def report_text(self) -> str:
        return "\n".join(self.report_lines())
