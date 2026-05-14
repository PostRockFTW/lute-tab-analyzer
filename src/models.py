from __future__ import annotations
from dataclasses import dataclass, field

FRET_LETTERS = "abcdefghiklmnopqrstuvwxyz"  # j is not used in French tablature

_FRET_FROM_LETTER: dict[str, int] = {ch: i for i, ch in enumerate(FRET_LETTERS)}

DURATION_FROM_FLAG: dict[str, str] = {
    "L": "longa",
    "0": "whole",
    "W": "whole",
    "w": "half",
    "1": "half",
    "2": "quarter",
    "3": "eighth",
    "4": "sixteenth",
    "5": "thirty_second",
    "R": "rest",
}


@dataclass
class Note:
    course: int   # 1-based; 1 = highest (treble) string
    fret: int     # 0 = open string
    letter: str   # original tablature character

    @classmethod
    def from_letter(cls, course: int, letter: str) -> "Note":
        ch = letter.lower()
        fret = _FRET_FROM_LETTER.get(ch, 0)  # 'j' or unknown → fret 0
        return cls(course=course, fret=fret, letter=ch)


@dataclass
class Beat:
    duration: str           # see DURATION_FROM_FLAG values
    dotted: bool = False
    is_rest: bool = False
    notes: list[Note] = field(default_factory=list)


@dataclass
class Bar:
    number: int
    beats: list[Beat] = field(default_factory=list)


@dataclass
class Piece:
    title: str = ""
    composer: str = ""
    tuning: str = ""
    time_signature: str = ""
    num_courses: int = 6
    source_format: str = "tab"
    bars: list[Bar] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible structure for passing to Claude."""
        return {
            "title": self.title,
            "composer": self.composer,
            "tuning": self.tuning or "unknown (likely G-tuning)",
            "time_signature": self.time_signature,
            "num_courses": self.num_courses,
            "bars": [
                {
                    "number": bar.number,
                    "beats": [
                        {
                            "duration": beat.duration,
                            "dotted": beat.dotted,
                            "is_rest": beat.is_rest,
                            "notes": [
                                {
                                    "course": n.course,
                                    "fret": n.fret,
                                    "letter": n.letter,
                                }
                                for n in beat.notes
                            ],
                        }
                        for beat in bar.beats
                    ],
                }
                for bar in self.bars
            ],
        }
