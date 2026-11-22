"""Evidence-bound action warrants: claims, signing, verification and single-use nonces.

A warrant (Section 3.4, Table 3 of the article) is a compact signed token

    w = Sig_skG(wid, act, tgt, evd, pol, conf, tier, iat, exp, nonce, pred)

encoded as ``base64url(header).base64url(claims).base64url(signature)`` (a JWS-like
compact serialization over canonical JSON).  Ed25519 from the ``cryptography`` package is
used when it is installed (it is pre-installed on Google Colab); otherwise the module falls
back to HMAC-SHA256 so that the reference code always runs.  The fallback is a symmetric
MAC and is meant for experiments only: an enforcement point that holds the HMAC key could
mint warrants, which violates assumption A1 of Proposition 3.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass, field

try:  # pragma: no cover - availability depends on the environment
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    HAVE_ED25519 = True
except Exception:  # pragma: no cover
    HAVE_ED25519 = False

WARRANT_NS = uuid.UUID("6f1c2a3e-8a7b-4c1d-9e2f-0b5a6c7d8e9f")


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def canonical(obj) -> bytes:
    """Canonical JSON (sorted keys, no whitespace, finite floats rounded to 1 microsecond)."""
    def fix(o):
        if isinstance(o, float):
            return round(o, 6)
        if isinstance(o, dict):
            return {k: fix(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [fix(v) for v in o]
        return o
    return json.dumps(fix(obj), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def merkle_root(leaves_hex: list[str]) -> str:
    """Binary Merkle root over hex digests (duplicating the last node on odd levels)."""
    if not leaves_hex:
        return sha256_hex(b"")
    level = [bytes.fromhex(h) for h in leaves_hex]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


class Signer:
    """Gateway signing key (sk_G).  ``seed`` makes keys reproducible for experiments; in a
    deployment the key lives in a hardware security module and is never exported."""

    def __init__(self, seed: bytes | str = b"ebaw-gateway", kid: str = "gw-1", force_hmac: bool = False):
        seed = seed.encode() if isinstance(seed, str) else seed
        self.kid = kid
        sk = hashlib.sha256(b"ebaw-key|" + seed).digest()
        self.alg = "EdDSA" if (HAVE_ED25519 and not force_hmac) else "HS256"
        if self.alg == "EdDSA":
            self._sk = Ed25519PrivateKey.from_private_bytes(sk)
            self.public_bytes = self._sk.public_key().public_bytes_raw()
        else:
            self._sk = sk
            self.public_bytes = sk          # symmetric: the "public" key is the secret itself

    def sign(self, msg: bytes) -> bytes:
        if self.alg == "EdDSA":
            return self._sk.sign(msg)
        return hmac.new(self._sk, msg, hashlib.sha256).digest()

    def verifier(self) -> "Verifier":
        return Verifier(self.alg, self.public_bytes, self.kid)


class Verifier:
    def __init__(self, alg: str, key: bytes, kid: str):
        self.alg, self.key, self.kid = alg, key, kid
        if alg == "EdDSA":
            self._pk = Ed25519PublicKey.from_public_bytes(key)

    def verify(self, msg: bytes, sig: bytes) -> bool:
        try:
            if self.alg == "EdDSA":
                self._pk.verify(sig, msg)
                return True
            return hmac.compare_digest(hmac.new(self.key, msg, hashlib.sha256).digest(), sig)
        except Exception:
            return False


@dataclass
class Warrant:
    """Claims of Table 3.  Times are seconds on the synchronized gateway clock."""
    wid: str
    act: str
    tgt: str
    evd: str                     # Merkle root of evidence digests and ledger transaction ids
    pol: dict                    # {"partition": ..., "version": ...}
    conf: float                  # calibrated confidence g(s)
    tier: str
    regime: str
    iat: float
    exp: float
    nonce: str
    pred: dict = field(default_factory=dict)
    human: bool = False          # human-attested warrant (replaces P1, P2, P5)

    def claims(self) -> dict:
        return asdict(self)


def make_wid(*parts) -> str:
    return str(uuid.uuid5(WARRANT_NS, "|".join(str(p) for p in parts)))


def make_nonce(*parts) -> str:
    return sha256_hex("nonce|" + "|".join(str(p) for p in parts))[:32]


def encode(w: Warrant, signer: Signer) -> str:
    header = {"alg": signer.alg, "typ": "ebaw+jwt", "kid": signer.kid}
    h, c = b64u(canonical(header)), b64u(canonical(w.claims()))
    sig = signer.sign(f"{h}.{c}".encode())
    return f"{h}.{c}.{b64u(sig)}"


def decode(token: str, verifier: Verifier) -> Warrant | None:
    """Return the warrant if the token parses and its signature verifies, else ``None``
    (fail-closed: every parse error is a verification failure, assumption A4)."""
    try:
        h, c, s = token.split(".")
        header = json.loads(b64u_dec(h))
        if header.get("alg") != verifier.alg or header.get("kid") != verifier.kid:
            return None
        if not verifier.verify(f"{h}.{c}".encode(), b64u_dec(s)):
            return None
        return Warrant(**json.loads(b64u_dec(c)))
    except Exception:
        return None


class NonceStore:
    """Single-use nonce registry of the enforcement points.  ``consume`` is atomic: it
    succeeds once per nonce and returns False for every replay.  The consumption log can be
    anchored on the ledger (``log``)."""

    def __init__(self):
        self._used: dict[str, float] = {}
        self.log: list[tuple[str, float, str]] = []

    def used(self, nonce: str) -> bool:
        return nonce in self._used

    def consume(self, nonce: str, t: float, wid: str = "") -> bool:
        if nonce in self._used:
            return False
        self._used[nonce] = t
        self.log.append((nonce, t, wid))
        return True
