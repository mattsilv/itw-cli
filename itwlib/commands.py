"""The two commands behind the CLI: a single name lookup (the share card, plus an
optional per-model detail view) and the leaderboard. Glue between api + render."""
from __future__ import annotations

import urllib.parse

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from itwlib.config import console, cat_style, TIER_COLOR, BASE
from itwlib.api import get, slugify, avatar_url, avatar_exists, fetch_bytes, local_avatar
from itwlib.render import bar, render_avatar
from itwlib import card as cardlib


# --------------------------------------------------------------------------
# small shared helpers
# --------------------------------------------------------------------------
# org words that are NOT also the model's brand, so they're safe to drop.
# (DeepSeek / Mistral / Qwen / Kimi ARE the brand, so they stay.)
_PROVIDER_PREFIXES = {"google", "meta", "xai", "x-ai", "z.ai", "openai", "anthropic",
                      "moonshotai"}


def _short_model_label(label: str) -> str:
    """Tighten a model label for the card: drop a leading provider word and a
    trailing 'Instruct'. 'Google Gemini 3.1 Flash Lite' -> 'Gemini 3.1 Flash Lite';
    'Meta Llama 3.3 70B Instruct' -> 'Llama 3.3 70B'. (Full label stays in --detail.)"""
    parts = label.split()
    if len(parts) > 1 and parts[0].lower() in _PROVIDER_PREFIXES:
        parts = parts[1:]
    if len(parts) > 1 and parts[-1].lower() == "instruct":
        parts = parts[:-1]
    return " ".join(parts)


def _short_name(name: str) -> str:
    """Gallery tile label: a recognizable short name. Last token, but skip suffix
    tokens like II/III/Jr/Sr so 'Queen Elizabeth II' -> 'Elizabeth' and
    'Martin Luther King Jr.' -> 'King'."""
    toks = [t for t in name.replace(".", "").split() if t]
    if not toks:
        return name
    last = toks[-1]
    if last.lower() in {"ii", "iii", "iv", "jr", "sr"} and len(toks) > 1:
        last = toks[-2]
    return last


def _avatar_slug(name: str) -> str:
    """Slug used to look up a bundled avatar (matches the on-disk filenames)."""
    return slugify(name).rstrip(".")


def _placeholder_tile(cols: int = 14):
    """A fixed-size dark tile with a centered red ✕ — stands in for a name we
    intentionally did not generate (e.g. Adolf Hitler) so the gallery grid stays whole."""
    rows = max(2, cols // 2)
    mid = rows // 2
    lines = []
    for i in range(rows):
        chars = [" "] * cols
        if i == mid:
            chars[cols // 2] = "✕"
        lines.append(Text("".join(chars), style=f"bold red on {cardlib.TRACK}"))
    return Group(*lines)


# --------------------------------------------------------------------------
# board
# --------------------------------------------------------------------------
def cmd_board(slice_: str = "top"):
    rows = get(f"/api/leaderboard?slice={urllib.parse.quote(slice_)}")
    if not rows:
        console.print("[yellow]empty / unknown slice[/]")
        return
    vmax = max((r.get("weight", 0) for r in rows), default=1)

    table = Table(
        title=f"⚖  IN THE WEIGHTS  ·  leaderboard [dim]({slice_})[/]",
        box=box.ROUNDED, border_style="bright_black", header_style="bold white",
        title_style="bold bright_magenta", expand=True,
    )
    table.add_column("#", justify="right", style="bold bright_black", width=4)
    table.add_column("Name", style="bold", no_wrap=True)
    table.add_column("Weight", justify="right", style="bright_green", width=6)
    table.add_column("", width=24)  # bar
    table.add_column("Category", no_wrap=True)
    table.add_column("Descriptor", style="dim italic", overflow="ellipsis", no_wrap=True)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for r in rows:
        rank = r.get("rank")
        cat = r.get("category")
        w = r.get("weight", 0)
        table.add_row(
            medals.get(rank, str(rank)),
            r.get("name", "?"),
            str(w),
            bar(w, vmax, color=cat_style(cat)),
            Text(cat or "—", style=cat_style(cat)),
            r.get("descriptor", ""),
        )
    console.print(table)
    console.print(f"[dim]{len(rows)} entries · weights are cross-model consensus · "
                  f"look up any name with [bold]itw \"<name>\"[/][/]")


# --------------------------------------------------------------------------
# lookup (share card + optional per-model detail) — the primary command
# --------------------------------------------------------------------------
def _spaced(s: str) -> str:
    """Letter-spaced uppercase, matching the card's monospace look."""
    return " ".join(s.upper())


def _model_bar(fill_pct: int, value: int, color: str, width: int = 22) -> Text:
    """A brand-colored confidence bar with the numeric value appended, so rows stay
    legible even when several models max out and the bars look identical."""
    fill = max(0, min(width, round(width * fill_pct / 100)))
    t = Text()
    t.append("█" * fill, style=color)
    t.append("█" * (width - fill), style=cardlib.TRACK)
    t.append(f" {value:>3}", style=f"bold {cardlib.FG}")
    return t


def _card_renderable(data: dict, name: str, cols: int):
    """Build the compact share card: a small avatar on the left, the name / descriptor /
    strength header to its right, and the per-model confidence bars in a snug block
    below."""
    ref = (data.get("referents") or [{}])[0]
    models = data.get("models") or []
    cells = ref.get("cells") or {}
    fg, accent = cardlib.FG, cardlib.ACCENT

    # avatar: prefer our own bundled pixel avatar, then the site's hosted one, else none
    img = local_avatar(_avatar_slug(name))
    if img is None:
        av = avatar_url(slugify(name))
        if avatar_exists(av):
            img = fetch_bytes(av, slug=slugify(name))
    # last resort: our generic generated silhouette so the card never looks empty
    if img is None:
        img = local_avatar("_placeholder")
    avatar = None
    if img:
        try:
            # full-detail avatar (~32x32) — small renders turn the face to mush
            avatar = render_avatar(img, cols=32)
        except Exception:  # noqa: BLE001
            avatar = None

    # values
    cname = ref.get("canonicalName") or data.get("query", name)
    strength = cardlib.strength(ref, models)
    wr = ref.get("weightRank") or {}
    top = cardlib.top_pct(wr.get("rank"), wr.get("total"))
    stat = f"❯ {strength} STRENGTH" + (f" · {top.upper()} ❮" if top else " ❮")

    # per-model rows: shortened label + brand-colored confidence bar (+ number).
    # full labels and the "<model> says" snippet live in --detail.
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="left", no_wrap=True)
    grid.add_column(justify="left", no_wrap=True)
    for m in models:
        mid = m.get("id")
        c = cells.get(mid) or {}
        ok = c.get("status") == "ok"
        raw_conf = c.get("confidence", 0) if ok else 0
        fill_pct = cardlib.bar_fill_pct(raw_conf) if ok else 0
        try:
            conf = max(0, min(100, int(round(float(raw_conf)))))
        except (TypeError, ValueError):
            conf = 0
        grid.add_row(
            Text(_short_model_label(m.get("label", mid)).upper(), style=fg),
            _model_bar(fill_pct, conf, cardlib.brand_color(mid), width=10),
        )

    # avatar on top (full detail), then centered header, then the bars block.
    blocks: list = []
    if avatar is not None:
        blocks.append(Align.center(avatar))
        blocks.append(Text(""))
    blocks.append(Align.center(Text(_spaced(cname), style=f"bold {fg}")))
    desc = ref.get("canonicalDescriptor")
    if desc:
        blocks.append(Align.center(Text(desc, style=f"dim {fg}")))
    blocks.append(Text(""))
    blocks.append(Align.center(Text(stat, style=f"bold {accent}")))
    blocks.append(Text(""))
    blocks.append(Align.center(grid))
    blocks.append(Text(""))
    # clickable footer: OSC 8 hyperlink to THIS person's profile page on the site
    # (opens in the default browser on Ghostty / iTerm2 / kitty / WezTerm)
    profile_url = f"{BASE}/p/{slugify(name)}"
    permalink = profile_url.replace("https://", "").replace("http://", "")
    blocks.append(Align.right(Text(permalink, style=f"dim underline {fg} link {profile_url}")))

    return Panel(
        Group(*blocks), box=box.ROUNDED, border_style=fg,
        style=f"on {cardlib.BG}", padding=(1, 3), width=min(console.width, 56),
    )


def _detail_view(data: dict):
    """The deeper breakdown shown under the card with `--detail`: the headline model
    snippet, then the per-model recognition table (scores, tiers, evidence) + grader
    footer."""
    ref = (data.get("referents") or [{}])[0]
    cells = ref.get("cells") or {}
    models = data.get("models") or []
    by_id = {m.get("id"): m for m in models}

    # "<model> says" headline snippet — readable normal case (the card omits this)
    disp = ref.get("displaySnippet") or {}
    if disp.get("text"):
        says_label = (by_id.get(disp.get("modelId"), {}).get("label")
                      or disp.get("modelId") or "AI")
        snip = Text()
        snip.append(f"{says_label} says  ", style="bold cyan")
        snip.append(disp["text"], style="italic")
        console.print(snip)
        console.print("")

    table = Table(box=box.SIMPLE_HEAD, header_style="bold white",
                  title="per-model recognition", title_style="bold cyan", pad_edge=False)
    table.add_column("Model", style="bold", no_wrap=True, width=18)
    table.add_column("Tier", no_wrap=True, width=8)
    table.add_column("Score", justify="right", width=6)
    table.add_column("", width=22, no_wrap=True)
    table.add_column("Evidence", style="dim italic", overflow="ellipsis",
                     no_wrap=True, width=max(20, console.width - 60))

    ordered = sorted(cells.items(),
                     key=lambda kv: kv[1].get("recognitionScore", 0), reverse=True)
    for mid, c in ordered:
        m = by_id.get(mid, {})
        tier = m.get("displayTier") or m.get("paramClass") or "—"
        score = c.get("recognitionScore", 0)
        col = "bright_green" if score >= 90 else "yellow" if score >= 50 else "red"
        snips = c.get("evidenceSnippets") or []
        ev = snips[0].get("text", "") if snips else ""
        table.add_row(
            m.get("label") or mid,
            Text(tier, style=TIER_COLOR.get(tier, "white")),
            Text(str(score), style=col),
            bar(score, 100, color=col),
            ev,
        )
    console.print(table)

    clus = data.get("clusteringModel") or {}
    foot = (f"grader: [bold]{clus.get('label', '?')}[/] ({clus.get('method','?')})   ·   "
            f"prompt: [dim]{data.get('promptVersion','?')}[/]   ·   "
            f"roster: [dim]{data.get('rosterVersion','?')}[/]")
    console.print(Panel(foot, border_style="bright_black", box=box.MINIMAL))


def cmd_lookup(name: str, cols: int = 64, detail: bool = False):
    """Look up a name: the share card (avatar + strength + per-model bars), plus the
    per-model evidence breakdown when `detail` is set. One network fetch for both."""
    slug = slugify(name)
    data = get(f"/api/result/{urllib.parse.quote(slug)}")
    if not data:
        console.print(f"[yellow]no result for[/] [bold]{name}[/] "
                      f"[dim](slug: {slug}) — that name hasn't been searched on the site yet[/]")
        return
    console.print(_card_renderable(data, name, cols=cols))
    if detail:
        _detail_view(data)


# --------------------------------------------------------------------------
# top — tiled gallery of our pixel avatars for the leaderboard's top names
# --------------------------------------------------------------------------
_TILE_COLS = 16  # avatar width per gallery tile


def _gallery_tile(name: str, rank, cols: int = _TILE_COLS):
    """One gallery cell: our bundled avatar (or a red ✕ placeholder) above a short
    name + rank."""
    img = local_avatar(_avatar_slug(name))
    if img is not None:
        try:
            art = render_avatar(img, cols=cols)
        except Exception:  # noqa: BLE001
            art = _placeholder_tile(cols)
    else:
        art = _placeholder_tile(cols)
    label = Text(justify="center")
    label.append(_short_name(name), style="bold white")
    label.append(f"  #{rank}", style="dim")
    return Group(art, label)


def cmd_top(per_row: int = 0):
    """Render the leaderboard's top names as a tiled pixel-avatar gallery.

    `per_row` defaults to as many tiles as fit the current terminal width so the
    panel never exceeds the terminal (overflow would wrap into a broken left edge)."""
    rows = get("/api/leaderboard?slice=top")
    if not rows:
        console.print("[yellow]leaderboard unavailable[/]")
        return

    if per_row <= 0:
        # each cell ≈ tile width + grid padding (2 each side); leave room for the
        # panel border + padding. Clamp to a sane 2..5 range.
        avail = console.width - 8
        per_row = max(2, min(5, avail // (_TILE_COLS + 4)))

    grid = Table.grid(padding=(1, 2))
    for _ in range(per_row):
        grid.add_column(justify="center")

    tiles = [_gallery_tile(r.get("name", "?"), r.get("rank", "?")) for r in rows]
    for i in range(0, len(tiles), per_row):
        chunk = tiles[i:i + per_row]
        chunk += [Text("")] * (per_row - len(chunk))  # pad the last row
        grid.add_row(*chunk)

    console.print(Panel(
        grid, box=box.ROUNDED, border_style="bright_magenta",
        title="[bold bright_magenta]⬛  IN THE WEIGHTS  ·  top 20[/]",
        padding=(1, 2),
    ))
    console.print("[dim]our generated pixel avatars · ✕ = intentionally omitted · "
                  "look one up with [bold]itw \"<name>\"[/][/]")
