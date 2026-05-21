#!/usr/bin/env bash
# Vendor monaco-editor min/vs into plugin static files.
set -euo pipefail

VERSION="${MONACO_VERSION:-0.52.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATIC_VENDOR="${ROOT}/netbox_panorama_configpump_plugin/static/netbox_panorama_configpump_plugin/js/vendor"
DEST="${STATIC_VENDOR}/monaco/vs"
MIN_MAPS_DEST="${STATIC_VENDOR}/min-maps"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cd "$tmpdir"
npm pack "monaco-editor@${VERSION}" >/dev/null
tar -xzf "monaco-editor-${VERSION}.tgz"

rm -rf "$DEST" "$MIN_MAPS_DEST"
mkdir -p "$(dirname "$DEST")"
cp -R "package/min/vs" "$DEST"
cp -R "package/min-maps" "$MIN_MAPS_DEST"
cp "package/LICENSE" "$(dirname "$DEST")/LICENSE"

echo "Vendored monaco-editor@${VERSION} to:"
echo "  ${DEST}"
echo "  ${MIN_MAPS_DEST}"
