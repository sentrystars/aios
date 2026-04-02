from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_os.capabilities import CapabilityRegistry
from ai_os.candidates import CandidateTaskService
from ai_os.cloud_intelligence import DeepSeekConversationIntelligence
from ai_os.domain import DeviceStatus, DeviceUpsertPayload
from ai_os.kernel import (
    CognitionEngine,
    Database,
    DeviceService,
    ExecutionRunService,
    GoalService,
    GovernanceLayer,
    IntentEngine,
    MemoryEngine,
    RelationService,
    SelfKernel,
    TaskEngine,
)
from ai_os.plugin_registry import PluginRegistry
from ai_os.scheduler import SchedulerService
from ai_os.storage import (
    DeviceRepository,
    EventRepository,
    ExecutionRunRepository,
    GoalRepository,
    MemoryRepository,
    RelationRepository,
    SelfRepository,
    TaskRepository,
)
from ai_os.runtimes import RuntimeRegistry
from ai_os.policy import PolicyEngine
from ai_os.workflow_registry import WorkflowRegistry, default_workflow_factories
from ai_os.workflows import DeliveryCoordinator


@dataclass
class KernelContainer:
    self_kernel: SelfKernel
    goal_service: GoalService
    device_service: DeviceService
    intent_engine: IntentEngine
    cognition_engine: CognitionEngine
    memory_engine: MemoryEngine
    relation_service: RelationService
    execution_run_service: ExecutionRunService
    task_engine: TaskEngine
    capability_bus: CapabilityRegistry
    runtime_registry: RuntimeRegistry
    policy_engine: PolicyEngine
    workflow_registry: WorkflowRegistry
    plugin_registry: PluginRegistry
    event_repo: EventRepository
    scheduler_service: SchedulerService


def build_container(data_dir: Path) -> KernelContainer:
    workspace_root = data_dir if data_dir.is_dir() else data_dir.parent
    app_root = Path(__file__).resolve().parent.parent
    db = Database(data_dir / "ai_os.db")
    events = EventRepository(db)
    self_repo = SelfRepository(db)
    memory_repo = MemoryRepository(db)
    goal_repo = GoalRepository(db)
    device_repo = DeviceRepository(db)
    relation_repo = RelationRepository(db)
    execution_run_repo = ExecutionRunRepository(db)
    task_repo = TaskRepository(db)
    conversation_intelligence = DeepSeekConversationIntelligence.from_env()
    governance = GovernanceLayer()
    relation_service = RelationService(relation_repo, events)
    execution_run_service = ExecutionRunService(execution_run_repo, events, relation_service)
    memory_engine = MemoryEngine(memory_repo, events, relation_service)
    self_kernel = SelfKernel(self_repo, events)
    goal_service = GoalService(goal_repo, events, memory_engine=memory_engine, self_kernel=self_kernel)
    device_service = DeviceService(device_repo, events)
    intent_engine = IntentEngine(governance, conversation_intelligence=conversation_intelligence)
    cognition_engine = CognitionEngine(memory_engine=memory_engine, conversation_intelligence=conversation_intelligence)
    task_engine = TaskEngine(task_repo, events, memory_engine=memory_engine)
    capability_bus = CapabilityRegistry(workspace_root)
    runtime_registry = RuntimeRegistry(workspace_root=workspace_root, app_root=app_root)
    policy_engine = PolicyEngine()
    policy_engine.extend_rules(runtime_registry.contributed_policy_rules())
    workflow_registry = WorkflowRegistry(
        manifests_root=Path(__file__).resolve().parent / "workflows" / "manifests",
        factories=default_workflow_factories(),
    )
    plugin_registry = PluginRegistry(
        manifests_root=app_root / "plugins",
        capability_registry=capability_bus,
        runtime_registry=runtime_registry,
        workflow_registry=workflow_registry,
    )
    candidate_service = CandidateTaskService(
        self_kernel=self_kernel,
        goal_service=goal_service,
        task_engine=task_engine,
        event_repo=events,
        capability_bus=capability_bus,
        runtime_registry=runtime_registry,
        relation_service=relation_service,
    )
    delivery: DeliveryCoordinator = workflow_registry.build(
        "delivery",
        task_engine=task_engine,
        memory_engine=memory_engine,
        capability_bus=capability_bus,
        relation_service=relation_service,
        execution_run_service=execution_run_service,
        runtime_registry=runtime_registry,
        policy_engine=policy_engine,
    )
    scheduler_service = SchedulerService(
        candidate_service,
        task_engine,
        delivery,
        events,
        self_kernel,
        relation_service,
        memory_engine,
        goal_service,
    )

    if not device_service.list():
        device_service.upsert(
            DeviceUpsertPayload(
                id="mac-local",
                name="Local Mac",
                device_class="mac_local",
                status=DeviceStatus.ACTIVE,
                capabilities=[
                    "local_files",
                    "notes",
                    "aios_local_messaging",
                    "aios_local_reminders",
                    "aios_local_calendar",
                    "system_messaging",
                    "system_reminders",
                    "system_calendar",
                ],
                metadata={"bootstrap": True},
            )
        )

    return KernelContainer(
        self_kernel=self_kernel,
        goal_service=goal_service,
        device_service=device_service,
        intent_engine=intent_engine,
        cognition_engine=cognition_engine,
        memory_engine=memory_engine,
        relation_service=relation_service,
        execution_run_service=execution_run_service,
        task_engine=task_engine,
        capability_bus=capability_bus,
        runtime_registry=runtime_registry,
        policy_engine=policy_engine,
        workflow_registry=workflow_registry,
        plugin_registry=plugin_registry,
        event_repo=events,
        scheduler_service=scheduler_service,
    )
