"""itwlib — modular pieces of the intheweights.com CLI.

Layout:
  config.py    constants + shared Rich console + color maps + cache dir
  api.py       HTTP client + slug/avatar helpers + on-disk avatar cache (no rendering)
  render.py    pure Rich renderers (bars, pixel art, graphics-protocol dispatch) — no network
  card.py      pure card logic (brand colors, strength/top% formulas) — no network, no rendering
  commands.py  one function per subcommand (glue: api + render)
  cli.py       argument dispatch / entrypoint
"""

from importlib.metadata import version, PackageNotFoundError

# Single runtime source of truth: the installed package metadata (from pyproject's
# `version`). Bumping pyproject + tagging vX.Y.Z is the only place a human touches it.
try:
    __version__ = version("itw-cli")
except PackageNotFoundError:  # running from source / PEP-723 zero-install, not installed
    __version__ = "0.0.0+local"
