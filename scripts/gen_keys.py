#!/usr/bin/env python
"""Generate an Ed25519 keypair for OTA firmware signing.

Usage: python scripts/gen_keys.py [keys_dir]
Writes ota_priv.pem and ota_pub.pem (PEM). Never commit the private key.
"""
import sys

from cryptography.hazmat.primitives import serialization

sys.path.insert(0, ".")
from backend.crypto import generate_keypair  # noqa: E402


def main(keys_dir: str = "keys") -> None:
    import os
    os.makedirs(keys_dir, exist_ok=True)
    priv, pub = generate_keypair()
    with open(f"{keys_dir}/ota_priv.pem", "wb") as f:
        f.write(priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
    with open(f"{keys_dir}/ota_pub.pem", "wb") as f:
        f.write(pub.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"wrote {keys_dir}/ota_priv.pem and {keys_dir}/ota_pub.pem")


if __name__ == "__main__":
    main(*sys.argv[1:])
