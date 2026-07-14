import copy
import unittest
from pathlib import Path
from types import SimpleNamespace

from doomsday.intelligence.adapters import (
    UIGraphMacroBindingProvider,
    observations_from_ui_evaluation,
)
from doomsday.intelligence.evidence import EvidenceResolver, ProviderContribution
from doomsday.intelligence.execution import ExecutionPolicyContext, ExecutionPolicyGate
from doomsday.intelligence.models import (
    ActionBinding,
    AutomationPolicy,
    GameState,
    GoalInterpretation,
    RiskClass,
    Observation,
)
from doomsday.intelligence.planner import WorkflowPlanner
from doomsday.intelligence.outcomes import OutcomeEvaluator
from doomsday.intelligence.providers import (
    ProviderDescriptor,
    ProviderHealth,
    ProviderOrchestrator,
)
from doomsday.intelligence.registry import DomainRegistry
from doomsday.intelligence.service import GameIntelligenceService
from doomsday.intelligence.state_estimator import StateEstimator
from doomsday.intelligence.sources import KnowledgeSourceSelector


def build_minimal_registry_payload():
    return {
        "schema": "doomsday.intelligence.domain.v1",
        "registry_version": "1.0.0",
        "game_version": "2.1.0",
        "updated_at": "2026-07-14T12:00:00+00:00",
        "sources": [
            {
                "source_id": "official-rules",
                "label": "Regole ufficiali",
                "source_type": "official",
                "trust_score": 0.95,
            }
        ],
        "claims": [
            {
                "claim_id": "campaign-current-rules",
                "subject": "mode.campaign",
                "predicate": "ruleset",
                "value": "campaign-v2",
                "confidence": 0.95,
                "source_id": "official-rules",
            }
        ],
        "actions": [
            {
                "action_id": "already-open",
                "label": "Apri Campagna",
                "intents": ["open_campaign"],
                "preconditions": {},
                "effects": {"ui.campaign.open": True},
                "automation_policy": "autonomous",
                "risk_class": "low",
            },
            {
                "action_id": "ticket-gate",
                "label": "Verifica ticket",
                "intents": ["check_ticket"],
                "preconditions": {"ticket.available": True},
                "effects": {"ticket.checked": True},
                "automation_policy": "autonomous",
                "risk_class": "low",
            },
            {
                "action_id": "confirm-battle",
                "label": "Avvia battaglia",
                "intents": ["start_battle"],
                "preconditions": {},
                "effects": {"battle.confirmed": True},
                "automation_policy": "confirm_each",
                "risk_class": "high",
                "macro_intent": "start_battle",
                "target_ui_node": "battle_start_button",
                "reversible": False,
            },
            {
                "action_id": "unbound-finish",
                "label": "Concludi attività",
                "intents": ["finish_activity"],
                "preconditions": {},
                "effects": {"objective.complete": True},
                "automation_policy": "autonomous",
                "risk_class": "low",
                "macro_intent": "finish_activity",
                "target_ui_node": "finish_button",
            },
        ],
        "modes": [
            {
                "mode_id": "campaign",
                "label": "Campagna",
                "aliases": ["missione"],
                "mode_kind": "activity",
                "lifecycle": "active",
                "rulesets": [
                    {
                        "ruleset_id": "campaign-v1",
                        "label": "Campagna legacy",
                        "engine": "legacy",
                        "lifecycle": "retired",
                        "valid_from_game_version": "1.0.0",
                        "valid_until_game_version": "1.9.9",
                        "workflow": [],
                        "objectives": [
                            {
                                "objective_id": "legacy-finish",
                                "label": "Completa campagna legacy",
                                "aliases": ["completa"],
                                "goal_facts": {"legacy.complete": True},
                            }
                        ],
                        "success_facts": {"legacy.complete": True},
                        "risk_class": "low",
                        "evidence_claim_ids": [],
                    },
                    {
                        "ruleset_id": "campaign-v2",
                        "label": "Campagna corrente",
                        "engine": "workflow",
                        "lifecycle": "current",
                        "valid_from_game_version": "2.0.0",
                        "valid_until_game_version": "2.9.9",
                        "workflow": [
                            "already-open",
                            "ticket-gate",
                            "confirm-battle",
                            "unbound-finish",
                        ],
                        "objectives": [
                            {
                                "objective_id": "finish-campaign",
                                "label": "Completa campagna",
                                "aliases": ["completa", "vincere"],
                                "goal_facts": {"objective.complete": True},
                            }
                        ],
                        "constraints": [{"confirmation": "battle"}],
                        "success_facts": {"objective.complete": True},
                        "risk_class": "high",
                        "evidence_claim_ids": ["campaign-current-rules"],
                    },
                ],
            },
            {
                "mode_id": "challenge",
                "label": "Challenge",
                "aliases": ["missione"],
                "mode_kind": "activity",
                "lifecycle": "active",
                "rulesets": [
                    {
                        "ruleset_id": "challenge-v2",
                        "label": "Challenge corrente",
                        "engine": "workflow",
                        "lifecycle": "current",
                        "valid_from_game_version": "2.0.0",
                        "valid_until_game_version": "2.9.9",
                        "workflow": [],
                        "objectives": [
                            {
                                "objective_id": "finish-challenge",
                                "label": "Completa challenge",
                                "aliases": ["completa"],
                                "goal_facts": {"challenge.complete": True},
                            }
                        ],
                        "success_facts": {"challenge.complete": True},
                        "risk_class": "medium",
                        "evidence_claim_ids": [],
                    }
                ],
            },
            {
                "mode_id": "archive",
                "label": "Modalità archivio",
                "aliases": ["archivio"],
                "mode_kind": "activity",
                "lifecycle": "inactive",
                "rulesets": [
                    {
                        "ruleset_id": "archive-v1",
                        "label": "Archivio scaduto",
                        "engine": "legacy",
                        "lifecycle": "retired",
                        "valid_from_game_version": "1.0.0",
                        "valid_until_game_version": "1.9.9",
                        "workflow": [],
                        "objectives": [],
                        "success_facts": {},
                        "risk_class": "low",
                        "evidence_claim_ids": [],
                    }
                ],
            },
        ],
    }


class SelectiveBindingProvider:
    def resolve(self, action, *, ruleset, state):
        if action.action_id != "confirm-battle":
            return None
        return ActionBinding(
            action_id=action.action_id,
            binding_type="fake",
            binding_id="binding-confirm-battle",
            label="Fake battle executor",
            confidence=0.9,
            metadata={"ruleset_id": ruleset.ruleset_id},
        )


class DomainRegistryTests(unittest.TestCase):
    def test_minimal_payload_is_parsed_and_validated(self):
        registry = DomainRegistry.from_payload(build_minimal_registry_payload())

        self.assertEqual(registry.validate(), ())
        self.assertEqual(registry.registry_version, "1.0.0")
        self.assertEqual(registry.get_action("confirm-battle").risk_class, RiskClass.HIGH)
        self.assertEqual(
            registry.get_action("confirm-battle").automation_policy,
            AutomationPolicy.CONFIRM_EACH,
        )
        self.assertEqual(registry.get_source("official-rules").trust_score, 0.95)
        self.assertEqual(registry.get_claim("campaign-current-rules").value, "campaign-v2")

    def test_validation_reports_broken_references_and_duplicates(self):
        payload = copy.deepcopy(build_minimal_registry_payload())
        payload["modes"].append(copy.deepcopy(payload["modes"][0]))
        payload["modes"][0]["rulesets"][1]["workflow"].append("missing-action")
        payload["claims"][0]["source_id"] = "missing-source"

        issues = DomainRegistry.from_payload(payload).validate()

        self.assertTrue(any("duplicate mode_id: campaign" in issue for issue in issues))
        self.assertTrue(any("unknown action missing-action" in issue for issue in issues))
        self.assertTrue(any("unknown source missing-source" in issue for issue in issues))

    def test_rulesets_are_filtered_by_version_and_inactive_mode_is_opt_in(self):
        registry = DomainRegistry.from_payload(build_minimal_registry_payload())

        self.assertEqual(registry.resolve_ruleset("campaign", game_version="1.5.0").ruleset_id, "campaign-v1")
        self.assertEqual(registry.resolve_ruleset("campaign", game_version="2.1.0").ruleset_id, "campaign-v2")
        self.assertIsNone(registry.resolve_ruleset("campaign", game_version="3.0.0"))
        self.assertEqual(registry.resolve_modes("archivio", game_version="2.1.0"), ())
        inactive = registry.resolve_modes(
            "archivio",
            game_version="2.1.0",
            include_inactive=True,
        )
        self.assertEqual([mode.mode_id for mode, _score in inactive], ["archive"])

    def test_published_registry_validates_and_selects_arena_transition(self):
        registry_path = Path(__file__).parents[1] / "data" / "doomsday" / "intelligence" / "domain_registry.json"
        registry = DomainRegistry.load(registry_path)

        self.assertEqual(registry.validate(), ())
        self.assertEqual(
            registry.resolve_ruleset("arena_of_doom", game_version="1.43.4").ruleset_id,
            "arena_of_doom.freedom",
        )
        self.assertEqual(
            registry.resolve_ruleset("arena_of_doom", game_version="1.43.5").ruleset_id,
            "arena_of_doom.glory_current",
        )


class InterpretationAndPlannerTests(unittest.TestCase):
    def setUp(self):
        self.registry = DomainRegistry.from_payload(build_minimal_registry_payload())

    def test_interpretation_exposes_close_mode_ambiguity(self):
        interpretation = GameIntelligenceService(self.registry).interpret_goal(
            "missione",
            game_version="2.1.0",
        )

        candidate_ids = {interpretation.mode_id, *interpretation.alternatives}
        self.assertEqual(candidate_ids, {"campaign", "challenge"})
        self.assertTrue(interpretation.needs_context)
        self.assertTrue(interpretation.assumptions)

    def test_planner_covers_skip_missing_precondition_confirmation_and_unbound(self):
        interpretation = GoalInterpretation(
            query="completa campagna",
            mode_id="campaign",
            ruleset_id="campaign-v2",
            objective_id="finish-campaign",
            confidence=1.0,
        )
        planner = WorkflowPlanner(
            self.registry,
            binding_provider=SelectiveBindingProvider(),
        )

        plan = planner.plan(
            interpretation,
            GameState(facts={"ui.campaign.open": True}, game_version="2.1.0"),
        )
        steps = {step.action_id: step for step in plan.steps}

        self.assertEqual(steps["already-open"].status, "skipped")
        self.assertEqual(steps["ticket-gate"].status, "blocked")
        self.assertIn("ticket.available=True", steps["ticket-gate"].reason)
        self.assertEqual(steps["confirm-battle"].status, "confirmation_required")
        self.assertEqual(steps["confirm-battle"].binding.binding_id, "binding-confirm-battle")
        self.assertEqual(steps["unbound-finish"].status, "unbound")
        self.assertIsNone(steps["unbound-finish"].binding)
        self.assertTrue(plan.blocked)
        self.assertTrue(any("nessuna macro collegata" in warning for warning in plan.warnings))

    def test_planner_does_not_promote_unexecuted_effects_to_facts(self):
        payload = build_minimal_registry_payload()
        payload["actions"][-1]["preconditions"] = {"battle.confirmed": True}
        registry = DomainRegistry.from_payload(payload)
        interpretation = GoalInterpretation(
            query="completa campagna",
            mode_id="campaign",
            ruleset_id="campaign-v2",
            objective_id="finish-campaign",
            confidence=1.0,
        )

        plan = WorkflowPlanner(
            registry,
            binding_provider=SelectiveBindingProvider(),
        ).plan(interpretation, GameState(facts={"ticket.available": True}, game_version="2.1.0"))
        steps = {step.action_id: step for step in plan.steps}

        self.assertEqual(steps["confirm-battle"].status, "confirmation_required")
        self.assertEqual(steps["unbound-finish"].status, "blocked")
        self.assertNotIn("battle.confirmed", plan.projected_facts)

    def test_interpretation_extracts_explicit_resource_constraint(self):
        interpretation = GameIntelligenceService(self.registry).interpret_goal(
            "completa campagna senza spendere valuta",
            game_version="2.1.0",
        )

        self.assertEqual(
            interpretation.constraints["forbidden_resources"],
            ("event_currency", "gems", "premium_currency"),
        )

    def test_planner_excludes_action_that_violates_goal_resource_constraint(self):
        payload = build_minimal_registry_payload()
        payload["actions"][-1]["cost"] = {"resources": ["event_currency"]}
        registry = DomainRegistry.from_payload(payload)
        interpretation = GoalInterpretation(
            query="completa senza spendere valuta",
            mode_id="campaign",
            ruleset_id="campaign-v2",
            objective_id="finish-campaign",
            confidence=1.0,
            constraints={"forbidden_resources": ("event_currency",)},
        )

        plan = WorkflowPlanner(registry).plan(interpretation, GameState())

        finish = next(step for step in plan.steps if step.action_id == "unbound-finish")
        self.assertEqual(finish.status, "excluded")


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry = DomainRegistry.from_payload(build_minimal_registry_payload())

    def test_ui_graph_macro_adapter_uses_fake_resolver_and_prefers_preferred_link(self):
        calls = []

        def fake_resolver(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                candidate_links=(
                    SimpleNamespace(
                        relation_type="candidate",
                        priority=1,
                        macro_id=5,
                        macro_name="Candidate macro",
                    ),
                    SimpleNamespace(
                        relation_type="preferred",
                        priority=50,
                        macro_id=9,
                        macro_name="Preferred macro",
                    ),
                )
            )

        provider = UIGraphMacroBindingProvider(resolver=fake_resolver)
        action = self.registry.get_action("confirm-battle")
        ruleset = self.registry.get_ruleset("campaign-v2")

        binding = provider.resolve(action, ruleset=ruleset, state=GameState())

        self.assertEqual(calls, [{
            "graph_id": "doomsday-default-ui-graph",
            "node_id": "battle_start_button",
            "intent_key": "start_battle",
        }])
        self.assertEqual(binding.binding_id, "9")
        self.assertEqual(binding.label, "Preferred macro")
        self.assertEqual(binding.metadata["relation_type"], "preferred")

    def test_ui_evaluation_adapter_accepts_plain_fake_objects_and_clamps_confidence(self):
        evaluation = SimpleNamespace(
            graph_id="fake-graph",
            node_results=(
                SimpleNamespace(
                    node_id="campaign",
                    active=True,
                    confidence=1.4,
                    condition_results=(SimpleNamespace(satisfied=True),),
                ),
                SimpleNamespace(
                    node_id="popup",
                    active=False,
                    confidence=-0.2,
                    condition_results=(SimpleNamespace(satisfied=False),),
                ),
            ),
        )

        observations = observations_from_ui_evaluation(evaluation)
        by_key = {item.key: item for item in observations}

        self.assertEqual(by_key["ui.node.campaign.active"].value, True)
        self.assertEqual(by_key["ui.node.campaign.active"].confidence, 1.0)
        self.assertEqual(by_key["ui.node.popup.active"].value, False)
        self.assertEqual(by_key["ui.node.popup.active"].confidence, 0.0)
        self.assertEqual(by_key["ui.observed"].metadata["graph_id"], "fake-graph")


class EvidenceResolverTests(unittest.TestCase):
    def test_conflicting_values_are_ranked_without_discarding_alternatives(self):
        contributions = (
            ProviderContribution(
                provider_id="official",
                provider_type="official",
                subject_id="hero.elena",
                field_name="skill_damage",
                field_value=100,
                confidence=0.9,
                trust_score=0.9,
                observed_at="",
                source_ref="official:elena",
                game_version="2.1.0",
            ),
            ProviderContribution(
                provider_id="ocr",
                provider_type="runtime-ocr",
                subject_id="hero.elena",
                field_name="skill_damage",
                field_value=100,
                confidence=0.8,
                trust_score=0.8,
                observed_at="",
                source_ref="ocr:screenshot-1",
                game_version="2.1.0",
            ),
            ProviderContribution(
                provider_id="community",
                provider_type="discord",
                subject_id="hero.elena",
                field_name="skill_damage",
                field_value=120,
                confidence=0.95,
                trust_score=0.95,
                observed_at="",
                source_ref="discord:message-1",
                game_version="2.1.0",
            ),
        )

        resolution = EvidenceResolver().resolve(contributions)

        self.assertEqual(resolution.selected_value, 100)
        self.assertTrue(resolution.conflicts)
        self.assertEqual(resolution.contribution_count, 3)
        self.assertEqual(len(resolution.alternatives), 2)
        self.assertEqual(resolution.alternatives[0].provider_ids, ("ocr", "official"))
        self.assertGreater(resolution.confidence, 0.5)
        self.assertTrue(any("conflitto" in note for note in resolution.notes))

    def test_resolver_rejects_contributions_for_different_fields(self):
        common = dict(
            provider_id="provider",
            provider_type="test",
            subject_id="hero.elena",
            field_value=100,
            confidence=0.8,
            observed_at="",
            source_ref="test",
        )
        with self.assertRaises(ValueError):
            EvidenceResolver().resolve(
                (
                    ProviderContribution(field_name="skill_damage", **common),
                    ProviderContribution(field_name="attack", **common),
                )
            )


class StateEstimatorTests(unittest.TestCase):
    def test_conflicting_observations_remain_unknown_to_planner_state(self):
        observations = (
            Observation(
                key="ui.mode",
                value="arena",
                confidence=0.85,
                source_id="ocr",
                evidence_id="ocr-1",
            ),
            Observation(
                key="ui.mode",
                value="campaign",
                confidence=0.8,
                source_id="ui-graph",
                evidence_id="ui-1",
            ),
        )

        estimate = StateEstimator(conflict_margin=0.1).estimate(observations)

        self.assertNotIn("ui.mode", estimate.state.materialize())
        self.assertEqual(len(estimate.conflicts), 1)
        self.assertEqual(len(estimate.conflicting_observations), 2)

    def test_explicit_fact_has_precedence_over_observation(self):
        estimate = StateEstimator().estimate(
            (
                Observation(
                    key="account.spend_allowed",
                    value=True,
                    confidence=1.0,
                    source_id="ocr",
                ),
            ),
            base_state=GameState(facts={"account.spend_allowed": False}),
        )

        self.assertEqual(estimate.state.value("account.spend_allowed"), False)
        self.assertEqual(estimate.state.materialize()["account.spend_allowed"], False)


class _StagedProvider:
    def __init__(self, provider_id, *, failure_stage=""):
        self.provider_id = provider_id
        self.failure_stage = failure_stage

    def describe_provider(self):
        return ProviderDescriptor(
            provider_id=self.provider_id,
            provider_type="test",
            label=self.provider_id,
            object_types=("hero",),
        )

    def supports(self, object_type, fields, context):
        return object_type == "hero"

    def health(self):
        return ProviderHealth(provider_id=self.provider_id, available=True)

    def discover(self, seed, cursor=None):
        return ("candidate",)

    def collect(self, candidate):
        if self.failure_stage == "collect":
            raise RuntimeError("collect failed")
        return candidate

    def normalize(self, artifact):
        if self.failure_stage == "normalize":
            raise RuntimeError("normalize failed")
        return artifact

    def emit_observations(self, normalized):
        if self.failure_stage == "emit":
            raise RuntimeError("emit failed")
        return (
            ProviderContribution(
                provider_id=self.provider_id,
                provider_type="test",
                subject_id="hero.test",
                field_name="rarity",
                field_value="legendary",
                confidence=0.8,
                observed_at="",
                source_ref=f"test:{self.provider_id}",
            ),
        )


class ProviderOrchestratorTests(unittest.TestCase):
    def test_provider_stage_failure_does_not_abort_other_providers(self):
        orchestrator = ProviderOrchestrator(
            (
                _StagedProvider("broken", failure_stage="normalize"),
                _StagedProvider("healthy"),
            )
        )

        result = orchestrator.run(object_type="hero", seed={"name": "test"})

        self.assertEqual([item.provider_id for item in result.contributions], ["healthy"])
        self.assertEqual(result.providers_considered, ("broken", "healthy"))
        self.assertEqual([(item.provider_id, item.stage) for item in result.errors], [("broken", "normalize")])


class KnowledgeSourceSelectorTests(unittest.TestCase):
    def test_selector_delegates_ranking_to_shared_registry(self):
        calls = []

        class FakeRegistry:
            def find(self, query, **kwargs):
                calls.append((query, kwargs))
                return [
                    SimpleNamespace(
                        source_id="in-game-rules",
                        label="Regole in-game",
                        category="game_runtime_evidence",
                        trust_score=1.0,
                        signal_score=1.0,
                        noise_score=0.0,
                        access_mode="authenticated-local-runtime",
                        metadata={"current": True},
                    )
                ]

        hints = KnowledgeSourceSelector(FakeRegistry()).rank(
            "arena rules",
            usage_mode="current_rules",
            limit=3,
        )

        self.assertEqual(hints[0].source_id, "in-game-rules")
        self.assertEqual(hints[0].metadata, {"current": True})
        self.assertEqual(
            calls,
            [("arena rules", {"category": None, "usage_mode": "current_rules", "domain": "doomsday_last_survivors", "limit": 3})],
        )


class ExecutionAndOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.registry = DomainRegistry.from_payload(build_minimal_registry_payload())
        interpretation = GoalInterpretation(
            query="completa campagna",
            mode_id="campaign",
            ruleset_id="campaign-v2",
            objective_id="finish-campaign",
            confidence=1.0,
        )
        self.plan = WorkflowPlanner(
            self.registry,
            binding_provider=SelectiveBindingProvider(),
        ).plan(interpretation, GameState(facts={"ticket.available": True}))

    def test_policy_gate_requires_fresh_confirmation_for_high_risk_step(self):
        step = next(item for item in self.plan.steps if item.action_id == "confirm-battle")
        gate = ExecutionPolicyGate()

        denied = gate.evaluate(
            step,
            state=GameState(),
            context=ExecutionPolicyContext(perception_confidence=0.95),
        )
        allowed = gate.evaluate(
            step,
            state=GameState(),
            context=ExecutionPolicyContext(user_confirmed=True, perception_confidence=0.95),
        )

        self.assertFalse(denied.allowed)
        self.assertTrue(denied.requires_confirmation)
        self.assertTrue(allowed.allowed)

    def test_outcome_evaluator_detects_completed_objective_and_effect_mismatch(self):
        completed = OutcomeEvaluator().evaluate(
            self.plan,
            post_state=GameState(
                facts={
                    "battle.confirmed": True,
                    "objective.complete": True,
                }
            ),
            executed_action_ids=("confirm-battle", "unbound-finish"),
        )
        mismatch = OutcomeEvaluator().evaluate(
            self.plan,
            post_state=GameState(facts={}),
            executed_action_ids=("confirm-battle",),
        )

        self.assertTrue(completed.objective_complete)
        self.assertEqual(completed.status, "completed")
        self.assertEqual(mismatch.status, "effect_mismatch")
        self.assertTrue(mismatch.discrepancies)


if __name__ == "__main__":
    unittest.main()
