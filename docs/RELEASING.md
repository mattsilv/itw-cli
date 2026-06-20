# Releasing

Versions are `vX.Y.Z` and each one is a tagged **GitHub Release**. There is no PyPI
package — users install and upgrade straight from git, and `itw update` checks the
latest release.

## Cut a release

1. Bump the version in **`pyproject.toml`** (`[project] version = "X.Y.Z"`). This is the
   single source — `itwlib.__version__` reads it from the installed package metadata, so
   nothing else needs editing.
2. Commit it: `git commit -am "release: vX.Y.Z"`.
3. Tag and push:
   ```bash
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

That's it. The `release.yml` workflow fires on the `v*` tag and:

- **guards** that the tag matches `pyproject.toml`'s version (fails loudly on drift),
- runs the test suite, and
- creates the GitHub Release with auto-generated notes.

Users pick it up with `itw update`.

## Versioning

Semver-ish: bump **patch** for fixes, **minor** for new commands/features, **major** for
breaking CLI changes. The tag and `pyproject.toml` must always agree — the workflow
enforces it, so if the guard fails, bump `pyproject.toml` and re-tag.
