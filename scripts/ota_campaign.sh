#!/usr/bin/env bash
# Sign a firmware artifact and print its version, checksum, and signature.
# Usage: ./scripts/ota_campaign.sh <artifact> <version> [target_pct]
set -euo pipefail

ARTIFACT="${1:?artifact path required}"
VERSION="${2:?version required}"
TARGET_PCT="${3:-100}"
KEYS_DIR="${KEYS_DIR:-keys}"

if [[ ! -f "$KEYS_DIR/ota_priv.pem" ]]; then
  echo "No signing key at $KEYS_DIR/ota_priv.pem — generating one..."
  python scripts/gen_keys.py "$KEYS_DIR"
fi

echo "Signing $ARTIFACT as version $VERSION (target ${TARGET_PCT}%)"
python scripts/sign_firmware.py "$ARTIFACT" "$KEYS_DIR/ota_priv.pem"
echo "Register this firmware and launch a campaign via the OTA API / backend."
