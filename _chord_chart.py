"""
Build a period-accurate chord chart from all Dowland analysis files.

Finds: major, minor, dom7, dim7, diminished (triad), half-dim7, min7 chords
for every root that appears in the corpus, showing the max-string voicings
and citing which pieces they come from.

Only chords that contain the full required intervals (root + 3rd + 5th,
plus 7th where applicable) are included — "no 5th" / "no 3rd" partials
are excluded.

For each chord, 6-course voicings are preferred; if none exist, the
best 7- or 8-course voicing is included and flagged with an asterisk.

Usage: python _chord_chart.py [--out analysis/_chord_chart.txt]
"""

import os
import glob
import re
import argparse
from collections import defaultdict

CHORD_TYPES = [
    ("major",      "Major"),
    ("minor",      "Minor"),
    ("dom7",       "Dominant 7th"),
    ("min7",       "Minor 7th"),
    ("dim7",       "Diminished 7th"),
    ("diminished", "Diminished (triad)"),
    ("half-dim7",  "Half-Diminished 7th"),
    ("aug",        "Augmented"),
    ("maj7",       "Major 7th"),
]

NOTE_ORDER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_RANK  = {n: i for i, n in enumerate(NOTE_ORDER)}

# French lute fret letters → fret number (j skipped)
_FRET_LETTERS = "abcdefghiklmn"
_LETTER_TO_FRET = {ch: i for i, ch in enumerate(_FRET_LETTERS)}


def poulton_number(filename: str) -> str:
    """Extract the Poulton number prefix from a filename (e.g. '23a' from '23a_frogg...')."""
    m = re.match(r"^(\d+[a-z]?)_", filename)
    return m.group(1) if m else ""


def piece_title(filename: str) -> str:
    """'23a_frogg_galliard_2_chords.txt' → 'P.23a Frogg Galliard 2'"""
    stem = filename.replace("_chords.txt", "")
    pnum = poulton_number(stem)
    title = re.sub(r"^\d+[a-z]?_", "", stem).replace("_", " ").title()
    if pnum:
        return f"P.{pnum} {title}"
    return title


def letters_to_frets(fingering: str) -> str:
    """Convert tab-letter fingering to fret-number fingering.
    e.g. '- - a - c - a e' → '- - 0 - 2 - 0 4'
    """
    parts = []
    for slot in fingering.split():
        if slot == "-":
            parts.append("-")
        else:
            fret = _LETTER_TO_FRET.get(slot.lower(), "?")
            parts.append(str(fret))
    return " ".join(parts)


def slot_count(fingering: str) -> int:
    return sum(1 for s in fingering.split() if s != "-")


def needs_extra_courses(fingering: str) -> bool:
    """True if the fingering uses courses 7 or 8 (first two slots of an 8-slot fingering)."""
    slots = fingering.split()
    if len(slots) <= 6:
        return False
    return slots[0] != "-" or slots[1] != "-"


def to_display(fingering: str) -> str:
    """For 8-slot fingerings that only use courses 1-6, strip the leading two dash slots."""
    slots = fingering.split()
    if len(slots) == 8 and slots[0] == "-" and slots[1] == "-":
        return " ".join(slots[2:])
    return fingering


def parse_all_analysis() -> dict:
    """
    Returns:
        {chord_name: [(piece_filename, bar, raw_fingering, pitches, n_notes), ...]}
    """
    data = defaultdict(list)

    for path in sorted(glob.glob("analysis/*_chords.txt")):
        fname = os.path.basename(path)
        in_main = False

        for line in open(path, encoding="utf-8"):
            if line.startswith("| Bar"):
                in_main = True
                continue
            if line.startswith("## Summary") or line.startswith("---"):
                in_main = False
            if not in_main:
                continue
            if not line.startswith("|") or line.startswith("|--") or line.startswith("|-"):
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6:
                continue

            fingering  = parts[3]
            pitches    = parts[4]
            chord_name = parts[5]

            chord_type = None
            for key, _ in CHORD_TYPES:
                if chord_name.endswith(" " + key):
                    chord_type = key
                    break
            if chord_type is None:
                continue

            n = slot_count(fingering)
            data[chord_name].append((fname, fingering, pitches, n))

    return data


def _best_voicings(occurrences: list, predicate) -> list[dict]:
    """
    From occurrences matching predicate, return all unique fingerings that tie
    for the maximum note count.
    """
    subset = [(fn, f, pi, n) for fn, f, pi, n in occurrences if predicate(f)]
    if not subset:
        return []
    max_notes = max(n for *_, n in subset)
    fing_info: dict[str, dict] = {}
    for fname, fing, pitches, n_notes in subset:
        if n_notes < max_notes:
            continue
        if fing not in fing_info:
            fing_info[fing] = {"pitches": pitches, "pieces": set()}
        fing_info[fing]["pieces"].add(piece_title(fname))
    return [
        {
            "fingering": fing,
            "frets":     letters_to_frets(fing),
            "pitches":   info["pitches"],
            "n_notes":   max_notes,
            "courses":   len(fing.split()),
            "pieces":    sorted(info["pieces"]),
        }
        for fing, info in fing_info.items()
    ]


def build_chart(data: dict) -> dict:
    """
    Returns:
        {ct_key: {root: [voicing_dict, ...]}}

    For each chord, finds the max-note 6-course voicing(s) AND the max-note
    8-course voicing(s) independently, then combines them. This preserves
    6-course voicings even when higher-note 8-course ones exist.
    """
    chart = defaultdict(lambda: defaultdict(list))

    for chord_name, occurrences in data.items():
        chord_type = root = None
        for key, _ in CHORD_TYPES:
            if chord_name.endswith(" " + key):
                chord_type = key
                root = chord_name[: -(len(key) + 1)]
                break
        if chord_type is None:
            continue

        six_voicings   = _best_voicings(occurrences, lambda f: not needs_extra_courses(f))
        eight_voicings = _best_voicings(occurrences, needs_extra_courses)

        # De-duplicate: skip an 8-course voicing if an identical stripped form
        # already appears in six_voicings (shouldn't happen, but safety check)
        six_fings = {v["fingering"] for v in six_voicings}
        unique_eight = [v for v in eight_voicings if v["fingering"] not in six_fings]

        chart[chord_type][root].extend(six_voicings)
        chart[chord_type][root].extend(unique_eight)

    return chart


def fmt_citations(pieces: list[str], limit: int = 4) -> str:
    if len(pieces) <= limit:
        return "; ".join(pieces)
    return "; ".join(pieces[:limit]) + f" +{len(pieces) - limit} more"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="analysis/_chord_chart.txt")
    args = ap.parse_args()

    data  = parse_all_analysis()
    chart = build_chart(data)

    lines = [
        "# Dowland Corpus — Period-Accurate Chord Voicings",
        "",
        "*Source: 113 Poulton-numbered Dowland lute tablatures from lutemusic.org (CC BY-NC-SA 4.0)*",
        "*Only chords with root + 3rd + 5th (+ 7th where applicable) are shown. Partial voicings excluded.*",
        "*Voicings shown use the maximum number of strings found in the corpus.*",
        "*Tab fingering: bass course on left → treble (course 1) on right. '-' = string not played.*",
        "*Frets: same layout as Tab, but showing fret numbers (0 = open string).*",
        "*Crs: total course slots in the fingering (6 = 6-course lute, 8 = 8-course lute).*",
        "",
    ]

    for ct_key, ct_label in CHORD_TYPES:
        if ct_key not in chart:
            continue

        lines.append(f"## {ct_label}")
        lines.append("")

        headers = ["Root", "Str", "Crs", "Tab Fingering", "Frets", "Pitches", "Appears In"]
        rows = []

        roots = sorted(chart[ct_key].keys(), key=lambda r: NOTE_RANK.get(r, 99))
        for root in roots:
            voicings = sorted(
                chart[ct_key][root],
                key=lambda v: (-v["n_notes"], v["fingering"])
            )
            for v in voicings:
                rows.append((
                    root,
                    str(v["n_notes"]),
                    str(v["courses"]),
                    v["fingering"],
                    v["frets"],
                    v["pitches"],
                    fmt_citations(v["pieces"]),
                ))

        col_w = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_w[i] = max(col_w[i], len(cell))

        def fmt_row(cells, widths=col_w):
            return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

        sep = "|-" + "-|-".join("-" * w for w in col_w) + "-|"

        lines.append(fmt_row(headers))
        lines.append(sep)
        for row in rows:
            lines.append(fmt_row(row))
        lines.append("")

    result = "\n".join(lines)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Chord chart written to {args.out}")
    print()
    for ct_key, ct_label in CHORD_TYPES:
        if ct_key not in chart:
            print(f"  {ct_label}: (none found)")
            continue
        roots = sorted(chart[ct_key].keys(), key=lambda r: NOTE_RANK.get(r, 99))
        extra = [r for r in roots if any(v["courses"] == 8 for v in chart[ct_key][r])]
        tag = f"  [{', '.join(extra)} have 8-course voicings]" if extra else ""
        print(f"  {ct_label}: {len(roots)} roots  [{', '.join(roots)}]{tag}")


if __name__ == "__main__":
    main()
