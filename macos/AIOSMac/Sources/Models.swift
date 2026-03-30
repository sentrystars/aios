import Foundation

struct SelfProfile: Codable, Sendable {
    var longTermGoals: [String]
    var currentPhase: String
    var values: [String]
    var preferences: [String: JSONValue]
    var riskStyle: String
    var boundaries: [String]
    var relationshipNetwork: [String]
    var updatedAt: Date

    static let empty = SelfProfile(
        longTermGoals: [],
        currentPhase: "bootstrap",
        values: [],
        preferences: [:],
        riskStyle: "balanced",
        boundaries: [],
        relationshipNetwork: [],
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
        case updatedAt = "updated_at"
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
    var suggestedExecutionMode: String
    var suggestedExecutionPlan: ExecutionPlan
    var suggestedTaskTags: [String]
    var suggestedSuccessCriteria: [String]
    var suggestedNextStep: String

    enum CodingKeys: String, CodingKey {
        case commonsense
        case insight
        case courage
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
    var executionPlan: ExecutionPlan
    var rollbackPlan: String?
    var blockerReason: String?
    var artifactPaths: [String]
    var verificationNotes: [String]
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
        case executionPlan = "execution_plan"
        case rollbackPlan = "rollback_plan"
        case blockerReason = "blocker_reason"
        case artifactPaths = "artifact_paths"
        case verificationNotes = "verification_notes"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct CapabilityDescriptor: Codable, Identifiable, Sendable {
    var id: String { name }
    var name: String
    var description: String
    var riskLevel: String

    enum CodingKeys: String, CodingKey {
        case name
        case description
        case riskLevel = "risk_level"
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

struct ExecutionPlan: Codable, Sendable {
    var mode: String
    var steps: [ExecutionStep]
    var confirmationRequired: Bool
    var expectedEvidence: [String]

    enum CodingKeys: String, CodingKey {
        case mode
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
    var title: String
    var content: String
    var tags: [String]
    var createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case memoryType = "memory_type"
        case title
        case content
        case tags
        case createdAt = "created_at"
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

    enum CodingKeys: String, CodingKey {
        case objective
        case tags
        case successCriteria = "success_criteria"
        case riskLevel = "risk_level"
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
}
