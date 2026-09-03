import re, os, sys, pathlib

SRC = sys.argv[1] if len(sys.argv) > 1 else "UMSF_CyberRange_Digital_Twin_Modules_UA.md"
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "proj")

lines = open(SRC, encoding="utf8").read().split("\n")

# locate start of Appendix H
start = None
for i, l in enumerate(lines):
    if l.startswith("# Додаток H."):
        start = i
        break
print("Appendix H starts at line", start + 1)

fence_re = re.compile(r"^(`{3,})\s*([A-Za-z0-9_+-]*)\s*$")
head_re = re.compile(r"^#### `([^`]+)`\s*$")

i = start
files = []
fence = None          # closing fence string when inside a block
pending = None        # path awaiting its code block
n = len(lines)
while i < n:
    l = lines[i]
    if fence is None:
        m = head_re.match(l)
        if m:
            pending = m.group(1)
            i += 1
            continue
        m = fence_re.match(l)
        if m:
            fence = m.group(1)
            lang = m.group(2)
            body = []
            i += 1
            while i < n and not (lines[i].startswith(fence) and lines[i].strip() == fence):
                body.append(lines[i])
                i += 1
            # i is closing fence
            fence = None
            if pending:
                files.append((pending, "\n".join(body) + "\n", lang))
                pending = None
            i += 1
            continue
    i += 1

print("collected", len(files), "files")
seen = {}
for path, body, lang in files:
    if path in seen:
        print("DUPLICATE:", path)
    seen[path] = 1
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf8")
    print(f"{len(body.split(chr(10)))-1:6d}  {lang:10s}  {path}")
