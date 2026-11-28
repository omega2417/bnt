"""Verify the extracted release without third-party dependencies."""
import hashlib
from pathlib import Path
import sys

def main():
    root=Path(__file__).resolve().parents[1];manifest=root/'SHA256SUMS.txt'
    failures=[];count=0
    for line in manifest.read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        expected,relative=line.split('  ',1)
        target=(root/relative).resolve()
        if not target.is_relative_to(root):
            failures.append(relative+': unsafe path');continue
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
            failures.append(relative)
        count+=1
    if failures:
        print('FAILED:', '\n'.join(failures));return 1
    print(f'PASS: {count} release-file checksums');return 0
if __name__=='__main__':sys.exit(main())
