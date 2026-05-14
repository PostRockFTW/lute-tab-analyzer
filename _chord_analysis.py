"""
Algorithmic chord analysis for a .tab file.
No Claude API required — all pitch/chord identification is local.

Usage:
    python _chord_analysis.py <file.tab> [--min-notes N] [--out output.txt]
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from src.parser.tab_parser import parse_tab_file
from src.pitch_utils import parse_tuning_string, note_name

TUNING_STR = "E4,B3,F#3,D3,A2,E2,D2,B1"

# ── Duration → quarter-note units (dotted adds 50%) ─────────────────────────
DURATION_QUARTERS = {
    "longa":        8.0,
    "whole":        4.0,
    "half":         2.0,
    "quarter":      1.0,
    "eighth":       0.5,
    "sixteenth":    0.25,
    "thirty_second":0.125,
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# French tablature fret letters (j is skipped historically)
_FRET_LETTERS = ['a','b','c','d','e','f','g','h','i','k','l','m','n']

def fret_letter(fret: int) -> str:
    if 0 <= fret < len(_FRET_LETTERS):
        return _FRET_LETTERS[fret]
    return str(fret)

# Chord templates: (display_label, required_intervals, full_intervals)
# required = must all be present; full = allowed additional notes
CHORD_TEMPLATES = [
    # Triads
    ("major",           {0, 4, 7},          {0, 4, 7}),
    ("minor",           {0, 3, 7},          {0, 3, 7}),
    ("diminished",      {0, 3, 6},          {0, 3, 6}),
    ("augmented",       {0, 4, 8},          {0, 4, 8}),
    # Seventh chords
    ("dom7",            {0, 4, 7, 10},      {0, 4, 7, 10}),
    ("maj7",            {0, 4, 7, 11},      {0, 4, 7, 11}),
    ("min7",            {0, 3, 7, 10},      {0, 3, 7, 10}),
    ("half-dim7",       {0, 3, 6, 10},      {0, 3, 6, 10}),
    ("dim7",            {0, 3, 6, 9},       {0, 3, 6, 9}),
    # Partial triads (root + third, no fifth)
    ("major (no 5th)",  {0, 4},             {0, 4}),
    ("minor (no 5th)",  {0, 3},             {0, 3}),
    # Power / open fifth
    ("(no 3rd)",        {0, 7},             {0, 7}),
]


def pitch_class_int(midi: int) -> int:
    return midi % 12


def identify_chord(midi_notes: list[int]) -> str:
    """Return the best chord name for a set of MIDI notes."""
    pcs = {pitch_class_int(m) for m in midi_notes}

    best_label = None
    best_score = (-1, -1)  # (coverage, -extras) — maximise both

    for root_pc in range(12):
        if root_pc not in pcs:
            continue  # root must be present
        for label, required, full in CHORD_TEMPLATES:
            req_pcs = {(root_pc + i) % 12 for i in required}
            full_pcs = {(root_pc + i) % 12 for i in full}

            if not req_pcs.issubset(pcs):
                continue  # required notes missing

            covered = len(pcs & full_pcs)
            extras = len(pcs - full_pcs)

            # Prefer more coverage; penalise extra notes outside the chord
            score = (covered, -extras)
            if score > best_score:
                best_score = score
                best_label = f"{NOTE_NAMES[root_pc]} {label}"

    if best_label is None:
        # Fallback: list pitch-class names
        best_label = "/".join(NOTE_NAMES[pc] for pc in sorted(pcs))

    return best_label


def beat_position(beats: list, idx: int) -> float:
    """Return 1-based quarter-note beat position of beat[idx] within the bar."""
    pos = 1.0
    for i, b in enumerate(beats):
        if i == idx:
            return pos
        dur = DURATION_QUARTERS.get(b.duration, 1.0)
        if b.dotted:
            dur *= 1.5
        pos += dur
    return pos


def fmt_beat(pos: float) -> str:
    """Format a beat position as a readable string (e.g. 1, 1.5, 2)."""
    if pos == int(pos):
        return str(int(pos))
    return f"{pos:.3g}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tab_file", nargs="?", default="tabs/23a_frogg_galliard_2.tab")
    parser.add_argument("--min-notes", type=int, default=3)
    parser.add_argument("--tuning", default=TUNING_STR)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    tuning = parse_tuning_string(args.tuning)

    with open(args.tab_file, encoding="utf-8", errors="replace") as f:
        piece = parse_tab_file(f.read())

    stem = os.path.splitext(os.path.basename(args.tab_file))[0]
    out_file = args.out or f"analysis/{stem}_chords.txt"

    rows = []
    chord_counts: dict[str, int] = {}  # chord name → count (for console summary)
    # fingering_key → {"chord": str, "count": int, "notes": int}
    fingering_summary: dict[str, dict] = {}

    for bar in piece.bars:
        for idx, beat in enumerate(bar.beats):
            if beat.is_rest or len(beat.notes) < args.min_notes:
                continue

            valid_notes = [n for n in beat.notes if n.course <= len(tuning.courses)]
            if len(valid_notes) < args.min_notes:
                continue
            midis = [tuning.open_pitch(n.course) + n.fret for n in valid_notes]
            num_courses = len(tuning.courses)
            course_map = {n.course: n for n in valid_notes if 1 <= n.course <= num_courses}
            fingering_slots = []
            ordered_pitches = []
            for c in range(num_courses, 0, -1):  # bass (high course#) on left
                if c in course_map:
                    n = course_map[c]
                    fingering_slots.append(fret_letter(n.fret))
                    ordered_pitches.append(note_name(n.course, n.fret, tuning))
                else:
                    fingering_slots.append('-')
            fingerings = fingering_slots
            pitches = ordered_pitches
            chord = identify_chord(midis)
            bpos = beat_position(bar.beats, idx)

            rows.append((bar.number, bpos, fingerings, pitches, chord))
            chord_counts[chord] = chord_counts.get(chord, 0) + 1
            fkey = " ".join(fingerings)
            if fkey not in fingering_summary:
                fingering_summary[fkey] = {"chord": chord, "count": 0, "notes": len(valid_notes)}
            fingering_summary[fkey]["count"] += 1

    # ── Build output ──────────────────────────────────────────────────────────
    title = piece.title or os.path.basename(args.tab_file)

    headers = ["Bar", "Beat", "Fingering", "Pitches", "Chord Name"]
    table_rows = [
        (str(bar_num), fmt_beat(bpos), " ".join(fingerings), ", ".join(pitches), chord)
        for bar_num, bpos, fingerings, pitches, chord in rows
    ]

    col_widths = [len(h) for h in headers]
    for row in table_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt_row(cells, widths=col_widths):
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    sep = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"

    lines = [
        f"# {title} — Chord Table",
        f"",
        f"*Tuning (bass→treble): {','.join(reversed(args.tuning.split(',')))}. Only beats with {args.min_notes}+ simultaneous notes shown.*",
        f"",
        fmt_row(headers),
        sep,
    ]
    for row in table_rows:
        lines.append(fmt_row(row))

    sum_headers = ["Fingering", "Chord Name", "Occurrences", "Notes"]
    sum_rows = [
        (fkey, entry["chord"], str(entry["count"]), str(entry["notes"]))
        for fkey, entry in sorted(fingering_summary.items(), key=lambda kv: (kv[1]["chord"], kv[0]))
    ]
    sum_widths = [len(h) for h in sum_headers]
    for row in sum_rows:
        for i, cell in enumerate(row):
            sum_widths[i] = max(sum_widths[i], len(cell))

    sum_sep = "|-" + "-|-".join("-" * w for w in sum_widths) + "-|"

    lines += [
        f"",
        f"---",
        f"",
        f"## Summary of Distinct Chord Types",
        f"",
        fmt_row(sum_headers, sum_widths),
        sum_sep,
    ]
    for row in sum_rows:
        lines.append(fmt_row(row, sum_widths))

    result = "\n".join(lines)

    from pathlib import Path
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Wrote {len(rows)} chord entries to {out_file}")
    print()
    print("Top chord types:")
    for chord, count in sorted(chord_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {count:3d}x  {chord}")


if __name__ == "__main__":
    main()
