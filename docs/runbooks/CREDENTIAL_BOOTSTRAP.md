# Credential Bootstrap — Stage 1

**Audience:** Operators performing first-time Engine setup  
**Prerequisites:** PostgreSQL running, migrations at head (`0002_stage1`)

All commands use the local CLI. There are **no HTTP endpoints** for identity administration.

---

## 1. Overview

Bootstrap sequence:

```text
bootstrap-owner → register-application → create-credential → grant-scope
```

Each step appends catalog events and audit records. The API secret is shown **once** at credential creation.

---

## 2. Bootstrap the owner

Creates the private tenant and owner user.

```powershell
python -m intelligence_maxxxing.cli bootstrap-owner `
  --tenant-name "Private Instance" `
  --owner-name "Constitutional Owner"
```

Output:

```text
tenant_id=tnt_...
owner_id=usr_...
```

Save both IDs. The owner id is required for application registration.

---

## 3. Register an application

`owner_id` is assigned here — it cannot be chosen later via the public API.

```powershell
python -m intelligence_maxxxing.cli register-application `
  --display-name "Demo Client" `
  --owner-id usr_<from bootstrap>
```

Output:

```text
application_id=app_...
owner_id=usr_...
tenant_id=tnt_...
```

---

## 4. Create an API credential

```powershell
python -m intelligence_maxxxing.cli create-credential `
  --application-id app_<from registration>
```

Output:

```text
credential_id=cred_<24 hex chars>
secret=imx_sk_<24 hex><random>
Store the secret now; it will never be shown again.
```

**Store the secret immediately.** Only the SHA-256 hash is persisted. There is no recovery path.

Optional expiration:

```powershell
python -m intelligence_maxxxing.cli create-credential `
  --application-id app_<id> `
  --expires-at 2027-01-01T00:00:00+00:00
```

---

## 5. Grant scopes

Grant the scopes required for API access:

```powershell
# Submit observations
python -m intelligence_maxxxing.cli grant-scope `
  --application-id app_<id> `
  --scope SUBMIT_OBSERVATION

# Read observations
python -m intelligence_maxxxing.cli grant-scope `
  --application-id app_<id> `
  --scope READ_INTELLIGENCE

# Read audit records
python -m intelligence_maxxxing.cli grant-scope `
  --application-id app_<id> `
  --scope READ_AUDIT
```

Available scopes: `READ_INTELLIGENCE`, `SUBMIT_EVIDENCE`, `SUBMIT_OBSERVATION`, `EXECUTE_ACTION`, `READ_AUDIT`, `SUBMIT_DECISION`, `SUBMIT_OUTCOME`, `REQUEST_DELETION`, `MANAGE_DOMAIN_PACK`, `APPROVE_EXECUTION`, `ADMINISTER_ENGINE`.

Scopes are read from the identity store on every request. A credential cannot grant itself additional scopes.

---

## 6. Use the credential

All authenticated API calls require:

```text
Authorization: Bearer imx_sk_<secret>
```

Example:

```powershell
curl.exe -X POST http://127.0.0.1:8100/api/v1/observations `
  -H "Authorization: Bearer imx_sk_..." `
  -H "Content-Type: application/json" `
  -H "Idempotency-Key: demo-001" `
  -d "{\"schema_version\":\"1.0\",\"subject\":\"sleep\",\"statement\":\"Slept 7.5 hours\",\"knowledge_class\":\"OBSERVED_FACT\",\"observed_by\":\"demo\",\"context\":{\"scope\":\"personal\"}}"
```

Public endpoints without auth: `GET /health/live`, `GET /health/ready`.

---

## 7. Credential lifecycle

| Command | Purpose |
|---|---|
| `rotate-credential --credential-id cred_...` | Revoke old, issue new secret (shown once) |
| `revoke-credential --credential-id cred_...` | Permanently revoke |
| `list-applications` | List registered applications |

---

## 8. SDK usage

```python
from intelligence_maxxxing_client import IntelligenceMaxxxingClient

with IntelligenceMaxxxingClient(
    base_url="http://127.0.0.1:8100",
    credential_secret="imx_sk_...",
) as client:
    print(client.health().status)
```

The SDK never logs the secret.

---

## 9. Security notes

- Dev compose PostgreSQL credentials are not production-safe.
- Bearer secrets over `127.0.0.1` are appropriate for the private local backend; remote deployment requires TLS and secret management (deferred).
- Revoked, expired, and disabled-application credentials are rejected deny-closed.

See also: `docs/architecture/IDENTITY_AND_PERMISSION_MODEL.md`.
