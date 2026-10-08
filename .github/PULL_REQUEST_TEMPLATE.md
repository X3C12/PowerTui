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

- [ ] `python3 -m unittest discover -s tests -p "test_*.py"` passes
- [ ] `shellcheck -s sh scripts/run_tui.sh scripts/install.sh scripts/uninstall.sh scripts/get.sh` passes (if scripts changed)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No behavior change beyond the stated scope
