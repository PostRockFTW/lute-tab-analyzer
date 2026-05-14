import os, sys
from pathlib import Path

# Load API key from sibling project's .env if not already set
if not os.environ.get("ANTHROPIC_API_KEY"):
    env_path = Path(__file__).parent.parent / "SSoT_Bot_v3.0" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
                break

from src.parser.tab_parser import parse_tab_file
from src.ai_interface import StreamingAnalyzer

text = open("sample_pavane.tab", encoding="utf-8").read()
piece = parse_tab_file(text)
print(f"Loaded: {piece.title} — {len(piece.bars)} bars\n")

analyzer = StreamingAnalyzer(piece)

queries = [
    "Give me a quick summary of the structure of this piece — how many bars, what durations appear, and what courses are used.",
    "Which beats contain chords with 3 or more simultaneous notes? List bar and beat number.",
    "Describe bar 3 in musical terms — what kind of passage is it?",
]

for q in queries:
    print(f"Query: {q}")
    print("-" * 60)
    analyzer.analyze(q)
    print()
