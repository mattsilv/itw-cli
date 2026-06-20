"""itwlib — modular pieces of the intheweights.com CLI.

Layout:
  config.py    constants + shared Rich console + color maps + cache dir
  api.py       HTTP client + slug/avatar helpers + on-disk avatar cache (no rendering)
  render.py    pure Rich renderers (bars, pixel art, graphics-protocol dispatch) — no network
  card.py      pure card logic (brand colors, strength/top% formulas) — no network, no rendering
  commands.py  one function per subcommand (glue: api + render)
  cli.py       argument dispatch / entrypoint
"""

__version__ = "0.1.0"
