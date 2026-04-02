import Foundation

struct PersonaAnchor: Codable, Sendable {
    var identityStatement: String
    var tone: String
    var nonNegotiables: [String]
    var defaultPlanningStyle: String
    var autonomyPreference: String

    enum CodingKeys: String, CodingKey {
        case identityStatement = "identity_statement"
        case tone
        case nonNegotiables = "non_negotiables"
        case defaultPlanningStyle = "default_planning_style"
        case autonomyPreference = "autonomy_preference"
    }
}

struct SessionContext: Codable, Sendable {
    var activeFocus: [String]
    var openLoops: [String]
    var recentDecisions: [String]
    var currentCommitments: [String]
    var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case activeFocus = "active_focus"
        case openLoops = "open_loops"
        case recentDecisions = "recent_decisions"
        case currentCommitments = "current_commitments"
        case updatedAt = "updated_at"
    }
}

struct SelfProfile: Codable, Sendable {
    var longTermGoals: [String]
    var currentPhase: String
    var values: [String]
    var preferences: [String: JSONValue]
    var riskStyle: String
    var boundaries: [String]
    var relationshipNetwork: [String]
    var personaAnchor: PersonaAnchor
    var sessionContext: SessionContext
    var updatedAt: Date

    static let empty = SelfProfile(
        longTermGoals: [],
        currentPhase: "bootstrap",
        values: [],
        preferences: [:],
        riskStyle: "balanced",
        boundaries: [],
        relationshipNetwork: [],
        personaAnchor: PersonaAnchor(
            identityStatement: "A local-first personal intelligence system.",
            tone: "clear, direct, pragmatic",
            nonNegotiables: [],
            defaultPlanningStyle: "goal-first",
            autonomyPreference: "controlled_autonomy"
        ),
        sessionContext: SessionContext(
            activeFocus: [],
            openLoops: [],
            recentDecisions: [],
            currentCommitments: [],
            updatedAt: .now
        ),
        updatedAt: .now
    )

    enum CodingKeys: String, CodingKey {
        case longTermGoals = "long_term_goals"
        case currentPhase = "current_phase"
        case values
        case preferences
        case riskStyle = "risk_style"
        case boundaries
        case relationshipNetwork = "relationship_network"
        case personaAnchor = "persona_anchor"
        case sessionContext = "session_context"
        case updatedAt = "updated_at"
    }
}

struct StructuredUnderstanding: Codable, Sendable {
    var requestedOutcome: String
    var successShape: String
    var explicitConstraints: [String]
    var inferredConstraints: [String]
    var stakeholders: [String]
    var timeHorizon: String
    var continuationPreference: String

    enum CodingKeys: String, CodingKey {
        case requestedOutcome = "requested_outcome"
        case successShape = "success_shape"
        case explicitConstraints = "explicit_constraints"
        case inferredConstraints = "inferred_constraints"
        case stakeholders
        case timeHorizon = "time_horizon"
        case continuationPreference = "continuation_preference"
    }
}

struct InputRequest: Encodable, Sendable {
    var text: String
}

struct IntentEvaluation: Codable, Sendable {
    var intentType: String
    var goal: String
    var urgency: Int
    var riskLevel: String
    var needsConfirmation: Bool
    var relatedContextIDs: [String]
    var rationale: String

    enum CodingKeys: String, CodingKey {
        case intentType = "intent_type"
        case goal
        case urgency
        case riskLevel = "risk_level"
        case needsConfirmation = "needs_confirmation"
        case relatedContextIDs = "related_context_ids"
        case rationale
    }
}

struct CommonsenseAssessment: Codable, Sendable {
    var realistic: Bool
    var safetyOK: Bool
    var costNote: String
    var notes: [String]

    enum CodingKeys: String, CodingKey {
        case realistic
        case safetyOK = "safety_ok"
        case costNote = "cost_note"
        case notes
    }
}

struct InsightAssessment: Codable, Sendable {
    var isRootProblem: Bool
    var strategicPosition: String
    var betterPath: String?
    var longTermSideEffects: [String]

    enum CodingKeys: String, CodingKey {
        case isRootProblem = "is_root_problem"
        case strategicPosition = "strategic_position"
        case betterPath = "better_path"
        case longTermSideEffects = "long_term_side_effects"
    }
}

struct CourageAssessment: Codable, Sendable {
    var actionMode: String
    var shouldPushBack: Bool
    var needsConfirmation: Bool
    var rationale: String

    enum CodingKeys: String, CodingKey {
        case actionMode = "action_mode"
        case shouldPushBack = "should_push_back"
        case needsConfirmation = "needs_confirmation"
        case rationale
    }
}

struct CognitionReport: Codable, Sendable {
    var commonsense: CommonsenseAssessment
    var insight: InsightAssessment
    var courage: CourageAssessment
    var understanding: StructuredUnderstanding
    var suggestedExecutionMode: String
    var suggestedExecutionPlan: ExecutionPlan
    var suggestedTaskTags: [String]
    var suggestedSuccessCriteria: [String]
    var suggestedNextStep: String

    enum CodingKeys: String, CodingKey {
        case commonsense
        case insight
        case courage
        case understanding
        case suggestedExecutionMode = "suggested_execution_mode"
        case suggestedExecutionPlan = "suggested_execution_plan"
        case suggestedTaskTags = "suggested_task_tags"
        case suggestedSuccessCriteria = "suggested_success_criteria"
        case suggestedNextStep = "suggested_next_step"
    }
}

struct IntakeResponse: Codable, Sendable {
    var intent: IntentEvaluation
    var cognition: CognitionReport
    var task: TaskRecord?
}

struct ImplementationTaskContract: Codable, Sendable {
    struct OutputRequirement: Codable, Sendable {
        var key: String
        var label: String
        var source: String
        var required: Bool
    }

    var summary: String
    var deliverableType: String
    var executionScope: [String]
    var acceptanceCriteria: [String]
    var constraints: [String]
    var plannedSubtasks: [String]
    var expectedOutputs: [String]
    var outputRequirements: [OutputRequirement]?
    var repoInstructions: [String]
    var preferredRuntime: String?

    enum CodingKeys: String, CodingKey {
        case summary
        case deliverableType = "deliverable_type"
        case executionScope = "execution_scope"
        case acceptanceCriteria = "acceptance_criteria"
        case constraints
        case plannedSubtasks = "planned_subtasks"
        case expectedOutputs = "expected_outputs"
        case outputRequirements = "output_requirements"
        case repoInstructions = "repo_instructions"
        case preferredRuntime = "preferred_runtime"
    }
}

struct TaskRecord: Codable, Identifiable, Sendable {
    var id: String
    var objective: String
    var tags: [String]
    var successCriteria: [String]
    var owner: String
    var status: String
    var subtasks: [String]
    var deadline: Date?
    var riskLevel: String
    var executionMode: String
    var runtimeName: String?
    var executionPlan: ExecutionPlan
    var rollbackPlan: String?
    var blockerReason: String?
    var linkedGoalIDs: [String]
    var artifactPaths: [String]
    var verificationNotes: [String]
    var intelligenceTrace: [String: JSONValue]
    var implementationContract: ImplementationTaskContract?
    var createdAt: Date
    var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case objective
        case tags
        case successCriteria = "success_criteria"
        case owner
        case status
        case subtasks
        case deadline
        case riskLevel = "risk_level"
        case executionMode = "execution_mode"
        case runtimeName = "runtime_name"
        case executionPlan = "execution_plan"
        case rollbackPlan = "rollback_plan"
        case blockerReason = "blocker_reason"
        case linkedGoalIDs = "linked_goal_ids"
        case artifactPaths = "artifact_paths"
        case verificationNotes = "verification_notes"
        case intelligenceTrace = "intelligence_trace"
        case implementationContract = "implementation_contract"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct CapabilityDescriptor: Codable, Identifiable, Sendable {
    var id: String { name }
    var name: String
    var description: String
    var riskLevel: String
    var confirmationRequired: Bool
    var scopes: [String]
    var deviceAffinity: [String]
    var evidenceOutputs: [String]

    enum CodingKeys: String, CodingKey {
        case name
        case description
        case riskLevel = "risk_level"
        case confirmationRequired = "confirmation_required"
        case scopes
        case deviceAffinity = "device_affinity"
        case evidenceOutputs = "evidence_outputs"
    }
}

struct PluginDescriptor: Codable, Identifiable, Hashable, Sendable {
    var id: String { name }
    var name: String
    var description: String
    var version: String
    var status: String
    var runtimes: [String]
    var capabilities: [String]
    var workflows: [String]
    var notes: [String]
}

struct WorkflowManifest: Codable, Identifiable, Sendable {
    var id: String { name }
    var name: String
    var handler: String
    var description: String
    var entrypoint: String
    var tags: [String]
}

struct UsageTaskSummary: Codable, Identifiable, Sendable {
    var id: String
    var objective: String
    var status: String
    var runtimeName: String?
    var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case objective
        case status
        case runtimeName = "runtime_name"
        case updatedAt = "updated_at"
    }
}

struct CapabilityExecutionRequest: Encodable, Sendable {
    var capabilityName: String
    var action: String
    var parameters: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case capabilityName = "capability_name"
        case action
        case parameters
    }
}

struct CapabilityExecutionResult: Codable, Sendable {
    var capabilityName: String
    var action: String
    var status: String
    var output: String
    var requiresConfirmation: Bool

    enum CodingKeys: String, CodingKey {
        case capabilityName = "capability_name"
        case action
        case status
        case output
        case requiresConfirmation = "requires_confirmation"
    }
}

struct RuntimeDescriptor: Codable, Identifiable, Sendable {
    var id: String { name }
    var name: String
    var description: String
    var status: String
    var runtimeType: String
    var rootPath: String?
    var supportedCapabilities: [String]
    var notes: [String]

    enum CodingKeys: String, CodingKey {
        case name
        case description
        case status
        case runtimeType = "runtime_type"
        case rootPath = "root_path"
        case supportedCapabilities = "supported_capabilities"
        case notes
    }
}

struct RuntimePreview: Codable, Sendable {
    var runtime: String
    var status: String
    var workspaceRoot: String
    var runtimeRoot: String
    var commandPreview: String
    var promptPreview: String

    enum CodingKeys: String, CodingKey {
        case runtime
        case status
        case workspaceRoot = "workspace_root"
        case runtimeRoot = "runtime_root"
        case commandPreview = "command_preview"
        case promptPreview = "prompt_preview"
    }
}

struct RuntimeInvocation: Codable, Sendable {
    var runtime: String
    var status: String
    var launchCommand: String
    var launchArgs: [String]
    var workingDirectory: String
    var environmentHints: [String: String]
    var prompt: String
    var invocationMode: String
    var notes: [String]

    enum CodingKeys: String, CodingKey {
        case runtime
        case status
        case launchCommand = "launch_command"
        case launchArgs = "launch_args"
        case workingDirectory = "working_directory"
        case environmentHints = "environment_hints"
        case prompt
        case invocationMode = "invocation_mode"
        case notes
    }
}

struct ExecutionPlan: Codable, Sendable {
    var mode: String
    var runtimeName: String?
    var steps: [ExecutionStep]
    var confirmationRequired: Bool
    var expectedEvidence: [String]

    enum CodingKeys: String, CodingKey {
        case mode
        case runtimeName = "runtime_name"
        case steps
        case confirmationRequired = "confirmation_required"
        case expectedEvidence = "expected_evidence"
    }
}

struct ExecutionStep: Codable, Identifiable, Sendable {
    var id: String { "\(capabilityName)-\(action)-\(purpose)" }
    var capabilityName: String
    var action: String
    var purpose: String

    enum CodingKeys: String, CodingKey {
        case capabilityName = "capability_name"
        case action
        case purpose
    }
}

struct EventRecord: Codable, Identifiable, Sendable {
    var id: Int
    var eventType: String
    var payload: [String: JSONValue]
    var createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case eventType = "event_type"
        case payload
        case createdAt = "created_at"
    }
}

struct MemoryRecord: Codable, Identifiable, Sendable {
    var id: String
    var memoryType: String
    var layer: String
    var title: String
    var content: String
    var tags: [String]
    var source: String
    var confidence: Double
    var freshness: String
    var relatedGoalIDs: [String]
    var createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case memoryType = "memory_type"
        case layer
        case title
        case content
        case tags
        case source
        case confidence
        case freshness
        case relatedGoalIDs = "related_goal_ids"
        case createdAt = "created_at"
    }
}

struct MemoryRecallItem: Codable, Identifiable, Sendable {
    var id: String { memoryID }
    var memoryID: String
    var title: String
    var layer: String
    var score: Double
    var reason: String

    enum CodingKeys: String, CodingKey {
        case memoryID = "memory_id"
        case title
        case layer
        case score
        case reason
    }
}

struct MemoryRecallResponse: Codable, Sendable {
    var query: String
    var items: [MemoryRecallItem]
}

struct GoalRecord: Codable, Identifiable, Sendable {
    var id: String
    var title: String
    var kind: String
    var status: String
    var horizon: String
    var summary: String
    var successMetrics: [String]
    var parentGoalID: String?
    var tags: [String]
    var priority: Int
    var progress: Double
    var createdAt: Date
    var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case kind
        case status
        case horizon
        case summary
        case successMetrics = "success_metrics"
        case parentGoalID = "parent_goal_id"
        case tags
        case priority
        case progress
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct GoalCreateRequest: Encodable, Sendable {
    var title: String
    var kind: String
    var status: String
    var horizon: String
    var summary: String
    var successMetrics: [String]
    var parentGoalID: String?
    var tags: [String]
    var priority: Int
    var progress: Double

    enum CodingKeys: String, CodingKey {
        case title
        case kind
        case status
        case horizon
        case summary
        case successMetrics = "success_metrics"
        case parentGoalID = "parent_goal_id"
        case tags
        case priority
        case progress
    }
}

struct GoalUpdateRequest: Encodable, Sendable {
    var title: String?
    var status: String?
    var summary: String?
    var successMetrics: [String]?
    var tags: [String]?
    var priority: Int?
    var progress: Double?

    enum CodingKeys: String, CodingKey {
        case title
        case status
        case summary
        case successMetrics = "success_metrics"
        case tags
        case priority
        case progress
    }
}

struct GoalPlanResult: Codable, Sendable {
    var goalID: String
    var createdTasks: [TaskRecord]
    var summary: String

    enum CodingKeys: String, CodingKey {
        case goalID = "goal_id"
        case createdTasks = "created_tasks"
        case summary
    }
}

struct DeviceRecord: Codable, Identifiable, Sendable {
    var id: String
    var name: String
    var deviceClass: String
    var status: String
    var capabilities: [String]
    var lastSeenAt: Date
    var metadata: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case deviceClass = "device_class"
        case status
        case capabilities
        case lastSeenAt = "last_seen_at"
        case metadata
    }
}

struct DeviceUpsertRequest: Encodable, Sendable {
    var id: String
    var name: String
    var deviceClass: String
    var status: String
    var capabilities: [String]
    var metadata: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case deviceClass = "device_class"
        case status
        case capabilities
        case metadata
    }
}

struct ReminderRecord: Codable, Identifiable, Sendable {
    var id: String
    var title: String
    var note: String
    var dueHint: String
    var scheduledFor: Date
    var sourceTaskID: String?
    var origin: String?
    var lastSeenAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case note
        case dueHint = "due_hint"
        case scheduledFor = "scheduled_for"
        case sourceTaskID = "source_task_id"
        case origin
        case lastSeenAt = "last_seen_at"
    }
}

struct CandidateTask: Codable, Identifiable, Sendable {
    var id: String { "\(kind)-\(title)-\(reasonCode)-\(sourceTaskID ?? "none")" }
    var kind: String
    var title: String
    var detail: String
    var sourceTaskID: String?
    var reasonCode: String
    var triggerSource: String
    var metadata: [String: JSONValue]
    var priority: Int
    var autoAcceptable: Bool
    var needsConfirmation: Bool

    enum CodingKeys: String, CodingKey {
        case kind
        case title
        case detail
        case sourceTaskID = "source_task_id"
        case reasonCode = "reason_code"
        case triggerSource = "trigger_source"
        case metadata
        case priority
        case autoAcceptable = "auto_acceptable"
        case needsConfirmation = "needs_confirmation"
    }
}

struct CandidateAcceptanceResult: Codable, Sendable {
    var action: String
    var task: TaskRecord
}

struct CandidateSkipDetail: Codable, Identifiable, Sendable {
    var id: String { "\(kind)-\(title)-\(reason)" }
    var kind: String
    var title: String
    var reason: String
    var sourceTaskID: String?
    var reasonCode: String?
    var triggerSource: String?

    enum CodingKeys: String, CodingKey {
        case kind
        case title
        case reason
        case sourceTaskID = "source_task_id"
        case reasonCode = "reason_code"
        case triggerSource = "trigger_source"
    }
}

struct CandidateBatchAutoAcceptResult: Codable, Sendable {
    var accepted: [CandidateAcceptanceResult]
    var skipped: [String]
    var skipDetails: [CandidateSkipDetail]
    var errors: [String]

    enum CodingKeys: String, CodingKey {
        case accepted
        case skipped
        case skipDetails = "skip_details"
        case errors
    }
}

struct EscalationOutcome: Codable, Identifiable, Sendable {
    var id: String { "\(taskID)-\(policyName)" }
    var taskID: String
    var status: String
    var policyName: String
    var actions: [String]
    var escalationTaskID: String?
    var reminderID: String?
    var riskPromoted: Bool

    enum CodingKeys: String, CodingKey {
        case taskID = "task_id"
        case status
        case policyName = "policy_name"
        case actions
        case escalationTaskID = "escalation_task_id"
        case reminderID = "reminder_id"
        case riskPromoted = "risk_promoted"
    }
}

struct SchedulerTickResult: Codable, Sendable {
    var discoveredCount: Int
    var autoAcceptedCount: Int
    var autoStartedCount: Int
    var autoVerifiedCount: Int
    var blockedFollowupCount: Int
    var stalledReminderCount: Int
    var escalatedCount: Int
    var skippedCount: Int
    var errorCount: Int
    var accepted: [CandidateAcceptanceResult]
    var autoStartedTaskIDs: [String]
    var autoVerifiedTaskIDs: [String]
    var blockedFollowupTaskIDs: [String]
    var stalledTaskIDs: [String]
    var escalatedTaskIDs: [String]
    var escalations: [EscalationOutcome]
    var skipped: [String]
    var skipDetails: [CandidateSkipDetail]
    var errors: [String]

    enum CodingKeys: String, CodingKey {
        case discoveredCount = "discovered_count"
        case autoAcceptedCount = "auto_accepted_count"
        case autoStartedCount = "auto_started_count"
        case autoVerifiedCount = "auto_verified_count"
        case blockedFollowupCount = "blocked_followup_count"
        case stalledReminderCount = "stalled_reminder_count"
        case escalatedCount = "escalated_count"
        case skippedCount = "skipped_count"
        case errorCount = "error_count"
        case accepted
        case autoStartedTaskIDs = "auto_started_task_ids"
        case autoVerifiedTaskIDs = "auto_verified_task_ids"
        case blockedFollowupTaskIDs = "blocked_followup_task_ids"
        case stalledTaskIDs = "stalled_task_ids"
        case escalatedTaskIDs = "escalated_task_ids"
        case escalations
        case skipped
        case skipDetails = "skip_details"
        case errors
    }
}

struct CandidateDeferResult: Codable, Sendable {
    var action: String
    var metadata: [String: JSONValue]
}

struct TimelineItem: Codable, Identifiable, Sendable {
    var id: String { "\(timestamp.timeIntervalSince1970)-\(eventType)-\(title)" }
    var timestamp: Date
    var phase: String
    var title: String
    var detail: String
    var eventType: String

    enum CodingKeys: String, CodingKey {
        case timestamp
        case phase
        case title
        case detail
        case eventType = "event_type"
    }
}

struct EntityRelation: Codable, Identifiable, Sendable {
    var id: String
    var sourceType: String
    var sourceID: String
    var relationType: String
    var targetType: String
    var targetID: String
    var metadata: [String: JSONValue]
    var createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case sourceType = "source_type"
        case sourceID = "source_id"
        case relationType = "relation_type"
        case targetType = "target_type"
        case targetID = "target_id"
        case metadata
        case createdAt = "created_at"
    }
}

struct ExecutionRunRecord: Codable, Identifiable, Sendable {
    var id: String
    var taskID: String
    var status: String
    var startedAt: Date
    var completedAt: Date?
    var metadata: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case id
        case taskID = "task_id"
        case status
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case metadata
    }
}

struct CreateTaskRequest: Encodable, Sendable {
    var objective: String
    var tags: [String]
    var successCriteria: [String]
    var riskLevel: String
    var linkedGoalIDs: [String] = []
    var runtimeName: String?

    enum CodingKeys: String, CodingKey {
        case objective
        case tags
        case successCriteria = "success_criteria"
        case riskLevel = "risk_level"
        case linkedGoalIDs = "linked_goal_ids"
        case runtimeName = "runtime_name"
    }
}

struct VerifyTaskRequest: Encodable, Sendable {
    var checks: [String]
    var verifierNotes: String?

    enum CodingKeys: String, CodingKey {
        case checks
        case verifierNotes = "verifier_notes"
    }
}

struct ConfirmTaskRequest: Encodable, Sendable {
    var approved: Bool
    var note: String?
}

struct ReflectTaskRequest: Encodable, Sendable {
    var summary: String
    var lessons: [String]
}

struct CandidateAcceptRequest: Encodable, Sendable {
    var kind: String
    var title: String
    var detail: String
    var sourceTaskID: String?
    var reasonCode: String?
    var triggerSource: String?
    var metadata: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case kind
        case title
        case detail
        case sourceTaskID = "source_task_id"
        case reasonCode = "reason_code"
        case triggerSource = "trigger_source"
        case metadata
    }
}

struct CandidateBatchAutoAcceptRequest: Encodable, Sendable {
    var limit: Int
}

struct SchedulerTickRequest: Encodable, Sendable {
    var candidateLimit: Int
    var staleAfterMinutes: Int
    var escalateAfterHits: Int

    enum CodingKeys: String, CodingKey {
        case candidateLimit = "candidate_limit"
        case staleAfterMinutes = "stale_after_minutes"
        case escalateAfterHits = "escalate_after_hits"
    }
}

struct CandidateDeferRequest: Encodable, Sendable {
    var kind: String
    var title: String
    var detail: String
    var reasonCode: String?
    var triggerSource: String?
    var metadata: [String: JSONValue]
    var dueHint: String?

    enum CodingKeys: String, CodingKey {
        case kind
        case title
        case detail
        case reasonCode = "reason_code"
        case triggerSource = "trigger_source"
        case metadata
        case dueHint = "due_hint"
    }
}

enum JSONValue: Codable, Hashable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }

    var displayText: String {
        switch self {
        case .string(let value):
            return value
        case .number(let value):
            return value.formatted()
        case .bool(let value):
            return value ? "true" : "false"
        case .object(let value):
            return "\(value.count) fields"
        case .array(let value):
            return "\(value.count) items"
        case .null:
            return "null"
        }
    }

    var stringValue: String? {
        switch self {
        case .string(let value):
            return value
        case .number(let value):
            if value.rounded() == value {
                return String(Int(value))
            }
            return String(value)
        case .bool(let value):
            return value ? "true" : "false"
        case .null, .object, .array:
            return nil
        }
    }

    var stringArrayValue: [String]? {
        guard case .array(let values) = self else {
            return nil
        }
        return values.compactMap { $0.stringValue }
    }

    var objectValue: [String: JSONValue]? {
        guard case .object(let value) = self else {
            return nil
        }
        return value
    }

    var isNull: Bool {
        if case .null = self {
            return true
        }
        return false
    }

    var prettyText: String {
        switch self {
        case .string(let value):
            return value
        case .number(let value):
            if value.rounded() == value {
                return String(Int(value))
            }
            return String(value)
        case .bool(let value):
            return value ? "true" : "false"
        case .null:
            return "null"
        case .object, .array:
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            guard let data = try? encoder.encode(self),
                  let text = String(data: data, encoding: .utf8)
            else {
                return displayText
            }
            return text
        }
    }
}
