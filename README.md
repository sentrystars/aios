# AIOS

[中文说明](./README.zh-CN.md)

AIOS is a local-first personal operating system for AI-driven work.

This repository now contains:

- a FastAPI backend kernel
- a manifest-driven runtime / capability / workflow system
- a policy and governance layer
- a macOS client with user-facing workspace pages and developer inspection pages

The current direction is:

- users describe a goal in natural language
- AIOS decides how to handle it
- the system automatically creates, plans, executes, and verifies work when it is safe
- the loop only stops when confirmation or policy review is genuinely required

## Current Architecture

The codebase is no longer organized around a single `services.py` file.

It is split into these layers:

- `ai_os/domain/`
  - core data models for tasks, memory, runtime, policy, plugins, workflows, usage, devices, goals, and relations
- `ai_os/repositories/`
  - persistence and storage boundaries
- `ai_os/kernel_execution.py`
  - intent evaluation, cognition, task state machine, execution planning
- `ai_os/kernel_services.py`
  - self, goals, memory, relations, execution run support
- `ai_os/capabilities/`
  - capability registry plus concrete handlers such as `local_files`, `notes`, `messaging`, `reminders`, `calendar`
- `ai_os/runtimes/`
  - runtime registry and adapters, including `claude-code`
- `ai_os/workflows.py`
  - intake and delivery orchestration
- `ai_os/policy.py`
  - lifecycle hooks, rules, and runtime-contributed policy injection
- `ai_os/plugin_registry.py`
  - plugin manifest discovery
- `ai_os/api.py`
  - FastAPI transport layer
- `main.py`
  - thin app entrypoint

## Manifest-Driven Discovery

AIOS now supports declaration-based discovery for:

- runtimes
- capabilities
- workflows
- plugins

Current examples:

- runtime manifest: [runtimes/claude-code/runtime.json](/Users/liuxiaofeng/AI%20OS/runtimes/claude-code/runtime.json)
- capability manifests: [ai_os/capabilities/manifests](/Users/liuxiaofeng/AI%20OS/ai_os/capabilities/manifests)
- workflow manifests: [ai_os/workflows/manifests](/Users/liuxiaofeng/AI%20OS/ai_os/workflows/manifests)
- plugin manifests: [plugins](/Users/liuxiaofeng/AI%20OS/plugins)

This means the system is now closer to:

`kernel + policy + runtime/capability/workflow/plugin discovery`

instead of a hardcoded monolith.

## Runtime Model

`claude-code` is integrated as a runtime, not as kernel logic.

The runtime stack supports:

- runtime listing
- runtime preview
- runtime invocation description
- runtime-aware task planning
- runtime execution metadata on `ExecutionRun`
- real `claude -p` execution when the local CLI is available
- safe fallback to handoff-style execution artifacts when it is not

Reference design notes live in [docs/claude-code-integration.md](/Users/liuxiaofeng/AI%20OS/docs/claude-code-integration.md).

## Policy Model

Policy is no longer only hardcoded branching.

`PolicyEngine` now supports:

- lifecycle hooks such as `before_execute` and `before_external_side_effect`
- structured rules
- runtime-contributed rules
- explicit confirmation override flow
- policy decisions recorded into `ExecutionRun.metadata`

This is the first step toward a configurable governance system.

## Backend Features

The backend currently supports:

- self profile and persistent context
- layered memory
- task planning, execution, verification, and reflection
- execution runs and relation graph
- reminders and calendar events
- candidate discovery and accept/defer flows
- scheduler tick and stalled-task escalation
- runtime-aware execution
- usage reporting for capabilities, runtimes, and plugins

The main user-facing flow is:

1. `POST /inbox/process`
2. task creation when the request should become tracked work
3. `plan`
4. `start`
5. `verify`
6. optional `reflect`

The macOS app now uses that flow automatically from the conversation page.

## macOS App

The macOS client is no longer only a backend admin panel.

It now includes user-facing workspace pages:

- `Overview`
- `Conversation`
- `Tasks`
- `Memory`
- `Reminders`
- `Candidates`

It also keeps developer inspection pages:

- `Capabilities`
- `Runtimes`
- `Plugins`
- `Workflows`
- `Events`
- `Self`

The conversation page is designed so a user can send one request and let AIOS auto-run the workflow.

Menu bar support is also included for:

- backend connection status
- quick task creation
- refresh and scheduler actions

## Run The Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
.venv/bin/python -m uvicorn main:app --reload --port 8787
```

Health check:

```bash
curl -s http://127.0.0.1:8787/healthz
```

Expected result:

```json
{"status":"ok"}
```

Optional cloud intent understanding with DeepSeek:

```bash
export DEEPSEEK_API_KEY=your_key
export DEEPSEEK_MODEL=deepseek-chat
```

When configured, AIOS uses DeepSeek for dialogue intent understanding and falls back to local rules if the API is unavailable.

## Build The macOS App

Quick local build:

```bash
swift build
```

Xcode-style app bundle build:

```bash
xcodebuild -project macos/AIOSMac/AIOSMac.xcodeproj \
  -scheme AIOSMac \
  -configuration Debug \
  -derivedDataPath .build/xcode-derived \
  CODE_SIGNING_ALLOWED=NO build
```

Open the app:

```bash
open -n ./.build/xcode-derived/Build/Products/Debug/AIOSMac.app
```

## Key Endpoints

Core:

- `GET /healthz`
- `GET /self`
- `PUT /self`
- `GET /self/timeline`
- `POST /intents/evaluate`
- `POST /inbox/process`
- `GET /events`

Tasks:

- `POST /tasks`
- `GET /tasks`
- `POST /tasks/{task_id}/plan`
- `POST /tasks/{task_id}/start`
- `POST /tasks/{task_id}/advance`
- `POST /tasks/{task_id}/confirm`
- `POST /tasks/{task_id}/verify`
- `POST /tasks/{task_id}/reflect`
- `GET /tasks/{task_id}/timeline`
- `GET /tasks/{task_id}/relations`
- `GET /tasks/{task_id}/runs`

Runs and relations:

- `GET /runs/{run_id}/events`
- `GET /runs/{run_id}/timeline`
- `GET /memories/{memory_id}/relations`

Memory and goals:

- `POST /memory/facts`
- `GET /memory/facts`
- `GET /memory/recall`
- `GET /goals`
- `POST /goals`
- `POST /goals/{goal_id}`

Capabilities and runtimes:

- `GET /capabilities`
- `POST /capabilities/execute`
- `GET /runtimes`
- `GET /tasks/{task_id}/runtime-preview`
- `GET /tasks/{task_id}/runtime-invocation`

Plugins, workflows, policy, usage:

- `GET /plugins`
- `GET /workflows`
- `GET /policies`
- `GET /capabilities/{name}/usage`
- `GET /runtimes/{name}/usage`
- `GET /plugins/{name}/usage`

Candidates and scheduler:

- `GET /candidates`
- `POST /candidates/accept`
- `POST /candidates/auto-accept`
- `POST /candidates/auto-accept-eligible`
- `POST /candidates/defer`
- `POST /scheduler/tick`

## Current Notes

- The backend port is `8787`, not `8000`.
- `main.py` is intentionally a thin import-only entrypoint.
- Candidate discovery is exposed through `/candidates` and backed by `CandidateTaskService.discover()`.
- Chinese requests such as calendar scheduling now map into the calendar execution path.
- The conversation page is optimized for a one-shot automatic workflow, not a step-by-step admin flow.

## Verification

Backend tests:

```bash
.venv/bin/python -m unittest discover -s tests -q
```

Swift build verification:

```bash
swift build
```
