#!/usr/bin/env bash
# Builds the archive that is uploaded to Zenodo: the source tree of the
# release with the reproducibility package, without VCS data and build
# outputs. Usage: bash scripts/make-zenodo-archive.sh [version]
set -euo pipefail
cd "$(dirname "$0")/.."
version=${1:-$(sed -n 's/^version: *//p' CITATION.cff)}
name=gonext-${version}
mkdir -p dist
rm -rf "dist/${name}" "dist/${name}.zip"
mkdir -p "dist/${name}"
# copy everything except VCS metadata and local build outputs
tar --exclude=./.git --exclude=./dist --exclude=./bin --exclude='__pycache__' -cf - . | tar -xf - -C "dist/${name}"
(cd dist && zip -qr -X "${name}.zip" "${name}")
rm -rf "dist/${name}"
(cd dist && sha256sum "${name}.zip" > "${name}.zip.sha256")
echo "dist/${name}.zip"
cat "dist/${name}.zip.sha256"
