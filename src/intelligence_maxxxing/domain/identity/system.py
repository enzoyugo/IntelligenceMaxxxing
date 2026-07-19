"""The Engine's own modeled governance identity.

Engine-internal writes (bootstrap, projection rebuilds, integrity checks)
must be attributed to an explicit, modeled identity - never to an implicit
magic string scattered through the code. These constants ARE that model:
they name the Engine's own governance stream, which is documented and
constant by design (it exists before any tenant/user row can exist).
"""

from typing import Final

from intelligence_maxxxing.domain.audit.models import Actor
from intelligence_maxxxing.domain.common.epistemic import ActorType

SYSTEM_TENANT_ID: Final = "tnt_system"
SYSTEM_OWNER_ID: Final = "usr_system"
SYSTEM_APPLICATION_ID: Final = "app_system"

SYSTEM_ACTOR: Final = Actor(actor_type=ActorType.SYSTEM, actor_id="engine-system")
