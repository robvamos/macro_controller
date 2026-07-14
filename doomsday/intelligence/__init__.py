"""Goal-driven, provenance-aware intelligence core for Doomsday."""

from doomsday.intelligence.models import (
    ActionBinding,
    ActionDefinition,
    AutomationPolicy,
    EvidenceClaim,
    EvidenceSource,
    GamePlan,
    GameModeDefinition,
    GameState,
    GoalInterpretation,
    ObjectiveDefinition,
    Observation,
    PlanStep,
    RiskClass,
    RulesetDefinition,
)
from doomsday.intelligence.adapters import ActionBindingProvider
from doomsday.intelligence.evidence import EvidenceResolver, ProviderContribution
from doomsday.intelligence.execution import (
    ExecutionPolicyContext,
    ExecutionPolicyGate,
    ExecutionReceipt,
    StepExecutor,
)
from doomsday.intelligence.outcomes import OutcomeAssessment, OutcomeEvaluator
from doomsday.intelligence.persistence import IntelligenceRepository
from doomsday.intelligence.planner import WorkflowPlanner
from doomsday.intelligence.providers import EnrichmentProvider, ProviderOrchestrator
from doomsday.intelligence.registry import DomainRegistry
from doomsday.intelligence.service import GameIntelligenceResult, GameIntelligenceService
from doomsday.intelligence.state_estimator import StateEstimate, StateEstimator
from doomsday.intelligence.sources import KnowledgeSourceSelector, RankedSourceHint

__all__ = [
    "ActionBinding",
    "ActionDefinition",
    "ActionBindingProvider",
    "AutomationPolicy",
    "DomainRegistry",
    "EvidenceClaim",
    "EvidenceSource",
    "EvidenceResolver",
    "EnrichmentProvider",
    "ExecutionPolicyContext",
    "ExecutionPolicyGate",
    "ExecutionReceipt",
    "GameIntelligenceResult",
    "GameIntelligenceService",
    "GameModeDefinition",
    "GamePlan",
    "GameState",
    "GoalInterpretation",
    "KnowledgeSourceSelector",
    "ObjectiveDefinition",
    "Observation",
    "OutcomeAssessment",
    "OutcomeEvaluator",
    "PlanStep",
    "ProviderContribution",
    "ProviderOrchestrator",
    "RankedSourceHint",
    "RiskClass",
    "RulesetDefinition",
    "StateEstimate",
    "StateEstimator",
    "StepExecutor",
    "WorkflowPlanner",
]
