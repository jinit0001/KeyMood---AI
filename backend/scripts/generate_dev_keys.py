"""Generate a local RS256 keypair for development (keys/ is git-ignored).

    python scripts/generate_dev_keys.py

Works on Windows/macOS/Linux - needs only the `cryptography` package, which
is installed with `pyjwt[crypto]` from requirements.txt.
"""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

keys_dir = Path(__file__).resolve().parent.parent / "keys"
keys_dir.mkdir(exist_ok=True)
private_path = keys_dir / "dev_jwt_private.pem"
public_path = keys_dir / "dev_jwt_public.pem"

if private_path.exists() and public_path.exists():
    print(f"Keys already exist in {keys_dir} - leaving them alone.")
else:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Wrote {private_path} and {public_path}")
