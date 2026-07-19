"""ObservationAccepted event contract (v1).

The payload of an ObservationAccepted event is the accepted Observation
serialized in canonical JSON form.
"""

from typing import Final

from intelligence_maxxxing.domain.observations import Observation

OBSERVATION_ACCEPTED_EVENT_TYPE: Final = "ObservationAccepted"

# The payload schema of the event is the Observation contract itself.
ObservationAcceptedPayload = Observation
