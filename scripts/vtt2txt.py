"""Collapse a YouTube auto-caption VTT into de-duplicated lines: [HH:MM:SS] text.

Usage: python3 vtt2txt.py IN.vtt OUT.txt
"""
import re, sys

src, dst = sys.argv[1], sys.argv[2]
ts_re = re.compile(r"^(\d\d:\d\d:\d\d)\.\d{3} -->")
tag_re = re.compile(r"<[^>]+>")
out, seen, cur = [], set(), None
for line in open(src, encoding="utf-8"):
    line = line.rstrip("\n")
    m = ts_re.match(line)
    if m:
        cur = m.group(1)
        continue
    if not line.strip() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
        continue
    text = tag_re.sub("", line).strip()
    if not text or text in seen:
        continue
    seen.add(text)
    out.append(f"[{cur}] {text}")
open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(len(out), "lines")
