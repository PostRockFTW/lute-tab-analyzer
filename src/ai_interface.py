"""
Claude AI interface for lute tablature analysis.

Builds a cached system prompt containing both French tablature knowledge and
the serialised piece JSON. Each user query streams a fresh response while
the large static context is served from the prompt cache, saving tokens on
repeated queries within the same session (cache TTL = 5 min).
"""

from __future__ import annotations
import json
import sys
import anthropic
from src.models import Piece
from src.pitch_utils import Tuning, STANDARD_LUTE, tuning_table, note_name

_MODEL = "claude-sonnet-4-6"


def _build_tablature_knowledge(tuning: Tuning) -> str:
    table = tuning_table(tuning)
    return (
        "## French Lute Tablature Reference\n\n"
        "**Courses (strings):** Numbered 1-N from highest (treble) to lowest (bass).\n"
        "Open-string pitches for this instrument (course -> pitch):\n"
        + table + "\n\n"
        "Baroque lutes add bass courses (7+), but tuning varies -- always check the piece's \"tuning\" field.\n\n"
        "**Fret letters (French style, j is skipped):**\n"
        "  a=open  b=1st  c=2nd  d=3rd  e=4th  f=5th  g=6th  h=7th  i=8th\n"
        "  k=9th   l=10th m=11th n=12th (octave)\n"
        "Each fret is one chromatic semitone above the open pitch.\n\n"
        "**Chords:** Multiple notes on the same beat are played simultaneously.\n"
        "A beat with one note is a single melody or bass note.\n\n"
        "**Durations:** whole, half, quarter, eighth, sixteenth, thirty_second.\n"
        "A dotted beat lasts 1.5x its nominal value.\n\n"
        "**Data structure you receive:**\n"
        "Each bar has a list of beats; each beat has duration, dotted, is_rest, "
        "and notes (each note has course, fret, letter).\n"
    )

_RESPONSE_GUIDELINES = """
## How to respond

Adapt your output format to the query type:
- **"find / where / show me"** → list each match as "Bar N, beat M: <notes>"
- **"count / how many / how often"** → give a number plus a brief distribution summary
- **"what chords / identify"** → name the chord and list its occurrences
- **"show measure N" / "bar N"** → display every beat in that bar with pitches if tuning is known
- **"compare / pattern / how does"** → describe the musical structure with bar references
- **Statistical / analytical** → tables or bullet lists with bar numbers

Always include bar numbers for each finding.
When identifying pitches or chord names, state your tuning assumption clearly.
If the query is ambiguous, answer the most musically useful interpretation and note the assumption.
"""


def _enrich_with_pitches(piece_dict: dict, tuning: Tuning) -> dict:
    """Add a pre-computed 'pitch' field to every note so Claude doesn't do arithmetic."""
    for bar in piece_dict["bars"]:
        for beat in bar["beats"]:
            for note in beat["notes"]:
                try:
                    note["pitch"] = note_name(note["course"], note["fret"], tuning)
                except (ValueError, IndexError):
                    note["pitch"] = "?"
    return piece_dict


class StreamingAnalyzer:
    """
    Holds a parsed Piece and streams Claude analysis responses.

    The piece JSON is embedded in the system prompt with a cache_control
    checkpoint so it is served from cache on subsequent queries.
    """

    def __init__(self, piece: Piece, tuning: Tuning | None = None) -> None:
        self.piece = piece
        self.client = anthropic.Anthropic()
        resolved_tuning = tuning if tuning is not None else STANDARD_LUTE
        self._piece_json = json.dumps(
            _enrich_with_pitches(piece.to_dict(), resolved_tuning), indent=2
        )
        self._system = [
            {
                "type": "text",
                "text": (
                    "You are an expert analyst of Renaissance and Baroque lute music. "
                    "You will receive lute tablature encoded as structured JSON and answer "
                    "the user's musical queries about it.\n\n"
                    + _build_tablature_knowledge(resolved_tuning)
                    + _RESPONSE_GUIDELINES
                    + "\n\n## Tablature to analyse\n\n"
                    + self._piece_json
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def analyze(self, query: str) -> None:
        """Stream an analysis response to stdout for the given query."""
        enc = sys.stdout.encoding or "utf-8"
        with self.client.messages.stream(
            model=_MODEL,
            max_tokens=8096,
            system=self._system,
            messages=[{"role": "user", "content": query}],
        ) as stream:
            for chunk in stream.text_stream:
                try:
                    print(chunk, end="", flush=True)
                except UnicodeEncodeError:
                    safe = chunk.encode(enc, errors="replace").decode(enc)
                    print(safe, end="", flush=True)
        print()  # trailing newline
