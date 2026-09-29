# Intelligent Doomsday Assistant

Status: draft architecture baseline  
Date: 2026-07-14  
Owner: DDGameAss

## Purpose

This document defines how DDassistant evolves from a Windows macro and visual
automation application into a goal-driven assistant that understands game modes,
plans safe workflows, observes the live game, and learns from outcomes.

The target is not an unrestricted bot. The target is an explainable assistant
that can distinguish campaigns, challenges, PvE, PvP, rallies, garrisons and
time-limited events; state what it knows; expose uncertainty; and automate only
within an explicit policy.

The public runtime contract is documented in
[doomsday-intelligence-runtime.md](../../interfaces/doomsday-intelligence-runtime.md).

## Current baseline

The repository currently contains four systems that must be joined without
collapsing their responsibilities:

1. The legacy desktop application owns the Tkinter UI, macro recording,
   scheduled execution, focus monitoring and playback.
2. The Doomsday modules own roster bootstrap, OCR, catalog data, window capture,
   template matching and the semantic UI graph.
3. The new [doomsday/intelligence](../../doomsday/intelligence) package owns
   domain concepts, intent interpretation, semantic planning, evidence
   contributions and learning episodes.
4. The shared Knowledge project owns reusable source selection and external
   source brokering.

The application facade is
[services/game_intelligence_service.py](../../services/game_intelligence_service.py).
It can interpret and plan a goal and record an episode. Macro binding is
disabled by default. Planning does not itself execute clicks, keyboard input or
macros.

The current package is an in-progress foundation, not yet a complete closed
loop:

- intent interpretation and semantic planning exist;
- risk and automation policy are represented on actions;
- provider failures are isolated by the provider orchestrator;
- evidence conflicts can be retained rather than overwritten;
- an adapter can resolve semantic actions to existing UI-node/macro links;
- an Executor port, policy gate and outcome evaluator exist, while a concrete
  legacy-macro executor remains intentionally blocked;
- the versioned domain registry passes the package validator;
- the Doomsday SourceRegistry overlay passes the shared Knowledge validator
  and is not a replacement for the shared ranking engine.

## Target flow

    Intent
      |
      v
    Planner
      |
      v
    Policy gate
      |
      v
    Executor
      |
      v
    Perception
      |
      v
    Outcome
      |
      +---- evidence and episode feedback ----> Planner

Every transition produces a typed, inspectable record. No layer may silently
convert an uncertain observation into a fact or a suggested action into an
authorized execution.

### 1. Intent

Input is a user goal plus the known game state, for example:

    "migliora il risultato in Arena senza spendere gemme"

The intent layer returns a GoalInterpretation with:

- selected mode, ruleset and objective;
- confidence and alternatives;
- assumptions;
- needs_context when the visible screen, account cohort or rules panel must be
  inspected before planning.

Terms such as Campaign and Challenge are not assumed to identify one combat
engine. They can be navigation containers, difficulty modifiers or event
labels.

### 2. Planner

The planner builds a GamePlan from semantic actions declared in the domain
registry. It does not plan raw screen coordinates.

Each PlanStep carries:

- action identity and human-readable reason;
- preconditions and expected effects;
- risk class and automation policy;
- optional macro intent and target UI node;
- optional executor binding;
- a status that makes missing context or bindings visible.

The planner is conservative. Missing preconditions, an unknown ruleset or
unreachable success facts produce a blocked plan rather than a guessed
execution.

### 3. Policy gate

Policy is evaluated immediately before execution, not only when the plan is
created. The minimum policy dimensions are:

- action AutomationPolicy: autonomous, confirm_each, suggest_only or manual;
- action RiskClass: low, medium, high or critical;
- current user authorization and session scope;
- current perception confidence;
- reversibility;
- resource and casualty budget;
- hostile, social or externally visible effects.

High and critical actions always require explicit confirmation. Hostile PvP
targeting, rally creation, spending, troop commitment, irreversible claims and
social actions must not be promoted to autonomous behavior by learning.

Ready and planned are planning states, not permission to execute.

### 4. Executor

The Executor is a port over existing playback and automation capabilities. It
must remain outside the domain planner.

Its contract is one semantic step at a time:

1. re-evaluate policy;
2. re-check focus and target window;
3. re-check visual preconditions;
4. resolve the approved binding;
5. execute with timeout and cancellation;
6. emit an execution receipt;
7. hand control to Perception before another step.

The existing macro runtime remains the implementation during migration.
Coordinates, mouse events and platform-specific details never enter
GamePlan or the evidence graph.

### 5. Perception

Perception converts UI graph evaluations, OCR, battle reports and provider
artifacts into Observation or ProviderContribution records.

An observation includes:

- key and value;
- confidence;
- source and observed timestamp;
- evidence reference;
- context such as graph id, node id, locale, account/server and game version.

Unknown is a first-class state. A structural UI node with no recognition
conditions is not active evidence.

### 6. Outcome

Outcome evaluation compares post-action observations with expected effects and
success facts. It records:

- executed action ids;
- completion status;
- observed result and resource deltas;
- duration;
- evidence references;
- user feedback;
- discrepancies between expected and observed effects.

Episodes and action performance may later rank suggestions. They do not mutate
risk class, policy or canonical game facts automatically.

## Separation of graphs

The UI graph and evidence graph solve different problems and must remain
separate.

| Concern | UI graph | Evidence graph |
| --- | --- | --- |
| Question | Where is the application and how can it navigate? | What is believed about the game and why? |
| Nodes | views, panels, controls, overlays, spatial actions | sources, claims, game entities, rulesets, observations |
| Edges | parentage, transitions, navigation and recovery | claim relations, support, conflict, supersession and validity |
| Evidence | recognition conditions and visual matches | source URI, timestamp, confidence, game version and evidence span |
| Volatility | screen layout and local capture state | mechanic validity, source freshness and version scope |
| Executor relation | target node and macro binding | policy rationale and expected outcome |

The bridge between them is explicit:

- ActionDefinition.target_ui_node identifies a UI target;
- ActionBinding identifies the concrete executor resource;
- observations_from_ui_evaluation emits evidence-linked observations;
- an EvidenceClaim may refer to the existence or meaning of a UI node, but it
  does not copy the node or its coordinates.

The UI graph remains useful even when a node is structural. Structural nodes
may organize navigation and binding, but cannot satisfy a runtime precondition
until a recognizer or a trusted derived rule exists.

## Domain registry and evidence

The domain registry is a versioned read model for:

- modes and lifecycle;
- rulesets scoped by game version;
- objectives and success facts;
- semantic actions and workflows;
- sources and claims.

It is not the raw evidence store. Provider contributions and learning episodes
belong in the dedicated intelligence persistence layer. Conflicting values are
retained as alternatives with confidence, provider identity, freshness and
normalization notes.

The runtime must load the registry through DomainRegistry and reject it when
validation fails. Direct ad hoc reads of the JSON payload are not part of the
public contract.

## Reuse of Knowledge source services

DDassistant consumes, rather than reimplements:

- Knowledge SourceRegistry for source categories, usage modes, trust, signal,
  noise, overlay merge and validation;
- Knowledge ExternalSourceBroker for provider selection and external-source
  mediation;
- Knowledge provenance concepts for source references and evidence.

DDassistant owns a Doomsday domain overlay. Its canonical project artifact is:

    data/doomsday/intelligence/source_registry.overlay.json

That overlay is published to the Knowledge overlay ingestion process and
contains game-specific source metadata such as:

- official store and release channels;
- official game sites and staff announcements;
- community wiki and guides;
- Reddit and Discord community sources;
- access mode, human-activation requirement and privacy class;
- supported object types and fields;
- locale, server and game-version scope;
- refresh policy and volatility.

DDassistant must not copy SourceRegistry.find, its scoring formula or overlay
merge logic. KnowledgeSourceSelector delegates ranking to the injected shared
registry, then DDassistant providers turn acquired artifacts into
ProviderContribution records.

The ExternalSourceBroker remains an acquisition and mediation dependency. It
does not decide gameplay strategy and it does not write the domain registry.

## Discord acquisition policy

Discord is an optional, authenticated and ephemeral community source. It is not
a default crawler target.

Every Discord session must satisfy all of the following:

- the user opens an already-authenticated tab and explicitly activates the
  local browser bridge on that tab;
- access is read-only;
- the server and channels are allowlisted before collection;
- the time range, query and maximum message count are bounded;
- private messages, unrelated channels and broad recursive crawling are out of
  scope unless separately and explicitly authorized;
- credentials, cookies, tokens and browser secrets are never requested,
  logged or persisted;
- reactions, posts, replies, joins, edits and other Discord mutations are
  prohibited;
- raw page dumps are ephemeral and are not committed or copied into the shared
  registries;
- persisted evidence is minimal: source id, server/channel, permalink, message
  timestamp, retrieval timestamp, staff/community role, bounded excerpt or
  hash, and the normalized claim;
- staff announcements outrank ordinary community messages, while gameplay
  claims require corroboration or an explicit conflicted status;
- the session produces a receipt describing scope, counts, omissions and
  deletion of temporary artifacts.

If the bridge is not active on an allowlisted tab, Discord providers report
unavailable. They never start a login flow or ask for credentials.

## Persistence boundaries

The application currently has three distinct SQLite concerns:

- the legacy macro database for macros, tasks, game elements and UI/macro
  links;
- the Doomsday roster database for catalog and account roster bootstrap;
- the intelligence database for evidence contributions, episodes and action
  performance.

The intelligence store must remain separate while the legacy macro database is
being stabilized. No intelligence migration may rewrite the macro or roster
database implicitly.

Cross-store references use stable ids and are resolved by adapters. They are
not enforced with cross-database foreign keys.

## Strangler migration

The existing application remains the host while use cases move behind the new
facade incrementally.

### Phase 0: safety and observability

- resolve the macro database conflict;
- make empty-condition UI nodes explicitly structural or unknown;
- keep domain registry and overlay validation in release checks;
- keep bind_macros disabled by default;
- add receipts and diagnostics before execution.

### Phase 1: read-only shadow planning

- expose goal interpretation and plan preview in CLI and UI;
- compare generated plans with the user's chosen actions;
- collect feedback without executing;
- measure ambiguity, missing facts and missing bindings.

### Phase 2: suggested bound actions

- resolve semantic steps to existing macro links;
- show the exact macro, target UI node, risk and preconditions;
- retain suggest_only or confirm_each policy;
- do not change the legacy macro implementation.

### Phase 3: guarded single-step execution

- introduce the Executor port;
- allow only one confirmed step;
- require perception and outcome verification before continuing;
- stop on focus loss, unknown UI state, timeout or unexpected effect.

### Phase 4: supervised workflows

- compose verified steps;
- keep high-risk boundaries confirmed;
- use episode performance to rank alternatives;
- provide rollback or recovery plans where meaningful.

### Phase 5: bounded autonomy

- allow only explicitly allowlisted, low-risk and reversible workflows;
- retain session budgets, audit receipts and immediate cancellation;
- never learn broader authority from successful execution.

Legacy code is removed only after its use cases have a contract, adapter,
equivalent tests and observed production parity.

## P0 blockers

### P0-1: local legacy macro state

The legacy macro database lives under the selected workstation profile and is
not a shared source of authority. A new clone starts with its own local state;
semantic knowledge travels through the versioned catalog and learning exports.
SQLite files cannot be merged through Git, and importing another workstation's
macro playback state is not part of the knowledge-sharing flow.

Until a migration and review process exists:

- bind_macros remains disabled for normal intelligence calls;
- the semantic runtime does not write to the legacy macro database;
- Executor integration remains blocked;
- any local recovery or migration must use backups, schema/table comparison and
  explicit operator review.

The dedicated intelligence database is a separate bounded context; it does not
replace the per-workstation macro database.

### P0-2: UI nodes without recognizers

The exported UI graph currently has 24 nodes, of which 21 have no recognition
conditions. They are useful as taxonomy but cannot be treated as observed
screen state.

Required invariant:

    no recognition conditions => unknown, never active

The intelligence adapter already filters evaluations without condition
results. The underlying UI evaluator and all future consumers must enforce the
same rule.

Release acceptance requires:

- structural and observable node roles are explicit;
- every node used as an execution precondition has a discriminating recognizer
  or a documented derived rule;
- empty-condition nodes never emit positive observations;
- tests cover empty, partial and conflicting recognition;
- confidence is preserved through Perception into Outcome.

## Release gates

The first runtime release is ready only when:

- DomainRegistry loads and validates the published registry;
- the Doomsday source overlay exists and validates through Knowledge;
- the two P0 blockers are closed;
- shadow planning works without Windows vision dependencies;
- macro binding is read-only and optional;
- no plan execution occurs from plan_game_goal;
- every execution attempt has policy, precondition and receipt checks;
- Discord remains bounded, read-only and manually activated;
- UI graph and evidence graph remain separately inspectable.
