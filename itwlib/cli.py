"""Argument dispatch / entrypoint. Hand-rolled argv parsing — no dependency.

Surface is deliberately tiny: a single name lookup plus the leaderboard.
  itw "<name>"            profile card (avatar + strength + per-model bars)
  itw "<name>" --detail   + per-model evidence & tiers
  itw board [slice]       leaderboard
"""
from __future__ import annotations

import sys

from rich.panel import Panel

from itwlib import __version__
from itwlib.config import console
from itwlib import commands

USAGE = Panel(
    "[bold bright_magenta]itw[/] — intheweights.com CLI\n\n"
    "[cyan]itw [bold]\"<name>\"[/bold][/]            ⭐ profile card — avatar + strength + model bars\n"
    "[cyan]itw [bold]\"<name>\"[/bold] --detail[/]   per-model evidence & tiers\n"
    "[cyan]itw [bold]<a> v <b>[/bold][/]        head-to-head (winner left)\n"
    "[cyan]itw top[/]                  the top 20 as a pixel-avatar gallery\n"
    "[cyan]itw board[/] [dim][slice][/]        leaderboard table\n"
    "[cyan]itw generate [bold]\"<name>\"[/bold][/]  make your own avatar [dim](needs OPENROUTER_API_KEY)[/]\n"
    "[cyan]itw update[/]               check for a newer release & upgrade\n\n"
    "[dim]flags:[/] [cyan]--detail[/] · [cyan]--check[/] · [cyan]--version[/] · [cyan]-h/--help[/]\n"
    "[dim]read-only — never writes to the site. unofficial & unaffiliated.[/]",
    title="usage", border_style="bright_magenta")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "--version" in args:
        console.print(f"itw {__version__}")
        return 0

    # global flags, stripped before positional parsing
    detail = "--detail" in args
    check = "--check" in args
    args = [a for a in args if a not in ("--detail", "--check")]

    cmd = args[0] if args else "help"

    if cmd in ("-h", "--help", "help"):
        console.print(USAGE)
        return 0

    if cmd == "update":
        return _cmd_update(check=check)

    if cmd == "top":
        commands.cmd_top()
        return 0

    if cmd == "board":
        commands.cmd_board(args[1] if len(args) > 1 else "top")
        return 0

    if cmd == "generate":
        rest = args[1:]
        if not rest:
            console.print("[red]generate needs a <name>[/]  e.g. [dim]itw generate \"tiger woods\"[/]")
            return 2
        return _cmd_generate(" ".join(rest))

    # head-to-head: `itw <a> v <b>` — split the name tokens on the first standalone
    # `v`/`vs`/`versus` separator (case-insensitive); winner is rendered on the left.
    seps = {"v", "vs", "versus"}
    for i, tok in enumerate(args):
        if tok.lower() in seps:
            left = " ".join(args[:i]).strip()
            right = " ".join(args[i + 1:]).strip()
            if left and right:
                commands.cmd_versus(left, right)
                return 0
            break

    # everything else is a name lookup (quotes optional: `itw paul mccartney`)
    name = " ".join(args).strip()
    if not name:
        console.print(USAGE)
        return 0
    commands.cmd_lookup(name, detail=detail)
    return 0


def _cmd_generate(name: str) -> int:
    """Generate your own pixel avatar for `name` with your OpenRouter key, then render."""
    import os

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        console.print("[red]OPENROUTER_API_KEY is not set.[/]\n"
                      "[dim]Get a key at https://openrouter.ai/keys, then:[/] "
                      "[cyan]export OPENROUTER_API_KEY=sk-or-...[/]")
        return 2

    from itwlib import generate as gen

    console.print(f"[dim]generating a pixel avatar for[/] [bold]{name}[/] "
                  f"[dim](image model + quantize, ~$0.04)…[/]")
    try:
        path, cost = gen.generate_avatar(name, key)
    except gen.GenerateError as e:
        console.print(f"[red]generation failed:[/] {e}")
        return 1
    console.print(f"[green]saved →[/] {path}  [dim](${cost:.4f})[/]")
    console.print(f"[dim]now run[/] [cyan]itw \"{name}\"[/] [dim]to see it.[/]")
    return 0


def _cmd_update(check: bool = False) -> int:
    """Compare the running version to the latest GitHub Release and, unless `--check`,
    offer to upgrade in place via whichever tool (uv/pipx) manages the install."""
    import subprocess

    from itwlib import update as upd

    cur = __version__
    rel = upd.latest_release()
    if rel is None:
        console.print("[dim]couldn't reach GitHub (or no releases yet) — try again later.[/]\n"
                      f"[dim]releases:[/] {upd.RELEASES_URL}")
        return 0

    if not upd.is_newer(rel.tag, cur):
        console.print(f"[green]✓[/] itw [bold]{cur}[/] is the latest.")
        return 0

    console.print(f"[yellow]update available[/]  [dim]{cur}[/] → [bold]{rel.tag.lstrip('v')}[/]\n"
                  f"[dim]notes:[/] {rel.url}")
    if check:
        return 0

    cmd = upd.upgrade_cmd()
    if cmd is None:
        console.print(f"[dim]upgrade with:[/] [cyan]{upd.MANUAL_CMD}[/]")
        return 0

    pretty = " ".join(cmd)
    if not sys.stdin.isatty():  # non-interactive: don't block on a prompt, just show it
        console.print(f"[dim]upgrade with:[/] [cyan]{pretty}[/]")
        return 0

    try:
        ans = console.input(f"[bold]upgrade now?[/] [dim]({pretty})[/] [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return 0
    if ans not in ("y", "yes"):
        console.print(f"[dim]skipped — run[/] [cyan]{pretty}[/] [dim]when ready.[/]")
        return 0

    console.print(f"[dim]running[/] [cyan]{pretty}[/]…")
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        console.print(f"[green]✓[/] upgraded to [bold]{rel.tag.lstrip('v')}[/].")
    else:
        console.print(f"[red]upgrade exited with {rc}[/] — try [cyan]{pretty}[/] manually.")
    return rc
