#!/usr/bin/env bash
# Replaces the placeholder module path github.com/ORGANIZATION/gonext by the
# final repository path, e.g.
#   bash scripts/set-module-path.sh github.com/pforkert/gonext
set -euo pipefail
cd "$(dirname "$0")/.."
new=${1:?usage: set-module-path.sh NEW_MODULE_PATH}
old=github.com/ORGANIZATION/gonext
grep -rl --exclude-dir=.git --exclude-dir=results --exclude-dir=figures "$old" . | while read -r f; do
	sed -i.bak "s#${old}#${new}#g" "$f" && rm -f "$f.bak"
done
echo "module path set to $new; run: go test ./... && go test ./internal/driver -run Golden -update"
