# Release checklist

`get.sh` prefers a GitHub **release asset** named `powertui.tar.gz` and verifies it
against `SHA256SUMS` when `--verify` is used. If no release exists it falls back to
the `main` branch archive, so releases are optional — but they enable version pinning
and checksum verification.

## Cut a release

Run from the repository root, on the commit you want to release.

1. Bump the version (single source of truth):

   ```sh
   # edit version = "x.y.z" in pyproject.toml
   git commit -am "Release vX.Y.Z"
   ```

2. Update `CHANGELOG.md`: move items from `[Unreleased]` into a new `[X.Y.Z]` section
   dated today, and update the compare links at the bottom.

3. Build the release assets (the tarball name **must** be `powertui.tar.gz`):

   ```sh
   VERSION=X.Y.Z
   git archive --format=tar.gz --prefix="powertui-$VERSION/" -o powertui.tar.gz HEAD
   sha256sum powertui.tar.gz > SHA256SUMS
   ```

4. Tag and publish (requires the GitHub CLI, `gh auth login`):

   ```sh
   git tag -a "v$VERSION" -m "v$VERSION"
   git push origin main "v$VERSION"
   gh release create "v$VERSION" powertui.tar.gz SHA256SUMS \
     --title "v$VERSION" --notes "See CHANGELOG.md"
   ```

5. Smoke-test the published installer:

   ```sh
   curl -fsSL https://raw.githubusercontent.com/X3C12/PowerTui/main/get.sh | sh -s -- --verify
   powertui --diagnostics
   ```

   `--verify` must print `Checksum verified.` — if it can't find `SHA256SUMS`, it exits
   non-zero by design (fail closed).

## Notes

- `pyproject.toml` version and the git tag must match.
- Keep the tarball prefix (`powertui-$VERSION/`) so `get.sh` finds a single top-level dir.
- `SHA256SUMS` must contain a line whose second field ends in `powertui.tar.gz`.
- Publishing to PyPI (once ready) is a separate step: `python -m build` then
  `twine upload dist/*`.
