## Summary

<!-- What does this change and why? -->

## Type

- [ ] Bug fix
- [ ] New backend / distribution
- [ ] UI / docs
- [ ] Other

## Tested on

<!-- distro + kernel, CPU, GPU; paste the relevant `powertui --diagnostics` lines -->

## Checklist

- [ ] `python3 -m unittest discover -p "test_*.py"` passes
- [ ] `shellcheck -s sh run_tui.sh install.sh uninstall.sh get.sh` passes (if scripts changed)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No behavior change beyond the stated scope
