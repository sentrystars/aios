from pathlib import Path
from datetime import datetime, timedelta
import json
from tempfile import TemporaryDirectory
import unittest

from ai_os.domain import (
    CandidateAcceptancePayload,
    CandidateAutoAcceptPayload,
    CandidateBatchAutoAcceptPayload,
    CandidateDeferPayload,
    SchedulerTickPayload,
    CapabilityExecutionPayload,
    ExecutionMode,
    GoalCreatePayload,
    GoalUpdatePayload,
    InputPayload,
    IntentType,
    MemoryCreatePayload,
    MemoryType,
    RiskLevel,
    TaskAdvancePayload,
    TaskConfirmationPayload,
    TaskCreatePayload,
    TaskReflectionPayload,
    TaskStatus,
    TaskVerificationPayload,
    utc_now,
)
from ai_os.services import CandidateTaskService, DeliveryCoordinator, EventQueryService, IntakeCoordinator, build_container
from ai_os.policy import LifecycleHook, PolicyContext, PolicyRule
from ai_os.runtimes import ClaudeCodeRuntime


class KernelServicesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.container = build_container(Path(self.tempdir.name))
        self.intake = IntakeCoordinator(
            self_kernel=self.container.self_kernel,
            goal_service=self.container.goal_service,
            intent_engine=self.container.intent_engine,
            cognition_engine=self.container.cognition_engine,
            task_engine=self.container.task_engine,
        )
        self.delivery = DeliveryCoordinator(
            task_engine=self.container.task_engine,
            memory_engine=self.container.memory_engine,
            capability_bus=self.container.capability_bus,
            relation_service=self.container.relation_service,
            execution_run_service=self.container.execution_run_service,
            runtime_registry=self.container.runtime_registry,
            policy_engine=self.container.policy_engine,
        )
        self.events = EventQueryService(self.container.event_repo)
        self.candidates = CandidateTaskService(
            self.container.self_kernel,
            self.container.goal_service,
            self.container.task_engine,
            self.container.event_repo,
            self.container.capability_bus,
            self.container.relation_service,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_intent_engine_classifies_question(self) -> None:
        envelope = self.container.intent_engine.evaluate(InputPayload(text="How should I plan this?"), self.container.self_kernel.get())
        self.assertEqual(envelope.intent_type.value, "question")

    def test_memory_engine_persists_record(self) -> None:
        self.container.memory_engine.create(
            MemoryCreatePayload(memory_type=MemoryType.KNOWLEDGE, title="Preference", content="Prefers local-first systems")
        )
        records = self.container.memory_engine.list()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].layer.value, "semantic")

    def test_self_update_emits_event_and_timeline(self) -> None:
        profile = self.container.self_kernel.get()
        profile.current_phase = "execution"
        profile.values = ["local-first", "clarity"]
        self.container.self_kernel.update(profile)
        recent_events = self.events.list_recent(limit=20)
        self.assertTrue(any(event.event_type == "self.updated" for event in recent_events))
        timeline = self.events.self_timeline(limit=10)
        self.assertTrue(timeline)
        self.assertEqual(timeline[-1].phase, "self")
        self.assertIn("current_phase", timeline[-1].detail)

    def test_task_engine_advances_valid_transition(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Ship MVP"))
        advanced = self.container.task_engine.advance(task.id, TaskAdvancePayload(status=TaskStatus.PLANNED))
        self.assertEqual(advanced.status, TaskStatus.PLANNED)

    def test_task_engine_generates_plan(self) -> None:
        task = self.container.task_engine.create(
            TaskCreatePayload(objective="Ship MVP", tags=["planning"], success_criteria=["API responds", "Tasks persist"])
        )
        planned = self.container.task_engine.plan(task.id)
        self.assertEqual(planned.status, TaskStatus.PLANNED)
        self.assertEqual(planned.tags, ["planning"])
        self.assertEqual(planned.execution_mode, ExecutionMode.FILE_ARTIFACT)
        self.assertEqual(planned.execution_plan.steps[0].capability_name, "local_files")
        self.assertGreaterEqual(len(planned.subtasks), 3)

    def test_intake_creates_task_for_action_request(self) -> None:
        response = self.intake.process(InputPayload(text="Draft the first AI OS milestone plan"))
        self.assertEqual(response.intent.intent_type, IntentType.TASK)
        self.assertEqual(response.cognition.suggested_execution_mode, ExecutionMode.FILE_ARTIFACT)
        self.assertEqual(response.cognition.suggested_execution_plan.steps[0].capability_name, "local_files")
        self.assertEqual(response.cognition.understanding.requested_outcome, "Draft the first AI OS milestone plan")
        self.assertIsNotNone(response.task)
        self.assertEqual(response.task.objective, "Draft the first AI OS milestone plan")
        self.assertEqual(response.task.execution_mode, ExecutionMode.FILE_ARTIFACT)
        self.assertEqual(response.task.execution_plan.mode, ExecutionMode.FILE_ARTIFACT)
        self.assertIsNone(response.task.runtime_name)

    def test_intake_does_not_create_task_for_question(self) -> None:
        response = self.intake.process(InputPayload(text="What should AI OS optimize for first?"))
        self.assertEqual(response.intent.intent_type, IntentType.QUESTION)
        self.assertIsNone(response.task)

    def test_intake_assigns_memory_execution_mode(self) -> None:
        response = self.intake.process(InputPayload(text="Remember that I prefer local-first systems"))
        self.assertEqual(response.cognition.suggested_execution_mode, ExecutionMode.MEMORY_CAPTURE)
        self.assertEqual(response.cognition.suggested_execution_plan.steps[0].capability_name, "memory_engine")
        self.assertIsNotNone(response.task)
        self.assertEqual(response.task.execution_mode, ExecutionMode.MEMORY_CAPTURE)
        self.assertEqual(response.task.execution_plan.mode, ExecutionMode.MEMORY_CAPTURE)

    def test_intake_assigns_message_execution_mode(self) -> None:
        response = self.intake.process(InputPayload(text="Message Alice about the AI OS progress"))
        self.assertEqual(response.cognition.suggested_execution_mode, ExecutionMode.MESSAGE_DRAFT)
        self.assertTrue(response.cognition.suggested_execution_plan.confirmation_required)
        self.assertIsNotNone(response.task)
        self.assertEqual(response.task.execution_mode, ExecutionMode.MESSAGE_DRAFT)
        self.assertEqual(response.task.execution_plan.steps[0].capability_name, "messaging")

    def test_intake_assigns_reminder_execution_mode(self) -> None:
        response = self.intake.process(InputPayload(text="Remind me to review the AI OS roadmap"))
        self.assertEqual(response.cognition.suggested_execution_mode, ExecutionMode.REMINDER)
        self.assertEqual(response.cognition.suggested_execution_plan.steps[0].capability_name, "reminders")
        self.assertIsNotNone(response.task)
        self.assertEqual(response.task.execution_mode, ExecutionMode.REMINDER)

    def test_intake_assigns_calendar_execution_mode(self) -> None:
        response = self.intake.process(InputPayload(text="Schedule time block for AI OS roadmap review"))
        self.assertEqual(response.cognition.suggested_execution_mode, ExecutionMode.CALENDAR_EVENT)
        self.assertEqual(response.cognition.suggested_execution_plan.steps[0].capability_name, "calendar")
        self.assertIsNotNone(response.task)
        self.assertEqual(response.task.execution_mode, ExecutionMode.CALENDAR_EVENT)

    def test_intake_assigns_calendar_execution_mode_for_chinese_request(self) -> None:
        response = self.intake.process(InputPayload(text="在日历中增加日程：下午1点进行产品评审"))
        self.assertEqual(response.cognition.suggested_execution_mode, ExecutionMode.CALENDAR_EVENT)
        self.assertEqual(response.cognition.suggested_execution_plan.steps[0].capability_name, "calendar")
        self.assertIsNotNone(response.task)
        self.assertEqual(response.task.execution_mode, ExecutionMode.CALENDAR_EVENT)

    def test_candidate_service_list_alias_matches_discover(self) -> None:
        self.container.task_engine.create(TaskCreatePayload(objective="Plan the next release"))
        discovered = self.candidates.discover(limit=10)
        listed = self.candidates.list(limit=10)
        self.assertEqual(
            [(item.kind, item.title, item.source_task_id) for item in discovered],
            [(item.kind, item.title, item.source_task_id) for item in listed],
        )

    def test_intake_uses_reflection_guardrail_to_require_confirmation(self) -> None:
        completed = self.container.task_engine.create(TaskCreatePayload(objective="Capture Alice guardrail"))
        self.container.task_engine.plan(completed.id)
        self.delivery.execute_task(completed.id)
        self.delivery.verify_task(completed.id, TaskVerificationPayload())
        self.delivery.reflect_task(
            completed.id,
            TaskReflectionPayload(
                summary="Alice tasks need review before action.",
                lessons=["guardrail:cautious:alice"],
            ),
        )

        response = self.intake.process(InputPayload(text="Draft Alice partnership update"))

        self.assertIsNotNone(response.task)
        self.assertTrue(response.cognition.courage.needs_confirmation)
        self.assertEqual(response.cognition.courage.action_mode, "confirm_then_execute")
        self.assertTrue(response.cognition.suggested_execution_plan.confirmation_required)
        self.assertTrue(response.task.execution_plan.confirmation_required)
        self.assertIn("governance:cautious", response.cognition.suggested_task_tags)
        self.assertIn("guardrail:reflection", response.cognition.suggested_task_tags)
        self.assertIn("governance:cautious", response.task.tags)
        self.assertIn("guardrail:reflection", response.task.tags)
        self.assertTrue(any("Explicit confirmation or risk review" in item for item in response.task.success_criteria))
        self.assertTrue(any("Reflection guardrail" in note for note in response.cognition.commonsense.notes))

    def test_task_verify_and_reflect(self) -> None:
        task = self.container.task_engine.create(
            TaskCreatePayload(objective="Ship MVP", success_criteria=["API responds", "Tasks persist"])
        )
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        self.assertTrue(executed.artifact_paths)
        verified = self.delivery.verify_task(
            task.id,
            TaskVerificationPayload(checks=["API responds", "Tasks persist"], verifier_notes="All checks passed."),
        )
        self.assertEqual(verified.status, TaskStatus.DONE)
        reflection = self.delivery.reflect_task(
            task.id,
            TaskReflectionPayload(summary="Execution completed cleanly.", lessons=["Keep the API surface small."]),
        )
        self.assertEqual(reflection.memory_type, MemoryType.REFLECTION)

    def test_verify_uses_expected_artifact_evidence(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Draft milestone plan"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        verified = self.delivery.verify_task(task.id, TaskVerificationPayload())
        self.assertEqual(verified.status, TaskStatus.DONE)
        self.assertTrue(any(note.startswith("Artifact exists:") for note in verified.verification_notes))

    def test_verify_uses_expected_memory_evidence(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Remember the deployment preference"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        verified = self.delivery.verify_task(task.id, TaskVerificationPayload())
        self.assertEqual(verified.status, TaskStatus.DONE)
        self.assertIn("Memory record created", verified.verification_notes)

    def test_calendar_execution_parses_explicit_chinese_time(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="在日历中增加日程：明天下午1点进行产品评审"))
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        self.assertTrue(executed.artifact_paths is not None)
        events = self.container.capability_bus.execute(
            CapabilityExecutionPayload(capability_name="calendar", action="list", parameters={})
        )
        scheduled_events = json.loads(events.output)
        self.assertTrue(scheduled_events)
        latest = scheduled_events[-1]
        self.assertIn("T13:00:00", latest["scheduled_for"])

    def test_capability_bus_executes_notes_and_gates_messaging(self) -> None:
        note_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(capability_name="notes", action="draft", parameters={"title": "Plan", "body": "Outline v1"})
        )
        message_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="messaging",
                action="prepare",
                parameters={"recipient": "alice", "message": "Status update"},
            )
        )
        self.assertEqual(note_result.status, "ok")
        self.assertTrue(message_result.requires_confirmation)
        capability_names = {item.name for item in self.container.capability_bus.list()}
        self.assertIn("local_files", capability_names)

    def test_memory_recall_scores_matching_records(self) -> None:
        self.container.memory_engine.create(
            MemoryCreatePayload(
                memory_type=MemoryType.KNOWLEDGE,
                title="Roadmap preference",
                content="Prefer weekly AI OS roadmap review.",
                tags=["roadmap", "weekly"],
            )
        )
        recall = self.container.memory_engine.recall("roadmap weekly", limit=3)
        self.assertTrue(recall.items)
        self.assertEqual(recall.items[0].title, "Roadmap preference")

    def test_goal_service_creates_and_updates_goal(self) -> None:
        goal = self.container.goal_service.create(
            GoalCreatePayload(
                title="Build AI OS goal graph",
                kind="initiative",
                summary="Turn long-term goals into structured execution paths.",
                success_metrics=["Goals are persisted", "Tasks can link to goals"],
            )
        )
        self.assertEqual(goal.title, "Build AI OS goal graph")
        updated = self.container.goal_service.update(goal.id, GoalUpdatePayload(progress=0.5, status="active"))
        self.assertEqual(updated.progress, 0.5)

    def test_goal_progress_refresh_follows_linked_task_states(self) -> None:
        goal = self.container.goal_service.create(
            GoalCreatePayload(title="Goal progress", kind="project", success_metrics=["Linked tasks complete"])
        )
        task = self.container.task_engine.create(
            TaskCreatePayload(objective="Linked task", linked_goal_ids=[goal.id])
        )
        self.container.goal_service.refresh_progress(self.container.task_engine.list())
        refreshed = self.container.goal_service.get(goal.id)
        self.assertEqual(refreshed.progress, 0.0)

        self.container.task_engine.plan(task.id)
        changes = self.container.goal_service.refresh_progress(self.container.task_engine.list())
        refreshed = self.container.goal_service.get(goal.id)
        self.assertGreaterEqual(refreshed.progress, 0.5)

        self.delivery.execute_task(task.id)
        self.delivery.verify_task(task.id, TaskVerificationPayload())
        self.container.goal_service.refresh_progress(self.container.task_engine.list())
        refreshed = self.container.goal_service.get(goal.id)
        self.assertEqual(refreshed.status.value, "done")
        self.assertEqual(refreshed.progress, 1.0)

    def test_device_service_bootstraps_local_device(self) -> None:
        devices = self.container.device_service.list()
        self.assertTrue(devices)
        self.assertEqual(devices[0].device_class, "mac_local")
        self.assertIn("calendar", devices[0].capabilities)

    def test_runtime_registry_lists_claude_code_runtime(self) -> None:
        runtimes = self.container.runtime_registry.list()
        self.assertTrue(runtimes)
        runtime = next(item for item in runtimes if item.name == "claude-code")
        self.assertEqual(runtime.runtime_type, "development")
        self.assertIn("code.execute", runtime.supported_capabilities)
        self.assertTrue(any("Discovered from runtime manifest." in note for note in runtime.notes))

    def test_capability_registry_discovers_manifests(self) -> None:
        manifests = self.container.capability_bus.list_manifests()
        self.assertTrue(manifests)
        manifest = next(item for item in manifests if item.name == "messaging")
        self.assertEqual(manifest.handler, "messaging")
        self.assertTrue(manifest.confirmation_required)

    def test_runtime_registry_discovers_manifests(self) -> None:
        manifests = self.container.runtime_registry.list_manifests()
        self.assertTrue(manifests)
        manifest = next(item for item in manifests if item.name == "claude-code")
        self.assertEqual(manifest.adapter, "claude-code")
        self.assertIn("git.workflow", manifest.supported_capabilities)

    def test_workflow_registry_discovers_manifests(self) -> None:
        manifests = self.container.workflow_registry.list_manifests()
        self.assertTrue(manifests)
        names = {item.name for item in manifests}
        self.assertIn("intake", names)
        self.assertIn("delivery", names)

    def test_runtime_registry_contributes_policy_rules(self) -> None:
        rules = self.container.runtime_registry.contributed_policy_rules()
        self.assertTrue(any(rule.name == "claude_code_runtime_tracks_code_execution" for rule in rules))

    def test_runtime_registry_prepares_task_preview(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Refactor AI OS services"))
        self.container.task_engine.plan(task.id)
        planned = self.container.task_engine.repo.get(task.id)
        self.assertEqual(planned.runtime_name, "claude-code")
        self.assertEqual(planned.execution_plan.runtime_name, "claude-code")
        preview = self.container.runtime_registry.prepare_task("claude-code", planned)
        self.assertEqual(preview["runtime"], "claude-code")
        self.assertEqual(preview["command_preview"], "claude -p")
        self.assertIn("Objective:", preview["prompt_preview"])

    def test_runtime_registry_executes_task_bundle(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Implement AI OS runtime adapter"))
        self.container.task_engine.plan(task.id)
        planned = self.container.task_engine.repo.get(task.id)
        result = self.container.runtime_registry.execute_task("claude-code", planned)
        self.assertEqual(result["runtime"], "claude-code")
        self.assertIn("Runtime Execution: claude-code", result["artifact_content"])
        self.assertIn("Command Preview: claude -p", result["artifact_content"])
        self.assertIn(result["execution_status"], {"completed", "failed", "not_installed"})

    def test_runtime_registry_builds_invocation(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Implement AI OS runtime adapter"))
        self.container.task_engine.plan(task.id)
        planned = self.container.task_engine.repo.get(task.id)
        invocation = self.container.runtime_registry.build_invocation("claude-code", planned)
        self.assertEqual(invocation.runtime, "claude-code")
        self.assertEqual(invocation.launch_command, "claude")
        self.assertEqual(invocation.launch_args, ["-p"])
        self.assertEqual(invocation.invocation_mode, "print_mode")
        self.assertEqual(invocation.environment_hints["AI_OS_TASK_ID"], planned.id)

    def test_claude_runtime_uses_injected_runner_for_live_execution(self) -> None:
        runtime = ClaudeCodeRuntime(
            workspace_root=Path(self.tempdir.name),
            app_root=Path("/Users/liuxiaofeng/AI OS"),
            command_runner=lambda invocation: {
                "execution_status": "completed",
                "exit_code": 0,
                "stdout": "live output",
                "stderr": "",
                "executed_command": "claude -p",
                "live_execution": True,
            },
            command_exists=lambda _: "/usr/local/bin/claude",
        )
        task = self.container.task_engine.create(TaskCreatePayload(objective="Implement AI OS runtime adapter"))
        self.container.task_engine.plan(task.id)
        planned = self.container.task_engine.repo.get(task.id)
        result = runtime.execute_task(planned)
        self.assertEqual(result["execution_status"], "completed")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "live output")
        self.assertTrue(result["live_execution"])

    def test_task_create_persists_explicit_runtime_name(self) -> None:
        task = self.container.task_engine.create(
            TaskCreatePayload(
                objective="Draft architecture note",
                runtime_name="claude-code",
            )
        )
        self.assertEqual(task.runtime_name, "claude-code")
        self.assertEqual(task.execution_plan.runtime_name, "claude-code")

    def test_delivery_prepares_runtime_for_code_task_artifact(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Implement API refactor for AI OS runtime"))
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        self.assertTrue(any(note.startswith("Runtime prepared: claude-code") for note in executed.verification_notes))
        self.assertTrue(any(note.startswith("Runtime executed: claude-code") for note in executed.verification_notes))
        run = self.container.execution_run_service.latest_for_task(task.id)
        self.assertEqual(run.metadata["runtime_name"], "claude-code")
        self.assertIn("runtime_invocation", run.metadata)
        self.assertEqual(run.metadata["artifact_kind"], "file_artifact")
        self.assertIn("runtime_execution_status", run.metadata)
        self.assertIn("runtime_live_execution", run.metadata)
        relations = self.container.relation_service.list_for_entity("execution_run", run.id)
        self.assertTrue(any(relation.relation_type == "prepared_runtime" and relation.target_id == "claude-code" for relation in relations))
        self.assertTrue(any(relation.relation_type == "executed_runtime" and relation.target_id == "claude-code" for relation in relations))
        artifact = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="local_files",
                action="read_text",
                parameters={"path": executed.artifact_paths[0]},
            )
        )
        self.assertIn("Runtime Execution: claude-code", artifact.output)

    def test_candidate_discovery_adds_goal_review_for_unlinked_goal(self) -> None:
        goal = self.container.goal_service.create(
            GoalCreatePayload(title="Ship AI OS v0.2", kind="project", success_metrics=["Persona runtime exists"])
        )
        candidates = self.candidates.discover(limit=20)
        review = next(candidate for candidate in candidates if candidate.kind == "goal_review")
        self.assertEqual(review.metadata["goal_id"], goal.id)

    def test_intake_links_task_to_matching_goal(self) -> None:
        goal = self.container.goal_service.create(
            GoalCreatePayload(title="Roadmap Review", kind="project", success_metrics=["Review task created"])
        )
        response = self.intake.process(InputPayload(text="Prepare Roadmap Review checklist"))
        self.assertIsNotNone(response.task)
        self.assertIn(goal.id, response.task.linked_goal_ids)

    def test_goal_service_plan_goal_creates_backlog_tasks(self) -> None:
        goal = self.container.goal_service.create(
            GoalCreatePayload(title="Launch AI OS planning", kind="project", success_metrics=["Deliverable exists"])
        )
        result = self.container.goal_service.plan_goal(goal.id, self.container.task_engine)
        self.assertEqual(result.goal_id, goal.id)
        self.assertEqual(len(result.created_tasks), 3)
        self.assertTrue(all(goal.id in task.linked_goal_ids for task in result.created_tasks))

    def test_goal_service_plan_goal_adds_contextual_tasks(self) -> None:
        self.container.memory_engine.create(
            MemoryCreatePayload(
                memory_type=MemoryType.REFLECTION,
                title="Stakeholder review lesson",
                content="Schedule recurring roadmap review carefully with stakeholders.",
                tags=["roadmap", "stakeholder"],
                layer="procedural",
            )
        )
        goal = self.container.goal_service.create(
            GoalCreatePayload(
                title="Plan stakeholder roadmap review cadence",
                kind="initiative",
                summary="Schedule recurring review with partner stakeholders and draft roadmap note.",
                success_metrics=["Calendar slot exists", "Roadmap draft exists"],
            )
        )
        result = self.container.goal_service.plan_goal(goal.id, self.container.task_engine)
        objectives = {task.objective for task in result.created_tasks}
        self.assertTrue(any("Schedule working session" in item for item in objectives))
        self.assertTrue(any("Draft primary artifact" in item for item in objectives))
        self.assertTrue(any("Prepare stakeholder alignment" in item for item in objectives))
        self.assertTrue(any("Break down milestone map" in item for item in objectives))
        self.assertTrue(any("Apply recalled lessons" in item for item in objectives))

    def test_goal_service_plan_goal_is_idempotent_when_backlog_exists(self) -> None:
        goal = self.container.goal_service.create(
            GoalCreatePayload(title="Repeatable goal plan", kind="project", success_metrics=["Backlog stable"])
        )
        self.container.goal_service.plan_goal(goal.id, self.container.task_engine)
        second = self.container.goal_service.plan_goal(goal.id, self.container.task_engine)
        self.assertFalse(second.created_tasks)
        self.assertEqual(second.summary, "Goal backlog already existed.")

    def test_scheduler_tick_refreshes_goal_progress(self) -> None:
        goal = self.container.goal_service.create(
            GoalCreatePayload(title="Scheduler linked goal", kind="project", success_metrics=["Task done"])
        )
        self.container.task_engine.create(
            TaskCreatePayload(objective="Scheduler lifecycle task for linked goal", linked_goal_ids=[goal.id])
        )
        self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=10))
        refreshed = self.container.goal_service.get(goal.id)
        self.assertEqual(refreshed.progress, 1.0)

    def test_reminders_capability_creates_local_entry(self) -> None:
        create_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Review roadmap",
                    "note": "From test",
                    "due_hint": "tomorrow",
                    "source_task_id": "task-123",
                    "origin": "test",
                },
            )
        )
        list_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
        )
        reminders = json.loads(list_result.output)
        self.assertEqual(create_result.status, "ok")
        self.assertTrue(any(item["title"] == "Review roadmap" for item in reminders))
        self.assertTrue(any(item["scheduled_for"] for item in reminders))
        self.assertEqual(reminders[0]["source_task_id"], "task-123")
        self.assertEqual(reminders[0]["origin"], "test")

    def test_reminders_capability_can_reschedule_entry(self) -> None:
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Reschedule me",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                },
            )
        )
        original = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )[0]
        new_time = utc_now() + timedelta(hours=3)
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="reschedule",
                parameters={"id": original["id"], "scheduled_for": new_time.isoformat(), "due_hint": "later today"},
            )
        )
        updated = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )[0]
        self.assertEqual(updated["due_hint"], "later today")
        self.assertEqual(datetime.fromisoformat(updated["scheduled_for"]), new_time)
        self.assertIsNone(updated["last_seen_at"])

    def test_calendar_capability_creates_and_lists_local_event(self) -> None:
        create_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="calendar",
                action="create",
                parameters={
                    "title": "AI OS planning block",
                    "note": "Focus time",
                    "due_hint": "later today",
                    "duration_minutes": 45,
                    "source_task_id": "task-456",
                },
            )
        )
        list_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(capability_name="calendar", action="list", parameters={})
        )
        events = json.loads(list_result.output)
        self.assertEqual(create_result.status, "ok")
        self.assertTrue(any(item["title"] == "AI OS planning block" for item in events))
        self.assertEqual(events[0]["duration_minutes"], 45)
        self.assertEqual(events[0]["source_task_id"], "task-456")

    def test_calendar_capability_can_reschedule_event(self) -> None:
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="calendar",
                action="create",
                parameters={"title": "Reschedule calendar item", "scheduled_for": (utc_now() + timedelta(hours=1)).isoformat()},
            )
        )
        original = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="calendar", action="list", parameters={})
            ).output
        )[0]
        new_time = utc_now() + timedelta(days=1)
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="calendar",
                action="reschedule",
                parameters={"id": original["id"], "scheduled_for": new_time.isoformat()},
            )
        )
        updated = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="calendar", action="list", parameters={})
            ).output
        )[0]
        self.assertEqual(datetime.fromisoformat(updated["scheduled_for"]), new_time)

    def test_candidate_discovery_includes_due_calendar_event(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Schedule roadmap session source"))
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="calendar",
                action="create",
                parameters={
                    "title": "Roadmap session",
                    "note": "Resume planning from calendar",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                    "source_task_id": task.id,
                    "origin": "test",
                },
            )
        )
        candidates = self.candidates.discover(limit=20)
        candidate = next(candidate for candidate in candidates if candidate.kind == "calendar_due")
        self.assertEqual(candidate.reason_code, "due_calendar_event")
        self.assertEqual(candidate.trigger_source, "calendar_schedule")
        self.assertEqual(candidate.metadata["origin"], "test")

    def test_accept_due_calendar_event_resumes_task_and_clears_event(self) -> None:
        source_task = self.container.task_engine.create(TaskCreatePayload(objective="Calendar-linked review"))
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="calendar",
                action="create",
                parameters={
                    "title": "Calendar-linked review",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                    "source_task_id": source_task.id,
                    "origin": "calendar_test",
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "calendar_due")
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                source_task_id=candidate.source_task_id,
                metadata=candidate.metadata,
            )
        )
        remaining = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="calendar", action="list", parameters={})
            ).output
        )
        self.assertEqual(result.action, "resumed_existing_task")
        self.assertFalse(remaining)

    def test_defer_due_calendar_event_reschedules_it(self) -> None:
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="calendar",
                action="create",
                parameters={
                    "title": "Defer calendar event",
                    "scheduled_for": (utc_now() - timedelta(minutes=2)).isoformat(),
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "calendar_due")
        deferred_until = utc_now() + timedelta(hours=3)
        result = self.candidates.defer(
            CandidateDeferPayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                metadata=candidate.metadata,
                due_hint="later today",
                scheduled_for=deferred_until,
            )
        )
        remaining_candidates = self.candidates.discover(limit=20)
        events = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="calendar", action="list", parameters={})
            ).output
        )
        self.assertEqual(result.action, "rescheduled_calendar_event")
        self.assertFalse(any(item.kind == "calendar_due" for item in remaining_candidates))
        self.assertEqual(datetime.fromisoformat(events[0]["scheduled_for"]), deferred_until)

    def test_local_files_capability_reads_and_writes_inside_workspace(self) -> None:
        write_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="local_files",
                action="write_text",
                parameters={"path": "artifacts/note.txt", "content": "local-first"},
            )
        )
        read_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="local_files",
                action="read_text",
                parameters={"path": "artifacts/note.txt"},
            )
        )
        list_result = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="local_files",
                action="list_dir",
                parameters={"path": "artifacts"},
            )
        )
        self.assertEqual(write_result.status, "ok")
        self.assertEqual(read_result.output, "local-first")
        self.assertEqual(json.loads(list_result.output), ["note.txt"])

    def test_local_files_capability_blocks_escape(self) -> None:
        with self.assertRaises(ValueError):
            self.delivery.execute_capability(
                CapabilityExecutionPayload(
                    capability_name="local_files",
                    action="write_text",
                    parameters={"path": "../escape.txt", "content": "nope"},
                )
            )

    def test_execute_task_creates_artifact_file(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Draft milestone plan"))
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        self.assertEqual(executed.status, TaskStatus.EXECUTING)
        self.assertEqual(len(executed.artifact_paths), 1)
        artifact_read = self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="local_files",
                action="read_text",
                parameters={"path": executed.artifact_paths[0]},
            )
        )
        self.assertIn("Task Plan: Draft milestone plan", artifact_read.output)
        relations = self.container.relation_service.list_for_entity("task", task.id)
        runs = self.container.execution_run_service.list_for_task(task.id)
        self.assertTrue(any(relation.relation_type == "produced_artifact" for relation in relations))
        self.assertEqual(len(runs), 1)
        run_relations = self.container.relation_service.list_for_entity("execution_run", runs[0].id)
        self.assertTrue(any(relation.relation_type == "produced_artifact" for relation in run_relations))

    def test_execute_task_can_capture_memory(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Remember the user prefers local-first systems"))
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        records = self.container.memory_engine.list()
        self.assertEqual(executed.status, TaskStatus.EXECUTING)
        self.assertEqual(executed.execution_mode, ExecutionMode.MEMORY_CAPTURE)
        self.assertTrue(any(record.title == task.objective for record in records))
        relations = self.container.relation_service.list_for_entity("task", task.id)
        self.assertTrue(any(relation.relation_type == "captured_into_memory" for relation in relations))
        runs = self.container.execution_run_service.list_for_task(task.id)
        run_relations = self.container.relation_service.list_for_entity("execution_run", runs[0].id)
        self.assertTrue(any(relation.relation_type == "captured_into_memory" for relation in run_relations))

    def test_execute_task_blocks_message_work_pending_confirmation(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about the current AI OS status"))
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        self.assertEqual(executed.status, TaskStatus.BLOCKED)
        self.assertEqual(executed.execution_mode, ExecutionMode.MESSAGE_DRAFT)
        self.assertEqual(executed.blocker_reason, "Awaiting user confirmation to send drafted message.")

    def test_execute_task_can_schedule_reminder(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Remind me to review the roadmap"))
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        verified = self.delivery.verify_task(task.id, TaskVerificationPayload())
        self.assertEqual(executed.execution_mode, ExecutionMode.REMINDER)
        self.assertEqual(verified.status, TaskStatus.DONE)
        self.assertIn("Reminder scheduled", verified.verification_notes)
        relations = self.container.relation_service.list_for_entity("task", task.id)
        self.assertTrue(any(relation.relation_type == "scheduled_reminder" for relation in relations))
        runs = self.container.execution_run_service.list_for_task(task.id)
        self.assertEqual(runs[0].status, TaskStatus.DONE.value)
        run_relations = self.container.relation_service.list_for_entity("execution_run", runs[0].id)
        self.assertTrue(any(relation.relation_type == "scheduled_reminder" for relation in run_relations))

    def test_execute_task_can_schedule_calendar_event(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Schedule time block for roadmap review"))
        self.container.task_engine.plan(task.id)
        executed = self.delivery.execute_task(task.id)
        verified = self.delivery.verify_task(task.id, TaskVerificationPayload())
        self.assertEqual(executed.execution_mode, ExecutionMode.CALENDAR_EVENT)
        self.assertEqual(verified.status, TaskStatus.DONE)
        self.assertIn("Calendar event scheduled", verified.verification_notes)
        relations = self.container.relation_service.list_for_entity("task", task.id)
        self.assertTrue(any(relation.relation_type == "scheduled_calendar_event" for relation in relations))

    def test_policy_blocks_high_risk_external_side_effect_until_confirmed(self) -> None:
        task = self.container.task_engine.create(
            TaskCreatePayload(
                objective="Schedule time block for sensitive partner negotiation",
                risk_level=RiskLevel.HIGH,
            )
        )
        self.container.task_engine.plan(task.id)
        blocked = self.delivery.execute_task(task.id)
        self.assertEqual(blocked.status, TaskStatus.BLOCKED)
        self.assertEqual(blocked.blocker_reason, "Awaiting policy confirmation before external side effect.")
        run = self.container.execution_run_service.latest_for_task(task.id)
        self.assertEqual(run.status, TaskStatus.BLOCKED.value)
        self.assertIn("policy_before_external_side_effect", run.metadata)
        self.assertFalse(
            any(
                relation.relation_type == "scheduled_calendar_event"
                for relation in self.container.relation_service.list_for_entity("task", task.id)
            )
        )

        confirmed = self.delivery.confirm_task(task.id, TaskConfirmationPayload(approved=True))
        self.assertEqual(confirmed.status, TaskStatus.PLANNED)
        self.assertIn("policy:override_confirmed", confirmed.tags)

        executed = self.delivery.execute_task(task.id)
        self.assertEqual(executed.status, TaskStatus.EXECUTING)
        relations = self.container.relation_service.list_for_entity("task", task.id)
        self.assertTrue(any(relation.relation_type == "scheduled_calendar_event" for relation in relations))

    def test_policy_engine_exposes_rules_by_hook(self) -> None:
        before_execute_rules = self.container.policy_engine.rules_for(LifecycleHook.BEFORE_EXECUTE)
        before_side_effect_rules = self.container.policy_engine.rules_for(LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT)
        self.assertTrue(any(rule.name == "track_high_risk_execution" for rule in before_execute_rules))
        self.assertTrue(any(rule.name == "claude_code_runtime_tracks_code_execution" for rule in before_execute_rules))
        self.assertTrue(any(rule.name == "gate_high_risk_or_confirmation_required_side_effect" for rule in before_side_effect_rules))

    def test_policy_engine_can_register_runtime_rule(self) -> None:
        self.container.policy_engine.register_rule(
            PolicyRule(
                name="block_custom_external_effect",
                hook=LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT,
                condition=lambda ctx: ctx.effect_type == "custom.effect",
                allowed=False,
                reason="Custom effect blocked.",
                metadata={"policy_path": "custom_block"},
            ),
            prepend=True,
        )
        task = self.container.task_engine.create(TaskCreatePayload(objective="Draft architecture note"))
        decision = self.container.policy_engine.before_external_side_effect(task, "custom.effect")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "Custom effect blocked.")
        self.assertIn("block_custom_external_effect", decision.metadata["matched_rules"])

    def test_policy_engine_describes_rules(self) -> None:
        descriptors = self.container.policy_engine.describe_rules(LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT)
        self.assertTrue(descriptors)
        self.assertTrue(any(item.name == "gate_high_risk_or_confirmation_required_side_effect" for item in descriptors))

    def test_confirm_message_task_allows_verification_to_complete(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about the current AI OS status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        confirmed = self.delivery.confirm_task(task.id, TaskConfirmationPayload(approved=True))
        self.assertEqual(confirmed.status, TaskStatus.EXECUTING)
        verified = self.delivery.verify_task(task.id, TaskVerificationPayload())
        self.assertEqual(verified.status, TaskStatus.DONE)
        self.assertIn("User confirmation pending or complete", verified.verification_notes)

    def test_reject_message_task_archives_it(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about the current AI OS status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        rejected = self.delivery.confirm_task(task.id, TaskConfirmationPayload(approved=False, note="Do not send this."))
        self.assertEqual(rejected.status, TaskStatus.ARCHIVED)
        self.assertEqual(rejected.blocker_reason, "User rejected message delivery.")

    def test_task_create_accepts_explicit_execution_mode(self) -> None:
        task = self.container.task_engine.create(
            TaskCreatePayload(objective="Store this as memory", execution_mode=ExecutionMode.FILE_ARTIFACT)
        )
        self.assertEqual(task.execution_mode, ExecutionMode.FILE_ARTIFACT)
        self.assertEqual(task.execution_plan.mode, ExecutionMode.FILE_ARTIFACT)

    def test_event_query_lists_recent_events(self) -> None:
        self.container.task_engine.create(TaskCreatePayload(objective="Create timeline test"))
        events = self.events.list_recent(limit=10)
        self.assertTrue(any(event.event_type == "task.created" for event in events))

    def test_event_query_filters_by_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Track this task"))
        self.container.task_engine.plan(task.id)
        task_events = self.events.list_for_task(task.id, limit=10)
        self.assertTrue(task_events)
        self.assertTrue(all(event.payload.get("task_id", task.id) == task.id for event in task_events))
        self.assertTrue(any(event.event_type == "task.planned" for event in task_events))

    def test_task_timeline_summarizes_event_flow(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Timeline summary"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        timeline = self.events.task_timeline(task.id, limit=10)
        self.assertTrue(timeline)
        self.assertEqual(timeline[0].phase, "planned")
        self.assertTrue(any(item.title == "Execution Started" for item in timeline))
        self.assertTrue(any(item.title == "Execution Produced Output" for item in timeline))

    def test_execution_run_timeline_summarizes_run_flow(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Run timeline summary"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        self.delivery.verify_task(task.id, TaskVerificationPayload())
        run = self.container.execution_run_service.list_for_task(task.id)[0]
        timeline = self.events.execution_run_timeline(run.id, limit=20)
        self.assertTrue(timeline)
        self.assertEqual(timeline[0].title, "Execution Run Started")
        self.assertTrue(any(item.title == "Execution Run Updated" for item in timeline))
        self.assertTrue(any(item.title == "Relation Recorded" for item in timeline))
        self.assertTrue(any(item.title == "Execution Produced Output" for item in timeline))
        self.assertEqual(timeline[-1].title, "Execution Run Completed")

    def test_task_timeline_includes_candidate_acceptance_and_resume(self) -> None:
        source_task = self.container.task_engine.create(TaskCreatePayload(objective="Resume me from reminder"))
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Resume me from reminder",
                    "note": "Resume source task",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                    "source_task_id": source_task.id,
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "reminder_due")
        self.candidates.accept(
            CandidateAcceptancePayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                source_task_id=candidate.source_task_id,
                reason_code=candidate.reason_code,
                trigger_source=candidate.trigger_source,
                metadata=candidate.metadata,
            )
        )
        timeline = self.events.task_timeline(source_task.id, limit=20)
        self.assertTrue(any(item.title == "Candidate Accepted" for item in timeline))
        self.assertTrue(any(item.title == "Reminder Resumed Task" for item in timeline))
        self.assertTrue(any("due_reminder via reminder_schedule" in item.detail for item in timeline if item.title == "Candidate Accepted"))

    def test_task_timeline_includes_candidate_defer(self) -> None:
        source_task = self.container.task_engine.create(TaskCreatePayload(objective="Defer me from reminder"))
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Defer me from reminder",
                    "note": "Delay source task",
                    "scheduled_for": (utc_now() - timedelta(minutes=2)).isoformat(),
                    "source_task_id": source_task.id,
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "reminder_due")
        self.candidates.defer(
            CandidateDeferPayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                reason_code=candidate.reason_code,
                trigger_source=candidate.trigger_source,
                metadata=candidate.metadata,
                due_hint="later today",
                scheduled_for=utc_now() + timedelta(hours=2),
            )
        )
        timeline = self.events.task_timeline(source_task.id, limit=20)
        self.assertTrue(any(item.title == "Candidate Deferred" for item in timeline))
        self.assertTrue(any("due_reminder" in item.detail for item in timeline if item.title == "Candidate Deferred"))

    def test_auto_accept_allows_policy_approved_candidate(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Auto plan me"))
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "plan")
        result = self.candidates.auto_accept(
            CandidateAutoAcceptPayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                source_task_id=candidate.source_task_id,
                reason_code=candidate.reason_code,
                trigger_source=candidate.trigger_source,
                metadata=candidate.metadata,
                auto_acceptable=candidate.auto_acceptable,
                needs_confirmation=candidate.needs_confirmation,
            )
        )
        timeline = self.events.task_timeline(task.id, limit=20)
        self.assertEqual(result.action, "planned_task")
        self.assertTrue(any(item.title == "Candidate Auto-Accepted" for item in timeline))

    def test_auto_accept_rejects_candidate_requiring_confirmation(self) -> None:
        blocked = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about status"))
        self.container.task_engine.plan(blocked.id)
        self.delivery.execute_task(blocked.id)
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "unblock")
        with self.assertRaises(ValueError):
            self.candidates.auto_accept(
                CandidateAutoAcceptPayload(
                    kind=candidate.kind,
                    title=candidate.title,
                    detail=candidate.detail,
                    source_task_id=candidate.source_task_id,
                    reason_code=candidate.reason_code,
                    trigger_source=candidate.trigger_source,
                    metadata=candidate.metadata,
                    auto_acceptable=candidate.auto_acceptable,
                    needs_confirmation=candidate.needs_confirmation,
                )
            )

    def test_batch_auto_accept_only_advances_policy_eligible_candidates(self) -> None:
        captured = self.container.task_engine.create(TaskCreatePayload(objective="Auto plan batch task"))
        blocked = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about batch status"))
        self.container.task_engine.plan(blocked.id)
        self.delivery.execute_task(blocked.id)

        result = self.candidates.auto_accept_eligible(CandidateBatchAutoAcceptPayload(limit=20))

        accepted_ids = {item.task.id for item in result.accepted}
        self.assertIn(captured.id, accepted_ids)
        self.assertNotIn(blocked.id, accepted_ids)
        self.assertTrue(any("not auto-acceptable" in item or "needs confirmation" in item for item in result.skipped))
        self.assertTrue(any(item.reason in {"not_auto_acceptable", "needs_confirmation"} for item in result.skip_details))
        updated_captured = self.container.task_engine.repo.get(captured.id)
        self.assertEqual(updated_captured.status, TaskStatus.PLANNED)

    def test_batch_auto_accept_emits_summary_event(self) -> None:
        blocked = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about summary batch status"))
        self.container.task_engine.plan(blocked.id)
        self.delivery.execute_task(blocked.id)
        self.candidates.auto_accept_eligible(CandidateBatchAutoAcceptPayload(limit=10))
        recent_events = self.events.list_recent(limit=20)
        summary = next(event for event in recent_events if event.event_type == "candidate.auto_accept_batch_completed")
        self.assertIn("skip_reason_counts", summary.payload)
        self.assertTrue(summary.payload["skip_reason_counts"])
        detail = self.events._to_timeline_item(summary).detail
        self.assertIn("skip reasons:", detail)

    def test_scheduler_tick_advances_eligible_candidates_and_reports_counts(self) -> None:
        captured = self.container.task_engine.create(TaskCreatePayload(objective="Scheduler plan task"))
        blocked = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about the current AI OS status"))
        self.container.task_engine.plan(blocked.id)
        self.delivery.execute_task(blocked.id)

        result = self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=20))

        self.assertGreaterEqual(result.discovered_count, 2)
        self.assertGreaterEqual(result.auto_accepted_count, 1)
        self.assertGreaterEqual(result.auto_started_count, 1)
        self.assertGreaterEqual(result.auto_verified_count, 1)
        self.assertGreaterEqual(result.skipped_count, 1)
        self.assertTrue(any(item.reason in {"not_auto_acceptable", "needs_confirmation"} for item in result.skip_details))
        updated_captured = self.container.task_engine.repo.get(captured.id)
        self.assertEqual(updated_captured.status, TaskStatus.DONE)

    def test_scheduler_tick_advances_task_lifecycle_beyond_candidate_acceptance(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Scheduler lifecycle task"))
        result = self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=10))
        updated = self.container.task_engine.repo.get(task.id)
        self.assertEqual(updated.status, TaskStatus.DONE)
        self.assertIn(task.id, result.auto_started_task_ids)
        self.assertIn(task.id, result.auto_verified_task_ids)

    def test_scheduler_tick_emits_completion_event(self) -> None:
        blocked = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about scheduler summary status"))
        self.container.task_engine.plan(blocked.id)
        self.delivery.execute_task(blocked.id)
        self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=10))
        recent_events = self.events.list_recent(limit=20)
        summary = next(event for event in recent_events if event.event_type == "scheduler.tick.completed")
        self.assertIn("skip_reason_counts", summary.payload)
        self.assertIsInstance(summary.payload["skip_reason_counts"], dict)

    def test_scheduler_tick_timeline_reports_skip_reason_distribution(self) -> None:
        blocked = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about timeline skip reasons"))
        self.container.task_engine.plan(blocked.id)
        self.delivery.execute_task(blocked.id)
        self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=10))
        recent_events = self.events.list_recent(limit=20)
        summary = next(event for event in recent_events if event.event_type == "scheduler.tick.completed")
        detail = self.events._to_timeline_item(summary).detail
        self.assertIn("skip reasons:", detail)

    def test_scheduler_tick_creates_followup_for_stalled_blocked_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about stalled status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        result = self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60))
        tasks = self.container.task_engine.list()

        self.assertEqual(result.blocked_followup_count, 1)
        self.assertIn(task.id, result.blocked_followup_task_ids)
        self.assertTrue(any(item.objective == f"Resolve blocker: {task.objective}" for item in tasks))

    def test_scheduler_tick_does_not_duplicate_stalled_blocked_followup(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about stalled duplicate"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.task_engine.create(
            TaskCreatePayload(
                objective=f"Resolve blocker: {task.objective}",
                success_criteria=["Blocker is clarified or removed."],
            )
        )

        result = self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60))
        tasks = self.container.task_engine.list()

        self.assertEqual(result.blocked_followup_count, 0)
        self.assertEqual(sum(1 for item in tasks if item.objective == f"Resolve blocker: {task.objective}"), 1)

    def test_scheduler_tick_escalates_repeatedly_stalled_blocked_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about repeated blocked status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        first = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        self.assertEqual(first.blocked_followup_count, 1)

        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        tasks = self.container.task_engine.list()
        updated = self.container.task_engine.repo.get(task.id)
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertIn(task.id, second.escalated_task_ids)
        self.assertTrue(any(item.objective == f"Escalate stalled task: {task.objective}" for item in tasks))
        self.assertEqual(updated.risk_level, RiskLevel.HIGH)
        self.assertEqual(escalation.policy_name, "blocked_risk_review")
        self.assertIn("create_escalation_task", escalation.actions)
        self.assertIn("promote_risk:high", escalation.actions)
        self.assertIn("confirmation_guardrail", escalation.actions)
        self.assertTrue(any(action in escalation.actions for action in ["create_urgent_reminder", "reschedule_urgent_reminder"]))
        self.assertIsNotNone(escalation.reminder_id)

    def test_scheduler_tick_creates_reminder_for_stalled_executing_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about executing stall status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        self.delivery.confirm_task(task.id, TaskConfirmationPayload(approved=True))
        executing = self.container.task_engine.repo.get(task.id)
        executing.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(executing)

        result = self.container.scheduler_service.tick(SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60))
        reminders = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )

        self.assertEqual(result.stalled_reminder_count, 1)
        self.assertIn(task.id, result.stalled_task_ids)
        self.assertTrue(any(item["source_task_id"] == task.id and item["origin"] == "scheduler_tick" for item in reminders))

    def test_scheduler_tick_escalates_repeatedly_stalled_executing_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about repeated executing status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        self.delivery.confirm_task(task.id, TaskConfirmationPayload(approved=True))
        executing = self.container.task_engine.repo.get(task.id)
        executing.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(executing)

        first = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        self.assertEqual(first.stalled_reminder_count, 1)

        executing = self.container.task_engine.repo.get(task.id)
        executing.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(executing)
        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        tasks = self.container.task_engine.list()
        reminders = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        updated = self.container.task_engine.repo.get(task.id)
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertIn(task.id, second.escalated_task_ids)
        self.assertTrue(any(item.objective == f"Escalate stalled task: {task.objective}" for item in tasks))
        self.assertEqual(updated.risk_level, RiskLevel.HIGH)
        self.assertEqual(escalation.policy_name, "executing_urgent_review")
        self.assertIn("create_escalation_task", escalation.actions)
        self.assertTrue(any(action in escalation.actions for action in ["create_urgent_reminder", "reschedule_urgent_reminder"]))
        self.assertIn("promote_risk:high", escalation.actions)
        self.assertTrue(any(item["id"] == escalation.reminder_id and item["origin"] == "scheduler_escalation" for item in reminders))

    def test_scheduler_tick_uses_cautious_policy_for_blocked_escalation(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "cautious"
        self.container.self_kernel.update(profile)
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about cautious blocked status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        reminders = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "cautious_blocked_urgent_review")
        self.assertIn("create_urgent_reminder", escalation.actions)
        self.assertTrue(any(item["id"] == escalation.reminder_id and item["origin"] == "scheduler_escalation" for item in reminders))

    def test_scheduler_tick_uses_bold_policy_for_executing_escalation(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "bold"
        self.container.self_kernel.update(profile)
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about bold executing status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        self.delivery.confirm_task(task.id, TaskConfirmationPayload(approved=True))
        executing = self.container.task_engine.repo.get(task.id)
        executing.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(executing)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        executing = self.container.task_engine.repo.get(task.id)
        executing.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(executing)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        updated = self.container.task_engine.repo.get(task.id)
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "bold_executing_review")
        self.assertIn("create_escalation_task", escalation.actions)
        self.assertIn("confirmation_guardrail", escalation.actions)
        self.assertTrue(any(action in escalation.actions for action in ["create_urgent_reminder", "reschedule_urgent_reminder"]))
        self.assertFalse(escalation.risk_promoted)
        self.assertIsNotNone(escalation.reminder_id)
        self.assertEqual(updated.risk_level, RiskLevel.LOW)

    def test_scheduler_tick_task_tag_overrides_self_governance_style(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "cautious"
        self.container.self_kernel.update(profile)
        task = self.container.task_engine.create(
            TaskCreatePayload(
                objective="Manual blocked bold-tag escalation test",
                tags=["governance:bold", "escalation:no_urgent_reminder", "escalation:no_risk_promotion"],
            )
        )
        self.container.task_engine.plan(task.id)
        blocked = self.container.task_engine.advance(
            task.id, TaskAdvancePayload(status=TaskStatus.BLOCKED, blocker_reason="Manual policy override test")
        )
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        updated = self.container.task_engine.repo.get(task.id)
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "bold_blocked_review")
        self.assertNotIn("create_urgent_reminder", escalation.actions)
        self.assertNotIn("reschedule_urgent_reminder", escalation.actions)
        self.assertFalse(escalation.risk_promoted)
        self.assertEqual(updated.risk_level, RiskLevel.LOW)

    def test_scheduler_tick_confirmation_required_task_forces_urgent_reminder(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "bold"
        self.container.self_kernel.update(profile)
        task = self.container.task_engine.create(
            TaskCreatePayload(
                objective="Message Alice about confirmation override",
                tags=["governance:bold"],
            )
        )
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        reminders = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertIn("confirmation_guardrail", escalation.actions)
        self.assertTrue(any(action in escalation.actions for action in ["create_urgent_reminder", "reschedule_urgent_reminder"]))
        self.assertTrue(any(item["id"] == escalation.reminder_id and item["origin"] == "scheduler_escalation" for item in reminders))

    def test_candidate_discovery_prioritizes_blocked_and_executing_tasks(self) -> None:
        blocked = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about status"))
        self.container.task_engine.plan(blocked.id)
        self.delivery.execute_task(blocked.id)
        executing = self.container.task_engine.create(TaskCreatePayload(objective="Draft roadmap"))
        self.container.task_engine.plan(executing.id)
        self.delivery.execute_task(executing.id)
        candidates = self.candidates.discover(limit=10)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].kind, "unblock")
        self.assertEqual(candidates[0].reason_code, "blocked_task")
        self.assertTrue(candidates[0].needs_confirmation)
        self.assertFalse(candidates[0].auto_acceptable)
        self.assertTrue(any(candidate.kind == "follow_up" for candidate in candidates))
        follow_up = next(candidate for candidate in candidates if candidate.kind == "follow_up")
        self.assertTrue(follow_up.auto_acceptable)
        self.assertFalse(follow_up.needs_confirmation)

    def test_candidate_discovery_adds_phase_alignment_after_self_change(self) -> None:
        profile = self.container.self_kernel.get()
        profile.current_phase = "build"
        self.container.self_kernel.update(profile)
        candidates = self.candidates.discover(limit=10)
        self.assertTrue(any(candidate.kind == "phase_alignment" for candidate in candidates))

    def test_candidate_discovery_includes_reminders(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Review roadmap source"))
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Review roadmap",
                    "note": "Resume this later",
                    "due_hint": "tomorrow",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                    "source_task_id": task.id,
                    "origin": "test",
                },
            )
        )
        candidates = self.candidates.discover(limit=20)
        reminder_candidate = next(candidate for candidate in candidates if candidate.kind == "reminder_due")
        self.assertEqual(reminder_candidate.metadata["due_hint"], "tomorrow")
        self.assertIn("scheduled_for", reminder_candidate.metadata)
        self.assertEqual(reminder_candidate.source_task_id, task.id)
        self.assertEqual(reminder_candidate.metadata["origin"], "test")
        self.assertEqual(reminder_candidate.reason_code, "due_reminder")
        self.assertEqual(reminder_candidate.trigger_source, "reminder_schedule")
        self.assertTrue(reminder_candidate.auto_acceptable)
        self.assertFalse(reminder_candidate.needs_confirmation)

    def test_candidate_discovery_assigns_phase_policy(self) -> None:
        profile = self.container.self_kernel.get()
        profile.current_phase = "build"
        self.container.self_kernel.update(profile)
        candidate = next(candidate for candidate in self.candidates.discover(limit=10) if candidate.kind == "phase_alignment")
        self.assertEqual(candidate.reason_code, "phase_change")
        self.assertFalse(candidate.auto_acceptable)
        self.assertFalse(candidate.needs_confirmation)

    def test_candidate_discovery_respects_cautious_task_tags(self) -> None:
        task = self.container.task_engine.create(
            TaskCreatePayload(objective="Plan guarded work", tags=["governance:cautious", "guardrail:reflection"])
        )
        candidates = [candidate for candidate in self.candidates.discover(limit=10) if candidate.source_task_id == task.id]
        plan = next(candidate for candidate in candidates if candidate.kind == "plan")
        review = next(candidate for candidate in candidates if candidate.kind == "governance_review")
        self.assertFalse(plan.auto_acceptable)
        self.assertTrue(plan.needs_confirmation)
        self.assertGreaterEqual(plan.priority, 4)
        self.assertEqual(review.reason_code, "governance_review")
        self.assertFalse(review.auto_acceptable)

    def test_candidate_discovery_skips_future_reminders(self) -> None:
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Future review",
                    "note": "Not yet",
                    "scheduled_for": (utc_now() + timedelta(hours=2)).isoformat(),
                },
            )
        )
        candidates = self.candidates.discover(limit=20)
        self.assertFalse(any(candidate.kind == "reminder_due" for candidate in candidates))

    def test_candidate_discovery_marks_due_reminder_seen(self) -> None:
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Seen once",
                    "note": "Only surface once",
                    "scheduled_for": (utc_now() - timedelta(minutes=1)).isoformat(),
                },
            )
        )
        first_pass = self.candidates.discover(limit=20)
        second_pass = self.candidates.discover(limit=20)
        self.assertTrue(any(candidate.kind == "reminder_due" for candidate in first_pass))
        self.assertFalse(any(candidate.kind == "reminder_due" for candidate in second_pass))

    def test_candidate_discovery_respects_source_task_governance_for_due_reminder(self) -> None:
        task = self.container.task_engine.create(
            TaskCreatePayload(objective="Review guarded reminder", tags=["governance:cautious"])
        )
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Review guarded reminder",
                    "note": "Needs cautious handling",
                    "scheduled_for": (utc_now() - timedelta(minutes=1)).isoformat(),
                    "source_task_id": task.id,
                    "origin": "task_engine",
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "reminder_due")
        self.assertFalse(candidate.auto_acceptable)
        self.assertTrue(candidate.needs_confirmation)
        self.assertGreaterEqual(candidate.priority, 4)

    def test_candidate_discovery_adds_confirmation_gate_candidate(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about gate review"))
        candidates = [candidate for candidate in self.candidates.discover(limit=20) if candidate.source_task_id == task.id]
        gate = next(candidate for candidate in candidates if candidate.kind == "confirm_gate")
        self.assertEqual(gate.reason_code, "needs_confirmation_gate")
        self.assertFalse(gate.auto_acceptable)
        self.assertFalse(gate.needs_confirmation)

    def test_accept_plan_candidate_plans_existing_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Plan me"))
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind="plan",
                title=f"Plan: {task.objective}",
                detail="Captured task has not been planned yet.",
                source_task_id=task.id,
            )
        )
        self.assertEqual(result.action, "planned_task")
        self.assertEqual(result.task.status, TaskStatus.PLANNED)

    def test_accept_unblock_candidate_creates_followup_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about status"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind="unblock",
                title=f"Unblock: {task.objective}",
                detail=task.blocker_reason or "",
                source_task_id=task.id,
            )
        )
        self.assertEqual(result.action, "created_unblock_task")
        self.assertEqual(result.task.status, TaskStatus.CAPTURED)
        self.assertIn("Resolve blocker:", result.task.objective)

    def test_accept_confirmation_gate_candidate_returns_existing_task(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice about confirmation gate"))
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "confirm_gate")
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                source_task_id=candidate.source_task_id,
                reason_code=candidate.reason_code,
                trigger_source=candidate.trigger_source,
            )
        )
        self.assertEqual(result.action, "review_confirmation_gate")
        self.assertEqual(result.task.id, task.id)

    def test_accept_governance_review_candidate_creates_review_task(self) -> None:
        source = self.container.task_engine.create(
            TaskCreatePayload(objective="Guarded work item", tags=["governance:cautious", "guardrail:reflection"])
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "governance_review")
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                source_task_id=candidate.source_task_id,
                reason_code=candidate.reason_code,
                trigger_source=candidate.trigger_source,
            )
        )
        self.assertEqual(result.action, "created_governance_review_task")
        self.assertEqual(result.task.objective, f"Review governance for: {source.objective}")
        self.assertIn("governance:review", result.task.tags)

    def test_accept_phase_alignment_candidate_creates_task(self) -> None:
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind="phase_alignment",
                title="Align tasks with phase: build",
                detail="Self phase changed recently; review active tasks for alignment.",
            )
        )
        self.assertEqual(result.action, "created_task")
        self.assertEqual(result.task.objective, "Align tasks with phase: build")

    def test_accept_reminder_candidate_creates_task_and_clears_reminder(self) -> None:
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Review roadmap",
                    "note": "Resume this later",
                    "due_hint": "tomorrow",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "reminder_due")
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                metadata=candidate.metadata,
            )
        )
        remaining = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        self.assertEqual(result.action, "created_from_reminder")
        self.assertEqual(result.task.objective, "Review roadmap")
        self.assertFalse(remaining)

    def test_accept_reminder_candidate_resumes_captured_source_task(self) -> None:
        source_task = self.container.task_engine.create(TaskCreatePayload(objective="Review roadmap deeply"))
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Review roadmap deeply",
                    "note": "Resume source task",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                    "source_task_id": source_task.id,
                    "origin": "task_engine",
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "reminder_due")
        result = self.candidates.accept(
            CandidateAcceptancePayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                source_task_id=candidate.source_task_id,
                metadata=candidate.metadata,
            )
        )
        remaining = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        self.assertEqual(result.action, "resumed_existing_task")
        self.assertEqual(result.task.id, source_task.id)
        self.assertEqual(result.task.status, TaskStatus.PLANNED)
        self.assertFalse(remaining)
        relations = self.container.relation_service.list_for_entity("task", source_task.id)
        self.assertTrue(any(relation.relation_type == "resurfaced_task" for relation in relations))
        self.assertTrue(any(relation.metadata.get("reminder_origin") == "task_engine" for relation in relations))

    def test_scheduler_tick_uses_context_policy_for_resurfaced_scheduler_reminder(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "bold"
        self.container.self_kernel.update(profile)
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Escalated context task",
                    "note": "Created by prior scheduler escalation",
                    "scheduled_for": (utc_now() - timedelta(minutes=5)).isoformat(),
                    "origin": "scheduler_escalation",
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "reminder_due")
        accepted = self.candidates.accept(
            CandidateAcceptancePayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                source_task_id=candidate.source_task_id,
                reason_code=candidate.reason_code,
                trigger_source=candidate.trigger_source,
                metadata=candidate.metadata,
            )
        )
        planned = self.container.task_engine.plan(accepted.task.id)
        blocked = self.container.task_engine.advance(
            planned.id,
            TaskAdvancePayload(status=TaskStatus.BLOCKED, blocker_reason="Resurfaced task stalled again"),
        )
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(accepted.task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        reminders = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "cautious_blocked_urgent_review")
        self.assertTrue(any(action in escalation.actions for action in ["create_urgent_reminder", "reschedule_urgent_reminder"]))
        self.assertTrue(any(item["id"] == escalation.reminder_id and item["origin"] == "scheduler_escalation" for item in reminders))

    def test_scheduler_tick_uses_relationship_context_for_high_risk_contact(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "bold"
        profile.relationship_network = ["high_risk:Alice"]
        self.container.self_kernel.update(profile)
        task = self.container.task_engine.create(TaskCreatePayload(objective="Draft follow-up for Alice partnership"))
        self.container.task_engine.plan(task.id)
        blocked = self.container.task_engine.advance(
            task.id,
            TaskAdvancePayload(status=TaskStatus.BLOCKED, blocker_reason="Waiting on sensitive contact review"),
        )
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "cautious_blocked_urgent_review")
        self.assertIn("create_urgent_reminder", escalation.actions)

    def test_task_governance_tag_overrides_relationship_context(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "balanced"
        profile.relationship_network = ["high_risk:Alice"]
        self.container.self_kernel.update(profile)
        task = self.container.task_engine.create(
            TaskCreatePayload(
                objective="Draft bold override for Alice partnership",
                tags=["governance:bold", "escalation:no_urgent_reminder", "escalation:no_risk_promotion"],
            )
        )
        self.container.task_engine.plan(task.id)
        blocked = self.container.task_engine.advance(
            task.id,
            TaskAdvancePayload(status=TaskStatus.BLOCKED, blocker_reason="Manual bold override"),
        )
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "bold_blocked_review")
        self.assertNotIn("create_urgent_reminder", escalation.actions)
        self.assertFalse(escalation.risk_promoted)

    def test_scheduler_tick_uses_reflection_guardrail_for_matching_keyword(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "bold"
        self.container.self_kernel.update(profile)
        completed = self.container.task_engine.create(TaskCreatePayload(objective="Capture lesson for Alice"))
        self.container.task_engine.plan(completed.id)
        self.delivery.execute_task(completed.id)
        self.delivery.verify_task(completed.id, TaskVerificationPayload())
        self.delivery.reflect_task(
            completed.id,
            TaskReflectionPayload(
                summary="Sensitive stakeholder follow-ups need more care.",
                lessons=["guardrail:cautious:alice"],
            ),
        )
        task = self.container.task_engine.create(TaskCreatePayload(objective="Prepare Alice contract review"))
        self.container.task_engine.plan(task.id)
        blocked = self.container.task_engine.advance(
            task.id,
            TaskAdvancePayload(status=TaskStatus.BLOCKED, blocker_reason="Needs extra coordination"),
        )
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "cautious_blocked_urgent_review")
        self.assertIn("create_urgent_reminder", escalation.actions)

    def test_task_governance_tag_overrides_reflection_guardrail(self) -> None:
        profile = self.container.self_kernel.get()
        profile.risk_style = "balanced"
        self.container.self_kernel.update(profile)
        completed = self.container.task_engine.create(TaskCreatePayload(objective="Capture bold override lesson"))
        self.container.task_engine.plan(completed.id)
        self.delivery.execute_task(completed.id)
        self.delivery.verify_task(completed.id, TaskVerificationPayload())
        self.delivery.reflect_task(
            completed.id,
            TaskReflectionPayload(
                summary="Alice tasks are usually sensitive.",
                lessons=["guardrail:cautious:alice"],
            ),
        )
        task = self.container.task_engine.create(
            TaskCreatePayload(
                objective="Prepare Alice negotiation memo",
                tags=["governance:bold", "escalation:no_urgent_reminder", "escalation:no_risk_promotion"],
            )
        )
        self.container.task_engine.plan(task.id)
        blocked = self.container.task_engine.advance(
            task.id,
            TaskAdvancePayload(status=TaskStatus.BLOCKED, blocker_reason="Manual override should win"),
        )
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)
        self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        blocked = self.container.task_engine.repo.get(task.id)
        blocked.updated_at = utc_now() - timedelta(hours=3)
        self.container.task_engine.repo.update(blocked)

        second = self.container.scheduler_service.tick(
            SchedulerTickPayload(candidate_limit=20, stale_after_minutes=60, escalate_after_hits=2)
        )
        escalation = second.escalations[0]

        self.assertEqual(second.escalated_count, 1)
        self.assertEqual(escalation.policy_name, "bold_blocked_review")
        self.assertNotIn("create_urgent_reminder", escalation.actions)

    def test_defer_reminder_candidate_reschedules_it(self) -> None:
        self.delivery.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": "Review roadmap later",
                    "note": "Defer this",
                    "scheduled_for": (utc_now() - timedelta(minutes=2)).isoformat(),
                },
            )
        )
        candidate = next(candidate for candidate in self.candidates.discover(limit=20) if candidate.kind == "reminder_due")
        deferred_until = utc_now() + timedelta(hours=6)
        result = self.candidates.defer(
            CandidateDeferPayload(
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                metadata=candidate.metadata,
                due_hint="later today",
                scheduled_for=deferred_until,
            )
        )
        remaining_candidates = self.candidates.discover(limit=20)
        reminders = json.loads(
            self.delivery.execute_capability(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        self.assertEqual(result.action, "rescheduled_reminder")
        self.assertFalse(any(item.kind == "reminder_due" for item in remaining_candidates))
        self.assertEqual(datetime.fromisoformat(reminders[0]["scheduled_for"]), deferred_until)
        self.assertEqual(reminders[0]["due_hint"], "later today")

    def test_reflection_creates_task_to_memory_relation(self) -> None:
        task = self.container.task_engine.create(TaskCreatePayload(objective="Reflectable task"))
        self.container.task_engine.plan(task.id)
        self.delivery.execute_task(task.id)
        self.delivery.verify_task(task.id, TaskVerificationPayload())
        reflection = self.delivery.reflect_task(
            task.id,
            TaskReflectionPayload(summary="Done.", lessons=["Keep links explicit."]),
        )
        task_relations = self.container.relation_service.list_for_entity("task", task.id)
        memory_relations = self.container.relation_service.list_for_entity("memory", reflection.id)
        self.assertTrue(any(relation.relation_type == "produced_reflection" for relation in task_relations))
        self.assertTrue(any(relation.target_id == reflection.id for relation in task_relations))
        self.assertTrue(any(relation.source_id == task.id for relation in memory_relations))
        runs = self.container.execution_run_service.list_for_task(task.id)
        run_relations = self.container.relation_service.list_for_entity("execution_run", runs[0].id)
        self.assertTrue(any(relation.relation_type == "produced_reflection" for relation in run_relations))

    def test_plugin_registry_discovers_plugin_manifests(self) -> None:
        plugin_names = {item.name for item in self.container.plugin_registry.list_manifests()}

        self.assertIn("ai-os-core", plugin_names)
        self.assertIn("claude-code", plugin_names)

    def test_plugin_registry_resolves_runtime_capability_and_workflow_bindings(self) -> None:
        plugins = {item.name: item for item in self.container.plugin_registry.list()}
        core = plugins["ai-os-core"]
        claude = plugins["claude-code"]

        self.assertEqual(core.status, "available")
        self.assertIn("messaging", core.capabilities)
        self.assertIn("delivery", core.workflows)
        self.assertTrue(any("Discovered from plugin manifest." in note for note in core.notes))

        self.assertEqual(claude.status, "available")
        self.assertIn("claude-code", claude.runtimes)
        self.assertIn("delivery", claude.workflows)

    def test_capability_usage_summary_returns_recent_matching_tasks(self) -> None:
        first = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice with the first update"))
        second = self.container.task_engine.create(TaskCreatePayload(objective="Message Alice with another update"))
        self.container.task_engine.plan(first.id)
        planned_second = self.container.task_engine.plan(second.id)
        planned_second.updated_at = utc_now() + timedelta(seconds=1)
        self.container.task_engine.repo.update(planned_second)

        tasks = [task for task in self.container.task_engine.list() if any(step.capability_name == "messaging" for step in task.execution_plan.steps)]
        tasks.sort(key=lambda item: item.updated_at, reverse=True)

        self.assertEqual(tasks[0].id, second.id)
        self.assertEqual(tasks[1].id, first.id)

    def test_plugin_usage_matches_runtime_and_capability_tasks(self) -> None:
        coding = self.container.task_engine.create(TaskCreatePayload(objective="Implement runtime bridge"))
        reminder = self.container.task_engine.create(TaskCreatePayload(objective="Remind me about plugin audit", execution_mode=ExecutionMode.REMINDER))
        planned_coding = self.container.task_engine.plan(coding.id)
        planned_reminder = self.container.task_engine.plan(reminder.id)

        plugins = {item.name: item for item in self.container.plugin_registry.list()}
        claude = plugins["claude-code"]
        core = plugins["ai-os-core"]

        claude_matches = [
            task.id
            for task in self.container.task_engine.list()
            if (task.runtime_name in claude.runtimes if task.runtime_name else False)
            or (task.execution_plan.runtime_name in claude.runtimes if task.execution_plan.runtime_name else False)
            or any(step.capability_name in claude.capabilities for step in task.execution_plan.steps)
        ]
        core_matches = [
            task.id
            for task in self.container.task_engine.list()
            if (task.runtime_name in core.runtimes if task.runtime_name else False)
            or (task.execution_plan.runtime_name in core.runtimes if task.execution_plan.runtime_name else False)
            or any(step.capability_name in core.capabilities for step in task.execution_plan.steps)
        ]

        self.assertIn(planned_coding.id, claude_matches)
        self.assertIn(planned_reminder.id, core_matches)


if __name__ == "__main__":
    unittest.main()
