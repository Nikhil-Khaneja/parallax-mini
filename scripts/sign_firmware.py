#!/usr/bin/env python
"""Sign a firmware artifact: print its SHA-256 and base64 Ed25519 signature.

Usage: python scripts/sign_firmware.py <artifact> <priv_pem>
"""
import sys

from cryptography.hazmat.primitives import serialization

sys.path.insert(0, ".")
from backend.crypto import sha256_hex, sign  # noqa: E402


def main(artifact_path: str, priv_pem: str) -> None:
    with open(artifact_path, "rb") as f:
        data = f.read()
    with open(priv_pem, "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)
    checksum = sha256_hex(data)
    print("sha256:", checksum)
    print("sig:", sign(priv, checksum))


if __name__ == "__main__":
    main(*sys.argv[1:])
