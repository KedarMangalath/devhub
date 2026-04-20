# Updated Implementation Plan

## Purpose

This document turns the current pain points into a concrete next-step plan for `devhub_v2`.

It covers:

- what already exists
- what is still missing or broken
- why the API extraction pipeline is failing in real use
- how to fix agent observability properly
- where async and background execution should be improved
- how to update `README.md` so it reflects the real product state

This is a planning and documentation artifact only. It does not include implementation code.

---

## Executive Summary

The product already has a strong base for:

- code onboarding
- multi-file edits
- GitHub-connected repository workflows
- project-aware chat with trace metadata

The main blockers are now:

1. API extraction is still structurally unreliable for real Django repos.
2. The trace UX is partial and chat-scoped instead of being a first-class execution timeline.
3. Long-running work is split across sync code, threads, SSE, and WebSockets without one unified execution model.
4. The architecture is still too monolithic for fast, confident iteration.

The highest-priority fix is still the API pipeline.

Until API extraction is correct, the Blueprint will continue to underperform no matter how good the database, services, setup, or knowledge sections become.

---

## What Exists Today

## 1. Code onboarding

### Already exists

- Blueprint generation and persistence
- Deep documentation section regeneration
- Repository map and repo tree generation
- Semantic memory, episodic memory, and working memory
- `code-review-graph` integration through `graph_bridge.py`
- Onboarding UI in the frontend
- Project-aware chat with explicit context mentions
- Cached codebase context in `build_blueprint_context()`

### Current status

- This is real and already useful.
- It is not yet consistently fast enough or unified enough to justify the strongest product claims.

### Missing or weak

- A dedicated fast onboarding query path with predictable latency
- Better dependency and route navigation inside the UI
- Stronger canonicalization of repo understanding outputs
- Better observability into what the onboarding agents and extractors actually did

---

## 2. Turn issues into PRs

### Already exists

- GitHub OAuth
- GitHub repository import
- GitHub issue list/create
- GitHub PR list/create
- Workspace editing
- Terminal and runtime execution
- Chat-driven implementation and agent mode

### Current status

- GitHub primitives exist.
- The end-to-end issue-to-PR workflow does not.

### Missing

- GitLab support
- issue -> feature linkage
- branch creation and switching
- commit and push orchestration
- validation-gated PR creation
- draft PR generation from diff + validation + issue context
- a terminal-first issue-to-PR execution path

---

## 3. Make powerful edits

### Already exists

- Structured implementation pipeline
- Planner / coder / reviewer loop
- QueryEngine-based agent mode
- Tool execution with file read/edit/write/grep/glob/bash
- Checkpoint-backed undo
- Changeset recording
- Runtime/setup follow-up actions

### Current status

- This is the strongest implemented capability in the app.
- It still lacks a first-class review and publish workflow.

### Missing or weak

- diff-first review UI
- stronger patch-based editing
- stronger VCS-native workflow integration
- global execution visibility beyond chat traces
- consistent validation summaries for every agent execution path

---

## What Is Still Broken Right Now

## 1. API extraction is still fundamentally broken for the real imported project

The real failing case is the imported Django project at:

- `devhub_v2/data/projects/151fac82-0eae-4942-b637-7ec8c63661e8/backend`

Confirmed grounding:

- Real Django root:
  - `backend/backend/urls.py`
  - contains:
    - `path('admin/', admin.site.urls)`
    - `path("api/", include("remo.urls"))`
- Large app route surface:
  - `backend/remo/urls.py`
  - contains about `165` `path(...)` entries in the checked file
- The current Blueprint/API output collapsing toward `/admin/` means the extractor is not traversing the real app route graph correctly enough.

### Existing extraction path

Current relevant pipeline:

- `agents/api_reference.py`
  - `build_api_reference_catalog()`
  - `_find_root_urls_path()`
  - `_collect_django_routes()`
  - `_resolve_module_to_file()`
  - `_resolve_view_file_for_handler()`
  - `_extract_allowed_methods()`
- `agents/memory.py`
  - calls `build_api_reference_catalog(workspace_path)`
  - stores `api_reference`
  - stores `api_extraction_meta`
- `agents/documentation.py`
  - `_api_surface_section(cache)`
- `agents/deep_documentation.py`
  - `generate_api()`
- `backend/api/views.py`
  - merges `codebase_context['api_reference']` into the Blueprint

### What this means

The system is not missing an API extractor.
It has one.
The problem is that the extractor is not robust enough for real Django route topology.

### Likely failure classes

Without claiming one exact bug before the focused trace pass, the current failure almost certainly sits in one or more of these layers:

1. Root URL file selection is still too heuristic.
2. Include traversal is not reliably preserving and composing prefixes.
3. Django module resolution is too weak for real app layouts.
4. View resolution is too brittle for package-based views and imported class-based views.
5. Method detection is too source-shape-dependent.
6. The downstream Blueprint path trusts partial `api_reference` too early.

### Most important planning decision

Do not keep patching the API section at the LLM layer.

This needs to be fixed at the extractor and evidence layer first:

- route discovery
- include traversal
- handler resolution
- method inference
- provenance and diagnostics

The API section should become evidence-first, not prompt-first.

---

## 2. Setup is improved but not cleanly canonical

### Already better

- It stopped hallucinating `.env.example`
- It is more Windows-aware
- It can derive runtime/setup commands from repo signals

### Still wrong

- setup output still contains generic duplication after concrete steps
- command selection is not always tied to one canonical, repo-authored source
- there is no strong confidence/provenance model for setup guidance

### Root issue

The setup pipeline is mixing:

- inferred runtime heuristics
- README extraction
- generic fallback logic

without a strict ranking model for:

1. human-authored canonical command
2. config-file canonical command
3. runtime heuristic fallback

---

## 3. Testing strategy is still plausible rather than authoritative

### Existing behavior

- The system can detect scripts and generate a plausible test strategy.

### Still wrong

- It does not clearly distinguish:
  - canonical repo-owned test command
  - discovered test scripts
  - inferred fallback verification commands

### Root issue

The product still describes test execution as if all commands are equally authoritative.

It needs:

- source provenance
- confidence levels
- one recommended primary command
- secondary script list only when no canonical command exists

---

## 4. Agent observability exists, but only partially

### Already exists

The frontend chat trace UI already shows:

- files accessed
- commands ran
- workspace actions
- plan
- review
- semantic hits
- tool execution timeline
- turns used
- duration
- compaction flag

Current location:

- `frontend/src/components/ProjectChatPanel.tsx`

Current backend support:

- `backend/api/views.py`
  returns `trace`
- `agents/query_engine.py`
  returns tool call log, files modified, files read, turns, compaction, duration
- `_handle_agent_chat_request()` adds:
  - `tool_events`
  - `workspace_actions`
  - `commands_ran`
  - `files_accessed`

### What is missing

- trace is chat-result scoped, not a global execution system
- no live streaming of agent execution into the frontend while the run is happening
- no dedicated execution panel outside chat
- no unified event model shared by:
  - onboarding
  - blueprint generation
  - deep docs
  - edit runs
  - validation runs
  - runtime/setup actions
- no mirrored structured trace in terminal logs
- no proper compact vs verbose mode
- no expandable event tree with parent/child operations

### Important product note

The requirement should be:

- expose execution summaries, tool traces, file accesses, command results, plan/review summaries, and state transitions

not:

- expose raw hidden chain-of-thought

The correct product implementation is Claude/Codex-style execution visibility:

- what the agent did
- what it read
- what it changed
- what commands it ran
- what decisions it made at a user-facing summary level

not raw internal reasoning dumps.

---

## 5. Async behavior is uneven

### Already exists

- WebSocket process streaming
- async polling in `ProcessConsumer`
- SSE-based deep-doc streaming
- background thread usage for some long-running tasks

### Missing or weak

- no single execution scheduler model
- many expensive steps still happen synchronously in request-driven code paths
- API extraction and codebase context generation are not isolated as independently observable jobs
- frontend does not consume structured live progress for most agent executions
- thread use is opportunistic rather than systemic

### Result

The app feels slower and less transparent than it should, even where absolute performance is acceptable, because:

- work is not always streamed
- progress is not always surfaced
- blocking and background work are mixed inconsistently

---

## Updated Strategy

The next phase should not be "small fixes everywhere."

It should be a focused, ordered program:

1. Fix evidence extraction quality at the source, starting with API extraction.
2. Make execution visible in a first-class way across backend and frontend.
3. Normalize async/background execution around a shared event model.
4. Only then expand issue-to-PR and broader onboarding claims.

---

## Detailed Implementation Plan

## Phase 0: Stabilization Rules

Before implementation work begins, adopt these decision rules:

### Rule 1

No more LLM-only patching of broken evidence sections.

If a Blueprint section is wrong because the extractor is wrong, fix the extractor first.

### Rule 2

Every generated section must support provenance.

Each major output should be traceable to:

- source file
- extraction method
- confidence
- fallback reason, if any

### Rule 3

Every long-running operation should emit structured events.

That includes:

- blueprint generation
- deep docs
- API extraction
- implementation runs
- validation runs
- review runs
- setup/runtime operations triggered by the agent

---

## Phase 1: Fix API Extraction Properly

### Goal

Make `api_reference` reliable enough that the API section becomes one of the strongest Blueprint sections instead of the weakest.

### Existing pieces to keep

- `agents/api_reference.py` as the extractor home
- `build_api_reference_catalog()`
- `memory.py` as the place where extracted API evidence enters cached codebase context
- downstream consumers in `documentation.py`, `deep_documentation.py`, and Blueprint enrichment

### What should change conceptually

The API extractor should move from:

- heuristic best guess

to:

- route graph traversal with explicit diagnostics

### Workstream 1A: Root URL detection

Current weakness:

- `_find_root_urls_path()` scores files heuristically by:
  - `urlpatterns`
  - include count
  - shallow depth

This is not strong enough for real Django repos.

Updated plan:

- prefer Django settings-driven root discovery when possible
- identify project package root via:
  - `manage.py`
  - `DJANGO_SETTINGS_MODULE`
  - settings file adjacency
- rank root candidates by:
  - imports `include`
  - contains `urlpatterns`
  - includes app routes
  - imports admin and app routes together
  - proximity to project settings package
- capture all candidate roots in diagnostics, not just the winner

Acceptance criteria:

- the failing imported repo resolves `backend/backend/urls.py` as root
- diagnostics show why that file won

### Workstream 1B: Include traversal

Current weakness:

- the extractor likely traverses includes, but not robustly enough for all module shapes and prefix composition cases

Updated plan:

- build an explicit route graph:
  - node = urls module
  - edge = include()
  - payload = path prefix
- preserve prefix accumulation deterministically
- record traversal path for each discovered endpoint:
  - root file
  - include chain
  - final view file

Acceptance criteria:

- `/api/` prefix from `backend/backend/urls.py` is preserved
- all routes in `remo/urls.py` are emitted under `/api/...`

### Workstream 1C: Module and view resolution

Current weakness:

- `_resolve_module_to_file()` and `_resolve_view_file_for_handler()` are still heuristic and file-system-biased

Updated plan:

- support:
  - package modules
  - nested `views/` packages
  - imported symbols from sibling modules
  - class-based DRF views
  - aliased imports
- build a reusable Django symbol index for:
  - view classes
  - function views
  - imported handler symbols

Acceptance criteria:

- admin APIs, course APIs, and video interview APIs resolve to actual handler files
- extractor output contains correct `url_file` and `view_file`

### Workstream 1D: Method inference

Current weakness:

- `_extract_allowed_methods()` depends heavily on source-shape heuristics

Updated plan:

- strengthen method inference for:
  - DRF APIView subclasses
  - explicit `get/post/put/patch/delete` class methods
  - decorators like `@api_view`
  - viewsets and action decorators where present
- if method cannot be proven, mark as:
  - `UNKNOWN`
  - with lower confidence

Acceptance criteria:

- route count is high
- method quality is high enough that endpoints are useful
- method confidence is surfaced

### Workstream 1E: Provenance and diagnostics

Updated plan:

- expand `api_extraction_meta` to include:
  - candidate root urls files
  - chosen root
  - include traversal count
  - total endpoints discovered
  - endpoints skipped
  - unresolved views
  - unresolved include modules
  - confidence summary

Acceptance criteria:

- when extraction fails, the reason is visible immediately
- future debugging does not require guesswork

### Workstream 1F: API section consumer behavior

Updated plan:

- `documentation.py` and `deep_documentation.py` should not silently trust tiny broken `api_reference` payloads
- if:
  - root exists
  - many route files exist
  - endpoint count is suspiciously low
then:
  - flag extraction degraded
  - show diagnostic warning
  - optionally trigger fallback evidence rendering from raw routed files

Acceptance criteria:

- a broken extractor cannot silently masquerade as a clean API section

### Phase 1 success definition

For the failing imported repo:

- endpoint count is in the correct order of magnitude
- `/api/` app surface dominates, not `/admin/`
- admin auth, course, and video interview endpoints appear
- API section score should move from `5/100` to a genuinely strong range

---

## Phase 2: Clean Setup and Testing Guidance

### Goal

Make setup and testing sections authoritative instead of merely plausible.

### Workstream 2A: Command provenance model

Introduce command classes conceptually:

- canonical human-authored command
- canonical config-derived command
- inferred fallback command

Each command should carry:

- source file
- extraction method
- confidence
- whether it is primary or fallback

### Workstream 2B: Setup deduplication

Updated plan:

- rank setup sources:
  1. repo README/setup doc
  2. project instructions
  3. config/manifests
  4. runtime heuristic
- collapse duplicate steps by normalized command identity
- separate:
  - human-readable setup
  - fallback/manual alternatives

Acceptance criteria:

- no duplicated generic steps after concrete setup steps

### Workstream 2C: Testing strategy normalization

Updated plan:

- identify one primary test command when possible
- only list script-level commands as secondary evidence when no canonical test command exists
- mark strategy as:
  - authoritative
  - partial
  - inferred

Acceptance criteria:

- testing section no longer reads as "plausible but vague"

---

## Phase 3: Make Agent Execution Visible Properly

### Goal

Expose execution in a first-class way across frontend and backend, similar in spirit to Claude Code/Codex visibility, without depending on hidden raw reasoning.

### Existing foundation

- chat trace metadata
- tool event timeline in `ProjectChatPanel`
- runtime/setup terminal WebSocket streaming

### Missing product layer

- a unified execution event model
- a live execution panel
- structured log mirroring into backend terminal output

### Workstream 3A: Define execution event model

All long-running tasks should emit normalized events like:

- `run_started`
- `phase_started`
- `tool_called`
- `file_read`
- `file_written`
- `command_started`
- `command_completed`
- `validation_started`
- `validation_completed`
- `review_completed`
- `run_completed`
- `run_failed`

Each event should include:

- run id
- parent run id
- timestamp
- category
- summary
- detail
- source component
- severity
- optional structured payload

### Workstream 3B: Frontend execution UI

Add a dedicated execution surface, not just chat trace blocks.

Proposed UX:

- compact execution chip
  - short unexpandable status
  - current phase
  - duration
- expandable execution drawer/panel
  - timeline of events
  - tool calls
  - file accesses
  - commands
  - validation
  - review
  - fallback path use
- verbose mode toggle
  - summary
  - normal
  - verbose

Important distinction:

- compact mode should give "small thinking"
- expanded mode should show detailed execution narrative and evidence

### Workstream 3C: Backend log mirroring

The user also wants this visible in VS Code terminal logs.

Updated plan:

- all structured agent events should also be mirrored to backend logs in human-readable form
- use one consistent log prefix family, for example:
  - `AGENT_RUN`
  - `AGENT_TOOL`
  - `AGENT_FILE`
  - `AGENT_CMD`
  - `AGENT_REVIEW`

Log requirements:

- readable in dev terminal
- correlated by run id
- not spammy in default mode
- expandable in app even when terminal output is terse

### Workstream 3D: Coverage beyond chat

The same execution model should cover:

- chat agent mode
- edit mode implementation pipeline
- blueprint generation
- deep docs generation
- API extraction
- issue-to-PR automation later

### Phase 3 success definition

Users can see:

- what the agent did
- what files it accessed
- what tools it called
- what commands it ran
- what phase it is currently in
- why it succeeded or failed

in both:

- frontend execution UI
- backend terminal logs

---

## Phase 4: Normalize Async and Background Execution

### Goal

Make the app feel faster and more reliable by moving to a more consistent execution model.

### Current state

- some work is sync
- some work is threaded
- some work is SSE
- some work is WebSocket

This works, but it is fragmented.

### Workstream 4A: Job-based execution model

Long-running flows should become explicit runs/jobs:

- blueprint run
- deep-doc run
- implementation run
- validation run
- review run
- API extraction run

Each run should:

- have an id
- persist status
- emit events
- expose current phase

### Workstream 4B: Parallelizable extraction

Candidates for concurrent/background execution:

- route file scanning
- view symbol indexing
- API extraction diagnostics
- file summarization for blueprint context
- graph enrichment
- documentation section preparation

### Workstream 4C: Frontend live progress

Replace blind polling where possible with:

- event streaming for active runs
- polling only as fallback or status reconciliation

### Workstream 4D: Prioritize perceived latency

Do not wait for everything before showing value.

Return:

- quick summary first
- detailed evidence progressively

This matters especially for:

- onboarding
- blueprint generation
- API section availability

### Phase 4 success definition

- fewer synchronous stalls
- more progressive rendering
- one recognizable execution model across product surfaces

---

## Phase 5: Prepare the Real Issue-to-PR Flow

This is not the first fix, but it should follow immediately after API correctness and observability are stabilized.

### Goal

Deliver a credible terminal-first and UI-backed workflow for:

- issue selection
- code implementation
- validation
- PR draft creation

### Existing base

- GitHub issue APIs
- GitHub PR APIs
- workspace editing
- command execution
- changesets
- validation/review concepts

### Missing

- provider abstraction
- issue-to-feature mapping
- branch workflow
- commit/push workflow
- PR draft synthesis

### Recommended first slice

- GitHub only
- draft PR only
- issue -> branch -> implement -> validate -> draft PR

GitLab should come after provider abstraction, not before.

---

## Architecture Normalization Plan

This is the structural cleanup required to support the above work.

### Current architecture problem

`backend/api/views.py` is still the execution core.

### Updated target ownership

Conceptually split into:

- `transport`
  - HTTP views / serializers / response handling
- `application`
  - runs, orchestration, workflows
- `domain`
  - project state, blueprint state, run state, changesets
- `infrastructure`
  - workspace, sandbox, git, provider adapters, extractor engines
- `understanding`
  - codebase context, API extraction, graph, documentation inputs

### Priority refactor targets

1. move API extraction concerns out of broad helper space into one focused extraction layer
2. move run/execution orchestration out of `views.py`
3. stop adding more product logic directly into controller endpoints

This is not optional if the app is meant to keep growing.

---

## Existing vs Missing Summary

| Area | Existing | Missing |
| --- | --- | --- |
| Code onboarding | Strong base | Fast unified query path, better dependency navigation, stronger observability |
| Powerful edits | Strong base | Diff-first review, unified trace UI, stronger VCS integration |
| GitHub workflows | Partial base | End-to-end issue-to-PR orchestration |
| GitLab | No | Provider implementation and integration |
| API extraction | Exists but unreliable | Correct root detection, include traversal, diagnostics, confidence model |
| Trace UX | Partial | Live execution system, global panel, terminal mirroring, verbose hierarchy |
| Async model | Partial | Unified run/job/event architecture |

---

## README Update Plan

`devhub_v2/README.md` should be updated after this planning work. It currently presents the product too broadly and does not explain the known limitations or the execution model clearly enough.

### What the README currently gets right

- broad product overview
- major surfaces
- local setup
- GitHub OAuth setup

### What the README currently misses

- current feature maturity by area
- known limitation of Blueprint/API extraction
- explanation of chat/edit/agent execution modes
- trace and observability story
- distinction between current GitHub support and the future issue-to-PR workflow
- roadmap direction grounded in real architecture work

### Recommended README structure

## Section 1: What DevHub Is

Keep, but tighten.

Say:

- project-aware engineering workspace
- repo understanding
- code editing
- runtime control
- GitHub-connected workflow primitives

Do not oversell:

- complete issue-to-PR automation
- GitLab integration
- fully reliable API extraction for every repo today

## Section 2: Current Capability Status

Add a simple truth table:

- Code onboarding: available
- Powerful edits: available
- GitHub issues/PR primitives: available
- End-to-end issue-to-PR workflow: in progress
- GitLab integration: planned
- Agent execution traces: partial, expanding

## Section 3: How Blueprint Generation Works

Document:

- cached codebase context
- API extraction
- deep documentation sections
- graph enrichment
- known limitations

Include explicit note:

- API extraction is under active hardening for large Django route graphs and nested include layouts

## Section 4: Workspace Chat Modes

Document:

- Ask
- Edit
- Agent

Explain what each mode does and how traces are surfaced.

## Section 5: Execution Visibility

Add a section on:

- files accessed
- commands ran
- workspace actions
- tool execution timeline
- current and planned trace surfaces

## Section 6: Roadmap

Replace vague direction text with concrete roadmap:

1. API extraction correctness
2. execution visibility and event streaming
3. issue-to-draft-PR workflow
4. Git provider abstraction and GitLab

## Section 7: Known Architecture Constraints

Briefly acknowledge:

- monolithic backend view layer
- overlapping blueprint/documentation pipelines
- ongoing consolidation work

This makes the README more honest and more useful for contributors.

### README acceptance criteria

The updated README should let a new contributor understand:

- what the app can do today
- what is still in progress
- how Blueprint generation currently works
- where observability exists today
- what the next roadmap items are

---

## Recommended Delivery Order

This is the recommended order of work.

### Step 1

Fix API extraction correctness and diagnostics.

### Step 2

Clean setup and testing provenance so Blueprint output is trustworthy.

### Step 3

Implement unified execution events and frontend/backend trace visibility.

### Step 4

Normalize async/background run handling around the shared event model.

### Step 5

Build GitHub issue -> branch -> implement -> validate -> draft PR.

### Step 6

Introduce Git provider abstraction and then add GitLab.

---

## Definition of Success

This next phase is successful when:

- the failing imported Django repo no longer collapses to `/admin/`
- Blueprint API output reflects the actual app route surface
- setup and testing sections show provenance and no obvious duplication
- users can watch agent execution live in the app and in terminal logs
- the product can honestly claim:
  - strong code onboarding
  - strong powerful edits
  - partial but real issue-to-PR flow

Until the API pipeline is fixed, that bar is not met.
