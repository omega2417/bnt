# Highlights

Elsevier asks for 3–5 bullets, each at most 85 characters including spaces.
The counts below are computed; check them again after any edit.

| # | Highlight | Characters |
|---|---|---|
| 1 | Phylogenetic, morphological and fossil data become design constraints | 69 |
| 2 | A six-type knowledge graph separates homology from convergence | 62 |
| 3 | Evidence score and transfer uncertainty gate weakly supported designs | 69 |
| 4 | Open reference implementation with seeded, provenance-tagged protocol | 69 |
| 5 | Case study: additively manufactured end-of-arm bracket, three baselines | 71 |

The manuscript's own highlights all fit the limit, but with almost no margin:
they measure 80, 84, 84, 80 and 85 characters, and the last one is exactly at
the maximum. Any later edit to them has to be re-counted. The shorter variants
in the table above carry 14-24 characters of slack and say the same thing; use
either set, but count again after every edit.

Recompute with:

```bash
python - <<'PY'
for line in open("docs/publication/highlights.md"):
    if line.startswith("| ") and line.count("|") == 4:
        text = line.split("|")[2].strip()
        if text and not text.startswith("---"):
            print(len(text), text)
PY
```
