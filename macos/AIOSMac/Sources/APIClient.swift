import Foundation

struct APIClient {
    var baseURL: URL

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom(Self.decodeDate)
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .custom(Self.encodeDate)
        return encoder
    }()

    private static func makeISO8601WithFractionalSecondsFormatter() -> ISO8601DateFormatter {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }

    private static func makeISO8601StandardFormatter() -> ISO8601DateFormatter {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }

    private static func makeNaiveUTCDateFormatter() -> DateFormatter {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .iso8601)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return formatter
    }

    private static func decodeDate(from decoder: Decoder) throws -> Date {
        let container = try decoder.singleValueContainer()
        let value = try container.decode(String.self)

        if let date = makeISO8601WithFractionalSecondsFormatter().date(from: value) {
            return date
        }
        if let date = makeISO8601StandardFormatter().date(from: value) {
            return date
        }
        if let date = makeNaiveUTCDateFormatter().date(from: value) {
            return date
        }

        throw DecodingError.dataCorruptedError(
            in: container,
            debugDescription: "Unsupported date format: \(value)"
        )
    }

    private static func encodeDate(_ date: Date, to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(makeISO8601WithFractionalSecondsFormatter().string(from: date))
    }

    func fetchSelfProfile() async throws -> SelfProfile {
        try await send(path: "/self")
    }

    func healthcheck() async throws -> [String: String] {
        try await send(path: "/healthz")
    }

    func fetchTasks() async throws -> [TaskRecord] {
        try await send(path: "/tasks")
    }

    func fetchEvents(limit: Int = 40) async throws -> [EventRecord] {
        try await send(path: "/events?limit=\(limit)")
    }

    func fetchCapabilities() async throws -> [CapabilityDescriptor] {
        try await send(path: "/capabilities")
    }

    func fetchRuntimes() async throws -> [RuntimeDescriptor] {
        try await send(path: "/runtimes")
    }

    func fetchPlugins() async throws -> [PluginDescriptor] {
        try await send(path: "/plugins")
    }

    func fetchWorkflows() async throws -> [WorkflowManifest] {
        try await send(path: "/workflows")
    }

    func fetchCapabilityUsage(name: String, limit: Int = 5) async throws -> [UsageTaskSummary] {
        let encoded = name.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? name
        return try await send(path: "/capabilities/\(encoded)/usage?limit=\(limit)")
    }

    func fetchRuntimeUsage(name: String, limit: Int = 5) async throws -> [UsageTaskSummary] {
        let encoded = name.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? name
        return try await send(path: "/runtimes/\(encoded)/usage?limit=\(limit)")
    }

    func fetchPluginUsage(name: String, limit: Int = 5) async throws -> [UsageTaskSummary] {
        let encoded = name.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? name
        return try await send(path: "/plugins/\(encoded)/usage?limit=\(limit)")
    }

    func fetchMemories() async throws -> [MemoryRecord] {
        try await send(path: "/memory/facts")
    }

    func recallMemories(query: String, limit: Int = 5) async throws -> MemoryRecallResponse {
        let encoded = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        return try await send(path: "/memory/recall?query=\(encoded)&limit=\(limit)")
    }

    func fetchGoals() async throws -> [GoalRecord] {
        try await send(path: "/goals")
    }

    func createGoal(_ request: GoalCreateRequest) async throws -> GoalRecord {
        try await send(path: "/goals", method: "POST", body: request)
    }

    func updateGoal(id: String, request: GoalUpdateRequest) async throws -> GoalRecord {
        try await send(path: "/goals/\(id)", method: "POST", body: request)
    }

    func planGoal(id: String) async throws -> GoalPlanResult {
        try await send(path: "/goals/\(id)/plan", method: "POST")
    }

    func fetchDevices() async throws -> [DeviceRecord] {
        try await send(path: "/devices")
    }

    func upsertDevice(_ request: DeviceUpsertRequest) async throws -> DeviceRecord {
        try await send(path: "/devices", method: "PUT", body: request)
    }

    func fetchCandidates(limit: Int = 20) async throws -> [CandidateTask] {
        try await send(path: "/candidates?limit=\(limit)")
    }

    func evaluateIntent(_ request: InputRequest) async throws -> IntentEvaluation {
        try await send(path: "/intents/evaluate", method: "POST", body: request)
    }

    func processInbox(_ request: InputRequest) async throws -> IntakeResponse {
        try await send(path: "/inbox/process", method: "POST", body: request)
    }

    func fetchTaskTimeline(id: String, limit: Int = 40) async throws -> [TimelineItem] {
        try await send(path: "/tasks/\(id)/timeline?limit=\(limit)")
    }

    func fetchTaskRelations(id: String, limit: Int = 40) async throws -> [EntityRelation] {
        try await send(path: "/tasks/\(id)/relations?limit=\(limit)")
    }

    func fetchTaskRuns(id: String, limit: Int = 40) async throws -> [ExecutionRunRecord] {
        try await send(path: "/tasks/\(id)/runs?limit=\(limit)")
    }

    func fetchTaskRuntimePreview(id: String, runtimeName: String = "claude-code") async throws -> RuntimePreview {
        let encoded = runtimeName.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? runtimeName
        return try await send(path: "/tasks/\(id)/runtime-preview?runtime_name=\(encoded)")
    }

    func fetchTaskRuntimeInvocation(id: String, runtimeName: String = "claude-code") async throws -> RuntimeInvocation {
        let encoded = runtimeName.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? runtimeName
        return try await send(path: "/tasks/\(id)/runtime-invocation?runtime_name=\(encoded)")
    }

    func fetchRunEvents(id: String, limit: Int = 40) async throws -> [EventRecord] {
        try await send(path: "/runs/\(id)/events?limit=\(limit)")
    }

    func fetchRunTimeline(id: String, limit: Int = 40) async throws -> [TimelineItem] {
        try await send(path: "/runs/\(id)/timeline?limit=\(limit)")
    }

    func fetchMemoryRelations(id: String, limit: Int = 40) async throws -> [EntityRelation] {
        try await send(path: "/memories/\(id)/relations?limit=\(limit)")
    }

    func createTask(_ request: CreateTaskRequest) async throws -> TaskRecord {
        try await send(path: "/tasks", method: "POST", body: request)
    }

    func updateSelfProfile(_ profile: SelfProfile) async throws -> SelfProfile {
        try await send(path: "/self", method: "PUT", body: profile)
    }

    func planTask(id: String) async throws -> TaskRecord {
        try await send(path: "/tasks/\(id)/plan", method: "POST")
    }

    func startTask(id: String) async throws -> TaskRecord {
        try await send(path: "/tasks/\(id)/start", method: "POST")
    }

    func verifyTask(id: String, request: VerifyTaskRequest) async throws -> TaskRecord {
        try await send(path: "/tasks/\(id)/verify", method: "POST", body: request)
    }

    func confirmTask(id: String, request: ConfirmTaskRequest) async throws -> TaskRecord {
        try await send(path: "/tasks/\(id)/confirm", method: "POST", body: request)
    }

    func reflectTask(id: String, request: ReflectTaskRequest) async throws -> MemoryRecord {
        try await send(path: "/tasks/\(id)/reflect", method: "POST", body: request)
    }

    func executeCapability(_ request: CapabilityExecutionRequest) async throws -> CapabilityExecutionResult {
        try await send(path: "/capabilities/execute", method: "POST", body: request)
    }

    func acceptCandidate(_ request: CandidateAcceptRequest) async throws -> CandidateAcceptanceResult {
        try await send(path: "/candidates/accept", method: "POST", body: request)
    }

    func autoAcceptEligible(limit: Int) async throws -> CandidateBatchAutoAcceptResult {
        try await send(path: "/candidates/auto-accept-eligible", method: "POST", body: CandidateBatchAutoAcceptRequest(limit: limit))
    }

    func deferCandidate(_ request: CandidateDeferRequest) async throws -> CandidateDeferResult {
        try await send(path: "/candidates/defer", method: "POST", body: request)
    }

    func runSchedulerTick(_ request: SchedulerTickRequest) async throws -> SchedulerTickResult {
        try await send(path: "/scheduler/tick", method: "POST", body: request)
    }

    private func send<Response: Decodable>(path: String, method: String = "GET") async throws -> Response {
        let request = try makeRequest(path: path, method: method)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(Response.self, from: data)
    }

    private func send<Body: Encodable, Response: Decodable>(path: String, method: String, body: Body) async throws -> Response {
        let data = try encoder.encode(body)
        let request = try makeRequest(path: path, method: method, body: data)
        let (responseData, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: responseData)
        return try decoder.decode(Response.self, from: responseData)
    }

    private func makeRequest(path: String, method: String, body: Data? = nil) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw APIError.invalidURL(path)
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 15
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return request
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown server error"
            throw APIError.server(http.statusCode, message)
        }
    }
}

enum APIError: LocalizedError {
    case invalidURL(String)
    case invalidResponse
    case server(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidURL(let path):
            return "Invalid API path: \(path)"
        case .invalidResponse:
            return "The server returned an invalid response."
        case .server(let code, let message):
            return "HTTP \(code): \(message)"
        }
    }
}
