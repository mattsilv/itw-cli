#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=13", "pillow>=10", "rich-pixels>=3"]
# ///
"""itw — zero-install PEP-723 launcher for the intheweights.com CLI.

For the installed entrypoint use `uv tool install .` / `pipx install .` (then `itw`).
This file lets you run the CLI with no install via `uv run itw.py <cmd>` — uv
auto-resolves the deps above. Logic lives in the itwlib/ package; resolving this
file's real path lets it be symlinked onto PATH while still importing sibling itwlib/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from itwlib.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
