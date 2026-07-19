"""Permission scopes (Engine Service Contract §5).

Stage 0 status: CONTRACT_ONLY. Scopes are declared so contracts and future
endpoints share one vocabulary. Enforcement (auth, tokens) is deferred and is
not simulated: Stage 0 runs on a private local interface only.
"""

from enum import StrEnum


class PermissionScope(StrEnum):
    READ_INTELLIGENCE = "READ_INTELLIGENCE"
    SUBMIT_EVIDENCE = "SUBMIT_EVIDENCE"
    EXECUTE_ACTION = "EXECUTE_ACTION"
    READ_AUDIT = "READ_AUDIT"
    SUBMIT_DECISION = "SUBMIT_DECISION"
    SUBMIT_OUTCOME = "SUBMIT_OUTCOME"
    REQUEST_DELETION = "REQUEST_DELETION"
    MANAGE_DOMAIN_PACK = "MANAGE_DOMAIN_PACK"
    APPROVE_EXECUTION = "APPROVE_EXECUTION"
