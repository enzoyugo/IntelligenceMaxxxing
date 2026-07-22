"""M3B Research Factory — Evidence / Safety / Report foundation (not Milestone 3 complete)."""

from intelligence_maxxxing.domain_packs.research_factory_m3b.constants import (
    M3B_ID,
    M3B_VERSION,
)
from intelligence_maxxxing.domain_packs.research_factory_m3b.evidence_agent_v1 import EvidenceAgentV1
from intelligence_maxxxing.domain_packs.research_factory_m3b.report_agent_v1 import ReportAgentV1
from intelligence_maxxxing.domain_packs.research_factory_m3b.safety_auditor_agent_v1 import (
    SafetyAuditorAgentV1,
)
from intelligence_maxxxing.domain_packs.research_factory_m3b.service_v1 import ResearchM3BService

__all__ = [
    "M3B_ID",
    "M3B_VERSION",
    "EvidenceAgentV1",
    "SafetyAuditorAgentV1",
    "ReportAgentV1",
    "ResearchM3BService",
]
