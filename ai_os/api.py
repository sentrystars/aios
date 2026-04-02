from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from ai_os.bootstrap import build_container
from ai_os.candidates import CandidateTaskService
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
    DeviceRecord,
    DeviceUpsertPayload,
    EntityRelation,
    EventRecord,
    ExecutionRunRecord,
    GoalCreatePayload,
    GoalPlanResult,
    GoalRecord,
    GoalUpdatePayload,
    InputPayload,
    MemoryCreatePayload,
    MemoryRecallResponse,
    PluginDescriptor,
    PolicyRuleDescriptor,
    RuntimeDescriptor,
    RuntimeInvocation,
    SchedulerTickPayload,
    SchedulerTickResult,
    SelfProfile,
    TaskAdvancePayload,
    TaskConfirmationPayload,
    TaskCreatePayload,
    TaskReflectionPayload,
    UsageTaskSummary,
    TaskVerificationPayload,
    TimelineItem,
    WorkflowManifest,
)
from ai_os.event_query import EventQueryService


def create_app(data_dir: Path = Path(".data")) -> FastAPI:
    app = FastAPI(title="AI OS MVP", version="0.1.0")
    container = build_container(data_dir)
    intake = container.workflow_registry.build(
        "intake",
        self_kernel=container.self_kernel,
        goal_service=container.goal_service,
        intent_engine=container.intent_engine,
        cognition_engine=container.cognition_engine,
        task_engine=container.task_engine,
    )
    delivery = container.workflow_registry.build(
        "delivery",
        task_engine=container.task_engine,
        memory_engine=container.memory_engine,
        capability_bus=container.capability_bus,
        relation_service=container.relation_service,
        execution_run_service=container.execution_run_service,
        runtime_registry=container.runtime_registry,
        policy_engine=container.policy_engine,
    )
    events = EventQueryService(container.event_repo)
    candidates = CandidateTaskService(
        container.self_kernel,
        container.goal_service,
        container.task_engine,
        container.event_repo,
        container.capability_bus,
        container.relation_service,
    )
    scheduler = container.scheduler_service

    def summarize_tasks(tasks: list) -> list[UsageTaskSummary]:
        return [
            UsageTaskSummary(
                id=task.id,
                objective=task.objective,
                status=task.status.value if hasattr(task.status, "value") else str(task.status),
                runtime_name=task.runtime_name or task.execution_plan.runtime_name,
                updated_at=task.updated_at,
            )
            for task in tasks
        ]

    def recent_usage_tasks(predicate, limit: int) -> list[UsageTaskSummary]:
        tasks = [task for task in container.task_engine.list() if predicate(task)]
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        return summarize_tasks(tasks[:limit])

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

    @app.get("/memory/recall", response_model=MemoryRecallResponse)
    def recall_memories(query: str, limit: int = 5):
        return container.memory_engine.recall(query=query, limit=limit)

    @app.get("/goals", response_model=list[GoalRecord])
    def list_goals():
        return container.goal_service.list()

    @app.post("/goals", response_model=GoalRecord)
    def create_goal(payload: GoalCreatePayload):
        return container.goal_service.create(payload)

    @app.post("/goals/{goal_id}", response_model=GoalRecord)
    def update_goal(goal_id: str, payload: GoalUpdatePayload):
        try:
            return container.goal_service.update(goal_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/goals/{goal_id}/plan", response_model=GoalPlanResult)
    def plan_goal(goal_id: str):
        try:
            return container.goal_service.plan_goal(goal_id, container.task_engine)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/devices", response_model=list[DeviceRecord])
    def list_devices():
        return container.device_service.list()

    @app.put("/devices", response_model=DeviceRecord)
    def upsert_device(payload: DeviceUpsertPayload):
        return container.device_service.upsert(payload)

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

    @app.get("/capabilities/{capability_name}/usage", response_model=list[UsageTaskSummary])
    def get_capability_usage(capability_name: str, limit: int = 5):
        return recent_usage_tasks(
            lambda task: any(step.capability_name == capability_name for step in task.execution_plan.steps),
            limit,
        )

    @app.get("/runtimes", response_model=list[RuntimeDescriptor])
    def list_runtimes():
        return container.runtime_registry.list()

    @app.get("/runtimes/{runtime_name}/usage", response_model=list[UsageTaskSummary])
    def get_runtime_usage(runtime_name: str, limit: int = 5):
        return recent_usage_tasks(
            lambda task: task.runtime_name == runtime_name or task.execution_plan.runtime_name == runtime_name,
            limit,
        )

    @app.get("/policies", response_model=list[PolicyRuleDescriptor])
    def list_policies(hook: str | None = None):
        if hook is None:
            return container.policy_engine.describe_rules()
        try:
            from ai_os.policy import LifecycleHook

            return container.policy_engine.describe_rules(LifecycleHook(hook))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/workflows", response_model=list[WorkflowManifest])
    def list_workflows():
        return container.workflow_registry.list_manifests()

    @app.get("/plugins", response_model=list[PluginDescriptor])
    def list_plugins():
        return container.plugin_registry.list()

    @app.get("/plugins/{plugin_name}/usage", response_model=list[UsageTaskSummary])
    def get_plugin_usage(plugin_name: str, limit: int = 5):
        plugins = {item.name: item for item in container.plugin_registry.list()}
        plugin = plugins.get(plugin_name)
        if plugin is None:
            raise HTTPException(status_code=404, detail=f"Plugin {plugin_name} not found.")
        return recent_usage_tasks(
            lambda task: (
                (task.runtime_name in plugin.runtimes if task.runtime_name else False)
                or (task.execution_plan.runtime_name in plugin.runtimes if task.execution_plan.runtime_name else False)
                or any(step.capability_name in plugin.capabilities for step in task.execution_plan.steps)
            ),
            limit,
        )

    @app.get("/tasks/{task_id}/runtime-preview")
    def preview_task_runtime(task_id: str, runtime_name: str = "claude-code"):
        task = container.task_engine.repo.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
        try:
            return container.runtime_registry.prepare_task(runtime_name, task)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/tasks/{task_id}/runtime-invocation", response_model=RuntimeInvocation)
    def get_task_runtime_invocation(task_id: str, runtime_name: str = "claude-code"):
        task = container.task_engine.repo.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
        try:
            return container.runtime_registry.build_invocation(runtime_name, task)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    def list_candidates(limit: int = 20):
        return candidates.list(limit=limit)

    @app.post("/candidates/accept", response_model=CandidateAcceptanceResult)
    def accept_candidate(payload: CandidateAcceptancePayload):
        return candidates.accept(payload)

    @app.post("/candidates/auto-accept", response_model=CandidateAcceptanceResult)
    def auto_accept_candidate(payload: CandidateAutoAcceptPayload):
        return candidates.auto_accept(payload)

    @app.post("/candidates/auto-accept-eligible", response_model=CandidateBatchAutoAcceptResult)
    def auto_accept_eligible_candidates(payload: CandidateBatchAutoAcceptPayload):
        return candidates.auto_accept_eligible(payload)

    @app.post("/candidates/defer", response_model=CandidateDeferResult)
    def defer_candidate(payload: CandidateDeferPayload):
        return candidates.defer(payload)

    @app.post("/scheduler/tick", response_model=SchedulerTickResult)
    def run_scheduler_tick(payload: SchedulerTickPayload):
        return scheduler.tick(payload)

    return app


app = create_app()
