import os
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from .capabilities import Capabilities


@dataclass
class CPUCore:
    core_id: int
    logical_cpus: List[int] = field(default_factory=list)
    sys_cpu_dir: str = "/sys/devices/system/cpu"

    @property
    def is_online(self) -> bool:
        """Returns True if any logical thread of this core is online."""
        for cpu in self.logical_cpus:
            path = os.path.join(self.sys_cpu_dir, f"cpu{cpu}", "online")
            if not os.path.exists(path):
                # CPU 0 is boot CPU and never has online file, always online
                if cpu == 0:
                    return True
                continue
            try:
                with open(path, "r") as f:
                    if f.read().strip() == "1":
                        return True
            except Exception:
                pass
        return False


# Logical GPU mode -> per-backend CLI argument.
GPU_MODE_MAP: Dict[str, Dict[str, str]] = {
    "supergfxctl": {"Hybrid": "Hybrid", "Integrated": "Integrated"},
    "envycontrol": {"Hybrid": "hybrid", "Integrated": "integrated"},
    "optimus-manager": {"Hybrid": "hybrid", "Integrated": "integrated"},
    "prime-select": {"Hybrid": "on-demand", "Integrated": "intel"},
    "system76-power": {"Hybrid": "hybrid", "Integrated": "integrated"},
}

# Logical power profile -> per-backend value.
PROFILE_MAP: Dict[str, Dict[str, str]] = {
    "powerprofilesctl": {"power-saver": "power-saver", "balanced": "balanced", "performance": "performance"},
    "tuned-adm": {"power-saver": "powersave", "balanced": "balanced", "performance": "throughput-performance"},
    "cpupower": {"power-saver": "powersave", "balanced": "schedutil", "performance": "performance"},
}


def _read_float(path: str, default: float = 0.0) -> float:
    try:
        with open(path, "r") as f:
            return float(f.read().strip())
    except Exception:
        return default


def _read_str(path: str, default: str = "") -> str:
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return default


class SystemController:
    def __init__(self, sys_cpu_dir: str = "/sys/devices/system/cpu",
                 capabilities: Optional[Capabilities] = None):
        self.sys_cpu_dir = sys_cpu_dir
        self.caps = capabilities or Capabilities(sys_cpu_dir=sys_cpu_dir)
        self.p_cores: List[CPUCore] = []
        self.e_cores: List[CPUCore] = []
        self.refresh_topology()

    # ------------------------------------------------------------------
    # CPU topology
    # ------------------------------------------------------------------
    def refresh_topology(self) -> None:
        """Parse Linux sysfs CPU topology. Caches results to prevent losing offline cores."""
        if self.p_cores or self.e_cores:
            return  # Hardware topology does not physically change; rely on cached core lists.

        self.p_cores.clear()
        self.e_cores.clear()
        core_map: Dict[int, List[int]] = {}

        if not os.path.exists(self.sys_cpu_dir):
            return

        # Enumerate all cpuX directories
        for entry in os.listdir(self.sys_cpu_dir):
            if not entry.startswith("cpu") or not entry[3:].isdigit():
                continue
            cpu_id = int(entry[3:])
            online_path = os.path.join(self.sys_cpu_dir, entry, "online")

            # If the core is currently offline (e.g. TUI started in Max Battery mode),
            # its topology sysfs directory is missing. We briefly wake it up to map it.
            was_offline = False
            if os.path.exists(online_path):
                try:
                    with open(online_path, "r") as f:
                        if f.read().strip() == "0":
                            was_offline = True
                            self._write_file_or_sudo(online_path, "1", ignore_err=True,
                                                     escalate=self.caps.is_root)
                except Exception:
                    pass

            topo_path = os.path.join(self.sys_cpu_dir, entry, "topology", "core_id")
            if os.path.exists(topo_path):
                try:
                    with open(topo_path, "r") as f:
                        core_id = int(f.read().strip())
                    core_map.setdefault(core_id, []).append(cpu_id)
                except Exception:
                    pass
            elif cpu_id == 0:
                core_map.setdefault(0, []).append(0)

            # Return the core to its offline state immediately
            if was_offline:
                self._write_file_or_sudo(online_path, "0", ignore_err=True,
                                         escalate=self.caps.is_root)

        # Sort logical CPU IDs inside each core and classify cores
        sorted_cores = sorted(core_map.items(), key=lambda item: min(item[1]) if item[1] else 0)

        for core_id, cpus in sorted_cores:
            cpus.sort()
            is_p_core = (len(cpus) > 1)
            if len(cpus) == 1:
                freq_path = os.path.join(self.sys_cpu_dir, f"cpu{cpus[0]}", "cpufreq", "cpuinfo_max_freq")
                if os.path.exists(freq_path):
                    try:
                        with open(freq_path, "r") as f:
                            freq = int(f.read().strip())
                        if freq > 4000000:
                            is_p_core = True
                    except Exception:
                        pass

            if is_p_core:
                self.p_cores.append(CPUCore(core_id, cpus, sys_cpu_dir=self.sys_cpu_dir))
            else:
                self.e_cores.append(CPUCore(core_id, cpus, sys_cpu_dir=self.sys_cpu_dir))

    def get_online_counts(self) -> Tuple[int, int]:
        """Return tuple of (online P-cores, online E-cores)."""
        active_p = sum(1 for c in self.p_cores if c.is_online)
        active_e = sum(1 for c in self.e_cores if c.is_online)
        return active_p, active_e

    def set_active_cores(self, target_p: int, target_e: int) -> Tuple[bool, str]:
        """Dynamically online/offline cores to match desired target counts."""
        cap = self.caps.get("cpu_online")
        if not cap.supported:
            return False, f"CPU core control unavailable: {cap.reason}"

        target_p = max(1, min(len(self.p_cores), target_p))
        target_e = max(0, min(len(self.e_cores), target_e))
        errors = []

        # Configure P-cores
        for idx, core in enumerate(self.p_cores):
            should_be_online = (idx < target_p)
            for cpu in core.logical_cpus:
                if cpu == 0:
                    continue  # Cannot toggle boot CPU
                self._set_cpu_online(cpu, should_be_online, errors)

        # Configure E-cores
        for idx, core in enumerate(self.e_cores):
            should_be_online = (idx < target_e)
            for cpu in core.logical_cpus:
                self._set_cpu_online(cpu, should_be_online, errors)

        if errors:
            return False, f"Failed to toggle some CPUs (ensure root): {errors[0]}"
        return True, f"CPU core configuration applied: {target_p} P-cores + {target_e} E-cores active."

    def _set_cpu_online(self, cpu: int, online: bool, errors: List[str]) -> None:
        path = os.path.join(self.sys_cpu_dir, f"cpu{cpu}", "online")
        val_str = "1" if online else "0"
        self._write_file_or_sudo(path, val_str, errors=errors, tag=f"cpu{cpu}")

    def _write_file_or_sudo(self, path: str, value: str, errors: Optional[List[str]] = None,
                            tag: str = "", ignore_err: bool = False, escalate: bool = True) -> bool:
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r") as f:
                if f.read().strip() == value.strip():
                    return True
        except Exception:
            pass
        try:
            with open(path, "w") as f:
                f.write(value)
            return True
        except PermissionError:
            if not escalate:
                if not ignore_err and errors is not None:
                    errors.append(f"{tag or path}: permission denied")
                return False
            tool = self.caps.distro.privilege_tool
            cmd = None
            if tool == "sudo":
                cmd = ["sudo", "-n", "tee", path]
            elif tool == "doas":
                cmd = ["doas", "tee", path]
            elif tool == "pkexec":
                cmd = ["pkexec", "tee", path]
            if cmd is None:
                if not ignore_err and errors is not None:
                    errors.append(f"{tag or path}: permission denied, no privilege tool available")
                return False
            try:
                # Never block the UI on an interactive password/polkit prompt.
                res = subprocess.run(cmd, input=value.encode(), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, timeout=3)
            except subprocess.TimeoutExpired:
                if not ignore_err and errors is not None:
                    errors.append(f"{tag or path}: privilege prompt timed out")
                return False
            if res.returncode != 0 and not ignore_err and errors is not None:
                errors.append(f"{tag or path}: {res.stderr.decode().strip() or 'Permission denied'}")
            return res.returncode == 0
        except Exception as e:
            if not ignore_err and errors is not None:
                errors.append(f"{tag or path}: {str(e)}")
            return False

    # ------------------------------------------------------------------
    # Battery telemetry
    # ------------------------------------------------------------------
    def _battery_watts(self, base: str, info: Dict[str, bool]) -> float:
        if info.get("power_now"):
            return _read_float(os.path.join(base, "power_now")) / 1_000_000.0
        if info.get("current_voltage"):
            cur = _read_float(os.path.join(base, "current_now")) / 1_000_000.0
            vol = _read_float(os.path.join(base, "voltage_now")) / 1_000_000.0
            return cur * vol
        return 0.0

    def _battery_energy_wh(self, base: str, info: Dict[str, bool]) -> Optional[float]:
        if info.get("energy_now"):
            return _read_float(os.path.join(base, "energy_now")) / 1_000_000.0
        if info.get("charge_now"):
            charge_ah = _read_float(os.path.join(base, "charge_now")) / 1_000_000.0
            vol = _read_float(os.path.join(base, "voltage_now")) / 1_000_000.0
            if charge_ah and vol:
                return charge_ah * vol
        return None

    def get_battery_status(self) -> str:
        """Read live battery consumption in Watts and calculate approximate backup time."""
        cap = self.caps.get("battery")
        if not cap.supported:
            return f"N/A ({cap.reason})"

        batteries = cap.meta.get("batteries", [])
        total_watts = 0.0
        total_energy_wh = 0.0
        capacities = []
        have_energy = False

        for info in batteries:
            base = os.path.join(self.caps.power_supply_dir, info["name"])
            total_watts += self._battery_watts(base, info)
            if info.get("capacity"):
                capacities.append(_read_str(os.path.join(base, "capacity")))
            energy = self._battery_energy_wh(base, info)
            if energy is not None:
                total_energy_wh += energy
                have_energy = True

        cap_str = "/".join(c for c in capacities if c) + "%" if capacities else "?"
        if not cap_str or cap_str == "%":
            cap_str = "?"

        if not have_energy and capacities:
            # Fall back to a nominal 75 Wh pack scaled by state of charge.
            first = capacities[0]
            if first.isdigit():
                total_energy_wh = 75.0 * (int(first) / 100.0)
                have_energy = True

        if total_watts > 0.5 and have_energy and total_energy_wh > 0:
            est_hours = total_energy_wh / total_watts
            hrs = int(est_hours)
            mins = int((est_hours - hrs) * 60)
            return f"{total_watts:.2f} W (Cap: {cap_str} | Est. Runtime: ~{hrs}h {mins}m)"
        elif total_watts > 0:
            return f"{total_watts:.2f} W (Cap: {cap_str} | AC Powered / Ultra Idle)"
        return f"0.00 W (Cap: {cap_str} | AC / Fully Charged)"

    # ------------------------------------------------------------------
    # Turbo Boost + EPP
    # ------------------------------------------------------------------
    def set_turbo(self, enable: bool) -> Tuple[bool, str]:
        """Enable/disable CPU Turbo Boost using the detected backend."""
        cap = self.caps.get("turbo")
        if not cap.supported:
            return False, f"Turbo control unavailable: {cap.reason}"
        path = str(cap.meta.get("path", ""))
        value = str(cap.meta.get("on" if enable else "off", ""))
        ok = self._write_file_or_sudo(path, value)
        state = "ON" if enable else "OFF (base clock cap)"
        if ok:
            return True, f"Turbo Boost {state} via {cap.backend}"
        return False, f"Failed to set Turbo Boost via {cap.backend}"

    def apply_safe_powersave(self, enable: bool = True) -> Tuple[bool, str]:
        """Apply safe, stable battery saving adjustments without touching PCIe buses or SSD controllers."""
        actions = []

        # 1. Turbo Boost (safe and high-impact), backend-aware.
        ok_turbo, msg_turbo = self.set_turbo(not enable)
        actions.append(msg_turbo)

        # 2. CPU Energy Performance Preference (EPP), validated against advertised values.
        cap = self.caps.get("epp")
        if cap.supported:
            logical = "power" if enable else "balance_performance"
            from .capabilities import map_epp
            epp_mode = map_epp(logical, list(cap.meta.get("allowed", [])))
            if epp_mode is None:
                actions.append("EPP skipped (unrecognised value)")
            else:
                attempted = 0
                applied = 0
                for core in self.p_cores + self.e_cores:
                    for cpu in core.logical_cpus:
                        epp_path = f"{self.sys_cpu_dir}/cpu{cpu}/cpufreq/energy_performance_preference"
                        if os.path.exists(epp_path):
                            attempted += 1
                            if self._write_file_or_sudo(epp_path, epp_mode, ignore_err=True):
                                applied += 1
                suffix = "" if applied == attempted else " — need root for the rest"
                actions.append(f"CPU EPP Mode={epp_mode} ({applied}/{attempted} CPUs){suffix}")
        else:
            actions.append(f"EPP skipped ({cap.reason})")

        return ok_turbo, f"🛡️ Safe CPU Efficiency Applied: {' | '.join(actions)}"

    # ------------------------------------------------------------------
    # Power profiles
    # ------------------------------------------------------------------
    def get_power_profile(self) -> str:
        cap = self.caps.get("power_profile")
        if not cap.supported:
            return "Unsupported"
        try:
            if cap.backend == "powerprofilesctl":
                res = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            elif cap.backend == "tuned-adm":
                res = subprocess.run(["tuned-adm", "active"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            elif cap.backend == "cpupower":
                gov = _read_str(f"{self.sys_cpu_dir}/cpu0/cpufreq/scaling_governor")
                if gov:
                    return gov
        except Exception:
            pass
        return "Unknown"

    def set_power_profile(self, profile: str) -> Tuple[bool, str]:
        cap = self.caps.get("power_profile")
        if not cap.supported:
            msg = f"Power profile control unavailable: {cap.reason}"
            if cap.hint:
                msg += f" | try: {cap.hint}"
            return False, msg

        backend = cap.backend
        mapped = PROFILE_MAP.get(backend, {}).get(profile, profile)
        try:
            if backend == "powerprofilesctl":
                res = subprocess.run(["powerprofilesctl", "set", mapped], capture_output=True, text=True, timeout=3)
            elif backend == "tuned-adm":
                res = subprocess.run(["tuned-adm", "profile", mapped], capture_output=True, text=True, timeout=3)
            elif backend == "cpupower":
                res = subprocess.run(["cpupower", "frequency-set", "-g", mapped], capture_output=True, text=True, timeout=3)
            else:
                return False, f"Unsupported power profile backend: {backend}"
            if res.returncode == 0:
                return True, f"Power profile set to '{profile}' via {backend}"
            return False, f"Error ({backend}): {res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return False, f"Exception calling {backend}: {e}"

    # ------------------------------------------------------------------
    # GPU / graphics switching
    # ------------------------------------------------------------------
    def get_gpu_state(self) -> Dict[str, str]:
        state = {"mode": "Unknown", "power_status": "Unknown", "pci_status": "Unknown"}
        cap = self.caps.get("gpu_switch")

        # Runtime power status of the NVIDIA PCI function (backend independent).
        pci_dir = self.caps.pci_dir
        if os.path.isdir(pci_dir):
            for entry in os.listdir(pci_dir):
                vendor_path = os.path.join(pci_dir, entry, "vendor")
                if _read_str(vendor_path).lower() in ("0x10de", "10de"):
                    status = _read_str(os.path.join(pci_dir, entry, "power", "runtime_status"))
                    if status:
                        state["pci_status"] = status.upper()
                    break

        if not cap.supported:
            state["mode"] = "N/A"
            state["power_status"] = cap.reason
            return state

        backend = cap.backend
        try:
            if backend == "supergfxctl":
                out = subprocess.run(["supergfxctl", "--get"], capture_output=True, text=True, timeout=2)
                if out.returncode == 0 and out.stdout.strip():
                    state["mode"] = out.stdout.strip()
                st = subprocess.run(["supergfxctl", "--status"], capture_output=True, text=True, timeout=2)
                if st.returncode == 0 and st.stdout.strip():
                    state["power_status"] = st.stdout.strip()
            elif backend == "envycontrol":
                out = subprocess.run(["envycontrol", "--query"], capture_output=True, text=True, timeout=2)
                if out.returncode == 0 and out.stdout.strip():
                    state["mode"] = out.stdout.strip()
                    state["power_status"] = "query"
            elif backend == "optimus-manager":
                out = subprocess.run(["optimus-manager", "--status"], capture_output=True, text=True, timeout=2)
                if out.returncode == 0 and out.stdout.strip():
                    state["mode"] = out.stdout.strip().splitlines()[0]
                    state["power_status"] = "status"
            elif backend == "prime-select":
                out = subprocess.run(["prime-select", "query"], capture_output=True, text=True, timeout=2)
                if out.returncode == 0 and out.stdout.strip():
                    state["mode"] = out.stdout.strip()
                    state["power_status"] = "query"
            elif backend == "system76-power":
                out = subprocess.run(["system76-power", "graphics"], capture_output=True, text=True, timeout=2)
                if out.returncode == 0 and out.stdout.strip():
                    state["mode"] = out.stdout.strip()
                    state["power_status"] = "status"
        except Exception:
            pass
        return state

    def set_gpu_mode(self, mode: str) -> Tuple[bool, str]:
        """Set graphics mode safely via the detected switching backend."""
        cap = self.caps.get("gpu_switch")
        if not cap.supported:
            msg = f"GPU mode switching unavailable: {cap.reason}"
            if cap.hint:
                msg += f" | try: {cap.hint}"
            return False, msg

        backend = cap.backend
        mapped = GPU_MODE_MAP.get(backend, {}).get(mode)
        if backend == "prime-select" and mode == "Integrated":
            # prime-select wants the integrated GPU vendor: "intel" or "amd".
            mapped = "amd" if self.caps._amd_gpu_present() else "intel"
        if not mapped:
            return False, f"Mode '{mode}' not supported by backend {backend}"

        try:
            if backend == "supergfxctl":
                res = subprocess.run(["supergfxctl", "--mode", mapped], capture_output=True, text=True, timeout=5)
            elif backend == "envycontrol":
                res = subprocess.run(["envycontrol", "--switch", mapped], capture_output=True, text=True, timeout=5)
            elif backend == "optimus-manager":
                res = subprocess.run(["optimus-manager", "--switch", mapped], capture_output=True, text=True, timeout=5)
            elif backend == "prime-select":
                res = subprocess.run(["prime-select", mapped], capture_output=True, text=True, timeout=5)
            elif backend == "system76-power":
                res = subprocess.run(["system76-power", "graphics", mapped], capture_output=True, text=True, timeout=5)
            else:
                return False, f"Unsupported GPU backend: {backend}"

            out = res.stdout.strip()
            err = res.stderr.strip()
            if res.returncode == 0:
                msg = f"GPU set to '{mode}' via {backend}."
                if out and "logout" in out.lower():
                    msg += " (ℹ️ Note: Log out of your desktop session and back in for drivers to rebind cleanly.)"
                return True, msg
            return False, f"{backend} message: {err or out}"
        except Exception as e:
            return False, f"Failed to call {backend}: {e}"

    # ------------------------------------------------------------------
    # Background cleanup
    # ------------------------------------------------------------------
    def clean_background_tasks(self) -> Tuple[bool, str]:
        cap = self.caps.get("cleanup")
        if not cap.supported:
            return False, f"Background cleanup unavailable: {cap.reason}"

        stopped = []
        container = cap.meta.get("container")
        if container:
            try:
                res_ps = subprocess.run([container, "ps", "-q"], capture_output=True, text=True, timeout=5)
                if res_ps.returncode == 0 and res_ps.stdout.strip():
                    ids = res_ps.stdout.strip().split()
                    subprocess.run([container, "stop"] + ids, capture_output=True, timeout=20)
                    stopped.append(f"{len(ids)} {container} container(s)")
            except Exception:
                pass

        if cap.meta.get("systemd"):
            try:
                subprocess.run(["systemctl", "--user", "stop", "hermes-gateway.service", "hermes-agent.service"],
                               capture_output=True, timeout=5)
                subprocess.run(["pkill", "-f", "hermes_cli.main"], capture_output=True, timeout=5)
                stopped.append("background AI daemons")
            except Exception:
                pass

        if stopped:
            return True, f"Cleaned up: {', '.join(stopped)}."
        return True, "No running unnecessary background workloads detected."

    # ------------------------------------------------------------------
    # Extended hardware: GPU power, AMD CPU power, platform profiles, fans
    # ------------------------------------------------------------------
    def get_nvidia_power(self) -> str:
        cap = self.caps.get("nvidia_power")
        if not cap.supported:
            return f"N/A ({cap.reason})"
        try:
            res = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,power.draw,power.limit,power.min_limit,power.max_limit",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                return " | ".join(res.stdout.strip().splitlines())
        except Exception:
            pass
        return "Unknown"

    def get_nvidia_limits(self) -> Optional[Dict[str, float]]:
        cap = self.caps.get("nvidia_power")
        if not cap.supported:
            return None
        try:
            res = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=power.min_limit,power.max_limit",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                first = res.stdout.strip().splitlines()[0]
                minl, maxl = [float(x) for x in first.split(",")]
                return {"min": minl, "max": maxl}
        except Exception:
            pass
        return None

    def set_nvidia_power_limit(self, watts: int) -> Tuple[bool, str]:
        cap = self.caps.get("nvidia_power")
        if not cap.supported:
            return False, f"NVIDIA power control unavailable: {cap.reason}"
        try:
            res = subprocess.run(["nvidia-smi", "-pl", str(watts)],
                                 capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return True, f"NVIDIA power limit set to {watts} W"
            return False, f"nvidia-smi failed: {res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return False, f"Failed to run nvidia-smi: {e}"

    def get_amd_gpu_state(self) -> str:
        cap = self.caps.get("amd_gpu")
        if not cap.supported:
            return f"N/A ({cap.reason})"
        level = _read_str(str(cap.meta.get("path", "")), "unknown")
        tools = cap.meta.get("tools", [])
        suffix = f" (tools: {', '.join(tools)})" if tools else ""
        return f"perf-level={level}{suffix}"

    def set_amd_gpu_power(self, level: str) -> Tuple[bool, str]:
        """Set amdgpu power_dpm_force_performance_level (low|high|auto)."""
        cap = self.caps.get("amd_gpu")
        if not cap.supported:
            return False, f"AMD GPU control unavailable: {cap.reason}"
        if level not in ("low", "high", "auto"):
            return False, f"Invalid AMD GPU level '{level}' (expected low/high/auto)"
        path = str(cap.meta.get("path", ""))
        ok = self._write_file_or_sudo(path, level)
        if ok:
            return True, f"AMD GPU DPM performance level set to '{level}'"
        return False, "Failed to write amdgpu performance level (need root)"

    def get_amd_cpu_power(self) -> str:
        cap = self.caps.get("amd_power")
        if not cap.supported:
            return f"N/A ({cap.reason})"
        try:
            res = subprocess.run(["ryzenadj", "--info"], capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                wanted = ("stapm", "fast limit", "slow limit", "tctl")
                parts = []
                for line in res.stdout.splitlines():
                    low = line.lower()
                    if any(w in low for w in wanted):
                        cells = [c.strip() for c in line.split("|") if c.strip()]
                        parts.append(" ".join(cells))
                return "; ".join(parts) if parts else res.stdout.strip().splitlines()[-1]
        except Exception:
            pass
        return "Unknown"

    def set_amd_cpu_power(self, stapm_mw: int, fast_mw: int, slow_mw: int,
                          temp_c: Optional[int] = None) -> Tuple[bool, str]:
        """Set AMD Ryzen power limits (milliwatts) via ryzenadj."""
        cap = self.caps.get("amd_power")
        if not cap.supported:
            return False, f"AMD CPU power control unavailable: {cap.reason}"
        cmd = ["ryzenadj",
               f"--stapm-limit={stapm_mw}",
               f"--fast-limit={fast_mw}",
               f"--slow-limit={slow_mw}"]
        if temp_c is not None:
            cmd.append(f"--tctl-temp={temp_c}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if res.returncode == 0:
                return True, f"Ryzen limits applied: STAPM={stapm_mw}mW FAST={fast_mw}mW SLOW={slow_mw}mW"
            return False, f"ryzenadj failed: {res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return False, f"Failed to run ryzenadj: {e}"

    ASUS_PROFILE_MAP = {"quiet": "Quiet", "balanced": "Balanced", "performance": "Performance"}
    # ACPI platform_profile uses lowercase, space-separated tokens.
    ACPI_TOKEN_ALIASES = {
        "quiet": ("quiet", "low-power", "power-saver"),
        "performance": ("performance", "balanced-performance"),
        "balanced": ("balanced",),
    }

    def get_platform_profile(self) -> str:
        cap = self.caps.get("asus_platform")
        if not cap.supported:
            return "Unsupported"
        if cap.backend == "platform_profile_sysfs":
            return _read_str(str(cap.meta.get("path", self.caps.acpi_profile_path)), "Unknown") or "Unknown"
        try:
            res = subprocess.run(["asusctl", "profile", "-p"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip().splitlines()[-1]
        except Exception:
            pass
        return "Unknown"

    def _acpi_profile_token(self, profile: str, choices: List[str]) -> Optional[str]:
        for token in self.ACPI_TOKEN_ALIASES.get(profile, (profile,)):
            if not choices or token in choices:
                return token
        return None

    def set_platform_profile(self, profile: str) -> Tuple[bool, str]:
        cap = self.caps.get("asus_platform")
        if not cap.supported:
            msg = f"Platform profile unavailable: {cap.reason}"
            if cap.hint:
                msg += f" | try: {cap.hint}"
            return False, msg

        if cap.backend == "platform_profile_sysfs":
            path = str(cap.meta.get("path", self.caps.acpi_profile_path))
            choices = list(cap.meta.get("choices", []))
            token = self._acpi_profile_token(profile, choices)
            if token is None:
                return False, f"Profile '{profile}' not offered; available: {', '.join(choices) or 'unknown'}"
            ok = self._write_file_or_sudo(path, token)
            if ok:
                return True, f"Platform profile set to '{token}' (ACPI)"
            return False, "Failed to write ACPI platform_profile (need root)"

        mapped = self.ASUS_PROFILE_MAP.get(profile)
        if not mapped:
            return False, f"Invalid platform profile '{profile}'"
        try:
            res = subprocess.run(["asusctl", "profile", "-P", mapped],
                                 capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return True, f"ASUS platform profile set to '{mapped}'"
            return False, f"asusctl failed: {res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return False, f"Failed to call asusctl: {e}"

    def get_fan_status(self) -> str:
        cap = self.caps.get("fan_control")
        if not cap.supported:
            return f"N/A ({cap.reason})"
        backend = cap.backend
        try:
            if backend == "nbfc":
                res = subprocess.run(["nbfc", "status"], capture_output=True, text=True, timeout=4)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip().splitlines()[0]
            elif backend == "asusctl":
                res = subprocess.run(["asusctl", "fan-curve", "-g"], capture_output=True, text=True, timeout=4)
                if res.returncode == 0 and res.stdout.strip():
                    return "asusctl fan-curve active"
        except Exception:
            pass
        return f"{backend} managed"

    def set_fan_profile(self, profile: str) -> Tuple[bool, str]:
        cap = self.caps.get("fan_control")
        if not cap.supported:
            msg = f"Fan control unavailable: {cap.reason}"
            if cap.hint:
                msg += f" | try: {cap.hint}"
            return False, msg
        backend = cap.backend
        try:
            if backend == "nbfc":
                if profile in ("quiet", "power-saver"):
                    cmd = ["nbfc", "set", "-s", "30"]
                elif profile == "performance":
                    cmd = ["nbfc", "set", "-s", "80"]
                else:
                    cmd = ["nbfc", "set", "-a"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Fan profile '{profile}' applied via nbfc"
                return False, f"nbfc failed: {res.stderr.strip() or res.stdout.strip()}"
            if backend == "asusctl":
                return self.set_platform_profile(profile)
        except Exception as e:
            return False, f"Failed to set fan profile: {e}"

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    def reset_to_defaults(self) -> Tuple[bool, str]:
        msgs = []
        _, msg_safe = self.apply_safe_powersave(enable=False)
        msgs.append(msg_safe)

        if self.caps.supported("cpu_online"):
            _, msg_cpu = self.set_active_cores(len(self.p_cores), len(self.e_cores))
            msgs.append(msg_cpu)
        else:
            msgs.append("CPU cores unchanged (control unavailable)")

        _, msg_prof = self.set_power_profile("balanced")
        msgs.append(msg_prof)

        _, msg_gpu = self.set_gpu_mode("Hybrid")
        msgs.append(msg_gpu)

        if self.caps.supported("amd_gpu"):
            _, msg_amd = self.set_amd_gpu_power("auto")
            msgs.append(msg_amd)

        if self.caps.supported("asus_platform"):
            _, msg_prof2 = self.set_platform_profile("balanced")
            msgs.append(msg_prof2)

        if self.caps.supported("fan_control"):
            _, msg_fan = self.set_fan_profile("balanced")
            msgs.append(msg_fan)

        return True, " | ".join(msgs)
