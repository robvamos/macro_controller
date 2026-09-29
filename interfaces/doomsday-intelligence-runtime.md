# doomsday-intelligence-runtime

- Producer: ddgameass
- Status: draft
- Interface version: 0.2.1
- Current transport: in-process Python
- Future transport: optional local JSON API, without changing domain payloads
- Default execution mode: planning only

## Purpose

This interface exposes the goal-driven, provenance-aware Doomsday intelligence
core without coupling consumers to Tkinter, SQLite table details, Windows
capture libraries or raw macro events.

The runtime:

- interprets natural-language game goals;
- selects a versioned mode, ruleset and objective;
- creates explainable semantic plans;
- exposes risk, policy, missing context and missing bindings;
- accepts provider contributions without flattening conflicts;
- records supervised episodes and action performance.

It does not grant authority to execute a plan. Execution requires a separate
policy-gated Executor contract.

Architecture and migration constraints are defined in
[intelligent-assistant.md](../docs/architecture/intelligent-assistant.md).

## Public entry point

Consumers should depend on the application facade:

[services/game_intelligence_service.py](../services/game_intelligence_service.py)

### build_game_intelligence_service

    build_game_intelligence_service(
        *,
        registry_path=DOOMSDAY_DOMAIN_REGISTRY_PATH,
        bind_macros=False,
    ) -> GameIntelligenceService

Behavior:

- loads the domain registry;
- validates it before returning a service;
- uses NullActionBindingProvider by default;
- when bind_macros is true, resolves read-only candidates through the existing
  UI graph macro-link service;
- never executes a macro.

Validation errors raise ValueError. Consumers must not bypass validation by
reading the registry JSON directly.

### plan_game_goal

    plan_game_goal(
        query,
        *,
        facts=None,
        game_version="",
        bind_macros=False,
        registry_path=DOOMSDAY_DOMAIN_REGISTRY_PATH,
    ) -> GameIntelligenceResult

Input:

- query: non-empty user goal;
- facts: already known, explicit state facts;
- game_version: installed or observed game version when known;
- bind_macros: optional read-only binding lookup;
- registry_path: injectable path for testing or alternate versioned registries.

Output:

- interpretation: GoalInterpretation;
- plan: GamePlan;
- registry_version;
- game_version;
- evidence_claim_ids used by the selected ruleset.

The result supports to_dict for JSON-safe serialization.

Planning is pure with respect to game control. It may read the registry and,
when binding is enabled, existing macro-link metadata. It does not click, type,
move the mouse, start playback or persist an episode.

### record_game_episode

    record_game_episode(
        plan,
        *,
        status,
        executed_action_ids,
        outcome=None,
        durations_sec=None,
        evidence_refs=(),
        user_feedback="",
        repository_path=DOOMSDAY_INTELLIGENCE_DB_PATH,
    ) -> str

Returns the new episode id.

This operation writes only the dedicated intelligence store. It records the
plan, outcome, evidence references, feedback and aggregate action performance.
It does not update canonical claims, policy or macro definitions.

### evaluate_game_outcome

    evaluate_game_outcome(
        plan,
        *,
        executed_action_ids,
        facts=None,
        state=None,
    ) -> OutcomeAssessment

Compares post-action perception with expected step effects and objective
criteria. It returns matched and missing facts plus discrepancies suitable for
an episode; it does not infer success from an attempted click or macro alone.

## Public package surface

The domain package is [doomsday/intelligence](../doomsday/intelligence).

The following names are public domain types:

- AutomationPolicy
- RiskClass
- EvidenceSource
- EvidenceClaim
- Observation
- ObjectiveDefinition
- ActionDefinition
- RulesetDefinition
- GameModeDefinition
- GameState
- GoalInterpretation
- ActionBinding
- PlanStep
- GamePlan

The following services and extension points are public:

- DomainRegistry
- GameIntelligenceService
- WorkflowPlanner
- ActionBindingProvider
- EnrichmentProvider
- ProviderOrchestrator
- EvidenceResolver
- IntelligenceRepository
- KnowledgeSourceSelector
- ExecutionPolicyGate
- StepExecutor
- OutcomeEvaluator

Consumers should prefer the application facade unless implementing an adapter,
provider or test.

Modules not exported by the package or facade are implementation details.

## Intent and planning contract

### GoalInterpretation

Required semantic fields:

| Field | Meaning |
| --- | --- |
| query | Original user wording |
| mode_id | Selected game mode |
| ruleset_id | Version-compatible ruleset |
| objective_id | Selected objective |
| confidence | Interpretation confidence from 0 to 1 |
| alternatives | Other plausible mode ids |
| needs_context | Live observation or user confirmation is required |
| assumptions | Explicit assumptions and lifecycle warnings |

An unresolved intent is returned as needs_context or as a blocked plan. It is
not guessed into an executable action.

### GameState

GameState contains:

- explicit facts;
- provenance-bearing observations;
- optional active mode and ruleset;
- game version.

Explicit facts take precedence over observations. Observation values are
materialized only when confidence meets the runtime threshold. Consumers must
retain the original observations for audit.

### GamePlan

GamePlan contains:

- stable plan id and creation timestamp;
- query, mode, ruleset and objective;
- ordered semantic steps;
- initial and projected facts;
- success facts;
- blocked flag and blocking reasons;
- warnings.

Plan projection is not an outcome. Expected effects become observed facts only
after Perception verifies them.

### PlanStep status

Current statuses are:

| Status | Meaning |
| --- | --- |
| skipped | Expected effect is already present |
| blocked | Required facts or action definition are missing |
| excluded | The action violates an explicit goal constraint |
| manual | Human interaction or observation is required |
| suggested | Advice only |
| unbound | Semantic action has no executor binding |
| confirmation_required | Explicit confirmation is required immediately before execution |
| ready | Current preconditions are observed |
| planned | Preconditions are expected from earlier steps and must be rechecked |

No status in this table independently authorizes execution.

## Policy contract

AutomationPolicy values:

- autonomous
- confirm_each
- suggest_only
- manual

RiskClass values:

- low
- medium
- high
- critical

Minimum enforcement:

- manual is never sent to an Executor;
- suggest_only is never sent to an Executor;
- confirm_each requires a fresh confirmation;
- high and critical require confirmation regardless of action policy;
- missing binding produces unbound;
- missing or stale perception blocks execution;
- hostile PvP, spending, rally creation, garrison commitment and social
  mutations cannot become autonomous from learning.

Policy is evaluated again immediately before execution.

## Action binding port

ActionBindingProvider resolves an ActionDefinition, RulesetDefinition and
GameState into an optional ActionBinding.

The current implementations are:

- NullActionBindingProvider: always returns no binding;
- UIGraphMacroBindingProvider: lazily reads existing UI graph macro links and
  selects the preferred candidate.

ActionBinding describes what could implement the semantic action. It does not
execute it.

The default graph id used by the current adapter is:

    doomsday-default-ui-graph

Binding lookup is blocked operationally while the macro database has an
unresolved conflict.

## Provider extension contract

EnrichmentProvider is object-agnostic and supports heroes, beasts, skills,
rules, game modes, battle reports and future domain objects.

Required methods:

    describe_provider() -> ProviderDescriptor
    supports(object_type, fields, context) -> bool
    discover(seed, cursor=None) -> iterable
    collect(candidate) -> artifact
    normalize(artifact) -> normalized artifact
    emit_observations(normalized) -> iterable[ProviderContribution]
    health() -> ProviderHealth

ProviderOrchestrator offers:

    list_providers() -> tuple[ProviderDescriptor, ...]
    run(
        *,
        object_type,
        fields=(),
        seed,
        context=None,
        provider_filter=None,
    ) -> ProviderRunResult

One provider failure does not abort the chain. Errors are returned with
provider id and stage.

Providers perform acquisition and normalization. They do not merge values into
canonical truth.

## Evidence contribution contract

ProviderContribution is compatible with the shared
doomsday-crawler-support shape and requires:

    {
      "provider_id": "ocr-provider-main",
      "provider_type": "ocr-provider",
      "subject_id": "hero:example",
      "field_name": "rarity",
      "field_value": "legendary",
      "confidence": 0.82,
      "observed_at": "2026-07-14T10:00:00Z",
      "source_ref": "screenshot:match-001",
      "trust_score": 0.8,
      "game_version": "1.56.0",
      "server_scope": "",
      "normalization_notes": []
    }

Confidence and trust_score are bounded from 0 to 1.

EvidenceResolver:

- groups contributions for one subject and field;
- weights confidence, provider trust and freshness;
- returns the selected value plus every alternative;
- marks conflicts explicitly;
- never deletes losing evidence.

The selected value is a read model, not a destructive merge.

## SourceRegistry and ExternalSourceBroker dependency

Source ranking is owned by the Knowledge project.

DDassistant publishes a Doomsday overlay from:

    data/doomsday/intelligence/source_registry.overlay.json

The overlay is consumed through Knowledge SourceRegistry. DDassistant must not
duplicate:

- registry search and ranking;
- trust, signal and noise scoring;
- overlay merge;
- registry validation.

KnowledgeSourceSelector delegates ranking to the injected shared registry.
ExternalSourceBroker is reused for source mediation. Game-specific providers
adapt broker results into ProviderContribution records.

The domain registry may snapshot the source id and trust used for a claim, but
it is not a second source-ranking engine.

If the shared source service is unavailable, external enrichment reports a
provider error; local planning may continue only from already validated local
evidence.

## Perception adapter

observations_from_ui_evaluation converts UI graph evaluation results into
Observation records without importing Windows vision types into the domain
core.

Invariant:

    a UI node with no condition results remains unknown

Such nodes are not emitted as active or inactive observations. Structural UI
nodes may still be action targets.

UI observations use keys shaped as:

    ui.node.{node_id}.active

and include graph id and node id in metadata.

The UI graph is not the evidence graph. See the architecture document for the
separation and linking rules.

## Persistence contract

IntelligenceRepository owns a dedicated SQLite database with schema versioning.

Public operations:

    setup()
    record_contribution(contribution) -> contribution_id
    list_contributions(subject_id=..., field_name=...) -> tuple
    record_episode(plan, ...) -> episode_id
    get_action_performance(action_id) -> mapping | None

Logical tables:

- IntelligenceSchema
- EvidenceContributions
- IntelligenceEpisodes
- ActionPerformance

The store contains learning and evidence records. It does not own:

- macro definitions or macro events;
- scheduled tasks;
- UI graph macro links;
- roster and catalog bootstrap tables;
- browser credentials or raw Discord dumps.

There are no cross-database foreign keys. Stable ids are resolved by adapters.

## Discord provider policy

Any provider with access_mode discord-authenticated must enforce:

- read-only access;
- explicit human tab activation;
- server and channel allowlist;
- bounded query, time window and message count;
- no credentials, cookies, tokens or secret persistence;
- no posts, reactions, replies, joins, edits or other mutations;
- no DMs or unrelated private channels without separate explicit authority;
- ephemeral raw DOM or page artifacts;
- minimal persisted provenance;
- community claims marked advisory, conflicted or corroborated as appropriate.

The reusable DISCORD_ACCESS_POLICY is defined in
[evidence.py](../doomsday/intelligence/evidence.py).

Unavailable or unactivated access returns provider unavailable. It never
triggers a login flow.

## Executor boundary

StepExecutor is a port in interface version 0.1.0; no concrete macro executor
is enabled. A compatible implementation must accept one approved PlanStep plus:

- fresh GameState;
- explicit policy decision;
- resolved ActionBinding;
- cancellation token and timeout;
- execution budget.

It must return a receipt containing:

- action and binding ids;
- timestamps and status;
- side effects attempted;
- error or cancellation reason;
- perception request for outcome verification.

ExecutionPolicyGate must authorize the fresh step before the port is called.
Allowing plan_game_goal to execute would be a breaking change.

## Error behavior

- Empty queries raise ValueError.
- Invalid registries raise ValueError from the facade.
- Unknown rulesets produce a blocked GamePlan.
- Missing preconditions produce blocked PlanStep records.
- Missing macro links produce unbound steps and warnings.
- Provider failures are returned in ProviderRunResult.errors.
- Persistence failures raise and roll back the current transaction.

Errors must not be converted into guessed actions.

## Versioning

Compatibility rules for 0.x:

- adding optional dataclass fields with defaults is backward compatible;
- adding a provider type or PlanStep status is backward compatible when
  consumers handle unknown strings safely;
- renaming fields, changing policy meaning or making planning execute are
  breaking changes;
- domain registry schema and interface version are versioned independently;
- every ruleset and claim may declare applicable game versions.

## Current operational blockers

1. The legacy macro database is workstation-local and is not a shared source of
   authority. Macro binding and semantic execution remain disabled until local
   state is reconciled and the migration path is explicitly validated.
2. The current exported UI graph has 43 of 49 nodes without recognition
   conditions. They are structural/unknown and cannot satisfy runtime
   preconditions.
3. A concrete Executor remains disabled until these runtime boundaries and
   the structural UI recognition gaps above are closed.

## Battle-report knowledge graph

Interface version 0.2.0 extends the structural UI graph from navigation into
evidence-backed battle reasoning. The graph now represents:

- `communications_button -> communications_center_view`;
- `battle_reports_tab_button -> battle_report_list_view`;
- repeatable report entries and a single battle-detail view;
- multiple participants per side instead of a fixed one-versus-one model;
- participant-specific buffs, debuffs, commander equipment, hero armaments,
  squad equipment and beasts;
- outcome measures such as kills, wounded, survivors, troop deltas and damage;
- an ordered, scrollable timeline of abilities, hits, targets, effects and
  durations;
- a battle-execution model fed separately by configuration, timeline and
  outcome evidence;
- an advice model for beasts, armaments and squads gated by repeated,
  comparable reports.

Interface version 0.2.1 adds user-confirmed report structure:

- a top summary for battle duration and opponent engagements;
- one repeatable section per opponent;
- participant-level initial and killed troop counts;
- vehicle configuration as a separate source of modifiers.

Structural graph nodes document meaning but do not authorize clicks. Advice
must retain report and frame provenance, distinguish observations from
inference, and cite uncertainty. A single battle cannot establish causal
superiority for a pairing.

## Implementation anchors

- [doomsday/intelligence/models.py](../doomsday/intelligence/models.py)
- [doomsday/intelligence/registry.py](../doomsday/intelligence/registry.py)
- [doomsday/intelligence/planner.py](../doomsday/intelligence/planner.py)
- [doomsday/intelligence/service.py](../doomsday/intelligence/service.py)
- [doomsday/intelligence/providers.py](../doomsday/intelligence/providers.py)
- [doomsday/intelligence/evidence.py](../doomsday/intelligence/evidence.py)
- [doomsday/intelligence/adapters.py](../doomsday/intelligence/adapters.py)
- [doomsday/intelligence/persistence.py](../doomsday/intelligence/persistence.py)
- [doomsday/intelligence/execution.py](../doomsday/intelligence/execution.py)
- [doomsday/intelligence/outcomes.py](../doomsday/intelligence/outcomes.py)
- [doomsday/intelligence/sources.py](../doomsday/intelligence/sources.py)
- [doomsday/intelligence/state_estimator.py](../doomsday/intelligence/state_estimator.py)
- [services/game_intelligence_service.py](../services/game_intelligence_service.py)
- [scripts/plan_game_objective.py](../scripts/plan_game_objective.py)
- [intelligent-assistant.md](../docs/architecture/intelligent-assistant.md)
