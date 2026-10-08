# PowerTUI Promotion Kit

Everything needed to launch PowerTUI. Copy-paste ready, no embellishment.
Repo: https://github.com/X3C12/PowerTui

---

## 1. Positioning

**Tagline:** Live CPU, GPU, fan and battery control from one Linux terminal.

**What it is / who it's for.** PowerTUI is a cross-distribution terminal UI (Python/Textual)
for Linux power and thermal control. It discovers hybrid P-core/E-core topology and lets you
hotplug cores, toggle Turbo Boost, set EPP, switch power profiles, and drive NVIDIA or AMD
GPUs, ASUS/ACPI platform profiles, fans and battery telemetry. Rather than assuming a distro,
it detects the host and probes every hardware backend before acting: where a supported backend
exists it does the right thing, and where it doesn't it greys the action out with the reason
and an install hint. It is for Linux laptop owners who want one keyboard-driven control panel
instead of five half-working vendor utilities.

---

## 2. Audience

- **Linux laptop users** who juggle power profiles, fans and battery without a vendor app.
- **Hybrid CPU owners** (Intel P/E-core, modern AMD) who want per-core online/offline control.
- **NVIDIA/AMD Optimus and dual-GPU owners** who switch integrated/hybrid from the terminal.
- **Distro hoppers** who want one tool that adapts across Debian, Arch, Fedora, openSUSE,
  Alpine, Void, Gentoo and NixOS instead of reinstalling configs.
- **Ricing / TUI crowd** and Textual/Rich developers who like good-looking terminal apps.

---

## 3. Launch posts

### Show HN

**Title:** Show HN: PowerTUI – cross-distro Linux TUI for CPU/GPU/fan/battery control

**First comment:**

> Author here. I kept installing one vendor tool for CPU cores, another for the GPU, another
> for fans, and each only worked on one distro or one laptop. PowerTUI is my attempt at one
> terminal UI that detects the distro and each hardware backend, then performs the correct
> backend-specific action where one exists and greys out + explains (with an install hint)
> where it doesn't.
>
> What it does today: hybrid CPU topology and core hotplug via sysfs, Turbo Boost
> (`intel_pstate/no_turbo` or `cpufreq/boost`), EPP validation, power profiles
> (`powerprofilesctl`/`tuned-adm`/`cpupower`), NVIDIA Optimus switching, NVIDIA power cap via
> `nvidia-smi -pl`, AMD GPU DPM performance level, Ryzen `ryzenadj` STAPM/FAST/SLOW presets,
> ACPI/ASUS platform profiles, `nbfc`/`asusctl` fans, and battery wattage/runtime telemetry.
>
> Honest limitations up front: Intel iGPU is unsupported; AMD GPU is DPM level only (no power
> cap/clocks/volts); TLP has no runtime switching; thinkfan is read-only; the app runs elevated.
>
> 49 hermetic tests (no root, no real /proc or /sys), CI on Python 3.10-3.13, a POSIX-sh
> installer that works on Alpine, and a NixOS flake. MIT.
>
> Install:
> `curl -fsSL https://raw.githubusercontent.com/X3C12/PowerTui/main/get.sh | sh`
> or `pipx install git+https://github.com/X3C12/PowerTui.git`
>
> Happy to answer anything about the capability-gating design or the sysfs backends.

### r/linux

**Title:** PowerTUI: one terminal UI for CPU cores, Turbo/EPP, GPU, fans and battery across Linux distros

**Body:**

> I built PowerTUI, a cross-distribution TUI (Python/Textual) for Linux power and thermal
> control. It reads `/etc/os-release`, classifies the distro family, probes each subsystem
> once, and only enables what actually exists on your machine - unsupported actions are disabled
> with the reason and a package install hint.
>
> Features: hybrid P/E-core hotplug, Turbo Boost, EPP, power profiles, NVIDIA Optimus switching
> and power cap, AMD GPU DPM level, Ryzen power presets, ACPI/ASUS platform profiles, fans,
> battery telemetry, and one-click Max Battery / Balanced / Max Performance presets.
>
> Install one line:
> `curl -fsSL https://raw.githubusercontent.com/X3C12/PowerTui/main/get.sh | sh`
>
> MIT, repo and full support matrix: https://github.com/X3C12/PowerTui
> (Please check the subreddit's self-promotion rules before posting; disclose that I'm the author.)

### r/archlinux

**Title:** PowerTUI - a Textual TUI for core hotplug, Turbo/EPP, GPU switching and fans (AUR-friendly source install)

**Body:**

> Sharing PowerTUI, a terminal UI for Arch and other distros. It detects the distro family and
> picks backend preference orders per family, so on Arch you get `powerprofilesctl` over
> `tuned`, `supergfxctl`/`envycontrol`/`optimus-manager`/`prime-select` for GPU switching, and
> `ryzenadj` for AMD power limits.
>
> It installs from source via the POSIX installer or pipx; no AUR package yet. Core hotplug,
> Turbo, EPP, EPP validation, AMD GPU DPM level, ASUS/ACPI platform profiles, `asusctl`/`nbfc`
> fans, battery telemetry, presets.
>
> `curl -fsSL https://raw.githubusercontent.com/X3C12/PowerTui/main/get.sh | sh`
>
> MIT: https://github.com/X3C12/PowerTui (I'm the author; follow the sub's self-promo rules.)

### r/thinkpad

**Title:** PowerTUI - ThinkPad power/thermal TUI (core hotplug, Turbo, EPP, platform profile, battery telemetry)

**Body:**

> For ThinkPad owners who want keyboard-driven power control: PowerTUI is a terminal UI that
> handles hybrid P/E-core hotplug, Turbo Boost, EPP, and ACPI platform profiles. Battery
> wattage/runtime telemetry comes straight from `/sys/class/power_supply`.
>
> One caveat specific to this sub: `thinkfan` is read-only/config-only, so PowerTUI reports it
> as unsupported rather than pretending to drive it. Those with `asusctl`/`nbfc` get fan control;
> ThinkPads typically don't. Everything unsupported is greyed out with a reason.
>
> Install: `curl -fsSL https://raw.githubusercontent.com/X3C12/PowerTui/main/get.sh | sh`
>
> MIT: https://github.com/X3C12/PowerTui (I'm the author; read the sub's self-promo rules first.)

### r/linuxhardware

**Title:** PowerTUI: distro-agnostic TUI for CPU/GPU/fan control, with an honest hardware support matrix

**Body:**

> Posting PowerTUI, a Linux power/thermal TUI that maps hardware support explicitly rather than
> guessing. It probes 12 capability keys (CPU hotplug, Turbo, EPP, power profile, GPU switching,
> NVIDIA power, AMD GPU, AMD power, ASUS platform, fans, battery, cleanup) and only enables what
> it detects.
>
> Support highlights: Intel CPU full control, AMD CPU full control + `ryzenadj` presets, NVIDIA
> telemetry + power cap (live probe), AMD GPU DPM performance level only (**not a power cap**),
> Intel iGPU unsupported, battery telemetry only. Full matrix in the README.
>
> `curl -fsSL https://raw.githubusercontent.com/X3C12/PowerTui/main/get.sh | sh`
>
> MIT, source and matrix: https://github.com/X3C12/PowerTui (I'm the author.)

### Lobsters

**Title:** PowerTUI: cross-distribution Linux TUI for CPU, GPU, fan and battery control

**Summary:**

> PowerTUI is a Python/Textual terminal UI that detects the host Linux distribution and probes
> each hardware subsystem before acting. It performs backend-specific actions for hybrid CPU
> core hotplug, Turbo Boost and EPP, power profiles, NVIDIA Optimus and power cap, AMD GPU DPM
> level, AMD Ryzen power presets, ACPI/ASUS platform profiles, fans and battery telemetry.
> Unsupported actions are disabled with a reason and an install hint. 49 hermetic tests, CI on
> Python 3.10-3.13, POSIX-sh installer (Alpine/Void compatible), NixOS flake, MIT.
> https://github.com/X3C12/PowerTui

### Textual Discord / "built with Textual" showcase

> Built with Textual: **PowerTUI** - a cross-distribution Linux power and thermal TUI. It
> discovers hybrid CPU topology, hotplugs cores, toggles Turbo/EPP, switches power profiles and
> GPUs (NVIDIA/AMD), drives ASUS/ACPI platform profiles, fans and battery telemetry, and greys
> out anything the host can't do with a reason. Capability-gated buttons map to probed backends;
> a 1s timer refreshes the dashboard. MIT, 49 hermetic tests.
> https://github.com/X3C12/PowerTui

---

## 4. Awesome-list PR targets

Verify each list's current entry format and CONTRIBUTING rules before opening a PR; links in
these lists are typically ordered alphabetically, so place the line accordingly.

**sindresorhus/awesome-tui** (Terminal / TUI apps)
```markdown
- [PowerTUI](https://github.com/X3C12/PowerTui) - Cross-distribution TUI for CPU core hotplug, Turbo/EPP, GPU, fan and battery control on Linux.
```

**sindresorhus/awesome-linux** (Utilities / System)
```markdown
- [PowerTUI](https://github.com/X3C12/PowerTui) - Cross-distribution terminal UI for Linux power, CPU, GPU, fan and battery management.
```

**awesome-cli-apps** (see agarrharr/awesome-cli-apps, System / Utilities section)
```markdown
- [PowerTUI](https://github.com/X3C12/PowerTui) - Terminal UI to control CPU cores, Turbo/EPP, GPU switching, platform profiles, fans and battery on Linux.
```

**Other relevant targets**
- **agarrharr/awesome-cli-apps** - same line as above (System section).
- A curated **awesome-linux-software** / **Awesome-Linux-Software** list, in System Tools:
  ```markdown
  - [PowerTUI](https://github.com/X3C12/PowerTui) - Cross-distro TUI for CPU, GPU, fan and battery control on Linux.
  ```
- A **Textual**/Python-TUI awesome list (e.g. an "awesome-textual" list if one exists), Showcase section:
  ```markdown
  - [PowerTUI](https://github.com/X3C12/PowerTui) - Power/thermal dashboard controlling CPU cores, GPU, fans and battery across Linux distros.
  ```

---

## 5. Repo discoverability checklist

- [ ] **GitHub About description** (use the one-liner):
      `Cross-distribution terminal UI for live CPU core, Turbo/EPP, GPU, platform-profile, fan and battery control on Linux.`
- [ ] **Topics** (add all):
      `linux, tui, textual, python, power-management, cpu, gpu, nvidia, amd, battery, terminal, cli, sysfs, asus, ryzen`
- [ ] **Social preview image**: upload a 1280x640 crop of `docs/screenshot.png`
      (Settings > General > Social preview). Crop to center the dashboard, keep text legible.
- [ ] **Enable Discussions** (Settings > Features > Discussions) so users land somewhere other
      than the issue tracker for questions and setup help.
- [ ] **Releases**: already automated via CI; no action, just confirm the latest tag renders.
- [ ] Pin the demo GIF (see Assets) near the top of the README slot that already exists.

---

## 6. Cadence / etiquette

**2-week plan**

- **Day 0:** Prep assets (demo GIF, social preview), enable Discussions, finalize README.
- **Day 1:** Post Show HN (link repo, not a landing page), publish Lobsters.
- **Day 2:** Post r/linux; answer every comment for the first 6 hours.
- **Day 3:** Post r/archlinux and r/linuxhardware.
- **Day 4:** Post r/thinkpad (fan caveat is the hook).
- **Day 5:** Post the Textual Discord/showcase blurb.
- **Day 6-7:** Open awesome-list PRs.
- **Week 2:** Follow up on issues, thank contributors, ship any quick DX fix raised in comments,
  then share the fix ("you asked, here it is") once.

**Do not spam**

- One post per community; do not cross-post the same text into five subs in one day.
- Always disclose authorship in the post.
- Read and follow each community's self-promotion rules before posting.
- Respond to comments; a post with an absent author gets ignored or removed.
- No unsolicited DMs, no reposting in the same sub, no fake accounts.

---

## 7. Assets

**Demo GIF - what to record (30-60s):**

1. Launch `powertui` and show the dashboard with live CPU/battery telemetry.
2. Toggle a P-core or E-core with `-`/`+` and show the core count change.
3. Hit `b` for Max Battery, then `p` for Max Performance.
4. Switch GPU mode Integrated -> Hybrid.
5. Show a greyed-out/unsupported button with its reason.
6. End on the battery wattage/runtime readout.

**Record with asciinema + agg:**
```bash
asciinema rec powertui.cast
# launch powertui, perform the steps above, then exit
agg --cols 100 --rows 30 --font-size 16 powertui.cast docs/demo.gif
```

**Or with vhs (scripted):**
```bash
cat > demo.tape <<'EOF'
Output docs/demo.gif
Set FontSize 16
Set Width 1000
Set Height 640
Type "powertui"
Enter
Sleep 3s
Sleep 20s
EOF
vhs demo.tape
```

**Placement:** `docs/demo.gif`, then uncomment the existing demo slot in `README.md`:

```markdown
![PowerTUI demo](docs/demo.gif)
```
