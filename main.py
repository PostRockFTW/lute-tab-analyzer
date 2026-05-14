"""
Lute Tablature Analyzer — CLI entry point.

Commands:
  search    Search wp.lutemusic.org for pieces by keyword.
  list      List all .tab files available for a composer.
  download  Download a .tab file from lutemusic.org.
  analyze   Load a .tab or .ft3 file and enter an interactive AI query loop.
  compare   Load two files and report structural differences (validation).

Usage:
  python main.py search "dowland galliard"
  python main.py list Dowland
  python main.py download Dowland 40_king_of_denmarks_galliard_long
  python main.py analyze path/to/piece.tab
  python main.py compare piece.ft3 piece.tab
"""

import sys
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def _load_piece(path: str):
    """Detect format and parse file into a Piece model."""
    from src.models import Piece

    p = Path(path)
    if not p.exists():
        console.print(f"[red]File not found:[/red] {path}")
        sys.exit(1)

    suffix = p.suffix.lower()

    if suffix == ".ft3":
        from src.parser.fronimo import parse_ft3_file, LuteconvNotFoundError
        try:
            piece = parse_ft3_file(p)
        except LuteconvNotFoundError as e:
            console.print(f"[red]luteconv not available:[/red]\n{e}")
            sys.exit(1)
        except RuntimeError as e:
            console.print(f"[red]Conversion failed:[/red]\n{e}")
            sys.exit(1)
    else:
        from src.parser.tab_parser import parse_tab_file
        text = p.read_text(encoding="utf-8", errors="replace")
        piece = parse_tab_file(text)

    return piece


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
def cli():
    pass


def _print_piece_summary(piece) -> None:
    title = piece.title or "(untitled)"
    composer = piece.composer or "(unknown composer)"
    console.print(f"\n[bold cyan]{title}[/bold cyan]  [dim]—[/dim]  [italic]{composer}[/italic]")
    if piece.tuning:
        console.print(f"  Tuning: {piece.tuning}")
    if piece.time_signature:
        console.print(f"  Time:   {piece.time_signature}")
    total_beats = sum(len(b.beats) for b in piece.bars)
    console.print(
        f"  Bars: {len(piece.bars)}  |  Beats: {total_beats}  |  "
        f"Courses: {piece.num_courses}  |  Format: {piece.source_format}"
    )
    console.print()


# ── search command ────────────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
def search(query: str):
    """Search wp.lutemusic.org for pieces matching QUERY."""
    from src.downloader import search_pieces
    console.print(f"Searching for [bold]{query}[/bold]...")
    try:
        results = search_pieces(query)
    except Exception as e:
        console.print(f"[red]Search failed:[/red] {e}")
        return
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    table = Table(title=f"Results for '{query}'", show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="cyan")
    table.add_column("URL", style="dim")
    for i, r in enumerate(results, 1):
        table.add_row(str(i), r["title"], r["url"])
    console.print(table)


# ── list command ───────────────────────────────────────────────────────────────

@cli.command(name="list")
@click.argument("composer")
def list_tabs(composer: str):
    """List all .tab files available for COMPOSER on lutemusic.org."""
    from src.downloader import list_composer_tabs
    console.print(f"Listing .tab files for [bold]{composer}[/bold]...")
    try:
        files = list_composer_tabs(composer)
    except Exception as e:
        console.print(f"[red]Failed:[/red] {e}")
        return
    if not files:
        console.print("[yellow]No .tab files found.[/yellow]")
        return
    for f in files:
        console.print(f"  {f}")
    console.print(f"\n[dim]{len(files)} files[/dim]")


# ── download command ───────────────────────────────────────────────────────────

@cli.command()
@click.argument("composer")
@click.argument("filename")
@click.option("--out", "-o", default=".", help="Output directory (default: current dir)")
def download(composer: str, filename: str, out: str):
    """Download a .tab file from lutemusic.org.

    Example: python main.py download Dowland 40_king_of_denmarks_galliard_long
    """
    from src.downloader import download_tab
    console.print(f"Downloading [bold]{filename}[/bold] by {composer}...", end=" ")
    try:
        dest = download_tab(composer, filename, dest_dir=out)
    except Exception as e:
        console.print(f"\n[red]Failed:[/red] {e}")
        return
    console.print(f"[green]saved to {dest}[/green]")
    console.print(f"[dim]Run: python main.py analyze \"{dest}\"[/dim]")


# ── download-pdf command ──────────────────────────────────────────────────────

@cli.command(name="download-pdf")
@click.argument("composer")
@click.argument("filename")
@click.option("--out", "-o", default=".", help="Output directory (default: current dir)")
def download_pdf(composer: str, filename: str, out: str):
    """Download the PDF for a piece from lutemusic.org.

    Example: python main.py download-pdf Dowland 23a_frogg_galliard_2
    """
    from src.downloader import download_pdf as _dl_pdf
    console.print(f"Downloading PDF for [bold]{filename}[/bold] by {composer}...", end=" ")
    try:
        dest = _dl_pdf(composer, filename, dest_dir=out)
    except FileNotFoundError as e:
        console.print(f"\n[red]Not found:[/red] {e}")
        return
    except Exception as e:
        console.print(f"\n[red]Failed:[/red] {e}")
        return
    console.print(f"[green]saved to {dest}[/green]")


# ── analyze command ────────────────────────────────────────────────────────────


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--tuning", "-T",
    default=None,
    metavar="PITCHES",
    help=(
        'Open-string pitches, course 1 first (highest string). '
        'Example: "E4,B3,F#3,D3,A2,E2" for guitar with F# third string. '
        'Default: standard Renaissance lute G-tuning (G4,D4,A3,F3,C3,G2).'
    ),
)
def analyze(file: str, tuning: str | None):
    """
    Load a lute tablature file (.tab or .ft3) and enter an interactive
    AI-powered query loop.

    Example queries:
      "find all D minor chords"
      "count how many times course 1 plays open"
      "show me bar 5"
      "where does the melody emphasise the interval of a tritone"
    """
    from src.pitch_utils import parse_tuning_string, STANDARD_LUTE, note_name

    resolved_tuning = STANDARD_LUTE
    if tuning:
        try:
            resolved_tuning = parse_tuning_string(tuning)
        except ValueError as e:
            console.print(f"[red]Invalid tuning:[/red] {e}")
            sys.exit(1)

    console.print("[bold]Loading...[/bold]", end=" ")
    piece = _load_piece(file)
    console.print("[green]done[/green]")
    _print_piece_summary(piece)

    # Show first-chord sanity check
    if piece.bars and piece.bars[0].beats:
        first_beat = piece.bars[0].beats[0]
        if first_beat.notes:
            pitches = [
                f"{note_name(n.course, n.fret, resolved_tuning)} (c{n.course}:{n.letter})"
                for n in first_beat.notes
            ]
            tuning_label = tuning if tuning else "standard G-tuning"
            console.print(
                f"  [dim]First chord ({tuning_label}):[/dim] "
                + ", ".join(pitches)
            )
            console.print()

    from src.ai_interface import StreamingAnalyzer
    analyzer = StreamingAnalyzer(piece, tuning=resolved_tuning)

    console.print("[dim]Type your query, or 'quit' / Ctrl-C to exit.[/dim]\n")
    while True:
        try:
            query = console.input("[bold yellow]Query>[/bold yellow] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye.[/dim]")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            console.print("[dim]Bye.[/dim]")
            break

        console.print()
        try:
            analyzer.analyze(query)
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
        console.print()


# ── compare command ────────────────────────────────────────────────────────────

@cli.command()
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
def compare(file_a: str, file_b: str):
    """
    Parse two tablature files and report structural differences.

    Useful for confirming that a Fronimo .ft3 file and its Wayne Cripps .tab
    counterpart encode the same music.
    """
    console.print(f"[bold]Loading[/bold] {Path(file_a).name}...", end=" ")
    piece_a = _load_piece(file_a)
    console.print("[green]done[/green]")

    console.print(f"[bold]Loading[/bold] {Path(file_b).name}...", end=" ")
    piece_b = _load_piece(file_b)
    console.print("[green]done[/green]\n")

    differences: list[str] = []

    # Bar count
    if len(piece_a.bars) != len(piece_b.bars):
        differences.append(
            f"Bar count differs: {Path(file_a).name} has {len(piece_a.bars)}, "
            f"{Path(file_b).name} has {len(piece_b.bars)}"
        )

    # Per-bar beat and note comparison
    for idx, (bar_a, bar_b) in enumerate(zip(piece_a.bars, piece_b.bars), start=1):
        if len(bar_a.beats) != len(bar_b.beats):
            differences.append(
                f"Bar {idx}: beat count differs "
                f"({len(bar_a.beats)} vs {len(bar_b.beats)})"
            )
            continue

        for beat_idx, (beat_a, beat_b) in enumerate(zip(bar_a.beats, bar_b.beats), start=1):
            if beat_a.duration != beat_b.duration:
                differences.append(
                    f"Bar {idx}, beat {beat_idx}: duration differs "
                    f"({beat_a.duration} vs {beat_b.duration})"
                )

            notes_a = {(n.course, n.fret) for n in beat_a.notes}
            notes_b = {(n.course, n.fret) for n in beat_b.notes}
            only_a = notes_a - notes_b
            only_b = notes_b - notes_a

            if only_a:
                differences.append(
                    f"Bar {idx}, beat {beat_idx}: notes only in A: {sorted(only_a)}"
                )
            if only_b:
                differences.append(
                    f"Bar {idx}, beat {beat_idx}: notes only in B: {sorted(only_b)}"
                )

    # Summary
    table = Table(title="Comparison Summary", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column(Path(file_a).name, style="white")
    table.add_column(Path(file_b).name, style="white")

    table.add_row("Title", piece_a.title or "—", piece_b.title or "—")
    table.add_row("Composer", piece_a.composer or "—", piece_b.composer or "—")
    table.add_row("Bars", str(len(piece_a.bars)), str(len(piece_b.bars)))
    total_a = sum(len(b.beats) for b in piece_a.bars)
    total_b = sum(len(b.beats) for b in piece_b.bars)
    table.add_row("Total beats", str(total_a), str(total_b))
    table.add_row("Format", piece_a.source_format, piece_b.source_format)

    console.print(table)
    console.print()

    if differences:
        console.print(f"[red]Found {len(differences)} difference(s):[/red]")
        for diff in differences[:50]:  # cap at 50 to avoid wall of text
            console.print(f"  • {diff}")
        if len(differences) > 50:
            console.print(f"  … and {len(differences) - 50} more.")
    else:
        console.print("[green]✓ No structural differences found.[/green]")


if __name__ == "__main__":
    cli()
