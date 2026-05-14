"""
Pitch resolution for lute tablature.

Maps course + fret → pitch name given a Tuning (list of open-string MIDI notes,
one per course, course 1 first = highest string).
"""

from __future__ import annotations
from dataclasses import dataclass

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Enharmonic aliases accepted on input
_ENHARMONIC: dict[str, str] = {
    "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#",
    "db": "C#", "eb": "D#", "gb": "F#", "ab": "G#", "bb": "A#",
}


def _pitch_to_midi(name: str) -> int:
    """Convert a pitch string like 'G4', 'F#3', 'Bb2' to a MIDI note number."""
    name = name.strip()
    # separate note name from octave digit
    if len(name) >= 2 and name[-1].isdigit():
        octave = int(name[-1])
        note = name[:-1]
    elif len(name) >= 3 and name[-2].isdigit() and name[-1] == "-":
        raise ValueError(f"Unexpected pitch format: {name!r}")
    else:
        raise ValueError(f"Cannot parse pitch: {name!r}")

    note = _ENHARMONIC.get(note, note)
    if note not in _NOTE_NAMES:
        raise ValueError(f"Unknown note name {note!r} in {name!r}")

    return 12 * (octave + 1) + _NOTE_NAMES.index(note)


def _midi_to_name(midi: int) -> str:
    """Convert a MIDI note number to a pitch name like 'G#4'."""
    octave = (midi // 12) - 1
    note = _NOTE_NAMES[midi % 12]
    return f"{note}{octave}"


@dataclass
class Tuning:
    """Open-string pitches for each course, course 1 first (highest string)."""
    courses: list[int]  # MIDI note numbers

    def open_pitch(self, course: int) -> int:
        """Return MIDI note for the open string of a 1-based course number."""
        idx = course - 1
        if idx < 0 or idx >= len(self.courses):
            raise ValueError(f"Course {course} out of range for this tuning")
        return self.courses[idx]


# Standard Renaissance 8-course lute, G-tuning.
# Intervals: P4, P4, M3, P4, P4 for courses 1-6; then M2, m3 for the bass courses.
STANDARD_LUTE = Tuning(courses=[
    _pitch_to_midi("G4"),  # course 1
    _pitch_to_midi("D4"),  # course 2
    _pitch_to_midi("A3"),  # course 3
    _pitch_to_midi("F3"),  # course 4
    _pitch_to_midi("C3"),  # course 5
    _pitch_to_midi("G2"),  # course 6
    _pitch_to_midi("F2"),  # course 7 — whole tone below course 6
    _pitch_to_midi("D2"),  # course 8 — minor third below course 7
])

# Guitar with G string tuned down to F# — a minor third below standard G-tuning
# on every course, including the bass diapasons.
# Bass course intervals mirror the standard: M2 (c6→c7), m3 (c7→c8).
GUITAR_F_SHARP = Tuning(courses=[
    _pitch_to_midi("E4"),   # course 1
    _pitch_to_midi("B3"),   # course 2
    _pitch_to_midi("F#3"),  # course 3
    _pitch_to_midi("D3"),   # course 4
    _pitch_to_midi("A2"),   # course 5
    _pitch_to_midi("E2"),   # course 6
    _pitch_to_midi("D2"),   # course 7 — whole tone below course 6
    _pitch_to_midi("B1"),   # course 8 — minor third below course 7
])


def note_name(course: int, fret: int, tuning: Tuning) -> str:
    """Return the pitch name (e.g. 'G#4') for a given course and fret."""
    return _midi_to_name(tuning.open_pitch(course) + fret)


def parse_tuning_string(s: str) -> Tuning:
    """
    Parse a comma-separated tuning string like 'E4,B3,F#3,D3,A2,E2'
    (course 1 first, highest string first) into a Tuning.
    """
    parts = [p.strip() for p in s.split(",")]
    return Tuning(courses=[_pitch_to_midi(p) for p in parts])


def tuning_table(tuning: Tuning) -> str:
    """Return a human-readable course → open-string-pitch table."""
    lines = []
    for i, midi in enumerate(tuning.courses, start=1):
        lines.append(f"  {i} -> {_midi_to_name(midi)}")
    return "\n".join(lines)
