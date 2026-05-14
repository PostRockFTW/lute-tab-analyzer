# Lute Tablature Analyzer

## Project Origin (for future Claude sessions)

### User's Initial Request
> "I want to make a new project in a new root folder. This one will be centered around a clerical
> task, trying to recognize old french style lute tablature and parsing out patterns found within
> that tablature looking for certain chords or collections of notes. I have access to an online
> resource that displays the tablature on a webpage and give the option to download it as pdf, or
> in a format unfamiliar to me called fronimo."

### Q&A That Shaped the Design

| Question | Answer |
|---|---|
| What online resource? | https://wp.lutemusic.org/ (17,000+ pieces; downloads: ft3, MIDI, PDF, Wayne Cripps TAB) |
| What output? | AI-driven, flexible per query: occurrence lists, annotations, statistical analysis — all in scope |
| ft3 or PDF/OCR? | Both equally available for manual download; Wayne Cripps .tab chosen as primary (simplest); ft3 via luteconv bridge as secondary; user wants cross-format validation |

---

## What This Tool Does

Parse French lute tablature from **Wayne Cripps `.tab` files** (or Fronimo `.ft3` files via
conversion), then let you ask natural-language questions about the music — "find all D minor
chords", "where does the melody hit a tritone", "how often does course 1 play open" — answered
by Claude with bar/beat references.

---

## Architecture

```
main.py                 — Click CLI: analyze, compare, search, list, download, download-pdf
src/
  models.py             — Note, Beat, Bar, Piece dataclasses + JSON serialiser
  pitch_utils.py        — Tuning dataclass + course/fret → pitch name resolver
  ai_interface.py       — Claude API (streaming + prompt caching on piece JSON)
  downloader.py         — wp.lutemusic.org search, .tab and .pdf download
  parser/
    tab_parser.py       — Wayne Cripps .tab ASCII format → Piece
    fronimo.py          — .ft3 → luteconv subprocess → re-parse as .tab
```

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

You also need an Anthropic API key:

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# or set it permanently in your environment / .env
```

### 2. (Optional) Install luteconv for .ft3 support

luteconv is only needed if you want to work with Fronimo `.ft3` files.
Wayne Cripps `.tab` files work with no extra tools.

1. Download a Windows binary from https://github.com/LukeEmmet/luteconv/releases
2. Either add it to your PATH or set:
   ```powershell
   $env:LUTECONV_PATH = "C:\path\to\luteconv.exe"
   ```

---

## Getting Tablature Files

Go to https://wp.lutemusic.org/ and click **Files** to browse the archive.
On a piece's page, right-click the **TAB** link to download the `.tab` file, or
click **Acquire** for the Fronimo `.ft3`.

---

## Usage

### Interactive analysis

```bash
python main.py analyze "path/to/piece.tab"
python main.py analyze "path/to/piece.ft3"    # requires luteconv

# Specify your tuning so Claude names chords correctly for your instrument:
python main.py analyze "path/to/piece.tab" --tuning "E4,B3,F#3,D3,A2,E2"
```

After loading, type queries at the `Query>` prompt:

```
Query> find all D minor chords
Query> how many times does the open first course appear
Query> show me bar 12
Query> where is the cadence in the final section
Query> count occurrences of a G major chord
```

Type `quit` or press Ctrl-C to exit.

### Searching and downloading

```bash
python main.py search "dowland galliard"
python main.py list Dowland
python main.py download Dowland 40_king_of_denmarks_galliard_long
python main.py download-pdf Dowland 23a_frogg_galliard_2
```

### Cross-format validation

```bash
python main.py compare piece.ft3 piece.tab
```

Reports any structural differences (bar count, beat count, note content) between
the two parsed files. If they agree, you can trust the data matches the PDF.

---

## French Tablature Quick Reference

| Letter | Fret | Letter | Fret |
|--------|------|--------|------|
| a | open | h | 7th |
| b | 1st  | i | 8th |
| c | 2nd  | k | 9th |
| d | 3rd  | l | 10th |
| e | 4th  | m | 11th |
| f | 5th  | n | 12th (octave) |
| g | 6th  | | |

The letter **j is not used** in French tablature (it was omitted to avoid confusion with i
in historical manuscripts). Letters continue k, l, m, n for frets 9–12.

### Tuning

Standard 6-course Renaissance lute (course 1 → 6, high to low): **G D A F C G**

Alternative — guitar with F# third string (course 1 → 6): **E B F# D A E**
This tuning sits exactly a minor third below standard G-tuning on every course.
Pass it to the analyzer so chord names match your instrument:

```bash
python main.py analyze piece.tab --tuning "E4,B3,F#3,D3,A2,E2"
```

---

## Known Limitations

- Multi-voice `#` grid notation is parsed best-effort (first voice captured; additional
  voices may be incomplete).
- Ornament characters are stripped rather than preserved — if ornament analysis is needed,
  the parser will need extension.
- Tuning is not always encoded in .tab files; Claude assumes Renaissance G-tuning unless
  the file specifies otherwise.
- The parser handles the most common single-staff lute tablature; exotic or very old
  file variants may need tweaks.

---

## Roadmap

- Batch analysis across a corpus with CSV/JSON export
- PDF text extraction as a third-way validation path
