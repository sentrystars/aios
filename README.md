# AI OS MVP

This repository contains a first-pass local-first backend kernel for AI OS.

## Scope

The MVP implements:

- `Self Kernel` for persistent user context
- `Persona Runtime` for identity anchor and session commitments
- `Intent Engine` for request classification
- `Structured Understanding` for requested outcome, constraints, stakeholders, and time horizon
- `Memory Engine` for layered recall (`episodic`, `semantic`, `procedural`)
- `Task Engine` with a task state machine
- `Goal Graph` for long-range objective structure
- `Governance Layer` for risk checks and confirmation policy
- `Capability Bus` for registering executable capabilities with metadata
- `Device Registry` for lightweight multi-device abstraction
- `FastAPI` endpoints to drive the kernel

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn main:app --reload --port 8787
```

## Key Endpoints

- `GET /healthz`
- `GET /self`
- `PUT /self`
- `GET /self/timeline`
- `POST /memory/facts`
- `GET /memory/facts`
- `GET /memory/recall`
- `GET /goals`
- `POST /goals`
- `POST /goals/{goal_id}`
- `POST /intents/evaluate`
- `POST /inbox/process`
- `POST /tasks`
- `GET /tasks`
- `POST /tasks/{task_id}/plan`
- `POST /tasks/{task_id}/start`
- `POST /tasks/{task_id}/advance`
- `POST /tasks/{task_id}/confirm`
- `POST /tasks/{task_id}/verify`
- `POST /tasks/{task_id}/reflect`
- `GET /capabilities`
- `POST /capabilities/execute`
- `GET /devices`
- `PUT /devices`
- `GET /events`
- `GET /tasks/{task_id}/events`
- `GET /tasks/{task_id}/timeline`
- `GET /tasks/{task_id}/relations`
- `GET /tasks/{task_id}/runs`
- `GET /runs/{run_id}/events`
- `GET /runs/{run_id}/timeline`
- `GET /memories/{memory_id}/relations`
- `GET /candidates`
- `POST /candidates/accept`
- `POST /candidates/auto-accept`
- `POST /candidates/auto-accept-eligible`
- `POST /candidates/defer`
- `POST /scheduler/tick`

## Design Notes

This is deliberately a small kernel. Higher-order autonomy, richer planning, and hardware bodies should be layered on top of these primitives rather than folded into the core.

The current iteration extends that kernel toward the intended AI OS definition:

- `SelfProfile` now carries a persistent `persona_anchor` and mutable `session_context`
- cognition now emits `structured_understanding` instead of only a mode suggestion
- memory records now capture layer, source, confidence, freshness, and goal linkage
- goals are persisted as first-class graph nodes and can drive candidate creation
- capabilities now publish metadata such as scopes, confirmation requirement, device affinity, and expected evidence
- devices are now registered explicitly so execution can grow beyond a single local machine

`POST /inbox/process` is the main MVP entrypoint. It runs:

- intent classification
- commonsense / insight / courage analysis
- execution plan selection
- automatic task creation for executable work

`POST /tasks/{task_id}/plan` moves a task into `planned` and generates a first-pass execution checklist.

`POST /tasks/{task_id}/start`, `verify`, and `reflect` cover the back half of the loop:

- move planned work into execution
- create a first-pass task artifact under `artifacts/tasks/`
- verify whether success criteria were satisfied
- write reflection memory after completion

Task execution is now strategy-based:

- document and planning tasks generate workspace artifacts
- capture and remember tasks write structured memory
- messaging tasks create a draft and then block for confirmation
- reminder tasks create local reminder entries for future follow-up

Each task now carries an explicit `execution_mode` and a structured `execution_plan` assigned at create/plan time, so execution no longer depends on last-minute keyword routing.

Verification also consumes `execution_plan.expected_evidence`, so completion checks can be derived from the same plan that drove execution.

Message draft tasks now support an explicit confirmation step before verification can complete.

The event log is also queryable now, both globally and per task, so you can inspect the AI OS timeline rather than only the latest task snapshot.

`GET /tasks/{task_id}/timeline` returns a display-oriented summary view on top of the raw event log.

`GET /self/timeline` provides the same kind of summary view for changes to the persistent self profile.

`GET /candidates` surfaces proactive next-step suggestions derived from task state, self changes, and recent system activity.

The candidate system also pulls due local reminders back into the task loop, so reminder entries can reappear as actionable work.

Reminder entries are now time-structured rather than just string-labeled:

- `scheduled_for` determines when a reminder becomes eligible for resurfacing
- `last_seen_at` prevents the same due reminder from being surfaced repeatedly on every candidate poll
- `source_task_id` and `origin` let a reminder keep explicit linkage back to the task context that created it

`GET /candidates` now acts as a lightweight scheduling pass for reminders: when a due reminder is surfaced as a candidate, it is marked seen so it does not immediately reappear unchanged.

`POST /candidates/accept` turns a suggestion into a concrete action by either advancing an existing task or creating a new one.

`POST /candidates/defer` is currently focused on due reminders. It reschedules a surfaced reminder candidate back onto the future timeline instead of forcing an immediate task conversion.

When a due reminder is accepted, the system now prefers restoring or continuing the linked source task context if one exists, instead of always creating a brand-new task.

The kernel now also persists an explicit relation layer across entities. Tasks can link to:

- produced artifacts
- captured or reflection memories
- scheduled reminders
- reminder-triggered resume events

This relation graph is stored separately from task state so the execution loop stays small while context linkage remains queryable.

The kernel now also records per-task execution runs. Each `start` creates an `execution_run`, and downstream artifacts, captured memory, reminders, verification, and reflection can be linked to that specific run instead of only to the task as a whole.

`GET /runs/{run_id}/timeline` provides a display-oriented view of a single execution pass, including run start/completion, run-scoped relation events, and execution output markers.

Task timelines now also summarize proactive coordination decisions, including candidate acceptance, reminder-based task resume, and candidate defer/reschedule actions. This makes the timeline reflect not only what the system executed, but also why it chose to push or delay work.

Candidates now carry explicit `reason_code` and `trigger_source` fields, so proactive suggestions are traceable back to their cause, such as blocked task state, due reminder resurfacing, active execution follow-up, or self phase change. Those fields are also written into candidate acceptance/defer events and surfaced in timeline details.

Candidates now also carry policy-facing governance defaults:

- `priority`
- `auto_acceptable`
- `needs_confirmation`

These defaults are derived from `reason_code`, so the system can start distinguishing between candidates that are safe to auto-push, candidates that should stay advisory, and candidates that should require explicit user confirmation.

`POST /candidates/auto-accept` is now available as a constrained governance path. It only permits candidates that are explicitly marked `auto_acceptable=true` and `needs_confirmation=false`; all other candidates remain blocked from automatic acceptance.

`POST /candidates/auto-accept-eligible` scans the current candidate set, auto-accepts only the policy-approved subset, and returns a batch report with `accepted`, `skipped`, and `errors`. This is the first minimal building block for a controlled autonomous push loop.

`POST /scheduler/tick` now wraps that loop into a single scheduler pass:

1. discover current candidates
2. auto-accept the eligible subset
3. auto-start planned tasks that do not require confirmation
4. auto-verify executing tasks that do not require confirmation
5. handle stalled tasks by state:
   blocked tasks create unblock follow-up tasks
   executing tasks create reminders when they go stale and do not already have a linked reminder
6. escalate repeatedly stalled tasks by explicit policy:
   the active policy is now selected from `Self.risk_style`
   `balanced` keeps the default middle path
   `cautious` escalates earlier and more loudly, including urgent reminder paths for blocked and executing work
   `bold` stays more permissive and keeps escalation lighter
   blocked tasks are typically promoted to higher risk and get an escalation review task
   executing tasks can also upgrade an existing reminder into an urgent reminder path
6. emit a scheduler completion report with discovered, accepted, started, verified, stalled-reminder, skipped, and error counts

This is still a deliberately small scheduler, but it establishes the core autonomous tick the system can build on later.

`SchedulerTickResult` now also carries structured `escalations`, so callers can inspect which task was escalated, which policy fired, whether risk was promoted, and whether the escalation produced a task, a reminder, or both.

Task-level governance can now override the self-level default. Tasks persist `tags`, and the scheduler currently understands:

- `governance:cautious`
- `governance:balanced`
- `governance:bold`
- `escalation:urgent_reminder`
- `escalation:no_urgent_reminder`
- `escalation:promote_high`
- `escalation:no_risk_promotion`

There is also an implicit guardrail: if a task's execution plan requires confirmation, repeated-stall escalation will always force an urgent reminder path even when the broader policy is more permissive.

The scheduler now also reads lightweight context from the relation graph. A task that was resurfaced from a reminder with origin `scheduler_tick` or `scheduler_escalation` is treated more cautiously on later repeated-stall escalation, even if the user's broader `risk_style` is more permissive.

The scheduler now also reads lightweight contact context from `Self.relationship_network`. The current minimal syntax is:

- `high_risk:Alice`
- `cautious:Alice`
- `balanced:Bob`
- `bold:Carol`

If a task objective mentions that contact name, the matching governance style is applied before the self-level default. Task tags still have the highest precedence, so explicit task governance overrides both relationship context and self defaults.

The scheduler now also reads lightweight lessons from reflection memory. The current minimal syntax inside reflection lessons/content is:

- `guardrail:cautious:alice`
- `guardrail:bold:vendor-x`

If a later task objective contains that keyword, the matching governance style is applied before relationship context and self defaults. The effective precedence is now:

1. task tags
2. reflection guardrails
3. relationship context
4. reminder/relation context
5. self default

Reflection guardrails are now also consumed during intake/cognition, not only during scheduler escalation. If a new request matches a cautious reflection guardrail, the cognition layer will switch the task toward `confirm_then_execute` and mark the execution plan as confirmation-required before any execution starts.

That same intake pass now also writes the guardrail into task understanding:

- `suggested_task_tags` includes tags such as `governance:cautious` and `guardrail:reflection`
- `suggested_success_criteria` is expanded to include explicit confirmation / risk review before action

So historical lessons now influence not only runtime gating, but also the task object that enters the system.

Candidate discovery now also consumes those persisted task tags. For task-backed candidates such as `plan`, `follow_up`, and reminder resurfacing tied to a source task, the candidate policy layer now prefers task governance tags like `governance:cautious` over the plain reason-code defaults. This keeps proactive scheduling aligned with the governance state already written onto the task.

Batch auto-accept and scheduler tick now also expose structured skip reasons via `skip_details`, in addition to the legacy summary strings. This makes it possible to distinguish cases like `not_auto_acceptable` and `needs_confirmation` without parsing free-form text.

Those skip reasons are now also summarized into the corresponding event payloads and timeline details via `skip_reason_counts`, so the event stream can explain not only how many candidates were skipped, but why they were skipped.

The system now also turns some skip reasons into actionable candidates:

- `confirm_gate`: surfaces tasks that require explicit confirmation before autonomous execution
- `governance_review`: surfaces tasks whose governance tags currently block autonomous advancement

Accepting `confirm_gate` keeps the current task in focus for review, while accepting `governance_review` creates an explicit governance review task.

`POST /capabilities/execute` currently includes:

- `local_files` for workspace-scoped file reads, writes, and directory listing
- `notes` for low-risk note drafting
- `messaging` as a gated high-risk stub that always requires confirmation
- `reminders` for local reminder create/list/delete/mark_seen/reschedule
