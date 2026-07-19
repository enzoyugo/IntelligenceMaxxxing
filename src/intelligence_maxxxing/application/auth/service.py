"""Initial authentication for the private backend (Stage 1 §6).

Model: application API credentials.
- public identifier:  cred_<24 hex chars>
- secret (shown ONCE): imx_sk_<24 hex chars><43 urlsafe random chars>
- storage: SHA-256 hash of the full secret only; never plaintext.
- request format: Authorization: Bearer <secret>

The credential id is embedded in the secret so lookup is O(1) by primary key
and the hash comparison is a single constant-time compare of the full secret.
Signed short-lived tokens were deliberately deferred: a bearer API secret over
a private loopback interface is simpler and has fewer failure modes than a
half-baked token signer (documented in IDENTITY_AND_PERMISSION_MODEL.md).
"""

import hashlib
import hmac
import secrets

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.application.errors import (
    AuthenticationError,
    PermissionDeniedError,
)
from intelligence_maxxxing.application.ports import IdentityStorePort
from intelligence_maxxxing.domain.audit.models import Actor
from intelligence_maxxxing.domain.common.base import UtcDatetime, utc_now
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.domain.identity import CredentialStatus, IdentityStatus
from intelligence_maxxxing.observability.logging import get_logger
from intelligence_maxxxing.permissions import PermissionScope

_SECRET_PREFIX = "imx_sk_"
_CRED_HEX_LENGTH = 24
_logger = get_logger("intelligence_maxxxing.auth")


class AuthContext(BaseModel):
    """The authenticated identity of a request.

    This is the ONLY source of actor identity for writes. Request bodies can
    never spoof these fields.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    application_id: str = Field(min_length=1)
    credential_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    scopes: frozenset[str]
    authenticated_at: UtcDatetime

    @property
    def actor(self) -> Actor:
        return Actor(actor_type=ActorType.APPLICATION, actor_id=self.application_id)

    def has_scope(self, scope: PermissionScope) -> bool:
        return scope.value in self.scopes


def require_scope(context: AuthContext, scope: PermissionScope) -> None:
    """Deny closed: raises PermissionDeniedError unless the scope is granted."""
    if not context.has_scope(scope):
        raise PermissionDeniedError(f"scope {scope.value} is required for this operation")


def generate_credential_secret(credential_hex: str) -> str:
    """Generate a cryptographically random secret embedding the credential id."""
    if len(credential_hex) != _CRED_HEX_LENGTH:
        raise ValueError("credential hex fragment must be exactly 24 characters")
    return f"{_SECRET_PREFIX}{credential_hex}{secrets.token_urlsafe(32)}"


def hash_credential_secret(secret: str) -> str:
    """SHA-256 of the full secret. High-entropy random secrets do not need a
    slow KDF; there is nothing human-chosen to brute-force."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def parse_credential_id_from_secret(secret: str) -> str | None:
    """Extract cred_<hex> from a well-formed secret, else None."""
    if not secret.startswith(_SECRET_PREFIX):
        return None
    remainder = secret[len(_SECRET_PREFIX) :]
    if len(remainder) <= _CRED_HEX_LENGTH:
        return None
    fragment = remainder[:_CRED_HEX_LENGTH]
    if any(ch not in "0123456789abcdef" for ch in fragment):
        return None
    return f"cred_{fragment}"


class AuthenticationService:
    """Resolves Authorization headers into an AuthContext, deny-closed."""

    def __init__(self, identity: IdentityStorePort) -> None:
        self._identity = identity

    def authenticate(self, authorization_header: str | None, request_id: str) -> AuthContext:
        try:
            context = self._authenticate(authorization_header)
        except AuthenticationError as exc:
            _logger.warning(
                "authentication rejected",
                extra={"request_id": request_id, "auth_error": exc.message},
            )
            raise
        _logger.info(
            "authentication accepted",
            extra={
                "request_id": request_id,
                "application_id": context.application_id,
                "credential_id": context.credential_id,
            },
        )
        return context

    def _authenticate(self, authorization_header: str | None) -> AuthContext:
        if not authorization_header:
            raise AuthenticationError("missing Authorization header")
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise AuthenticationError("Authorization header must be 'Bearer <credential>'")
        token = token.strip()

        credential_id = parse_credential_id_from_secret(token)
        if credential_id is None:
            raise AuthenticationError("malformed credential")

        credential = self._identity.get_credential(credential_id)
        if credential is None:
            raise AuthenticationError("unknown credential")

        provided_hash = hash_credential_secret(token)
        if not hmac.compare_digest(provided_hash, credential.secret_hash):
            raise AuthenticationError("invalid credential")

        now = utc_now()
        if credential.status is CredentialStatus.REVOKED:
            raise AuthenticationError("credential has been revoked")
        if credential.status is CredentialStatus.EXPIRED or (
            credential.expires_at is not None and credential.expires_at <= now
        ):
            raise AuthenticationError("credential has expired")
        if credential.status is not CredentialStatus.ACTIVE:
            raise AuthenticationError("credential is not active")

        application = self._identity.get_application(credential.application_id)
        if application is None:
            raise AuthenticationError("credential is not bound to a known application")
        if application.status is not IdentityStatus.ACTIVE:
            raise AuthenticationError("application is disabled")

        scopes = frozenset(self._identity.get_application_scopes(application.id))
        self._identity.touch_credential(credential_id, last_used_at=now)

        return AuthContext(
            application_id=application.id,
            credential_id=credential_id,
            tenant_id=application.tenant_id,
            owner_id=application.owner_id,
            scopes=scopes,
            authenticated_at=now,
        )
