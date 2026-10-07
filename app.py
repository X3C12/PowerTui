import sys
import time

# ---------------------------------------------------------------------------
# Non-TUI diagnostics mode: works even without Textual installed.
# ---------------------------------------------------------------------------
if "--diagnostics" in sys.argv:
    from capabilities import Capabilities

    print(Capabilities().report_text())
    sys.exit(0)

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, Log, Label
from rich.markup import escape as _esc
from capabilities import Capabilities
from sys_controller import SystemController


# Buttons gated by capability keys; a button is enabled when ANY listed key is
# supported. Buttons absent from this map are always enabled.
BUTTON_CAPABILITY = {
    "btn_battery": ("cpu_online",),
    "sub_p": ("cpu_online",),
    "add_p": ("cpu_online",),
    "sub_e": ("cpu_online",),
    "add_e": ("cpu_online",),
    "gpu_int": ("gpu_switch",),
    "gpu_hyb": ("gpu_switch",),
    "btn_clean": ("cleanup",),
    "nv_eco": ("nvidia_power",),
    "nv_max": ("nvidia_power",),
    "amd_low": ("amd_gpu",),
    "amd_auto": ("amd_gpu",),
    "ry_eco": ("amd_power",),
    "ry_perf": ("amd_power",),
    "plat_quiet": ("asus_platform", "fan_control"),
    "plat_perf": ("asus_platform", "fan_control"),
}

# Ryzenadj preset limits in milliwatts (conservative; laptop Ryzen friendly).
RYZEN_PRESETS = {
    "eco": {"stapm": 15000, "fast": 20000, "slow": 20000, "temp": 85},
    "perf": {"stapm": 35000, "fast": 45000, "slow": 40000, "temp": 95},
}


class PowerTUI(App):
    TITLE = "PowerTUI - Portable Hybrid Core & GPU Hardware Manager"
    SUB_TITLE = "Cross-Distribution Hardware Controller (1s Auto-Refresh Enabled)"
    CSS = """
    Screen {
        background: $surface;
    }
    #dashboard {
        border: solid $accent;
        padding: 1 2;
        margin: 1;
        height: auto;
        background: $panel;
    }
    .panel-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    .section-row {
        height: auto;
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #btn_reset {
        background: $warning;
        color: $text;
        text-style: bold;
    }
    #btn_reset:hover {
        background: $error;
    }
    #btn_battery {
        background: $success;
        text-style: bold;
    }
    #btn_perf {
        background: $primary;
        text-style: bold;
    }
    #btn_refresh {
        background: $secondary;
        text-style: bold;
    }
    #log_view {
        border: solid $secondary;
        height: 8;
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit Application"),
        ("u", "refresh_now", "Refresh Status"),
        ("r", "reset", "Reset to Default"),
        ("b", "battery_preset", "Max Battery Preset"),
        ("p", "perf_preset", "Max Performance"),
    ]

    def __init__(self):
        super().__init__()
        self.caps = Capabilities()
        self.controller = SystemController(capabilities=self.caps)
        self.current_p_count = max(1, len(self.controller.p_cores))
        self.current_e_count = len(self.controller.e_cores)
        self._tick = 0
        self._extended_cache = "[dim]Reading extended hardware...[/dim]"

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="dashboard"):
            yield Label("[bold]System Power, Battery Drain & Hardware Status (Live 1s Refresh)[/bold]", classes="panel-title")
            yield Static(id="platform_info")
            yield Static(id="caps_info")
            yield Static(id="extended_info")
            yield Static(id="status_info")
            yield Static(id="core_grid")

        with Vertical(classes="section-row"):
            yield Label("[bold yellow]🚀 Stable One-Click Power Presets & Live Sync[/bold yellow]", classes="panel-title")
            with Horizontal():
                yield Button("🌱 Max Battery (2P+2E + NoTurbo + iGPU)", id="btn_battery", variant="success")
                yield Button("⚖️ Balanced Work (4P+4E)", id="btn_balanced")
                yield Button("⚡ Max Performance (All Cores)", id="btn_perf", variant="primary")
                yield Button("🔄 RESET TO DEFAULT [r]", id="btn_reset")
                yield Button("🔄 Refresh UI [u]", id="btn_refresh")

        with Vertical(classes="section-row"):
            yield Label("[bold cyan]🎛️ Custom CPU Core Control[/bold cyan]", classes="panel-title")
            with Horizontal():
                yield Button("➖ P-Core", id="sub_p")
                yield Button("➕ P-Core", id="add_p")
                yield Button("➖ E-Core", id="sub_e")
                yield Button("➕ E-Core", id="add_e")

        with Vertical(classes="section-row"):
            yield Label("[bold magenta]🎮 Safe GPU Mode & Container Cleanup[/bold magenta]", classes="panel-title")
            with Horizontal():
                yield Button("🚫 Switch GPU to Integrated Mode", id="gpu_int")
                yield Button("🟢 Switch GPU to Hybrid Mode", id="gpu_hyb")
                yield Button("🧹 Clean Background Containers", id="btn_clean", variant="warning")

        with Vertical(classes="section-row"):
            yield Label("[bold cyan]🔬 Extended Hardware (NVIDIA · AMD · ASUS · Fans)[/bold cyan]", classes="panel-title")
            with Horizontal():
                yield Button("🐢 NVIDIA Eco Limit", id="nv_eco")
                yield Button("🚀 NVIDIA Max Limit", id="nv_max")
                yield Button("🐢 AMD GPU Low", id="amd_low")
                yield Button("♻️ AMD GPU Auto", id="amd_auto")
            with Horizontal():
                yield Button("⚡ Ryzen Eco (STAPM 15W)", id="ry_eco")
                yield Button("🔥 Ryzen Perf (STAPM 35W)", id="ry_perf")
                yield Button("🤫 Quiet Platform/Fans", id="plat_quiet")
                yield Button("🔥 Performance Platform/Fans", id="plat_perf")

        yield Log(id="log_view")
        yield Footer()

    def on_mount(self) -> None:
        self.log_msg("PowerTUI initialized. Cross-distribution capability detection active.")
        self._apply_capability_gating()
        self.refresh_ui()
        # Fast 1.0 second timer for immediate feedback
        self.set_interval(1.0, self.refresh_ui)

    def _apply_capability_gating(self) -> None:
        """Disable UI actions whose backend is unavailable on this system."""
        for button_id, cap_keys in BUTTON_CAPABILITY.items():
            if not any(self.caps.supported(k) for k in cap_keys):
                try:
                    self.query_one(f"#{button_id}", Button).disabled = True
                except Exception:
                    pass

    def log_msg(self, text: str) -> None:
        log_widget = self.query_one(Log)
        log_widget.write_line(f"➤ {text}")

    def _caps_summary(self) -> str:
        parts = []
        for key, label in (("turbo", "Turbo"), ("epp", "EPP"), ("power_profile", "Profile"),
                           ("gpu_switch", "GPU"), ("battery", "Battery"), ("cleanup", "Cleanup")):
            cap = self.caps.get(key)
            mark = "[green]✅[/green]" if cap.supported else "[red]❌[/red]"
            parts.append(f"{mark} {label}")
        return " ".join(parts)

    def _extended_line(self) -> str:
        parts = []
        if self.caps.supported("nvidia_power"):
            parts.append(f"NVIDIA: {_esc(self.controller.get_nvidia_power())}")
        if self.caps.supported("amd_gpu"):
            parts.append(f"AMD GPU: {_esc(self.controller.get_amd_gpu_state())}")
        if self.caps.supported("amd_power"):
            parts.append(f"Ryzen: {_esc(self.controller.get_amd_cpu_power())}")
        if self.caps.supported("asus_platform"):
            parts.append(f"Platform: {_esc(self.controller.get_platform_profile())}")
        if self.caps.supported("fan_control"):
            parts.append(f"Fans: {_esc(self.controller.get_fan_status())}")
        if not parts:
            return "[dim]🔬 No extended hardware backends available (NVIDIA power / AMD GPU / Ryzen / ASUS / fans).[/dim]"
        return "🔬 " + "  |  ".join(parts)

    def _core_grid_text(self) -> str:
        """Visual display of active and inactive P-cores and E-cores."""
        lines = ["\n[bold cyan]── Hybrid CPU Core States ──[/bold cyan]"]

        p_items = []
        for c in self.controller.p_cores:
            status = "[bold green]ON [/bold green]" if c.is_online else "[dim red]OFF[/dim red]"
            p_items.append(f"P-Core {c.core_id}: {status}")
        lines.append("[bold white]Performance Cores (2 threads/core):[/bold white] " + " | ".join(p_items))

        e_items = []
        for c in self.controller.e_cores:
            status = "[bold green]ON [/bold green]" if c.is_online else "[dim red]OFF[/dim red]"
            e_items.append(f"E-Core {c.core_id}: {status}")
        lines.append("[bold white]Efficiency Cores (1 thread/core):[/bold white]   " + " | ".join(e_items))

        return "\n".join(lines)

    def refresh_ui(self) -> None:
        self.controller.refresh_topology()
        p_on, e_on = self.controller.get_online_counts()
        self.current_p_count = max(1, p_on)
        self.current_e_count = e_on

        prof = self.controller.get_power_profile()
        gpu = self.controller.get_gpu_state()
        bat = self.controller.get_battery_status()

        gpu_str = (f"[cyan]{_esc(gpu['mode'])} (PM Status: {_esc(gpu['power_status'])} / "
                   f"PCI: {_esc(gpu['pci_status'])})[/cyan]")

        timestamp = time.strftime("%H:%M:%S")
        self.query_one("#platform_info", Static).update(
            f"🖥️ [bold]{_esc(self.caps.distro.display)}[/bold] "
            f"[dim](id={_esc(self.caps.distro.id)}, family={_esc(self.caps.distro.family)})[/dim]   |   "
            f"📦 [bold]{_esc(self.caps.distro.package_manager)}[/bold]   |   "
            f"⚙️ [bold]{_esc(self.caps.distro.init_system)}[/bold]   |   "
            f"🔑 [bold]{_esc(self.caps.distro.privilege_tool)}[/bold]\n"
            f"🧩 [bold]Capabilities:[/bold] {self._caps_summary()}"
        )
        self.query_one("#caps_info", Static).update(
            f"[dim]{_esc(str(self.caps.get('turbo').backend))} · {_esc(str(self.caps.get('epp').backend))} · "
            f"{_esc(str(self.caps.get('power_profile').backend))} · {_esc(str(self.caps.get('gpu_switch').backend))}[/dim]"
        )

        # Extended hardware telemetry is heavier (subprocess calls); refresh ~every 5s.
        self._tick += 1
        if self._tick % 5 == 1:
            self._extended_cache = self._extended_line()
        self.query_one("#extended_info", Static).update(self._extended_cache)

        self.query_one("#status_info", Static).update(
            f"🔋 [bold]Live Battery Drain & Runtime:[/bold] [bold cyan]{_esc(bat)}[/bold cyan]\n"
            f"⚡ [bold]Power Profile:[/bold] [green]{_esc(prof)}[/green]   |   "
            f"🎮 [bold]GPU:[/bold] {gpu_str}   |   "
            f"🧠 [bold]Active Cores:[/bold] [yellow]{p_on}/{len(self.controller.p_cores)} P[/yellow], [yellow]{e_on}/{len(self.controller.e_cores)} E[/yellow]   |   "
            f"🕒 [dim]Updated: {timestamp}[/dim]"
        )
        self.query_one("#core_grid", Static).update(self._core_grid_text())

    def action_refresh_now(self) -> None:
        self.log_msg("🔄 Manual status refresh triggered.")
        self.refresh_ui()

    def _log_unsupported(self, cap_key: str) -> bool:
        cap = self.caps.get(cap_key)
        if cap.supported:
            return False
        msg = f"⚠️ Not supported on this system: {cap.reason}"
        if cap.hint:
            msg += f" | try: {cap.hint}"
        self.log_msg(msg)
        return True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_battery":
            self.action_battery_preset()
        elif bid == "btn_balanced":
            self.log_msg("Applying Balanced preset (4 P-cores + 4 E-cores, Turbo ON, Hybrid GPU)...")
            _, m_safe = self.controller.apply_safe_powersave(enable=False)
            _, m_cpu = self.controller.set_active_cores(4, 4)
            _, m_prof = self.controller.set_power_profile("balanced")
            _, m_gpu = self.controller.set_gpu_mode("Hybrid")
            self.log_msg(f"{m_cpu} | {m_prof} | {m_gpu}")
            self.refresh_ui()
        elif bid == "btn_perf":
            self.action_perf_preset()
        elif bid == "btn_reset":
            self.action_reset()
        elif bid == "btn_refresh":
            self.action_refresh_now()
        elif bid == "sub_p":
            self.current_p_count = max(1, self.current_p_count - 1)
            _, msg = self.controller.set_active_cores(self.current_p_count, self.current_e_count)
            self.log_msg(msg)
            self.refresh_ui()
        elif bid == "add_p":
            self.current_p_count = min(len(self.controller.p_cores), self.current_p_count + 1)
            _, msg = self.controller.set_active_cores(self.current_p_count, self.current_e_count)
            self.log_msg(msg)
            self.refresh_ui()
        elif bid == "sub_e":
            self.current_e_count = max(0, self.current_e_count - 1)
            _, msg = self.controller.set_active_cores(self.current_p_count, self.current_e_count)
            self.log_msg(msg)
            self.refresh_ui()
        elif bid == "add_e":
            self.current_e_count = min(len(self.controller.e_cores), self.current_e_count + 1)
            _, msg = self.controller.set_active_cores(self.current_p_count, self.current_e_count)
            self.log_msg(msg)
            self.refresh_ui()
        elif bid == "gpu_int":
            self.log_msg("Switching GPU mode to Integrated...")
            _, msg = self.controller.set_gpu_mode("Integrated")
            self.log_msg(msg)
            self.refresh_ui()
        elif bid == "gpu_hyb":
            self.log_msg("Switching GPU mode to Hybrid...")
            _, msg = self.controller.set_gpu_mode("Hybrid")
            self.log_msg(msg)
            self.refresh_ui()
        elif bid == "btn_clean":
            self.action_clean_tasks()
        elif bid in ("nv_eco", "nv_max"):
            self._nvidia_limit(bid == "nv_max")
        elif bid == "amd_low":
            self._apply(self.controller.set_amd_gpu_power("low"))
        elif bid == "amd_auto":
            self._apply(self.controller.set_amd_gpu_power("auto"))
        elif bid == "ry_eco":
            self._ryzen("eco")
        elif bid == "ry_perf":
            self._ryzen("perf")
        elif bid == "plat_quiet":
            self._platform_fan("quiet")
        elif bid == "plat_perf":
            self._platform_fan("performance")

    def _apply(self, result) -> None:
        ok, msg = result
        self.log_msg(("✅ " if ok else "⚠️ ") + msg)
        self.refresh_ui()

    def _nvidia_limit(self, maximum: bool) -> None:
        if self._log_unsupported("nvidia_power"):
            return
        limits = self.controller.get_nvidia_limits()
        if not limits:
            self.log_msg("⚠️ Could not read NVIDIA power limits.")
            return
        watts = int(limits["max"]) if maximum else int(limits["min"] + (limits["max"] - limits["min"]) * 0.35)
        self._apply(self.controller.set_nvidia_power_limit(watts))

    def _ryzen(self, preset: str) -> None:
        if self._log_unsupported("amd_power"):
            return
        spec = RYZEN_PRESETS[preset]
        result = self.controller.set_amd_cpu_power(
            spec["stapm"], spec["fast"], spec["slow"], spec["temp"])
        self._apply(result)

    def _platform_fan(self, profile: str) -> None:
        did = False
        if self.caps.supported("asus_platform"):
            self._apply(self.controller.set_platform_profile(profile))
            did = True
        if self.caps.supported("fan_control"):
            self._apply(self.controller.set_fan_profile(profile))
            did = True
        if not did:
            self._log_unsupported("asus_platform")

    def _preset_extended(self, amd_level: str, profile: str) -> tuple:
        """Run the capability-gated AMD/platform/fan preset steps.

        Returns the three result messages in order, substituting fallback text
        for any backend that is not supported on this system.
        """
        msgs = []
        for cap_key, call, fallback in (
            ("amd_gpu", lambda: self.controller.set_amd_gpu_power(amd_level), "AMD GPU n/a"),
            ("asus_platform", lambda: self.controller.set_platform_profile(profile), "platform n/a"),
            ("fan_control", lambda: self.controller.set_fan_profile(profile), "fans n/a"),
        ):
            if self.caps.supported(cap_key):
                _, msg = call()
            else:
                msg = fallback
            msgs.append(msg)
        return tuple(msgs)

    def action_battery_preset(self) -> None:
        self.log_msg("Applying Stable Max Battery Preset: 2P+2E Cores, Turbo Boost OFF, CPU EPP Power, Integrated GPU...")
        _, m_cpu = self.controller.set_active_cores(2, 2)
        _, m_prof = self.controller.set_power_profile("power-saver")
        _, m_clean = self.controller.clean_background_tasks()
        _, m_safe = self.controller.apply_safe_powersave(enable=True)
        _, m_gpu = self.controller.set_gpu_mode("Integrated")
        m_amd, m_plat, m_fan = self._preset_extended("low", "quiet")
        self.log_msg(f"✅ {m_cpu} | {m_prof} | {m_clean} | {m_safe} | {m_gpu} | {m_amd} | {m_plat} | {m_fan}")
        self.refresh_ui()

    def action_perf_preset(self) -> None:
        self.log_msg("Applying Max Performance: All cores online, Turbo Boost ON, Performance profile, Hybrid GPU...")
        _, m_safe = self.controller.apply_safe_powersave(enable=False)
        _, m_cpu = self.controller.set_active_cores(len(self.controller.p_cores), len(self.controller.e_cores))
        _, m_prof = self.controller.set_power_profile("performance")
        _, m_gpu = self.controller.set_gpu_mode("Hybrid")
        m_amd, m_plat, m_fan = self._preset_extended("high", "performance")
        self.log_msg(f"🚀 {m_cpu} | {m_prof} | {m_gpu} | {m_amd} | {m_plat} | {m_fan}")
        self.refresh_ui()

    def action_reset(self) -> None:
        self.log_msg("🔄 Resetting system hardware states to factory default...")
        ok, msg = self.controller.reset_to_defaults()
        self.log_msg(f"✅ Default restored: {msg}")
        self.refresh_ui()

    def action_clean_tasks(self) -> None:
        self.log_msg("🧹 Cleaning background container development stacks and agent daemons...")
        _, msg = self.controller.clean_background_tasks()
        self.log_msg(f"✅ {msg}")


if __name__ == "__main__":
    app = PowerTUI()
    app.run()
