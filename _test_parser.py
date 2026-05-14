from src.parser.tab_parser import parse_tab_file

text = open("sample_pavane.tab", encoding="utf-8").read()
piece = parse_tab_file(text)
d = piece.to_dict()

print("Title   :", d["title"])
print("Composer:", d["composer"])
print("Time    :", d["time_signature"])
print("Bars    :", len(d["bars"]))
print()

for bar in d["bars"]:
    beat_strs = []
    for beat in bar["beats"]:
        if beat["is_rest"]:
            beat_strs.append(f"REST({beat['duration']})")
        else:
            notes = ",".join(f"c{n['course']}:{n['letter']}" for n in beat["notes"])
            dot = "." if beat["dotted"] else ""
            beat_strs.append(f"{beat['duration']}{dot}[{notes}]")
    print(f"  Bar {bar['number']}: {' | '.join(beat_strs)}")
