import os
from pathlib import Path

if not os.environ.get("ANTHROPIC_API_KEY"):
    env_path = Path(__file__).parent.parent / "SSoT_Bot_v3.0" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
                break

from src.parser.tab_parser import parse_tab_file
from src.ai_interface import StreamingAnalyzer

text = open("king_of_denmarks_galliard.tab", encoding="utf-8").read()
piece = parse_tab_file(text)
d = piece.to_dict()

print(f"Title:    {d['title']}")
print(f"Composer: {d['composer']}")
print(f"Time:     {d['time_signature'] or '(not specified)'}")
print(f"Bars:     {len(d['bars'])}")
total_beats = sum(len(b["beats"]) for b in d["bars"])
print(f"Beats:    {total_beats}")
print()

# Show first 3 bars
for bar in d["bars"][:3]:
    beat_strs = []
    for beat in bar["beats"]:
        if beat["is_rest"]:
            beat_strs.append(f"REST")
        else:
            notes = ",".join(f"c{n['course']}:{n['letter']}" for n in beat["notes"])
            dot = "." if beat["dotted"] else ""
            beat_strs.append(f"{beat['duration']}{dot}[{notes}]")
    print(f"  Bar {bar['number']}: {' | '.join(beat_strs)}")

print()
print("--- AI Analysis ---")
print()

analyzer = StreamingAnalyzer(piece)

queries = [
    "Give me a structural overview: how many sections does this galliard appear to have, and what are their approximate bar ranges?",
    "The galliard was famous for its repeated note bass patterns and strong cadential chords. Where do you see the most harmonically dense moments (beats with the most simultaneous notes)?",
]

for q in queries:
    print(f"Query: {q}")
    print("-" * 60)
    analyzer.analyze(q)
    print()
