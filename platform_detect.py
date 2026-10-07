"""Cross-distribution detection for PowerTUI.

Parses /etc/os-release (with fallbacks), classifies the distribution into a
family, and discovers the local package manager, init system and privilege
escalation tool. All functions are side-effect free and accept optional paths
so they can be unit-tested against a mocked filesystem.
"""

import os
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional

OS_RELEASE_CANDIDATES = [
    "/etc/os-release",
    "/usr/lib/os-release",
    "/etc/lsb-release",
]

FAMILY_MAP: Dict[str, str] = {
    # Debian family
    "debian": "debian",
    "ubuntu": "debian",
    "kali": "debian",
    "linuxmint": "debian",
    "pop": "debian",
    "raspbian": "debian",
    "devuan": "debian",
    "elementary": "debian",
    "zorin": "debian",
    "parrot": "debian",
    # Red Hat family
    "fedora": "rhel",
    "rhel": "rhel",
    "centos": "rhel",
    "rocky": "rhel",
    "alma": "rhel",
    "ol": "rhel",
    "oracle": "rhel",
    # Arch family
    "arch": "arch",
    "manjaro": "arch",
    "endeavouros": "arch",
    "garuda": "arch",
    "artix": "arch",
    "cachyos": "arch",
    # SUSE family
    "opensuse": "suse",
    "opensuse-leap": "suse",
    "opensuse-tumbleweed": "suse",
    "sles": "suse",
    "sled": "suse",
    # Others
    "alpine": "alpine",
    "gentoo": "gentoo",
    "void": "void",
    "nixos": "nixos",
    "solus": "solus",
}

# Ordered by preference; first match wins.
PKG_MANAGERS = [
    ("apt", "apt"),
    ("dnf", "dnf"),
    ("yum", "yum"),
    ("pacman", "pacman"),
    ("zypper", "zypper"),
    ("apk", "apk"),
    ("xbps-install", "xbps"),
    ("emerge", "portage"),
    ("eopkg", "eopkg"),
    ("nix", "nix"),
]

PRIVILEGE_TOOLS = ["sudo", "doas", "pkexec"]


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_os_release(text: str) -> Dict[str, str]:
    """Parse the key=value body of an os-release style file."""
    data: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip().upper()] = _unquote(value)
    return data


def read_os_release(paths: Optional[List[str]] = None) -> Dict[str, str]:
    """Read the first available os-release candidate file."""
    for path in paths or OS_RELEASE_CANDIDATES:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    parsed = parse_os_release(handle.read())
                if parsed:
                    return parsed
            except OSError:
                continue
    return {}


def classify_family(distro_id: str, id_like: List[str]) -> str:
    """Map a distro ID / ID_LIKE list onto a known family (case-insensitive)."""
    for candidate in [distro_id] + list(id_like):
        key = (candidate or "").lower()
        if key in FAMILY_MAP:
            return FAMILY_MAP[key]
    return "other"


def detect_package_manager(which=shutil.which) -> str:
    for command, label in PKG_MANAGERS:
        if which(command):
            return label
    return "unknown"


def detect_init_system(proc_comm_path: str = "/proc/1/comm") -> str:
    try:
        if os.path.exists(proc_comm_path):
            with open(proc_comm_path, "r", encoding="utf-8", errors="replace") as handle:
                name = handle.read().strip()
            if name:
                return name
    except OSError:
        pass
    return "unknown"


def detect_privilege_tool(which=shutil.which) -> str:
    for tool in PRIVILEGE_TOOLS:
        if which(tool):
            return tool
    return "none"


@dataclass
class DistroInfo:
    id: str = "unknown"
    name: str = "Unknown Linux"
    version: str = ""
    id_like: List[str] = field(default_factory=list)
    family: str = "other"
    package_manager: str = "unknown"
    init_system: str = "unknown"
    privilege_tool: str = "none"

    @property
    def display(self) -> str:
        base = self.name if not self.version else f"{self.name} {self.version}"
        return base

    def as_lines(self) -> List[str]:
        return [
            f"Distribution : {self.display} (id={self.id}, family={self.family})",
            f"ID_LIKE      : {', '.join(self.id_like) if self.id_like else '-'}",
            f"Package mgr  : {self.package_manager}",
            f"Init system  : {self.init_system}",
            f"Privilege    : {self.privilege_tool}",
        ]


def detect_distro(
    os_release_paths: Optional[List[str]] = None,
    which=shutil.which,
    proc_comm_path: str = "/proc/1/comm",
) -> DistroInfo:
    """Detect the current distribution and its environment capabilities."""
    data = read_os_release(os_release_paths)
    distro_id = (data.get("ID") or "unknown").lower()
    id_like = [part.lower() for part in (data.get("ID_LIKE") or "").split() if part]
    name = data.get("NAME") or data.get("ID") or "Unknown Linux"
    version = data.get("VERSION_ID") or data.get("VERSION") or ""

    return DistroInfo(
        id=distro_id,
        name=name,
        version=version,
        id_like=id_like,
        family=classify_family(distro_id, id_like),
        package_manager=detect_package_manager(which=which),
        init_system=detect_init_system(proc_comm_path=proc_comm_path),
        privilege_tool=detect_privilege_tool(which=which),
    )
