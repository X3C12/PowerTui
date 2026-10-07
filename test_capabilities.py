import os
import shutil
import tempfile
import unittest

from powertui.capabilities import Capabilities, Capability, install_hint, map_epp
from powertui.platform_detect import DistroInfo
from powertui.sys_controller import SystemController


def make_distro(package_manager="apt", init_system="systemd", family="debian"):
    return DistroInfo(
        id="test", name="Test", version="1", id_like=[], family=family,
        package_manager=package_manager, init_system=init_system, privilege_tool="sudo",
    )


class CapabilityTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cpu = os.path.join(self.tmp, "cpu")
        self.psu = os.path.join(self.tmp, "power_supply")
        self.pci = os.path.join(self.tmp, "pci")
        self.drm = os.path.join(self.tmp, "drm")
        self.cpuinfo = os.path.join(self.tmp, "cpuinfo")
        self._reset_env()

    def _reset_env(self):
        """Recreate the mocked sysfs tree; each table case starts clean."""
        for directory in (self.cpu, self.psu, self.pci, self.drm):
            shutil.rmtree(directory, ignore_errors=True)
            os.makedirs(directory)
        self.write(self.cpuinfo, "vendor_id\t: GenuineIntel\nmodel name\t: Test CPU\n\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, path, value):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(value)

    def read(self, path):
        with open(path, "r") as handle:
            return handle.read().strip()

    def controller(self, caps):
        """Build a SystemController bound to the mocked capability probe."""
        return SystemController(sys_cpu_dir=self.cpu, capabilities=caps)

    def build(self, which=None, is_root=True, family="debian"):
        return Capabilities(
            distro=make_distro(family=family),
            sys_cpu_dir=self.cpu,
            power_supply_dir=self.psu,
            pci_dir=self.pci,
            drm_dir=self.drm,
            cpuinfo_path=self.cpuinfo,
            acpi_profile_path=os.path.join(self.tmp, "acpi_profile"),
            acpi_profile_choices_path=os.path.join(self.tmp, "acpi_profile_choices"),
            which=which or (lambda c: None),
            is_root=is_root,
        )

    def add_nvidia(self):
        self.write(os.path.join(self.pci, "0000:01:00.0", "vendor"), "0x10de\n")

    def add_amd_gpu(self, with_perflevel=True):
        base = os.path.join(self.pci, "0000:03:00.0")
        self.write(os.path.join(base, "vendor"), "0x1002\n")
        if with_perflevel:
            self.write(os.path.join(base, "power_dpm_force_performance_level"), "auto\n")

    def set_amd_cpu(self):
        self.write(self.cpuinfo, "vendor_id\t: AuthenticAMD\nmodel name\t: Test Ryzen\n\n")

    def run_cases(self, cases):
        """Table-driven probe checker: one hermetic `which` stub per case.

        Each case dict has ``key`` + ``supported`` and optionally ``setup``
        (callable taking self), ``tools`` (exactly these binaries are
        "installed"), ``family``, ``backend``, ``hint``, ``reason`` and
        ``check`` (callable ``(self, caps, cap)``) for extra assertions.
        """
        bindir = os.path.join(self.tmp, "bin")
        os.makedirs(bindir, exist_ok=True)
        for case in cases:
            with self.subTest(case=case.get("label", case["key"])):
                self._reset_env()
                if case.get("setup"):
                    case["setup"](self)
                # ponytail: temp-dir stubs, so `which` never touches a real tool
                paths = {}
                for tool in set(case.get("tools", ())):
                    path = os.path.join(bindir, tool)
                    if not os.path.exists(path):
                        self.write(path, "#!/bin/sh\necho GPU\n")
                        os.chmod(path, 0o755)
                    paths[tool] = path
                caps = self.build(which=lambda c: paths.get(c), family=case.get("family", "debian"))
                cap = caps.get(case["key"])
                self.assertEqual(cap.supported, case["supported"], cap.reason)
                if "backend" in case:
                    self.assertEqual(cap.backend, case["backend"])
                if "hint" in case:
                    self.assertIn(case["hint"], cap.hint)
                if "reason" in case:
                    self.assertIn(case["reason"], cap.reason)
                if "check" in case:
                    case["check"](self, caps, cap)


class TestTurbo(CapabilityTestBase):
    CASES = [
        dict(label="test_intel_pstate_backend", key="turbo", supported=True, backend="intel_pstate",
             setup=lambda s: s.write(os.path.join(s.cpu, "intel_pstate", "no_turbo"), "0\n"),
             check=lambda s, c, cap: s.assertEqual(cap.meta["off"], "1")),
        dict(label="test_generic_cpufreq_boost_backend", key="turbo", supported=True, backend="cpufreq_boost",
             setup=lambda s: s.write(os.path.join(s.cpu, "cpufreq", "boost"), "1\n"),
             check=lambda s, c, cap: s.assertEqual(cap.meta["off"], "0")),
        dict(label="test_turbo_unsupported", key="turbo", supported=False),
        dict(label="test_intel_pstate_preferred_over_cpufreq_boost", key="turbo", supported=True,
             backend="intel_pstate", setup=lambda s: (
                 s.write(os.path.join(s.cpu, "intel_pstate", "no_turbo"), "0\n"),
                 s.write(os.path.join(s.cpu, "cpufreq", "boost"), "1\n"))),
    ]

    def test_turbo_probe(self):
        self.run_cases(self.CASES)

    def test_intel_pstate_on_off_values_and_writes(self):
        # intel_pstate/no_turbo is inverted: writing 0 ENABLES turbo, 1 disables.
        path = os.path.join(self.cpu, "intel_pstate", "no_turbo")
        self.write(path, "1\n")
        caps = self.build()
        cap = caps.get("turbo")
        self.assertTrue(cap.supported)
        self.assertEqual(cap.backend, "intel_pstate")
        self.assertEqual(cap.meta["on"], "0")
        self.assertEqual(cap.meta["off"], "1")

        controller = self.controller(caps)
        ok, _ = controller.set_turbo(True)
        self.assertTrue(ok)
        self.assertEqual(self.read(path), "0")
        ok, _ = controller.set_turbo(False)
        self.assertTrue(ok)
        self.assertEqual(self.read(path), "1")

    def test_cpufreq_boost_on_off_values_and_writes(self):
        # cpufreq/boost is direct: 1 enables turbo, 0 disables.
        path = os.path.join(self.cpu, "cpufreq", "boost")
        self.write(path, "0\n")
        caps = self.build()
        cap = caps.get("turbo")
        self.assertTrue(cap.supported)
        self.assertEqual(cap.backend, "cpufreq_boost")
        self.assertEqual(cap.meta["on"], "1")
        self.assertEqual(cap.meta["off"], "0")

        controller = self.controller(caps)
        ok, _ = controller.set_turbo(True)
        self.assertTrue(ok)
        self.assertEqual(self.read(path), "1")
        ok, _ = controller.set_turbo(False)
        self.assertTrue(ok)
        self.assertEqual(self.read(path), "0")


class TestEpp(CapabilityTestBase):
    def test_epp_available_and_values(self):
        self.write(os.path.join(self.cpu, "cpu0", "cpufreq", "energy_performance_preference"), "performance\n")
        self.write(os.path.join(self.cpu, "cpu0", "cpufreq",
                                "energy_performance_available_preferences"),
                   "default performance balance_performance power\n")
        self.write(os.path.join(self.cpu, "cpu0", "cpufreq", "scaling_driver"), "intel_pstate\n")
        caps = self.build()
        cap = caps.get("epp")
        self.assertTrue(cap.supported)
        self.assertEqual(cap.backend, "intel_pstate")

    # (logical, allowed, expected) — one row per former map_epp assertion.
    MAP_CASES = [
        # amd_fallback
        ("balance_performance", ["performance", "balance_power", "power"], "balance_power"),
        ("power", ["performance", "balance_power", "power"], "power"),
        ("balance_performance", [], "balance_performance"),
        # default_only_allowed_list
        ("power", ["default"], "default"),
        ("balance_performance", ["default"], "default"),
        ("performance", ["default"], "default"),
        # known_value_already_advertised
        ("performance", ["default", "performance", "power"], "performance"),
        ("power", ["default", "performance", "power"], "power"),
        # unknown_logical_value_is_rejected
        ("banana", [], None),
        ("banana", ["performance", "power", "balance_power"], None),
        ("banana", ["default", "power"], None),
        # known_logical_without_direct_match_uses_fallback
        ("performance", ["balance_power", "power"], "balance_power"),
        ("power", ["balance_performance"], "balance_performance"),
        # empty_allowed_returns_input_verbatim
        ("performance", [], "performance"),
        ("power", [], "power"),
    ]

    def test_map_epp(self):
        for logical, allowed, expected in self.MAP_CASES:
            with self.subTest(logical=logical, allowed=allowed):
                self.assertEqual(map_epp(logical, allowed), expected)

    def test_epp_cpufreq_backend_when_driver_file_missing(self):
        self.write(os.path.join(self.cpu, "cpu0", "cpufreq",
                                "energy_performance_preference"), "power\n")
        caps = self.build()
        cap = caps.get("epp")
        self.assertTrue(cap.supported)
        self.assertEqual(cap.backend, "cpufreq")


class TestPowerProfile(CapabilityTestBase):
    CASES = [
        dict(label="test_powerprofilesctl_selected", tools=("powerprofilesctl",), key="power_profile", supported=True, backend="powerprofilesctl"),
        dict(label="test_tuned_preferred_on_rhel", tools=("tuned-adm", "powerprofilesctl"), family="rhel", key="power_profile", supported=True, backend="tuned-adm"),
        dict(label="test_tlp_detected_but_unsupported", tools=("tlp",), key="power_profile", supported=False, backend="tlp"),
        dict(label="test_none_found_has_hint", key="power_profile", supported=False, hint="apt install"),
    ]

    def test_power_profile_probe(self):
        self.run_cases(self.CASES)


class TestGpu(CapabilityTestBase):
    CASES = [
        dict(label="test_supergfxctl_with_nvidia", setup=lambda s: s.add_nvidia(), tools=("supergfxctl",), key="gpu_switch", supported=True, backend="supergfxctl"),
        dict(label="test_no_nvidia_reports_unsupported", key="gpu_switch", supported=False, reason="NVIDIA"),
        dict(label="test_nvidia_without_tool_has_hint", setup=lambda s: s.add_nvidia(), key="gpu_switch", supported=False, hint="apt install"),
    ]

    def test_gpu_probe(self):
        self.run_cases(self.CASES)


class TestNvidiaPower(CapabilityTestBase):
    CASES = [
        dict(label="test_nvidia_smi_detected", setup=lambda s: s.add_nvidia(), tools=("nvidia-smi",), key="nvidia_power", supported=True, backend="nvidia-smi"),
        dict(label="test_nvidia_present_without_smi_has_hint", setup=lambda s: s.add_nvidia(), key="nvidia_power", supported=False, hint="apt install"),
    ]

    def test_nvidia_power_probe(self):
        self.run_cases(self.CASES)


class TestAmdGpu(CapabilityTestBase):
    CASES = [
        dict(label="test_amdgpu_sysfs_backend", setup=lambda s: s.add_amd_gpu(), key="amd_gpu", supported=True, backend="amdgpu_sysfs",
             check=lambda s, c, cap: s.assertIn("power_dpm_force_performance_level", cap.meta["path"])),
        # LACT/CoreCtrl are reported for awareness, but control is always sysfs.
        dict(label="test_lact_reported_but_control_stays_sysfs", setup=lambda s: s.add_amd_gpu(), tools=("lact",), key="amd_gpu", supported=True, backend="amdgpu_sysfs",
             check=lambda s, c, cap: (s.assertEqual(cap.meta["tools"], ["lact"]), s.assertIn("lact", cap.reason))),
        dict(label="test_amd_gpu_no_perflevel_unsupported", setup=lambda s: s.add_amd_gpu(with_perflevel=False), key="amd_gpu", supported=False),
        dict(label="test_no_amd_gpu", key="amd_gpu", supported=False),
    ]

    def test_amd_gpu_probe(self):
        self.run_cases(self.CASES)


class TestAmdPower(CapabilityTestBase):
    CASES = [
        dict(label="test_ryzenadj_with_amd_cpu", setup=lambda s: s.set_amd_cpu(), tools=("ryzenadj",), key="amd_power", supported=True, backend="ryzenadj"),
        dict(label="test_amd_cpu_without_ryzenadj_has_hint", setup=lambda s: s.set_amd_cpu(), key="amd_power", supported=False, hint="apt install"),
        dict(label="test_intel_cpu_unsupported", key="amd_power", supported=False),
    ]

    def test_amd_power_probe(self):
        self.run_cases(self.CASES)


class TestAsusFan(CapabilityTestBase):
    CASES = [
        dict(label="test_asusctl_platform", tools=("asusctl",), key="asus_platform", supported=True, backend="asusctl",
             # asusctl also provides fan control.
             check=lambda s, c, cap: s.assertEqual(c.get("fan_control").backend, "asusctl")),
        dict(label="test_fan_nbfc", tools=("nbfc",), key="fan_control", supported=True, backend="nbfc"),
        dict(label="test_no_fan_tools", key="fan_control", supported=False),
        dict(label="test_asus_platform_missing_has_hint", key="asus_platform", supported=False, hint="apt install"),
    ]

    def test_asus_fan_probe(self):
        self.run_cases(self.CASES)


class TestBattery(CapabilityTestBase):
    def test_battery_enumerated(self):
        self.write(os.path.join(self.psu, "BAT0", "type"), "Battery\n")
        self.write(os.path.join(self.psu, "BAT0", "power_now"), "10000000\n")
        self.write(os.path.join(self.psu, "BAT0", "capacity"), "80\n")
        self.write(os.path.join(self.psu, "ADP0", "type"), "Mains\n")
        caps = self.build()
        cap = caps.get("battery")
        self.assertTrue(cap.supported)
        self.assertEqual(len(cap.meta["batteries"]), 1)
        self.assertEqual(cap.meta["batteries"][0]["name"], "BAT0")
        self.assertEqual(cap.meta["mains"], "ADP0")

    def test_no_battery(self):
        caps = self.build()
        self.assertFalse(caps.get("battery").supported)


class TestInstallHints(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(install_hint("apt", "supergfxctl"), "sudo apt install supergfxctl")
        self.assertEqual(install_hint("pacman", "supergfxctl"), "sudo pacman -S supergfxctl")
        self.assertEqual(install_hint("apt", "nonexistent-tool"), "")


class TestGpuVendorCase(CapabilityTestBase):
    """PCI vendor IDs must be matched case-insensitively."""

    def _add_vendor(self, vendor_id):
        self.write(os.path.join(self.pci, "0000:01:00.0", "vendor"), vendor_id + "\n")

    def _add_uppercase_amd(self):
        base = os.path.join(self.pci, "0000:03:00.0")
        self.write(os.path.join(base, "vendor"), "0X1002\n")
        self.write(os.path.join(base, "power_dpm_force_performance_level"), "auto\n")

    CASES = [
        dict(label="test_uppercase_0x10de_detected", setup=lambda s: s._add_vendor("0x10DE"), tools=("supergfxctl",), key="gpu_switch", supported=True, backend="supergfxctl",
             check=lambda s, c, cap: s.assertTrue(c._nvidia_present())),
        dict(label="test_uppercase_bare_10de_detected", setup=lambda s: s._add_vendor("10DE"), key="gpu_switch", supported=False,
             check=lambda s, c, cap: s.assertTrue(c._nvidia_present())),
        dict(label="test_uppercase_amd_vendor_detected", setup=lambda s: s._add_uppercase_amd(), key="amd_gpu", supported=True,
             check=lambda s, c, cap: s.assertTrue(c._amd_gpu_present())),
        dict(label="test_unrelated_vendor_not_matched", setup=lambda s: s._add_vendor("0x1234"), key="gpu_switch", supported=False,
             check=lambda s, c, cap: s.assertFalse(c._nvidia_present())),
    ]

    def test_vendor_case_insensitive(self):
        self.run_cases(self.CASES)


class TestCapabilityLine(unittest.TestCase):
    def test_supported_line_names_backend(self):
        line = Capability("turbo", True, backend="intel_pstate").line()
        self.assertIn("[OK]", line)
        self.assertIn("intel_pstate", line)

    def test_unsupported_line_shows_reason_and_hint(self):
        line = Capability("turbo", False, reason="no interface", hint="sudo apt install x").line()
        self.assertIn("[--]", line)
        self.assertIn("no interface", line)
        self.assertIn("sudo apt install x", line)

    def test_unsupported_line_defaults_reason(self):
        self.assertIn("not supported", Capability("turbo", False).line())


class TestBatteryStatusMath(CapabilityTestBase):
    """Exercise SystemController.get_battery_status against mocked sysfs."""

    def _add_battery(self, name, **files):
        self.write(os.path.join(self.psu, name, "type"), "Battery\n")
        for key, value in files.items():
            self.write(os.path.join(self.psu, name, key), value + "\n")

    def _add_mains(self, name):
        self.write(os.path.join(self.psu, name, "type"), "Mains\n")

    # (label, batteries, mains, expected status line)
    STATUS_CASES = [
        # BAT0: 10 W / 50 Wh; BAT1: 2 A * 10 V = 20 W, 3 Ah * 10 V = 30 Wh -> 30 W, 80 Wh = 2h 39m
        ("total_watts_and_energy_math",
         [("BAT0", dict(power_now="10000000", energy_now="50000000", capacity="80")),
          ("BAT1", dict(current_now="2000000", voltage_now="10000000", charge_now="3000000", capacity="60"))],
         "ADP0", "30.00 W (Cap: 80/60% | Est. Runtime: ~2h 39m)"),
        # No energy/charge telemetry: 75 Wh * 50% = 37.5 Wh / 15 W = 2h 30m
        ("nominal_75wh_fallback_when_no_energy_files",
         [("BAT0", dict(power_now="15000000", capacity="50"))],
         None, "15.00 W (Cap: 50% | Est. Runtime: ~2h 30m)"),
        ("ultra_idle_when_watts_present_but_no_capacity_or_energy",
         [("BAT0", dict(power_now="7000000"))], None,
         "7.00 W (Cap: ? | AC Powered / Ultra Idle)"),
        ("fully_charged_zero_watts",
         [("BAT0", dict(power_now="0", capacity="100"))], None,
         "0.00 W (Cap: 100% | AC / Fully Charged)"),
        ("unsupported_reports_reason", [], None,
         "N/A (no battery device found (desktop?))"),
    ]

    def test_status_math(self):
        for label, batteries, mains, expected in self.STATUS_CASES:
            with self.subTest(case=label):
                self._reset_env()
                for name, files in batteries:
                    self._add_battery(name, **files)
                if mains:
                    self._add_mains(mains)
                self.assertEqual(self.controller(self.build()).get_battery_status(), expected)

    def test_multiple_batteries_and_mains_selection(self):
        self._add_battery("BAT0", power_now="10000000", energy_now="50000000", capacity="80")
        self._add_battery("BAT1", current_now="2000000", voltage_now="10000000", charge_now="3000000", capacity="60")
        self._add_mains("ADP0")
        self._add_mains("ADP1")

        cap = self.build().get("battery")
        self.assertTrue(cap.supported)
        names = [b["name"] for b in cap.meta["batteries"]]
        self.assertEqual(names, ["BAT0", "BAT1"])
        # Entries are enumerated in sorted order; the last mains device wins.
        self.assertEqual(cap.meta["mains"], "ADP1")

        bat0, bat1 = cap.meta["batteries"]
        self.assertTrue(bat0["power_now"] and bat0["energy_now"] and bat0["capacity"])
        self.assertFalse(bat0["current_voltage"] and bat0["charge_now"])
        self.assertTrue(bat1["current_voltage"] and bat1["charge_now"] and bat1["capacity"])
        self.assertFalse(bat1["power_now"] and bat1["energy_now"])


class TestHardening(CapabilityTestBase):
    """Regression tests for bugs surfaced by the review and fixed in source."""

    def test_malformed_vendor_id_line_does_not_crash(self):
        # _cpu_vendor() must tolerate a vendor_id line with no colon.
        self.write(self.cpuinfo, "vendor_id malformed\n\n")
        self.assertFalse(self.build().get("amd_power").supported)

    def test_generic_acpi_platform_profile_supported_without_asusctl(self):
        self.write(os.path.join(self.tmp, "acpi_profile"), "balanced\n")
        self.write(os.path.join(self.tmp, "acpi_profile_choices"),
                   "quiet balanced performance\n")
        caps = self.build()
        cap = caps.get("asus_platform")
        self.assertTrue(cap.supported)
        self.assertEqual(cap.backend, "platform_profile_sysfs")
        controller = self.controller(caps)
        ok, _ = controller.set_platform_profile("performance")
        self.assertTrue(ok)
        self.assertEqual(self.read(os.path.join(self.tmp, "acpi_profile")), "performance")

    def test_thinkfan_is_not_writable_fan_control(self):
        self.run_cases([dict(tools=("thinkfan",), key="fan_control", supported=False, backend="thinkfan")])


if __name__ == "__main__":
    unittest.main()
