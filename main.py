from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from ai_os.domain import (
    CandidateAcceptancePayload,
    CandidateAcceptanceResult,
    CandidateAutoAcceptPayload,
    CandidateBatchAutoAcceptPayload,
    CandidateBatchAutoAcceptResult,
    CandidateDeferPayload,
    CandidateDeferResult,
    CandidateTask,
    CapabilityExecutionPayload,
    EntityRelation,
    EventRecord,
    ExecutionRunRecord,
    InputPayload,
    MemoryCreatePayload,
    SchedulerTickPayload,
    SchedulerTickResult,
    SelfProfile,
    TaskAdvancePayload,
    TaskConfirmationPayload,
    TaskCreatePayload,
    TaskReflectionPayload,
    TaskVerificationPayload,
    TimelineItem,
)
from ai_os.services import CandidateTaskService, DeliveryCoordinator, EventQueryService, IntakeCoordinator, build_container

app = FastAPI(title="AI OS MVP", version="0.1.0")
container = build_container(Path(".data"))
intake = IntakeCoordinator(
    self_kernel=container.self_kernel,
    intent_engine=container.intent_engine,
    cognition_engine=container.cognition_engine,
    task_engine=container.task_engine,
)
delivery = DeliveryCoordinator(
    task_engine=container.task_engine,
    memory_engine=container.memory_engine,
    capability_bus=container.capability_bus,
    relation_service=container.relation_service,
    execution_run_service=container.execution_run_service,
)
events = EventQueryService(container.event_repo)
candidates = CandidateTaskService(
    container.self_kernel,
    container.task_engine,
    container.event_repo,
    container.capability_bus,
    container.relation_service,
)
scheduler = container.scheduler_service


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/self", response_model=SelfProfile)
def get_self() -> SelfProfile:
    return container.self_kernel.get()


@app.put("/self", response_model=SelfProfile)
def update_self(profile: SelfProfile) -> SelfProfile:
    return container.self_kernel.update(profile)


@app.get("/self/timeline", response_model=list[TimelineItem])
def get_self_timeline(limit: int = 100):
    return events.self_timeline(limit=limit)


@app.post("/memory/facts")
def create_memory(payload: MemoryCreatePayload):
    return container.memory_engine.create(payload)


@app.get("/memory/facts")
def list_memories():
    return container.memory_engine.list()


@app.post("/intents/evaluate")
def evaluate_intent(payload: InputPayload):
    profile = container.self_kernel.get()
    return container.intent_engine.evaluate(payload, profile)


@app.post("/inbox/process")
def process_input(payload: InputPayload):
    return intake.process(payload)


@app.post("/tasks")
def create_task(payload: TaskCreatePayload):
    return container.task_engine.create(payload)


@app.get("/tasks")
def list_tasks():
    return container.task_engine.list()


@app.post("/tasks/{task_id}/plan")
def plan_task(task_id: str):
    try:
        return container.task_engine.plan(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/start")
def start_task(task_id: str):
    try:
        return delivery.execute_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/advance")
def advance_task(task_id: str, payload: TaskAdvancePayload):
    try:
        return container.task_engine.advance(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/verify")
def verify_task(task_id: str, payload: TaskVerificationPayload):
    try:
        return delivery.verify_task(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/confirm")
def confirm_task(task_id: str, payload: TaskConfirmationPayload):
    try:
        return delivery.confirm_task(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/reflect")
def reflect_task(task_id: str, payload: TaskReflectionPayload):
    try:
        return delivery.reflect_task(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/capabilities")
def list_capabilities():
    return container.capability_bus.list()


@app.post("/capabilities/execute")
def execute_capability(payload: CapabilityExecutionPayload):
    try:
        return delivery.execute_capability(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/events", response_model=list[EventRecord])
def list_events(limit: int = 100):
    return events.list_recent(limit=limit)


@app.get("/tasks/{task_id}/events", response_model=list[EventRecord])
def list_task_events(task_id: str, limit: int = 100):
    return events.list_for_task(task_id=task_id, limit=limit)


@app.get("/tasks/{task_id}/timeline", response_model=list[TimelineItem])
def get_task_timeline(task_id: str, limit: int = 100):
    return events.task_timeline(task_id=task_id, limit=limit)


@app.get("/tasks/{task_id}/relations", response_model=list[EntityRelation])
def get_task_relations(task_id: str, limit: int = 100):
    return container.relation_service.list_for_entity(entity_type="task", entity_id=task_id, limit=limit)


@app.get("/tasks/{task_id}/runs", response_model=list[ExecutionRunRecord])
def get_task_runs(task_id: str, limit: int = 100):
    return container.execution_run_service.list_for_task(task_id=task_id, limit=limit)


@app.get("/runs/{run_id}/events", response_model=list[EventRecord])
def get_run_events(run_id: str, limit: int = 100):
    return events.list_for_execution_run(run_id=run_id, limit=limit)


@app.get("/runs/{run_id}/timeline", response_model=list[TimelineItem])
def get_run_timeline(run_id: str, limit: int = 100):
    return events.execution_run_timeline(run_id=run_id, limit=limit)


@app.get("/memories/{memory_id}/relations", response_model=list[EntityRelation])
def get_memory_relations(memory_id: str, limit: int = 100):
    return container.relation_service.list_for_entity(entity_type="memory", entity_id=memory_id, limit=limit)


@app.get("/candidates", response_model=list[CandidateTask])
def list_candidates(limit: int = 10):
    return candidates.discover(limit=limit)


@app.post("/candidates/accept", response_model=CandidateAcceptanceResult)
def accept_candidate(payload: CandidateAcceptancePayload):
    try:
        return candidates.accept(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/candidates/auto-accept", response_model=CandidateAcceptanceResult)
def auto_accept_candidate(payload: CandidateAutoAcceptPayload):
    try:
        return candidates.auto_accept(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/candidates/auto-accept-eligible", response_model=CandidateBatchAutoAcceptResult)
def auto_accept_eligible_candidates(payload: CandidateBatchAutoAcceptPayload):
    return candidates.auto_accept_eligible(payload)


@app.post("/candidates/defer", response_model=CandidateDeferResult)
def defer_candidate(payload: CandidateDeferPayload):
    try:
        return candidates.defer(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/scheduler/tick", response_model=SchedulerTickResult)
def run_scheduler_tick(payload: SchedulerTickPayload):
    return scheduler.tick(payload)
