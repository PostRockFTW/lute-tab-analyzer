"""
Generate ASCII fingering diagrams for all 4+ note chord shapes
found in a tab file, using exact course/fret data from the parser.

Usage:
    python _chord_diagrams.py <file.tab> [--out output.txt] [--tuning ...]
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from src.parser.tab_parser import parse_tab_file
from src.pitch_utils import parse_tuning_string, note_name

TUNING_STR = "E4,B3,F#3,D3,A2,E2,D2,B1"
NUM_COURSES = 8

OPEN_COURSE_NAMES = {1:"E4", 2:"B3", 3:"F#3", 4:"D3", 5:"A2", 6:"E2", 7:"D2", 8:"B1"}

def chord_key(notes):
    return frozenset((n.course, n.fret) for n in notes)

def pitch_for(course, fret, tuning):
    try:
        return note_name(course, fret, tuning)
    except Exception:
        return "?"

def make_diagram(notes, tuning, chord_name, bars):
    """
    Render an ASCII lute chord diagram.

    Courses run top (1) to bottom (8).
    Left side of nut shows open strings (o) or muted (x).
    Right of nut shows a fret grid; fretted notes shown as *.
    Only courses 1-6 typically shown unless c7/c8 are fretted.
    """
    played = {n.course: n.fret for n in notes}
    max_course = max(played.keys())
    # Always show at least 6 courses for context
    total_courses = max(6, max_course)

    max_fret = max(played.values())
    # Show at least 4 frets; scale up if needed
    fret_cols = max(4, max_fret + 1)

    # Build pitch label for played notes
    pitch_labels = {}
    for c, f in played.items():
        pitch_labels[c] = pitch_for(c, f, tuning)

    # Chord summary
    played_pitches = sorted(
        [pitch_for(c, f, tuning) for c, f in played.items()],
        key=lambda p: -int(p[-1]) if p[-1].isdigit() else 0
    )

    lines = []
    lines.append(f"  {chord_name}")
    lines.append(f"  Bars: {bars}")
    lines.append(f"  Notes: {', '.join(pitch_labels[c] for c in sorted(played))}")
    lines.append("")

    # Header: fret numbers above the grid
    fret_header = "       NUT" + "".join(f"  {f} " for f in range(1, fret_cols))
    lines.append(fret_header)

    for course in range(1, total_courses + 1):
        fret = played.get(course)
        open_marker = "o" if fret == 0 else ("x" if fret is None else " ")

        # Build the fret grid: nut | then one slot per fret
        grid = "|"
        for f in range(1, fret_cols):
            if fret == f:
                grid += "--*-"
            else:
                grid += "----"

        lines.append(f"  c{course}:  {open_marker} {grid}")

    # Fret position footnote if any fret > 5 (position marker)
    if max_fret >= 5:
        lines.append(f"  (fret numbers above; leftmost grid column = fret 1)")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tab_file", nargs="?", default="tabs/23a_frogg_galliard_2.tab")
    parser.add_argument("--tuning", default=TUNING_STR)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    tuning = parse_tuning_string(args.tuning)
    stem = os.path.splitext(os.path.basename(args.tab_file))[0]
    out_file = args.out or f"analysis/{stem}_diagrams.txt"

    with open(args.tab_file, encoding="utf-8", errors="replace") as f:
        piece = parse_tab_file(f.read())

    # Collect all 4+ note beats with their bar numbers
    seen: dict[frozenset, tuple] = {}  # key -> (notes_example, [bar_nums])

    for bar in piece.bars:
        for beat in bar.beats:
            if len(beat.notes) >= 4:
                key = chord_key(beat.notes)
                if key not in seen:
                    seen[key] = (beat.notes, [])
                seen[key][1].append(bar.number)

    if not seen:
        print("No 4+ note chords found.")
        return

    # Group by chord name (derive from pitches)
    # We'll just print them in order of first appearance
    chord_groups = sorted(seen.items(), key=lambda kv: min(kv[1][1]))

    output_lines = []
    output_lines.append("=" * 60)
    output_lines.append(f"  {piece.title or stem} — 4+ Note Chord Fingering Diagrams")
    output_lines.append(f"  Tuning: {args.tuning}")
    output_lines.append("=" * 60)
    output_lines.append("")

    for i, (key, (notes, bars)) in enumerate(chord_groups, 1):
        # Simple chord naming from pitches
        pitches_set = set(pitch_for(n.course, n.fret, tuning)[:-1] for n in notes)  # strip octave
        chord_label = f"Chord {i}"

        bars_str = ", ".join(str(b) for b in sorted(set(bars)))
        diagram = make_diagram(notes, tuning, chord_label, bars_str)
        output_lines.append(diagram)
        output_lines.append("-" * 50)

    result = "\n".join(output_lines)
    print(result)

    # Also write to file
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"\n[Written to {out_file}]")


if __name__ == "__main__":
    main()
