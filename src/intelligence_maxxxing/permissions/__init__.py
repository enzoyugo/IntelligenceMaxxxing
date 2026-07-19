"""Permission scopes (Engine Service Contract §5).

Stage 1 status: ENFORCED for the endpoints that exist. Scopes are granted to
applications through the governed local CLI, never through HTTP, and a token
can never elevate its own scopes (they are read from the identity store on
every request).
"""

from enum import StrEnum


class PermissionScope(StrEnum):
    READ_INTELLIGENCE = "READ_INTELLIGENCE"
    SUBMIT_EVIDENCE = "SUBMIT_EVIDENCE"
    SUBMIT_OBSERVATION = "SUBMIT_OBSERVATION"
    EXECUTE_ACTION = "EXECUTE_ACTION"
    READ_AUDIT = "READ_AUDIT"
    SUBMIT_DECISION = "SUBMIT_DECISION"
    SUBMIT_OUTCOME = "SUBMIT_OUTCOME"
    REQUEST_DELETION = "REQUEST_DELETION"
    MANAGE_DOMAIN_PACK = "MANAGE_DOMAIN_PACK"
    APPROVE_EXECUTION = "APPROVE_EXECUTION"
    ADMINISTER_ENGINE = "ADMINISTER_ENGINE"
