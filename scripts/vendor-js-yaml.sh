#!/usr/bin/env bash
# Vendor js-yaml browser bundle into plugin static files.
set -euo pipefail

VERSION="${JSYAML_VERSION:-4.1.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST_DIR="${ROOT}/netbox_panorama_configpump_plugin/static/netbox_panorama_configpump_plugin/js/vendor/js-yaml"
BUNDLE_DEST="${ROOT}/netbox_panorama_configpump_plugin/static/netbox_panorama_configpump_plugin/js/vendor/js-yaml.min.js"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cd "$tmpdir"
npm pack "js-yaml@${VERSION}" >/dev/null
tar -xzf "js-yaml-${VERSION}.tgz"

mkdir -p "$DEST_DIR"
cp "package/LICENSE" "${DEST_DIR}/LICENSE"

# Rebuild min bundle from dist if present; otherwise keep existing file.
if [[ -f "package/dist/js-yaml.min.js" ]]; then
  cp "package/dist/js-yaml.min.js" "$BUNDLE_DEST"
elif [[ -f "package/dist/js-yaml.js" ]]; then
  cp "package/dist/js-yaml.js" "$BUNDLE_DEST"
else
  echo "Warning: no dist bundle in js-yaml package; left ${BUNDLE_DEST} unchanged" >&2
fi

echo "Vendored js-yaml@${VERSION}:"
echo "  ${DEST_DIR}/LICENSE"
echo "  ${BUNDLE_DEST}"
