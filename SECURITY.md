# Security Policy

## Scope

PowerTUI runs as a privileged process (it writes to `/sys` and calls system
tools to change CPU, GPU, fan and power state). Security-relevant issues include,
but are not limited to:

- Command injection or unsafe argument handling in `powertui/sys_controller.py`
  or the POSIX shell installers (`run_tui.sh`, `install.sh`, `uninstall.sh`, `get.sh`).
- Path handling or privilege-escalation problems in `_write_file_or_sudo`.
- Any way untrusted input (e.g. tool output or `/etc/os-release`) could influence
  a command or a written sysfs value.

## Reporting

Please report vulnerabilities **privately** using GitHub's
[private vulnerability reporting](https://github.com/X3C12/PowerTui/security/advisories/new)
(Security tab → **Report a vulnerability**). Do not open a public issue for a
security problem.

Include:

- affected version or commit,
- a description of the issue and its impact,
- steps to reproduce (a distro + hardware description and a minimal repro is ideal).

You can expect an acknowledgement within a few days. Please allow a reasonable
window for a fix before any public disclosure.

## Supported versions

Only the latest release (and `main`) is supported with security fixes.
