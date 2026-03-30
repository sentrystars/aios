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


class KernelServicesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.container = build_container(Path(self.tempdir.name))
        self.intake = IntakeCoordinator(
            self_kernel=self.container.self_kernel,
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
        )
        self.events = EventQueryService(self.container.event_repo)
        self.candidates = CandidateTaskService(
            self.container.self_kernel,
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
        self.assertIsNotNone(response.task)
        self.assertEqual(response.task.objective, "Draft the first AI OS milestone plan")
        self.assertEqual(response.task.execution_mode, ExecutionMode.FILE_ARTIFACT)
        self.assertEqual(response.task.execution_plan.mode, ExecutionMode.FILE_ARTIFACT)

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


if __name__ == "__main__":
    unittest.main()
