import Foundation
import Combine
import UserNotifications
import AppKit

@MainActor
final class AppState: ObservableObject {
    private enum BackendDefaults {
        static let legacyBaseURL = "http://127.0.0.1:8000"
        static let recommendedBaseURL = "http://127.0.0.1:8787"
        static let legacyLaunchCommand = "uvicorn main:app --reload"
        static let recommendedLaunchCommand = "uvicorn main:app --reload --port 8787"
    }

    enum NotificationUserInfoKey {
        static let route = "aios.route"
        static let taskID = "aios.task_id"
    }

    enum NotificationRoute: String {
        case dashboard
        case task
    }

    private enum DefaultsKey {
        static let backendURL = "aiosmac.backendURL"
        static let selectedDestination = "aiosmac.selectedDestination"
        static let selectedTaskID = "aiosmac.selectedTaskID"
        static let selectedTaskDetailSection = "aiosmac.selectedTaskDetailSection"
        static let appLanguage = "aiosmac.appLanguage"
        static let autoRefreshEnabled = "aiosmac.autoRefreshEnabled"
        static let refreshInterval = "aiosmac.refreshInterval"
        static let backendLaunchCommand = "aiosmac.backendLaunchCommand"
        static let backendWorkingDirectory = "aiosmac.backendWorkingDirectory"
    }

    enum AppLanguage: String, CaseIterable, Identifiable {
        case english
        case chinese

        var id: String { rawValue }

        func label(in displayLanguage: AppLanguage) -> String {
            switch (self, displayLanguage) {
            case (.english, .english):
                return "English"
            case (.english, .chinese):
                return "英文"
            case (.chinese, .english):
                return "Chinese"
            case (.chinese, .chinese):
                return "中文"
            }
        }
    }

    enum SidebarDestination: String, CaseIterable, Identifiable {
        case overview
        case inbox
        case tasks
        case memory
        case reminders
        case capabilities
        case runtimes
        case plugins
        case workflows
        case events
        case selfProfile
        case candidates

        var id: String { rawValue }
        var title: String {
            switch self {
            case .overview:
                return "Overview"
            case .inbox:
                return "Conversation"
            case .tasks:
                return "Tasks"
            case .memory:
                return "Memory"
            case .reminders:
                return "Reminders"
            case .capabilities:
                return "Capabilities"
            case .runtimes:
                return "Runtimes"
            case .plugins:
                return "Plugins"
            case .workflows:
                return "Workflows"
            case .events:
                return "Events"
            case .selfProfile:
                return "Self"
            case .candidates:
                return "Candidates"
            }
        }
    }

    enum TaskDetailSection: String, CaseIterable, Identifiable {
        case summary
        case timeline
        case relations
        case runs

        var id: String { rawValue }

        var title: String { rawValue.capitalized }
    }

    @Published var backendURLString: String {
        didSet { UserDefaults.standard.set(backendURLString, forKey: DefaultsKey.backendURL) }
    }
    @Published var appLanguage: AppLanguage {
        didSet { UserDefaults.standard.set(appLanguage.rawValue, forKey: DefaultsKey.appLanguage) }
    }
    @Published var backendLaunchCommand: String {
        didSet { UserDefaults.standard.set(backendLaunchCommand, forKey: DefaultsKey.backendLaunchCommand) }
    }
    @Published var backendWorkingDirectory: String {
        didSet { UserDefaults.standard.set(backendWorkingDirectory, forKey: DefaultsKey.backendWorkingDirectory) }
    }
    @Published var selectedDestination: SidebarDestination? {
        didSet { UserDefaults.standard.set(selectedDestination?.rawValue, forKey: DefaultsKey.selectedDestination) }
    }
    @Published var selectedTaskDetailSection: TaskDetailSection {
        didSet { UserDefaults.standard.set(selectedTaskDetailSection.rawValue, forKey: DefaultsKey.selectedTaskDetailSection) }
    }
    @Published var autoRefreshEnabled: Bool {
        didSet { UserDefaults.standard.set(autoRefreshEnabled, forKey: DefaultsKey.autoRefreshEnabled) }
    }
    @Published var refreshIntervalSeconds: Int {
        didSet { UserDefaults.standard.set(refreshIntervalSeconds, forKey: DefaultsKey.refreshInterval) }
    }
    @Published var selfProfile = SelfProfile.empty
    @Published var selfProfileDraft = SelfProfile.empty
    @Published var selfPreferencesText = "{}"
    @Published var backendStatus = BackendStatus.unknown
    @Published var backendProcessState = BackendProcessState.idle
    @Published var tasks: [TaskRecord] = []
    @Published var events: [EventRecord] = []
    @Published var memories: [MemoryRecord] = []
    @Published var latestMemoryRecall: MemoryRecallResponse?
    @Published var goals: [GoalRecord] = []
    @Published var devices: [DeviceRecord] = []
    @Published var latestGoalPlanResult: GoalPlanResult?
    @Published var reminders: [ReminderRecord] = []
    @Published var capabilities: [CapabilityDescriptor] = []
    @Published var runtimes: [RuntimeDescriptor] = []
    @Published var plugins: [PluginDescriptor] = []
    @Published var workflows: [WorkflowManifest] = []
    @Published var candidates: [CandidateTask] = []
    @Published var latestSchedulerResult: SchedulerTickResult?
    @Published var latestAutoAcceptResult: CandidateBatchAutoAcceptResult?
    @Published var selectedTaskID: String? {
        didSet {
            UserDefaults.standard.set(selectedTaskID, forKey: DefaultsKey.selectedTaskID)
        }
    }
    @Published var selectedMemoryID: String?
    @Published var selectedReminderID: String?
    @Published var selectedCapabilityName: String?
    @Published var selectedRuntimeName: String?
    @Published var selectedPluginName: String?
    @Published var selectedWorkflowName: String?
    @Published var selectedTaskTimeline: [TimelineItem] = []
    @Published var selectedTaskRelations: [EntityRelation] = []
    @Published var selectedTaskRuns: [ExecutionRunRecord] = []
    @Published var selectedMemoryRelations: [EntityRelation] = []
    @Published var selectedRun: ExecutionRunRecord?
    @Published var selectedRunTimeline: [TimelineItem] = []
    @Published var selectedRunEvents: [EventRecord] = []
    @Published var latestCapabilityExecutionResult: CapabilityExecutionResult?
    @Published var latestRuntimePreview: RuntimePreview?
    @Published var latestRuntimeInvocation: RuntimeInvocation?
    @Published var capabilityUsage: [UsageTaskSummary] = []
    @Published var runtimeUsage: [UsageTaskSummary] = []
    @Published var pluginUsage: [UsageTaskSummary] = []
    @Published var isLoading = false
    @Published var isLoadingTaskContext = false
    @Published var isLoadingMemoryContext = false
    @Published var isLoadingRunContext = false
    @Published var capabilityActionText = ""
    @Published var capabilityParametersText = "{}"
    @Published var reminderDraft = ReminderDraft()
    @Published var errorMessage: String?
    @Published var successMessage: String?
    @Published var createTaskDraft = CreateTaskDraft()
    @Published var createGoalDraft = CreateGoalDraft()
    @Published var deviceDraft = DeviceDraft()
    @Published var inboxText = ""
    @Published var lastSubmittedConversationText = ""
    @Published var latestIntentEvaluation: IntentEvaluation?
    @Published var latestIntakeResponse: IntakeResponse?
    @Published var isProcessingInbox = false
    @Published var isPresentingCreateTask = false
    @Published var verificationDraft = VerificationDraft()
    @Published var confirmationDraft = ConfirmationDraft()
    @Published var reflectionDraft = ReflectionDraft()
    @Published var isPresentingVerifySheet = false
    @Published var isPresentingConfirmSheet = false
    @Published var isPresentingReflectSheet = false
    @Published var isPresentingDeferCandidateSheet = false
    @Published var isPresentingRunInspector = false
    @Published var schedulerDraft = SchedulerDraft()
    @Published var candidateDeferDraft = CandidateDeferDraft()
    @Published var selectedCandidateForDefer: CandidateTask?
    @Published var menuBarQuickTaskTitle = ""
    private var backendProcess: Process?
    private weak var mainWindow: NSWindow?
    private let mainWindowDelegate = MainWindowDelegate()

    init() {
        let defaults = UserDefaults.standard
        let backendURL = defaults.string(forKey: DefaultsKey.backendURL) ?? BackendDefaults.recommendedBaseURL
        let appLanguageRawValue = defaults.string(forKey: DefaultsKey.appLanguage)
        let backendLaunchCommand = defaults.string(forKey: DefaultsKey.backendLaunchCommand) ?? BackendDefaults.recommendedLaunchCommand
        let backendWorkingDirectory = defaults.string(forKey: DefaultsKey.backendWorkingDirectory) ?? FileManager.default.currentDirectoryPath
        let destinationRawValue = defaults.string(forKey: DefaultsKey.selectedDestination)
        let selectedTaskID = defaults.string(forKey: DefaultsKey.selectedTaskID)
        let detailSectionRawValue = defaults.string(forKey: DefaultsKey.selectedTaskDetailSection)
        let autoRefreshPreference = defaults.object(forKey: DefaultsKey.autoRefreshEnabled) as? Bool
        let refreshInterval = defaults.integer(forKey: DefaultsKey.refreshInterval)

        self.backendURLString = backendURL
        self.appLanguage = appLanguageRawValue.flatMap(AppLanguage.init(rawValue:)) ?? .english
        self.backendLaunchCommand = backendLaunchCommand
        self.backendWorkingDirectory = backendWorkingDirectory
        self.selectedDestination = destinationRawValue.flatMap(SidebarDestination.init(rawValue:)) ?? .overview
        self.selectedTaskID = selectedTaskID
        self.selectedTaskDetailSection = detailSectionRawValue.flatMap(TaskDetailSection.init(rawValue:)) ?? .summary
        self.autoRefreshEnabled = autoRefreshPreference ?? false
        self.refreshIntervalSeconds = refreshInterval > 0 ? refreshInterval : 30
        self.mainWindowDelegate.appState = self
    }

    private var apiClient: APIClient {
        APIClient(baseURL: backendURL)
    }

    func text(_ english: String, _ chinese: String) -> String {
        appLanguage == .chinese ? chinese : english
    }

    func displayToken(_ token: String, category: DisplayCategory? = nil) -> String {
        let normalized = token.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !normalized.isEmpty else { return token }

        if appLanguage == .english {
            return normalized
                .replacingOccurrences(of: "_", with: " ")
                .split(separator: " ")
                .map { $0.prefix(1).uppercased() + $0.dropFirst() }
                .joined(separator: " ")
        }

        switch category {
        case .taskStatus:
            switch normalized {
            case "captured": return "已捕获"
            case "planned": return "已规划"
            case "executing": return "执行中"
            case "verifying": return "验证中"
            case "blocked": return "已阻塞"
            case "done": return "已完成"
            case "archived": return "已归档"
            default: break
            }
        case .riskLevel:
            switch normalized {
            case "low": return "低"
            case "medium": return "中"
            case "high": return "高"
            default: break
            }
        case .executionMode:
            switch normalized {
            case "file_artifact": return "文件产物"
            case "message_draft": return "消息草稿"
            case "reminder": return "提醒"
            case "calendar_event": return "日程事件"
            case "note": return "笔记"
            case "manual": return "手动"
            case "none": return "无"
            default: break
            }
        case .memoryType:
            switch normalized {
            case "reflection": return "反思"
            case "fact": return "事实"
            case "artifact": return "产物"
            case "note": return "笔记"
            default: break
            }
        case .candidateKind:
            switch normalized {
            case "task": return "任务"
            case "reminder": return "提醒"
            case "calendar_due": return "到期日程"
            case "follow_up": return "跟进"
            case "memory": return "记忆"
            case "idea": return "想法"
            default: break
            }
        case .relationType:
            switch normalized {
            case "references": return "引用"
            case "blocks": return "阻塞"
            case "derived_from": return "派生自"
            case "related_to": return "相关"
            case "produced": return "产出"
            default: break
            }
        case .capabilityStatus:
            switch normalized {
            case "ok": return "成功"
            case "error": return "错误"
            case "pending": return "待处理"
            default: break
            }
        case .none:
            break
        }

        return normalized
            .replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { String($0) }
            .joined(separator: " ")
    }

    enum DisplayCategory {
        case taskStatus
        case riskLevel
        case executionMode
        case memoryType
        case candidateKind
        case relationType
        case capabilityStatus
    }

    private var backendURL: URL {
        URL(string: backendURLString) ?? URL(string: BackendDefaults.recommendedBaseURL)!
    }

    var selectedTask: TaskRecord? {
        guard let selectedTaskID else { return tasks.first }
        return tasks.first(where: { $0.id == selectedTaskID }) ?? tasks.first
    }

    var selectedMemory: MemoryRecord? {
        guard let selectedMemoryID else { return memories.first }
        return memories.first(where: { $0.id == selectedMemoryID }) ?? memories.first
    }

    var selectedReminder: ReminderRecord? {
        guard let selectedReminderID else { return reminders.first }
        return reminders.first(where: { $0.id == selectedReminderID }) ?? reminders.first
    }

    var selectedCapability: CapabilityDescriptor? {
        guard let selectedCapabilityName else { return capabilities.first }
        return capabilities.first(where: { $0.name == selectedCapabilityName }) ?? capabilities.first
    }

    var selectedRuntime: RuntimeDescriptor? {
        guard let selectedRuntimeName else { return runtimes.first }
        return runtimes.first(where: { $0.name == selectedRuntimeName }) ?? runtimes.first
    }

    var selectedPlugin: PluginDescriptor? {
        guard let selectedPluginName else { return plugins.first }
        return plugins.first(where: { $0.name == selectedPluginName }) ?? plugins.first
    }

    var selectedWorkflow: WorkflowManifest? {
        guard let selectedWorkflowName else { return workflows.first }
        return workflows.first(where: { $0.name == selectedWorkflowName }) ?? workflows.first
    }

    var pluginsForSelectedCapability: [PluginDescriptor] {
        guard let capability = selectedCapability else { return [] }
        return plugins.filter { $0.capabilities.contains(capability.name) }
    }

    var pluginsForSelectedRuntime: [PluginDescriptor] {
        guard let runtime = selectedRuntime else { return [] }
        return plugins.filter { $0.runtimes.contains(runtime.name) }
    }

    var pluginsForSelectedWorkflow: [PluginDescriptor] {
        guard let workflow = selectedWorkflow else { return [] }
        return plugins.filter { $0.workflows.contains(workflow.name) }
    }

    var recentTasksForSelectedCapability: [TaskRecord] {
        guard let capability = selectedCapability else { return [] }
        return tasks
            .filter { task in
                task.executionPlan.steps.contains(where: { $0.capabilityName == capability.name })
            }
            .sorted { $0.updatedAt > $1.updatedAt }
            .prefix(5)
            .map { $0 }
    }

    var recentTasksForSelectedRuntime: [TaskRecord] {
        guard let runtime = selectedRuntime else { return [] }
        return tasks
            .filter { task in
                task.runtimeName == runtime.name || task.executionPlan.runtimeName == runtime.name
            }
            .sorted { $0.updatedAt > $1.updatedAt }
            .prefix(5)
            .map { $0 }
    }

    var recentTasksForSelectedPlugin: [TaskRecord] {
        guard let plugin = selectedPlugin else { return [] }
        return tasks
            .filter { task in
                let usesRuntime = task.runtimeName.map(plugin.runtimes.contains) ?? false
                    || task.executionPlan.runtimeName.map(plugin.runtimes.contains) ?? false
                let usesCapability = task.executionPlan.steps.contains(where: { plugin.capabilities.contains($0.capabilityName) })
                return usesRuntime || usesCapability
            }
            .sorted { $0.updatedAt > $1.updatedAt }
            .prefix(5)
            .map { $0 }
    }

    var canPlanSelectedTask: Bool {
        guard let task = selectedTask, !isLoading else { return false }
        return !["done", "executing"].contains(task.status)
    }

    var canStartSelectedTask: Bool {
        guard let task = selectedTask, !isLoading else { return false }
        return canStartTask(task)
    }

    var canVerifySelectedTask: Bool {
        guard let task = selectedTask else { return false }
        return task.status == "executing" || task.status == "verifying"
    }

    var canConfirmSelectedTask: Bool {
        guard let task = selectedTask else { return false }
        return canConfirmTask(task)
    }

    var canReflectSelectedTask: Bool {
        guard let task = selectedTask else { return false }
        return task.status == "done"
    }

    var canEvaluateInbox: Bool {
        !inboxText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isProcessingInbox
    }

    var canProcessInbox: Bool {
        canEvaluateInbox
    }

    var taskStatusCounts: [(String, Int)] {
        let counts = Dictionary(grouping: tasks, by: \.status).mapValues(\.count)
        return counts.keys.sorted().map { ($0, counts[$0] ?? 0) }
    }

    func initialLoadIfNeeded() async {
        guard tasks.isEmpty, events.isEmpty else { return }
        await reloadAll()
    }

    func startupProbe() async {
        await reloadAll()
        if shouldFallbackFromLegacyPort() {
            backendURLString = BackendDefaults.recommendedBaseURL
            if backendLaunchCommand == BackendDefaults.legacyLaunchCommand {
                backendLaunchCommand = BackendDefaults.recommendedLaunchCommand
            }
            await reloadAll()
            if errorMessage == nil {
                successMessage = "Switched AIOS backend to port 8787 to avoid a local port conflict."
            }
        }
        if selectedDestination == .candidates || !candidates.isEmpty {
            await reloadCandidates()
        }
        if selectedDestination == .memory || !memories.isEmpty {
            await reloadMemories()
        }
        if selectedDestination == .reminders || !reminders.isEmpty {
            await reloadReminders()
        }
        if selectedDestination == .capabilities || !capabilities.isEmpty {
            await reloadCapabilities()
        }
        if selectedDestination == .runtimes || !runtimes.isEmpty {
            await reloadRuntimes()
        }
        if selectedDestination == .plugins || !plugins.isEmpty {
            await reloadPlugins()
        }
        if selectedDestination == .workflows || !workflows.isEmpty {
            await reloadWorkflows()
        }
    }

    func startBackendProcess() {
        guard backendProcess == nil else { return }
        let command = backendLaunchCommand.trimmingCharacters(in: .whitespacesAndNewlines)
        let workingDirectory = backendWorkingDirectory.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else {
            errorMessage = "Backend launch command is required."
            return
        }
        guard !workingDirectory.isEmpty else {
            errorMessage = "Backend working directory is required."
            return
        }

        let process = Process()
        process.currentDirectoryURL = URL(fileURLWithPath: workingDirectory, isDirectory: true)
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-lc", command]
        process.standardOutput = Pipe()
        process.standardError = Pipe()
        process.terminationHandler = { [weak self] process in
            Task { @MainActor in
                guard let self else { return }
                self.backendProcess = nil
                self.backendProcessState = .stopped(process.terminationStatus)
            }
        }

        do {
            try process.run()
            backendProcess = process
            backendProcessState = .running
            successMessage = "Backend launch started."
        } catch {
            backendProcess = nil
            backendProcessState = .failed
            errorMessage = "Failed to start backend: \(error.localizedDescription)"
        }
    }

    func stopBackendProcess() {
        guard let process = backendProcess else { return }
        process.terminate()
        backendProcess = nil
        backendProcessState = .idle
        successMessage = "Backend stop requested."
    }

    func reloadAll() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            async let health = apiClient.healthcheck()
            async let profile = apiClient.fetchSelfProfile()
            async let loadedTasks = apiClient.fetchTasks()
            async let loadedEvents = apiClient.fetchEvents()
            async let loadedMemories = apiClient.fetchMemories()
            async let loadedGoals = apiClient.fetchGoals()
            async let loadedDevices = apiClient.fetchDevices()
            async let loadedCapabilities = apiClient.fetchCapabilities()
            async let loadedRuntimes = apiClient.fetchRuntimes()
            async let loadedPlugins = apiClient.fetchPlugins()
            async let loadedWorkflows = apiClient.fetchWorkflows()
            _ = try await health
            backendStatus = .connected
            selfProfile = try await profile
            selfProfileDraft = selfProfile
            selfPreferencesText = Self.serializePreferences(selfProfile.preferences)
            tasks = try await loadedTasks
            events = try await loadedEvents
            memories = try await loadedMemories
            goals = try await loadedGoals
            devices = try await loadedDevices
            capabilities = try await loadedCapabilities
            runtimes = try await loadedRuntimes
            plugins = try await loadedPlugins
            workflows = try await loadedWorkflows
            if selectedTaskID == nil {
                selectedTaskID = tasks.first?.id
            }
            if selectedMemoryID == nil {
                selectedMemoryID = memories.first?.id
            }
            if selectedReminderID == nil {
                selectedReminderID = reminders.first?.id
            }
            if selectedCapabilityName == nil {
                selectedCapabilityName = capabilities.first?.name
            }
            if selectedRuntimeName == nil {
                selectedRuntimeName = runtimes.first?.name
            }
            if selectedPluginName == nil {
                selectedPluginName = plugins.first?.name
            }
            if selectedWorkflowName == nil {
                selectedWorkflowName = workflows.first?.name
            }
            await loadSelectedTaskContext()
            await loadSelectedMemoryContext()
            await loadSelectedCapabilityUsage()
            await loadSelectedRuntimePreview()
            await loadSelectedRuntimeUsage()
            await loadSelectedPluginUsage()
            latestMemoryRecall = try? await apiClient.recallMemories(query: selfProfile.currentPhase, limit: 3)
            await reloadReminders()
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func selectTask(id: String?) {
        selectedTaskID = id
        Task {
            await loadSelectedTaskContext()
            await loadSelectedRuntimePreview()
        }
    }

    func selectMemory(id: String?) {
        selectedMemoryID = id
        Task { await loadSelectedMemoryContext() }
    }

    func selectReminder(id: String?) {
        selectedReminderID = id
    }

    func selectCapability(name: String?) {
        selectedCapabilityName = name
        if capabilityActionText.isEmpty || suggestedCapabilityAction(for: selectedCapability) != capabilityActionText {
            capabilityActionText = suggestedCapabilityAction(for: selectedCapability)
        }
        Task { await loadSelectedCapabilityUsage() }
    }

    func selectRuntime(name: String?) {
        selectedRuntimeName = name
        Task {
            await loadSelectedRuntimePreview()
            await loadSelectedRuntimeUsage()
        }
    }

    func selectPlugin(name: String?) {
        selectedPluginName = name
        Task { await loadSelectedPluginUsage() }
    }

    func selectWorkflow(name: String?) {
        selectedWorkflowName = name
    }

    func presentRunInspector(for run: ExecutionRunRecord) {
        selectedRun = run
        selectedRunTimeline = []
        selectedRunEvents = []
        isPresentingRunInspector = true
        Task { await loadSelectedRunContext() }
    }

    func createTask() async {
        errorMessage = nil
        successMessage = nil
        let draft = createTaskDraft.normalized
        guard !draft.objective.isEmpty else {
            errorMessage = "Task objective is required."
            return
        }
        isLoading = true
        do {
            let task = try await apiClient.createTask(
                CreateTaskRequest(
                    objective: draft.objective,
                    tags: draft.tags,
                    successCriteria: draft.successCriteria,
                    riskLevel: draft.riskLevel,
                    linkedGoalIDs: draft.linkedGoalIDs,
                    runtimeName: draft.runtimeName
                )
            )
            isPresentingCreateTask = false
            createTaskDraft = CreateTaskDraft()
            selectedDestination = .tasks
            selectedTaskID = task.id
            await reloadAll()
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func createQuickTaskFromMenuBar() async {
        let objective = menuBarQuickTaskTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !objective.isEmpty else {
            errorMessage = "Quick task objective is required."
            return
        }

        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            let task = try await apiClient.createTask(
                CreateTaskRequest(
                    objective: objective,
                    tags: ["quick_capture", "menubar"],
                    successCriteria: [],
                    riskLevel: "low",
                    linkedGoalIDs: [],
                    runtimeName: nil
                )
            )
            menuBarQuickTaskTitle = ""
            await reloadAll()
            selectedDestination = .tasks
            selectedTaskID = task.id
            successMessage = "Quick task created."
            await postNotification(
                title: "AIOS",
                body: "Quick task created.",
                route: .task,
                taskID: task.id
            )
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func presentCreateTask(
        objective: String,
        successCriteria: [String] = [],
        tags: [String] = [],
        riskLevel: String = "low",
        runtimeName: String? = nil
    ) {
        showMainWindow()
        errorMessage = nil
        successMessage = nil
        createTaskDraft.objective = objective.trimmingCharacters(in: .whitespacesAndNewlines)
        createTaskDraft.successCriteriaText = successCriteria.joined(separator: "\n")
        createTaskDraft.tagsText = tags.joined(separator: ", ")
        createTaskDraft.riskLevel = riskLevel
        createTaskDraft.linkedGoalIDs = []
        createTaskDraft.runtimeName = runtimeName
        isPresentingCreateTask = true
    }

    func createGoal() async {
        let draft = createGoalDraft.normalized
        guard !draft.title.isEmpty else {
            errorMessage = "Goal title is required."
            return
        }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.createGoal(
                GoalCreateRequest(
                    title: draft.title,
                    kind: draft.kind,
                    status: draft.status,
                    horizon: draft.horizon,
                    summary: draft.summary,
                    successMetrics: draft.successMetrics,
                    parentGoalID: draft.parentGoalID,
                    tags: draft.tags,
                    priority: draft.priority,
                    progress: draft.progress
                )
            )
            createGoalDraft = CreateGoalDraft()
            await reloadAll()
            successMessage = "Goal created."
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func refreshGoalProgress(_ goal: GoalRecord, progress: Double) async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.updateGoal(
                id: goal.id,
                request: GoalUpdateRequest(
                    title: nil,
                    status: progress >= 1.0 ? "done" : nil,
                    summary: nil,
                    successMetrics: nil,
                    tags: nil,
                    priority: nil,
                    progress: progress
                )
            )
            await reloadAll()
            successMessage = "Goal updated."
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func planGoal(_ goal: GoalRecord) async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            latestGoalPlanResult = try await apiClient.planGoal(id: goal.id)
            await reloadAll()
            if let first = latestGoalPlanResult?.createdTasks.first {
                selectedDestination = .tasks
                selectedTaskID = first.id
            }
            successMessage = latestGoalPlanResult?.summary ?? "Goal planned."
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func upsertDevice() async {
        let draft = deviceDraft.normalized
        guard !draft.id.isEmpty, !draft.name.isEmpty else {
            errorMessage = "Device id and name are required."
            return
        }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.upsertDevice(
                DeviceUpsertRequest(
                    id: draft.id,
                    name: draft.name,
                    deviceClass: draft.deviceClass,
                    status: draft.status,
                    capabilities: draft.capabilities,
                    metadata: draft.metadata
                )
            )
            deviceDraft = DeviceDraft()
            await reloadAll()
            successMessage = "Device registered."
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func reloadCandidates() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            candidates = try await apiClient.fetchCandidates()
            backendStatus = .connected
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func reloadMemories() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            memories = try await apiClient.fetchMemories()
            backendStatus = .connected
            if selectedMemoryID == nil || memories.contains(where: { $0.id == selectedMemoryID }) == false {
                selectedMemoryID = memories.first?.id
            }
            await loadSelectedMemoryContext()
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func reloadReminders() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            let result = try await apiClient.executeCapability(
                CapabilityExecutionRequest(
                    capabilityName: "reminders",
                    action: "list",
                    parameters: [:]
                )
            )
            let data = Data(result.output.utf8)
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            reminders = try decoder.decode([ReminderRecord].self, from: data)
            backendStatus = .connected
            if selectedReminderID == nil || reminders.contains(where: { $0.id == selectedReminderID }) == false {
                selectedReminderID = reminders.first?.id
            }
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func createReminder() async {
        let title = reminderDraft.title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else {
            errorMessage = "Reminder title is required."
            return
        }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.executeCapability(
                CapabilityExecutionRequest(
                    capabilityName: "reminders",
                    action: "create",
                    parameters: [
                        "title": .string(title),
                        "note": .string(reminderDraft.note.trimmingCharacters(in: .whitespacesAndNewlines)),
                        "due_hint": .string(reminderDraft.dueHint.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "tomorrow" : reminderDraft.dueHint.trimmingCharacters(in: .whitespacesAndNewlines))
                    ]
                )
            )
            reminderDraft = ReminderDraft()
            await reloadReminders()
            successMessage = "Reminder created."
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func rescheduleSelectedReminder() async {
        guard let reminder = selectedReminder else { return }
        let dueHint = reminderDraft.dueHint.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !dueHint.isEmpty else {
            errorMessage = "Due hint is required to reschedule a reminder."
            return
        }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.executeCapability(
                CapabilityExecutionRequest(
                    capabilityName: "reminders",
                    action: "reschedule",
                    parameters: [
                        "id": .string(reminder.id),
                        "due_hint": .string(dueHint)
                    ]
                )
            )
            await reloadReminders()
            successMessage = "Reminder rescheduled."
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func markSelectedReminderSeen() async {
        guard let reminder = selectedReminder else { return }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.executeCapability(
                CapabilityExecutionRequest(
                    capabilityName: "reminders",
                    action: "mark_seen",
                    parameters: [
                        "id": .string(reminder.id)
                    ]
                )
            )
            await reloadReminders()
            successMessage = "Reminder marked seen."
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func deleteSelectedReminder() async {
        guard let reminder = selectedReminder else { return }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.executeCapability(
                CapabilityExecutionRequest(
                    capabilityName: "reminders",
                    action: "delete",
                    parameters: [
                        "id": .string(reminder.id)
                    ]
                )
            )
            await reloadReminders()
            successMessage = "Reminder deleted."
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func reloadCapabilities() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            capabilities = try await apiClient.fetchCapabilities()
            backendStatus = .connected
            if selectedCapabilityName == nil || capabilities.contains(where: { $0.name == selectedCapabilityName }) == false {
                selectedCapabilityName = capabilities.first?.name
            }
            if capabilityActionText.isEmpty {
                capabilityActionText = suggestedCapabilityAction(for: selectedCapability)
            }
            await loadSelectedCapabilityUsage()
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func reloadRuntimes() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            runtimes = try await apiClient.fetchRuntimes()
            backendStatus = .connected
            if selectedRuntimeName == nil || runtimes.contains(where: { $0.name == selectedRuntimeName }) == false {
                selectedRuntimeName = runtimes.first?.name
            }
            await loadSelectedRuntimePreview()
            await loadSelectedRuntimeUsage()
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func reloadPlugins() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            plugins = try await apiClient.fetchPlugins()
            backendStatus = .connected
            if selectedPluginName == nil || plugins.contains(where: { $0.name == selectedPluginName }) == false {
                selectedPluginName = plugins.first?.name
            }
            await loadSelectedPluginUsage()
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func reloadWorkflows() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            workflows = try await apiClient.fetchWorkflows()
            backendStatus = .connected
            if selectedWorkflowName == nil || workflows.contains(where: { $0.name == selectedWorkflowName }) == false {
                selectedWorkflowName = workflows.first?.name
            }
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func executeSelectedCapability() async {
        guard let capability = selectedCapability else { return }
        let action = capabilityActionText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !action.isEmpty else {
            errorMessage = "Capability action is required."
            return
        }

        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            let parameters = try Self.parsePreferences(from: capabilityParametersText)
            latestCapabilityExecutionResult = try await apiClient.executeCapability(
                CapabilityExecutionRequest(
                    capabilityName: capability.name,
                    action: action,
                    parameters: parameters
                )
            )
            backendStatus = .connected
            successMessage = "Capability executed."
            await reloadAll()
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func loadSelectedRuntimePreview() async {
        guard let runtime = selectedRuntime, let task = selectedTask else {
            latestRuntimePreview = nil
            latestRuntimeInvocation = nil
            return
        }
        do {
            latestRuntimePreview = try await apiClient.fetchTaskRuntimePreview(id: task.id, runtimeName: runtime.name)
            latestRuntimeInvocation = try await apiClient.fetchTaskRuntimeInvocation(id: task.id, runtimeName: runtime.name)
            backendStatus = .connected
        } catch {
            latestRuntimePreview = nil
            latestRuntimeInvocation = nil
            if backendStatus != .disconnected {
                errorMessage = error.localizedDescription
            }
        }
    }

    func loadSelectedCapabilityUsage() async {
        guard let capability = selectedCapability else {
            capabilityUsage = []
            return
        }
        do {
            capabilityUsage = try await apiClient.fetchCapabilityUsage(name: capability.name)
            backendStatus = .connected
        } catch {
            capabilityUsage = []
            if backendStatus != .disconnected {
                errorMessage = error.localizedDescription
            }
        }
    }

    func loadSelectedRuntimeUsage() async {
        guard let runtime = selectedRuntime else {
            runtimeUsage = []
            return
        }
        do {
            runtimeUsage = try await apiClient.fetchRuntimeUsage(name: runtime.name)
            backendStatus = .connected
        } catch {
            runtimeUsage = []
            if backendStatus != .disconnected {
                errorMessage = error.localizedDescription
            }
        }
    }

    func loadSelectedPluginUsage() async {
        guard let plugin = selectedPlugin else {
            pluginUsage = []
            return
        }
        do {
            pluginUsage = try await apiClient.fetchPluginUsage(name: plugin.name)
            backendStatus = .connected
        } catch {
            pluginUsage = []
            if backendStatus != .disconnected {
                errorMessage = error.localizedDescription
            }
        }
    }

    func autoRefreshLoop() async {
        guard autoRefreshEnabled else { return }
        while autoRefreshEnabled {
            do {
                try await Task.sleep(for: .seconds(refreshIntervalSeconds))
            } catch {
                return
            }
            guard autoRefreshEnabled else { return }
            await reloadAll()
            if selectedDestination == .candidates {
                await reloadCandidates()
            }
        }
    }

    func saveSelfProfile() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            selfProfileDraft.preferences = try Self.parsePreferences(from: selfPreferencesText)
            selfProfile = try await apiClient.updateSelfProfile(selfProfileDraft)
            selfProfileDraft = selfProfile
            selfPreferencesText = Self.serializePreferences(selfProfile.preferences)
            events = try await apiClient.fetchEvents()
            goals = try await apiClient.fetchGoals()
            devices = try await apiClient.fetchDevices()
            latestMemoryRecall = try? await apiClient.recallMemories(query: selfProfile.currentPhase, limit: 3)
            successMessage = "Self profile updated."
            await postNotification(title: "AIOS", body: "Self profile updated.", route: .dashboard)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func evaluateInboxIntent() async {
        let text = inboxText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        isProcessingInbox = true
        errorMessage = nil
        successMessage = nil
        do {
            latestIntentEvaluation = try await apiClient.evaluateIntent(InputRequest(text: text))
            successMessage = self.text("AIOS has read the request.", "AIOS 已经读完这条需求。")
        } catch {
            errorMessage = error.localizedDescription
        }
        isProcessingInbox = false
    }

    func processInbox() async {
        let text = inboxText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        isProcessingInbox = true
        errorMessage = nil
        successMessage = nil
        do {
            lastSubmittedConversationText = text
            var response = try await apiClient.processInbox(InputRequest(text: text))
            latestIntakeResponse = response
            latestIntentEvaluation = response.intent
            if let task = response.task {
                let advancedTask = try await autoAdvanceConversationTask(task)
                response.task = advancedTask
                latestIntakeResponse = response
                inboxText = ""
                await reloadAll()
                selectTask(id: advancedTask.id)
                if advancedTask.status == "blocked" {
                    successMessage = self.text("AIOS needs a confirmation before it can continue.", "AIOS 需要你确认后才能继续。")
                } else if advancedTask.status == "done" {
                    successMessage = self.text("AIOS has completed this request.", "AIOS 已经完成这条需求。")
                } else {
                    successMessage = self.text("AIOS is still working on this request.", "AIOS 正在继续推进这条需求。")
                }
            } else {
                inboxText = ""
                await reloadAll()
                successMessage = self.text("AIOS has processed the request.", "AIOS 已经处理完这条需求。")
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isProcessingInbox = false
    }

    private func autoAdvanceConversationTask(_ task: TaskRecord) async throws -> TaskRecord {
        var current = task

        if current.status == "captured" {
            current = try await apiClient.planTask(id: current.id)
        }

        if current.status == "planned" {
            current = try await apiClient.startTask(id: current.id)
        }

        if current.status == "executing" || current.status == "verifying" {
            current = try await apiClient.verifyTask(
                id: current.id,
                request: VerifyTaskRequest(
                    checks: [],
                    verifierNotes: "Auto-verified from conversation workflow."
                )
            )
        }

        return current
    }

    func planSelectedTask() async {
        guard let task = selectedTask else { return }
        guard canPlanSelectedTask else {
            errorMessage = "Task in status '\(task.status)' cannot be planned again."
            return
        }
        await mutateTask(task.id) { client, id in
            try await client.planTask(id: id)
        }
    }

    func startSelectedTask() async {
        guard let task = selectedTask else { return }
        guard canStartTask(task) else {
            errorMessage = task.status == "done"
                ? "This task is already done and cannot be started again."
                : "Task in status '\(task.status)' cannot be started."
            return
        }
        await startTask(id: task.id)
    }

    func verifySelectedTask() async {
        guard let task = selectedTask else { return }
        let checks = verificationDraft.checksText
            .split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        let verifierNotes = verificationDraft.verifierNotes.nilIfBlank
        await mutateTask(task.id) { client, id in
            try await client.verifyTask(
                id: id,
                request: VerifyTaskRequest(checks: checks, verifierNotes: verifierNotes)
            )
        }
        if errorMessage == nil {
            isPresentingVerifySheet = false
            verificationDraft = VerificationDraft()
            successMessage = "Task verification submitted."
            await postNotification(
                title: "AIOS",
                body: "Task verification submitted.",
                route: .task,
                taskID: task.id
            )
        }
    }

    func confirmSelectedTask(approved: Bool) async {
        guard let task = selectedTask else { return }
        guard canConfirmTask(task) else {
            errorMessage = "Task in status '\(task.status)' cannot be confirmed."
            return
        }
        let note = confirmationDraft.note.nilIfBlank
        await mutateTask(task.id) { client, id in
            try await client.confirmTask(
                id: id,
                request: ConfirmTaskRequest(approved: approved, note: note)
            )
        }
        if errorMessage == nil {
            isPresentingConfirmSheet = false
            confirmationDraft = ConfirmationDraft()
            successMessage = approved ? "Task approved." : "Task rejected."
            await postNotification(
                title: "AIOS",
                body: approved ? "Task approved." : "Task rejected.",
                route: .task,
                taskID: task.id
            )
        }
    }

    func startTask(id: String?) async {
        guard let id, let task = tasks.first(where: { $0.id == id }) else { return }
        guard canStartTask(task) else {
            errorMessage = task.status == "done"
                ? "This task is already done and cannot be started again."
                : "Task in status '\(task.status)' cannot be started."
            return
        }
        await mutateTask(id) { client, taskID in
            if task.status == "captured" {
                _ = try await client.planTask(id: taskID)
            }
            return try await client.startTask(id: taskID)
        }
        if selectedRun?.taskID == id {
            selectedRun = selectedTaskRuns.first
            await loadSelectedRunContext()
        }
    }

    func reflectSelectedTask() async {
        guard let task = selectedTask else { return }
        let lessons = reflectionDraft.lessonsText
            .split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.reflectTask(
                id: task.id,
                request: ReflectTaskRequest(summary: reflectionDraft.summary, lessons: lessons)
            )
            await reloadAll()
            isPresentingReflectSheet = false
            reflectionDraft = ReflectionDraft()
            successMessage = "Reflection stored."
            await postNotification(
                title: "AIOS",
                body: "Task reflection stored.",
                route: .task,
                taskID: task.id
            )
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func acceptCandidate(_ candidate: CandidateTask) async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            let result = try await apiClient.acceptCandidate(
                CandidateAcceptRequest(
                    kind: candidate.kind,
                    title: candidate.title,
                    detail: candidate.detail,
                    sourceTaskID: candidate.sourceTaskID,
                    reasonCode: candidate.reasonCode,
                    triggerSource: candidate.triggerSource,
                    metadata: candidate.metadata
                )
            )
            await reloadAll()
            candidates = try await apiClient.fetchCandidates()
            successMessage = "Candidate accepted."
            await postNotification(
                title: "AIOS",
                body: "Candidate accepted into task queue.",
                route: .task,
                taskID: result.task.id
            )
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func autoAcceptEligibleCandidates() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            let result = try await apiClient.autoAcceptEligible(limit: schedulerDraft.candidateLimit)
            latestAutoAcceptResult = result
            await reloadAll()
            candidates = try await apiClient.fetchCandidates()
            successMessage = "Auto-accepted \(result.accepted.count) candidates."
            await postNotification(
                title: "AIOS",
                body: "Auto-accepted \(result.accepted.count) candidates.",
                route: result.accepted.first == nil ? .dashboard : .task,
                taskID: result.accepted.first?.task.id
            )
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func openDeferSheet(for candidate: CandidateTask) {
        selectedCandidateForDefer = candidate
        candidateDeferDraft = CandidateDeferDraft()
        isPresentingDeferCandidateSheet = true
    }

    func deferSelectedCandidate() async {
        guard let candidate = selectedCandidateForDefer else { return }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            _ = try await apiClient.deferCandidate(
                CandidateDeferRequest(
                    kind: candidate.kind,
                    title: candidate.title,
                    detail: candidate.detail,
                    reasonCode: candidate.reasonCode,
                    triggerSource: candidate.triggerSource,
                    metadata: candidate.metadata,
                    dueHint: candidateDeferDraft.dueHint.nilIfBlank
                )
            )
            candidates = try await apiClient.fetchCandidates()
            events = try await apiClient.fetchEvents()
            isPresentingDeferCandidateSheet = false
            selectedCandidateForDefer = nil
            successMessage = "Candidate deferred."
            await postNotification(title: "AIOS", body: "Candidate deferred.", route: .dashboard)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func runSchedulerTick() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            latestSchedulerResult = try await apiClient.runSchedulerTick(
                SchedulerTickRequest(
                    candidateLimit: schedulerDraft.candidateLimit,
                    staleAfterMinutes: schedulerDraft.staleAfterMinutes,
                    escalateAfterHits: schedulerDraft.escalateAfterHits
                )
            )
            await reloadAll()
            candidates = try await apiClient.fetchCandidates()
            successMessage = "Scheduler tick completed."
            await postNotification(
                title: "AIOS",
                body: "Scheduler tick completed.",
                route: latestSchedulerResult?.accepted.first == nil ? .dashboard : .task,
                taskID: latestSchedulerResult?.accepted.first?.task.id
            )
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    private func mutateTask(_ id: String, operation: @escaping (APIClient, String) async throws -> TaskRecord) async {
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            let updated = try await operation(apiClient, id)
            backendStatus = .connected
            if let index = tasks.firstIndex(where: { $0.id == updated.id }) {
                tasks[index] = updated
            }
            selectedTaskID = updated.id
            events = try await apiClient.fetchEvents()
            await loadSelectedTaskContext()
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    private func canStartTask(_ task: TaskRecord) -> Bool {
        ["captured", "planned"].contains(task.status)
    }

    private func canConfirmTask(_ task: TaskRecord) -> Bool {
        guard task.status == "blocked" else { return false }
        return task.executionPlan.mode == "message_draft"
            || task.blockerReason == "Awaiting policy confirmation before external side effect."
    }

    func loadSelectedTaskContext() async {
        guard let task = selectedTask else {
            selectedTaskTimeline = []
            selectedTaskRelations = []
            selectedTaskRuns = []
            return
        }

        isLoadingTaskContext = true
        do {
            async let timeline = apiClient.fetchTaskTimeline(id: task.id)
            async let relations = apiClient.fetchTaskRelations(id: task.id)
            async let runs = apiClient.fetchTaskRuns(id: task.id)
            selectedTaskTimeline = try await timeline
            selectedTaskRelations = try await relations
            selectedTaskRuns = try await runs
            backendStatus = .connected
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoadingTaskContext = false
    }

    func loadSelectedMemoryContext() async {
        guard let memory = selectedMemory else {
            selectedMemoryRelations = []
            return
        }

        isLoadingMemoryContext = true
        do {
            selectedMemoryRelations = try await apiClient.fetchMemoryRelations(id: memory.id)
            backendStatus = .connected
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoadingMemoryContext = false
    }

    func loadSelectedRunContext() async {
        guard let run = selectedRun else {
            selectedRunTimeline = []
            selectedRunEvents = []
            return
        }

        isLoadingRunContext = true
        do {
            async let timeline = apiClient.fetchRunTimeline(id: run.id)
            async let events = apiClient.fetchRunEvents(id: run.id)
            selectedRunTimeline = try await timeline
            selectedRunEvents = try await events
            backendStatus = .connected
        } catch {
            backendStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoadingRunContext = false
    }

    func requestNotificationPermissionIfNeeded() async {
        let center = UNUserNotificationCenter.current()
        do {
            let settings = await center.notificationSettings()
            if settings.authorizationStatus == .notDetermined {
                _ = try await center.requestAuthorization(options: [.alert, .sound])
            }
        } catch {
            return
        }
    }

    func registerMainWindow(_ window: NSWindow) {
        guard mainWindow !== window else { return }
        mainWindow = window
        window.isReleasedWhenClosed = false
        window.setFrameAutosaveName("AIOSMac.MainWindow")
        window.delegate = mainWindowDelegate
    }

    func showMainWindow() {
        guard let mainWindow else { return }
        NSApplication.shared.activate(ignoringOtherApps: true)
        if mainWindow.isMiniaturized {
            mainWindow.deminiaturize(nil)
        }
        mainWindow.makeKeyAndOrderFront(nil)
    }

    func openDashboard() {
        showMainWindow()
        selectedDestination = .overview
    }

    func openTask(id: String?) async {
        showMainWindow()
        selectedDestination = .tasks

        guard let id, !id.isEmpty else { return }

        if !tasks.contains(where: { $0.id == id }) {
            await reloadAll()
        }

        guard tasks.contains(where: { $0.id == id }) else {
            errorMessage = "Task \(id) was not found."
            return
        }

        selectedTaskID = id
        await loadSelectedTaskContext()
    }

    func openMemory(id: String?) async {
        showMainWindow()
        selectedDestination = .memory

        guard let id, !id.isEmpty else { return }

        if !memories.contains(where: { $0.id == id }) {
            await reloadMemories()
        }

        guard memories.contains(where: { $0.id == id }) else {
            errorMessage = "Memory \(id) was not found."
            return
        }

        selectedMemoryID = id
        await loadSelectedMemoryContext()
    }

    func openCapability(name: String?) async {
        showMainWindow()
        selectedDestination = .capabilities

        guard let name, !name.isEmpty else { return }

        if !capabilities.contains(where: { $0.name == name }) {
            await reloadCapabilities()
        }

        guard capabilities.contains(where: { $0.name == name }) else {
            errorMessage = "Capability \(name) was not found."
            return
        }

        selectedCapabilityName = name
    }

    func openRuntime(name: String?) async {
        showMainWindow()
        selectedDestination = .runtimes

        guard let name, !name.isEmpty else { return }

        if !runtimes.contains(where: { $0.name == name }) {
            await reloadRuntimes()
        }

        guard runtimes.contains(where: { $0.name == name }) else {
            errorMessage = "Runtime \(name) was not found."
            return
        }

        selectRuntime(name: name)
    }

    func openWorkflow(name: String?) async {
        showMainWindow()
        selectedDestination = .workflows

        guard let name, !name.isEmpty else { return }

        if !workflows.contains(where: { $0.name == name }) {
            await reloadWorkflows()
        }

        guard workflows.contains(where: { $0.name == name }) else {
            errorMessage = "Workflow \(name) was not found."
            return
        }

        selectedWorkflowName = name
    }

    func openPlugin(name: String?) async {
        showMainWindow()
        selectedDestination = .plugins

        guard let name, !name.isEmpty else { return }

        if !plugins.contains(where: { $0.name == name }) {
            await reloadPlugins()
        }

        guard plugins.contains(where: { $0.name == name }) else {
            errorMessage = "Plugin \(name) was not found."
            return
        }

        selectedPluginName = name
    }

    func handleNotificationResponse(route: String?, taskID: String?) async {
        let route = route.flatMap(NotificationRoute.init(rawValue:))
        await openFromNotification(route: route, taskID: taskID)
    }

    private func openFromNotification(route: NotificationRoute?, taskID: String?) async {
        guard let taskID, route == .task else {
            if route == .dashboard {
                openDashboard()
            }
            return
        }

        await openTask(id: taskID)
    }

    private func postNotification(title: String, body: String, route: NotificationRoute, taskID: String? = nil) async {
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        guard settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional else {
            return
        }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        var userInfo: [String: String] = [NotificationUserInfoKey.route: route.rawValue]
        if let taskID {
            userInfo[NotificationUserInfoKey.taskID] = taskID
        }
        content.userInfo = userInfo
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        try? await center.add(request)
    }

    nonisolated static func serializePreferences(_ preferences: [String: JSONValue]) -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(preferences),
              let text = String(data: data, encoding: .utf8) else {
            return "{}"
        }
        return text
    }

    nonisolated static func parsePreferences(from text: String) throws -> [String: JSONValue] {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return [:] }
        let data = Data(trimmed.utf8)
        do {
            return try JSONDecoder().decode([String: JSONValue].self, from: data)
        } catch {
            throw NSError(domain: "AIOSMac", code: 1, userInfo: [NSLocalizedDescriptionKey: "Preferences must be valid JSON."])
        }
    }

    private func suggestedCapabilityAction(for capability: CapabilityDescriptor?) -> String {
        switch capability?.name {
        case "local_files":
            return "list_dir"
        case "reminders":
            return "list"
        case "calendar":
            return "list"
        case "notes":
            return "draft"
        case "messaging":
            return "prepare"
        default:
            return ""
        }
    }

    private func shouldFallbackFromLegacyPort() -> Bool {
        guard backendURLString == BackendDefaults.legacyBaseURL else { return false }
        guard let errorMessage else { return false }
        return errorMessage.contains("HTTP 404")
    }
}

enum BackendStatus: String {
    case unknown
    case connected
    case disconnected
}

enum BackendProcessState: Equatable {
    case idle
    case running
    case stopped(Int32)
    case failed
}

struct VerificationDraft {
    var checksText = ""
    var verifierNotes = ""
}

struct ConfirmationDraft {
    var note = ""
}

struct ReflectionDraft {
    var summary = ""
    var lessonsText = ""
}

struct SchedulerDraft {
    var candidateLimit = 10
    var staleAfterMinutes = 60
    var escalateAfterHits = 2
}

struct CandidateDeferDraft {
    var dueHint = "later today"
}

struct ReminderDraft {
    var title = ""
    var note = ""
    var dueHint = "tomorrow"
}

private final class MainWindowDelegate: NSObject, NSWindowDelegate {
    weak var appState: AppState?

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        sender.orderOut(nil)
        appState?.selectedDestination = appState?.selectedDestination ?? .overview
        return false
    }
}

private extension String {
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

struct CreateTaskDraft {
    var objective = ""
    var successCriteriaText = ""
    var tagsText = ""
    var riskLevel = "low"
    var linkedGoalIDs: [String] = []
    var runtimeName: String? = nil

    var normalized: (
        objective: String,
        successCriteria: [String],
        tags: [String],
        riskLevel: String,
        linkedGoalIDs: [String],
        runtimeName: String?
    ) {
        (
            objective.trimmingCharacters(in: .whitespacesAndNewlines),
            successCriteriaText
                .split(whereSeparator: \.isNewline)
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty },
            tagsText
                .split(separator: ",")
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty },
            riskLevel,
            linkedGoalIDs,
            runtimeName?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfBlank
        )
    }
}

struct CreateGoalDraft {
    var title = ""
    var kind = "project"
    var status = "active"
    var horizon = "current"
    var summary = ""
    var successMetricsText = ""
    var parentGoalID = ""
    var tagsText = ""
    var priority = 3
    var progress = 0.0

    var normalized: (
        title: String,
        kind: String,
        status: String,
        horizon: String,
        summary: String,
        successMetrics: [String],
        parentGoalID: String?,
        tags: [String],
        priority: Int,
        progress: Double
    ) {
        (
            title.trimmingCharacters(in: .whitespacesAndNewlines),
            kind,
            status,
            horizon.trimmingCharacters(in: .whitespacesAndNewlines),
            summary.trimmingCharacters(in: .whitespacesAndNewlines),
            successMetricsText
                .split(whereSeparator: \.isNewline)
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty },
            parentGoalID.nilIfBlank,
            tagsText
                .split(separator: ",")
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty },
            priority,
            progress
        )
    }
}

struct DeviceDraft {
    var id = ""
    var name = ""
    var deviceClass = "mac_local"
    var status = "active"
    var capabilitiesText = ""
    var metadataText = "{}"

    var normalized: (
        id: String,
        name: String,
        deviceClass: String,
        status: String,
        capabilities: [String],
        metadata: [String: JSONValue]
    ) {
        let metadata = (try? AppState.parsePreferences(from: metadataText)) ?? [:]
        return (
            id.trimmingCharacters(in: .whitespacesAndNewlines),
            name.trimmingCharacters(in: .whitespacesAndNewlines),
            deviceClass,
            status,
            capabilitiesText
                .split(separator: ",")
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty },
            metadata
        )
    }
}
