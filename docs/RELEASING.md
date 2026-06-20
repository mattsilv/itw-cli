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

> **Do not run `gh release create` manually.** The workflow owns releases. Creating one
> by hand races the workflow and makes it fail with `422 Release.tag_name already exists`
> (this broke the v0.3.2 / v0.3.3 release runs). Just push the tag.

### Local guard (recommended)

Enable the pre-push hook once per clone so a drifted or already-released tag is caught
before it reaches CI:

```bash
git config core.hooksPath .githooks
```

It checks `tag == pyproject version` and refuses to push a `vX.Y.Z` tag whose GitHub
Release already exists.

## Versioning

Semver-ish: bump **patch** for fixes, **minor** for new commands/features, **major** for
breaking CLI changes. The tag and `pyproject.toml` must always agree — the workflow
enforces it, so if the guard fails, bump `pyproject.toml` and re-tag.
