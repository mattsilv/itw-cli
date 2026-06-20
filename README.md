# itw — a terminal client for [intheweights.com](https://intheweights.com)

Show the [intheweights.com](https://intheweights.com) leaderboard, a name's per-model
recognition breakdown, and a **terminal share card with the hosted pixel avatar
embedded** — rendered as colored half-block pixel art that looks the same in every
terminal.

This is an open-source, **read-only** client. It only reads the public leaderboard,
cached results, and the hosted avatars — it never writes anything to the site.

```
itw "paul mccartney"
```

> One lookup shows everything: the embedded pixel avatar (the web card has none),
> the name, descriptor, the `STRENGTH · TOP%` line, and per-model brand-colored
> confidence bars. Add `--detail` for the headline model snippet, scores, tiers, and
> evidence.

## Install

**`uv tool` (recommended)** — installs the `itw` command on your PATH:

```bash
uv tool install git+https://github.com/mattsilv/itw-cli
itw "paul mccartney"
```

**`pipx`:**

```bash
pipx install git+https://github.com/mattsilv/itw-cli
```

**Zero-install (PEP 723 — uv resolves deps on the fly, no `itw` on PATH):**

```bash
uv run https://raw.githubusercontent.com/mattsilv/itw-cli/main/itw.py board
# or, from a clone:
uv run itw.py "paul mccartney"
```

From a local clone, `uv tool install .` / `pipx install .` also work.

## Usage

```bash
itw "paul mccartney"            # profile card — avatar + strength + model bars
itw "paul mccartney" --detail   # + headline snippet, scores, tiers, evidence
itw top                         # the top 20 as a pixel-avatar gallery
itw board                       # leaderboard table (optional slice, default: top)
```

| Command | What it does |
| --- | --- |
| `itw "<name>"` | ⭐ Profile card — embedded avatar, strength/top-%, per-model bars |
| `itw "<name>" --detail` | Adds the per-model snippet, scores, tiers, and evidence |
| `itw top` | The top 20 names as a 4×5 pixel-avatar gallery |
| `itw board [slice]` | Leaderboard table (default slice: `top`) |

Quotes are optional — `itw paul mccartney` works too.

**Flags:** `--detail`, `--version`, `-h`/`--help`.

Only the most popular ~20 names have a hosted avatar; for everyone else the card
renders fully and shows the stats without an image.

## Rendering

Avatars render as colored **half-block pixel art** (via `rich-pixels`): each glyph is
a real text cell, so the avatar composes cleanly inside the bordered card and looks
the same in every terminal, over SSH, and when piped to a file. (Terminal graphics
protocols like kitty/iTerm2 paint at the cursor and ignore a panel's interior, so an
inline image would overflow and corrupt the card — half-block avoids that entirely.)
The render uses the locked pixel-art recipe — `NEAREST` downscale + `FASTOCTREE`
color-quantize — for hard, chunky edges rather than a blurry shrink.

**Avatar source.** `itw` ships its **own** pixel avatars — generated with an image
model (`gemini-2.5-flash-image`) and quantized to a small palette — bundled in the
package so they render offline with no API key. A bundled avatar wins over the site's
hosted one (ours is built for the terminal); names with neither still render the full
card with a generic generated **silhouette** placeholder. `itw top` browses the
bundled gallery; names we intentionally didn't generate show a red ✕ placeholder.
(Try `itw alan turing` — bundled, generated, and the site hosts none for him.)

## Cache

Avatar bytes are cached on disk (default `~/.cache/itw/avatars/<slug>.png`, honoring
`XDG_CACHE_HOME` / `ITW_CACHE_DIR`) so re-renders are instant and work offline.

## Development

```bash
uv sync
uv run pytest
```

Stdlib HTTP only (no `requests`/`httpx`) to keep the install light. The card mirrors
the site's presentation; values are pinned to the current roster/prompt version and
surfaced in the `--detail` footer, so they may need updating if the site changes.

## Disclaimer

**Unofficial and unaffiliated.** This is a fan-made, read-only client and is not
built, endorsed, or supported by intheweights.com. It relies on the site's public,
**undocumented** behavior, which can change or break at any time without notice — if
a command stops working, the site likely changed. Use at your own risk. Please be a
good citizen: don't hammer the site, and respect its terms.

## License

MIT — see [LICENSE](LICENSE).
