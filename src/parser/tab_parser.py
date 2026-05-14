"""
Parser for the Wayne Cripps ASCII lute tablature (.tab) format.

Format summary (from cs.dartmouth.edu/~wbc/lute/tab_files/lute_tab.README):
  - Lines starting with % are comments
  - Lines starting with $ are metadata/settings directives
  - Lines wrapped in { } are text blocks (title, composer, etc.)
  - Lines starting with [ ] are above-system annotations
  - b / B / bb = barline variants
  - S = time signature  (e.g. S3-4, SC)
  - 0-5 = chord with that many flags (0=whole, 1=half, 2=qtr, 3=8th, 4=16th, 5=32nd)
  - W = whole note, w = half note
  - R = rest  (followed by optional flag count)
  - After the flag character: one character per course (letter = fret, space = unplayed)
  - x lines immediately following a chord extend it with additional courses (7th, 8th, ...)
  - # lines introduce multi-voice grids — not fully parsed; notes are captured best-effort
  - e = end of piece
"""

from __future__ import annotations
import re
from src.models import Beat, Bar, Note, Piece, DURATION_FROM_FLAG, FRET_LETTERS

# Ornament/modifier prefixes that appear BEFORE a course letter without consuming a string slot
_PREFIX_CHARS = frozenset("+*$<~%")
# All characters that represent a note (advance the course counter).
# 'j' is not valid in French tablature but is included defensively so it still
# advances the course if encountered in a non-standard file.
_NOTE_CHARS = frozenset(FRET_LETTERS) | frozenset("j")
# Characters that consume one slot but represent something other than a note
_SKIP_SLOT_CHARS = frozenset(" ")


def _strip_format_codes(text: str) -> str:
    """Remove TAB typesetting codes like ^01, \\CL/, etc."""
    text = re.sub(r"\^[0-9]{2}", "", text)
    text = re.sub(r"\\[A-Z]+/", "", text)
    return text.strip()


def _process_text_block(raw: str, piece: Piece) -> None:
    """Try to assign a { } text block content to title or composer."""
    clean = _strip_format_codes(raw)
    if not clean:
        return

    # {left/right} format — left = title, right = composer
    if "/" in clean:
        parts = clean.split("/", 1)
        left = parts[0].strip()
        right = parts[1].strip() if len(parts) > 1 else ""
        if left and not piece.title:
            piece.title = left
        if right and not piece.composer:
            # right side is typically "Composer Name" or "arr. Name"
            piece.composer = re.sub(r"^(by |arr\.\s*)", "", right, flags=re.IGNORECASE).strip()
        return

    lower = clean.lower()
    if lower.startswith("by ") or lower.startswith("arr. "):
        candidate = re.sub(r"^(by |arr\. )", "", clean, flags=re.IGNORECASE).strip()
        if not piece.composer:
            piece.composer = candidate
    elif not piece.title:
        piece.title = clean
    elif not piece.composer:
        piece.composer = clean


def _parse_directive(directive: str, piece: Piece) -> None:
    """Handle $key=value metadata lines."""
    if "=" not in directive:
        return
    key, _, value = directive.partition("=")
    key = key.strip().lower()
    value = value.strip()
    if key == "tuning":
        piece.tuning = value
    elif key in ("title", "name"):
        piece.title = value
    elif key in ("composer", "author"):
        piece.composer = value


def _parse_flag(line: str) -> tuple[str, bool, str]:
    """
    Parse the leading flag character(s) from a chord line.
    Returns (duration_name, dotted, remaining_chars).
    """
    i = 0
    flag_ch = line[i] if line else "2"
    duration = DURATION_FROM_FLAG.get(flag_ch, "quarter")
    i += 1

    dotted = False
    if i < len(line) and line[i] in (".", "*"):
        dotted = True
        i += 1

    # Skip tie/invisible-flag modifiers that don't affect note content
    while i < len(line) and line[i] in ("t", "!", "|", "Q", "@", "B", "W"):
        i += 1

    return duration, dotted, line[i:]


def _extract_notes(chars: str, start_course: int = 1) -> list[Note]:
    """
    Convert a run of tablature characters into Note objects.
    Each letter advances the course counter by 1; a space is an unplayed course.
    Ornament prefix characters (+, *, etc.) do NOT advance the course.
    """
    notes: list[Note] = []
    course = start_course
    i = 0

    while i < len(chars):
        ch = chars[i]

        if ch.lower() in _NOTE_CHARS:
            notes.append(Note.from_letter(course, ch))
            course += 1

        elif ch == " ":
            course += 1  # unplayed string — still advances

        elif ch in _PREFIX_CHARS:
            pass  # ornament prefix; does not advance course

        elif ch == "!":
            i += 1  # escape operator: skip the next character

        elif ch == "&":
            i += 1  # postfix operator: skip the next character

        elif ch == "N":
            # Numeric high fret: N10, N12, etc.
            j = i + 1
            num = ""
            while j < len(chars) and chars[j].isdigit():
                num += chars[j]
                j += 1
            if num:
                notes.append(Note(course=course, fret=int(num), letter=f"N{num}"))
                course += 1
                i = j
                continue

        elif ch in ("|", ":", ".", "]", "(", ")", "{", "}", "[", "U", "X", "/", "\\", "q", "r"):
            pass  # fingering dots, slur markers, etc. — skip without advancing

        # All other characters: skip silently

        i += 1

    return notes


def parse_tab_file(content: str) -> Piece:
    """
    Parse a Wayne Cripps .tab file and return a Piece data model.

    The parser handles:
      - Metadata extraction from { } blocks and $ directives
      - Single-voice chord lines with flag + course letters
      - x-continuation lines for courses beyond 6
      - Barlines (b, B, bb)
      - Time signatures (S)
      - Rests (R)
      - Multi-voice # grids (best-effort: notes from first voice captured)

    It intentionally ignores typesetting-only commands (fonts, margins, etc.)
    that carry no musical information.
    """
    piece = Piece()
    lines = content.splitlines()

    bars: list[Bar] = []
    current_bar = Bar(number=1)
    bar_number = 1

    in_text_block = False
    text_block_lines: list[str] = []

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1

        # ── Empty line ────────────────────────────────────────────────
        if not line:
            continue

        # ── Multi-line text block accumulation ────────────────────────
        if in_text_block:
            if "}" in line:
                end = line.index("}")
                text_block_lines.append(line[:end])
                _process_text_block(" ".join(text_block_lines), piece)
                text_block_lines = []
                in_text_block = False
            else:
                text_block_lines.append(line)
            continue

        fc = line[0]

        # ── Comment ───────────────────────────────────────────────────
        if fc == "%":
            continue

        # ── Text block { } ────────────────────────────────────────────
        if fc == "{":
            if "}" in line:
                content_text = line[1 : line.index("}")]
                _process_text_block(content_text, piece)
            else:
                in_text_block = True
                text_block_lines = [line[1:]]
            continue

        # ── Above-system annotation [ ] ───────────────────────────────
        if fc == "[":
            continue

        # ── Metadata directive $ ──────────────────────────────────────
        if fc == "$":
            _parse_directive(line[1:], piece)
            continue

        # ── End of piece ──────────────────────────────────────────────
        if fc == "e" and (len(line) == 1 or line[1:].strip() == ""):
            if current_bar.beats:
                bars.append(current_bar)
            break

        # ── Barlines ──────────────────────────────────────────────────
        if fc == "b" or line.startswith("bb") or fc == "B":
            if current_bar.beats:
                # Only close and advance when the current bar has content;
                # an opening barline before any notes should not shift numbering.
                bars.append(current_bar)
                bar_number += 1
                current_bar = Bar(number=bar_number)
            continue

        # ── Time signature ────────────────────────────────────────────
        if fc == "S":
            piece.time_signature = line[1:].strip()
            continue

        # ── Rest ──────────────────────────────────────────────────────
        if fc == "R":
            flag = line[1] if len(line) > 1 and line[1] in "012345" else "2"
            dotted = len(line) > 2 and line[2] == "."
            duration = DURATION_FROM_FLAG.get(flag, "quarter")
            current_bar.beats.append(Beat(duration=duration, dotted=dotted, is_rest=True))
            continue

        # ── Chord (rhythm flag) ───────────────────────────────────────
        if fc in "012345WwL":
            duration, dotted, note_chars = _parse_flag(line)
            notes = _extract_notes(note_chars, start_course=1)
            beat = Beat(duration=duration, dotted=dotted, notes=notes)

            # Consume any immediately following x-continuation lines
            next_course = len(notes) + 1
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith("x") and len(next_line) >= 1:
                    cont_chars = next_line[1:]
                    cont_notes = _extract_notes(cont_chars, start_course=next_course)
                    beat.notes.extend(cont_notes)
                    next_course += len(cont_notes)
                    i += 1
                else:
                    break

            current_bar.beats.append(beat)
            continue

        # ── Multi-voice grid # ────────────────────────────────────────
        if fc == "#":
            # A "#N" line opens one voice in a simultaneous grid.  Additional
            # "#N" lines immediately following (with their own "x" continuations)
            # are further simultaneous voices in the same beat.  We flatten all
            # voices into one Beat so that pattern matching sees every note that
            # sounds at this rhythmic position.
            rest = line[1:]
            if rest and rest[0].isdigit():
                flag_ch = rest[0]
                rest = rest[1:]
            else:
                flag_ch = "2"
            # Strip tie/modifier flags the same way _parse_flag does
            while rest and rest[0] in ("t", "!", "|", "Q", "@", "B", "W"):
                rest = rest[1:]
            duration = DURATION_FROM_FLAG.get(flag_ch, "quarter")
            all_notes: list[Note] = _extract_notes(rest, start_course=1)

            # Consume x-continuation AND additional #-voice lines that belong
            # to the same beat (i.e. the entire grid block until a line that
            # is neither "x" nor "#").
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith("x"):
                    # Continuation of the most-recent voice: use next unused course slot
                    used = len(all_notes) + 1
                    all_notes.extend(_extract_notes(next_line[1:], start_course=used))
                    i += 1
                elif next_line.startswith("#"):
                    # New simultaneous voice — strip flag and modifier, then fold notes in
                    vrest = next_line[1:]
                    if vrest and vrest[0].isdigit():
                        vrest = vrest[1:]
                    while vrest and vrest[0] in ("t", "!", "|", "Q", "@", "B", "W"):
                        vrest = vrest[1:]
                    all_notes.extend(_extract_notes(vrest, start_course=1))
                    i += 1
                else:
                    break

            beat = Beat(duration=duration, notes=all_notes)
            current_bar.beats.append(beat)
            continue

        # All other TAB commands (page layout, fonts, ornament marks, etc.)
        # carry no musical data — skip silently.

    # Append the final bar if it has content and wasn't already saved
    if current_bar.beats and (not bars or bars[-1] is not current_bar):
        bars.append(current_bar)

    piece.bars = bars
    return piece
