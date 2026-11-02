"""A software authenticator, answering WebAuthn ceremonies as a phone or a security key would.

Needs the ``passkeys`` extra, whose ``webauthn`` brings ``cbor2`` and ``cryptography``. It makes
real ES256 key pairs and real CBOR, so the server's verification runs exactly as it does for a
device; only the person's touch is skipped::

    authenticator = SoftAuthenticator(origin="http://myapp.test")
    options = (await client.post("/api/auth/passkeys/options")).json()
    await client.post("/api/auth/passkeys", json={"credential": authenticator.register(options)})
"""

from __future__ import annotations

import hashlib
import json
import secrets
import struct
from dataclasses import dataclass, field
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

FLAG_USER_PRESENT = 0x01
FLAG_USER_VERIFIED = 0x04
FLAG_ATTESTED = 0x40


@dataclass
class Credential:
    """One passkey the authenticator holds."""

    id: bytes
    key: ec.EllipticCurvePrivateKey
    rp_id: str
    user_handle: bytes
    sign_count: int = 0


@dataclass
class SoftAuthenticator:
    """Holds passkeys and answers a server's options with them, from ``origin``."""

    origin: str
    credentials: list[Credential] = field(default_factory=list)

    def register(
        self,
        options: dict[str, Any],
        *,
        origin: str | None = None,
        credential: Credential | None = None,
    ) -> dict[str, Any]:
        """Make a passkey for the options' site and user, and return the browser's JSON for it.

        With ``credential``, offer that existing passkey again instead; with ``origin``, answer
        as if from another site.
        """
        rp_id = options["rp"]["id"]
        if credential is None:
            credential = Credential(
                secrets.token_bytes(32),
                ec.generate_private_key(ec.SECP256R1()),
                rp_id,
                base64url_to_bytes(options["user"]["id"]),
            )
            self.credentials.append(credential)
        numbers = credential.key.public_key().public_numbers()
        cose_key = cbor2.dumps(
            {
                1: 2,  # key type: EC2
                3: -7,  # algorithm: ES256
                -1: 1,  # curve: P-256
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )
        auth_data = (
            hashlib.sha256(rp_id.encode()).digest()
            + bytes([FLAG_USER_PRESENT | FLAG_USER_VERIFIED | FLAG_ATTESTED])
            + struct.pack(">I", 0)
            + bytes(16)  # AAGUID: none
            + struct.pack(">H", len(credential.id))
            + credential.id
            + cose_key
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        return {
            "id": bytes_to_base64url(credential.id),
            "rawId": bytes_to_base64url(credential.id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal", "hybrid"],
            },
            "clientExtensionResults": {},
        }

    def authenticate(
        self,
        options: dict[str, Any],
        *,
        credential: Credential | None = None,
        origin: str | None = None,
    ) -> dict[str, Any]:
        """Sign the options' challenge with a passkey for its site, and return the browser's JSON.

        Uses the first passkey held for the site unless ``credential`` names one; each signature
        moves that passkey's counter on by one.
        """
        if credential is None:
            credential = next(c for c in self.credentials if c.rp_id == options["rpId"])
        credential.sign_count += 1
        auth_data = (
            hashlib.sha256(credential.rp_id.encode()).digest()
            + bytes([FLAG_USER_PRESENT | FLAG_USER_VERIFIED])
            + struct.pack(">I", credential.sign_count)
        )
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        signature = credential.key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": bytes_to_base64url(credential.id),
            "rawId": bytes_to_base64url(credential.id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(credential.user_handle),
            },
            "clientExtensionResults": {},
        }

    def _client_data(self, kind: str, challenge: str, origin: str | None) -> bytes:
        """The client data a browser signs over: the ceremony, its challenge and the origin."""
        return json.dumps(
            {
                "type": kind,
                "challenge": challenge,
                "origin": origin or self.origin,
                "crossOrigin": False,
            }
        ).encode()
