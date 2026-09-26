"""VAPID key pair used to sign web pushes.

The private key is a file under settings.PUSH_KEYS_DIR (gitignored). It must never be
regenerated once devices have subscribed: every existing subscription is bound to the
public key, and a new key silently breaks them all until each device re-subscribes.
"""
import os
from pathlib import Path
from typing import NamedTuple, Optional

from cryptography.hazmat.primitives import serialization
from django.conf import settings
from py_vapid import Vapid, b64urlencode

# The contact a push service would use if our pushes caused it trouble. RFC 8292 also
# allows an https URL, but py_vapid refuses to sign anything that isn't a mailto:, so
# this must stay one. It's a placeholder until `ensure_vapid_keys --subject` sets a real
# address; pushes work either way.
DEFAULT_SUBJECT = "mailto:splitwise@example.com"

class VapidKeys(NamedTuple):
    vapid: Vapid
    public_key: str
    subject: str

def _paths():
    base = Path(settings.PUSH_KEYS_DIR)
    return base, base / "private_key.pem", base / "subject.txt"

_cache = {}

def load() -> Optional[VapidKeys]:
    """Return the key pair, or None when push hasn't been set up on this server."""
    _, pem, subject_file = _paths()
    if not pem.exists():
        return None
    stamp = (pem.stat().st_mtime, subject_file.stat().st_mtime if subject_file.exists() else None)
    cached = _cache.get(str(pem))
    if cached and cached[0] == stamp:
        return cached[1]

    vapid = Vapid.from_file(str(pem))
    raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    subject = subject_file.read_text().strip() if subject_file.exists() else ""
    keys = VapidKeys(vapid, b64urlencode(raw), subject or DEFAULT_SUBJECT)
    _cache[str(pem)] = (stamp, keys)
    return keys

def ensure(subject: Optional[str] = None) -> bool:
    """Create the key if missing (never overwrites it). Returns True if a key was created."""
    base, pem, subject_file = _paths()
    base.mkdir(parents=True, exist_ok=True)
    created = False
    if not pem.exists():
        vapid = Vapid()
        vapid.generate_keys()
        vapid.save_key(str(pem))
        os.chmod(pem, 0o600)
        created = True
    if subject:
        subject_file.write_text(subject.strip() + "\n")
    return created
