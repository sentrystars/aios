import SwiftUI
import AppKit

struct RootView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        NavigationSplitView {
            SidebarView(appState: appState)
        } content: {
            switch appState.selectedDestination ?? .overview {
            case .overview:
                OverviewView(appState: appState)
            case .inbox:
                InboxWorkbenchView(appState: appState)
            case .tasks:
                TaskListView(appState: appState)
            case .memory:
                MemoryListView(appState: appState)
            case .reminders:
                ReminderOperationsView(appState: appState)
            case .capabilities:
                CapabilityListView(appState: appState)
            case .runtimes:
                RuntimeListView(appState: appState)
            case .plugins:
                PluginListView(appState: appState)
            case .workflows:
                WorkflowListView(appState: appState)
            case .events:
                EventStreamView(appState: appState)
            case .selfProfile:
                SelfProfileView(appState: appState)
            case .candidates:
                CandidateControlView(appState: appState)
            }
        } detail: {
            switch appState.selectedDestination ?? .overview {
            case .memory:
                MemoryDetailView(
                    appState: appState,
                    memory: appState.selectedMemory,
                    relations: appState.selectedMemoryRelations,
                    isLoading: appState.isLoading,
                    isLoadingContext: appState.isLoadingMemoryContext
                )
            case .reminders:
                ReminderDetailView(appState: appState)
            case .capabilities:
                CapabilityDetailView(appState: appState)
            case .runtimes:
                RuntimeDetailView(appState: appState)
            case .plugins:
                PluginDetailView(appState: appState)
            case .workflows:
                WorkflowDetailView(appState: appState)
            default:
                TaskDetailView(
                    appState: appState,
                    selection: $appState.selectedTaskDetailSection,
                    task: appState.selectedTask,
                    timeline: appState.selectedTaskTimeline,
                    relations: appState.selectedTaskRelations,
                    runs: appState.selectedTaskRuns,
                    isLoading: appState.isLoading,
                    isLoadingContext: appState.isLoadingTaskContext
                )
            }
        }
        .toolbar {
            ToolbarItemGroup {
                Button {
                    Task { await appState.reloadAll() }
                } label: {
                    Label(appState.text("Refresh", "刷新"), systemImage: "arrow.clockwise")
                }

                Button {
                    appState.isPresentingCreateTask = true
                } label: {
                    Label(appState.text("New Task", "新任务"), systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .sheet(isPresented: $appState.isPresentingCreateTask) {
            CreateTaskSheet(appState: appState)
                .frame(minWidth: 520, minHeight: 420)
        }
        .sheet(isPresented: $appState.isPresentingVerifySheet) {
            VerifyTaskSheet(appState: appState)
                .frame(minWidth: 520, minHeight: 420)
        }
        .sheet(isPresented: $appState.isPresentingConfirmSheet) {
            ConfirmTaskSheet(appState: appState)
                .frame(minWidth: 460, minHeight: 260)
        }
        .sheet(isPresented: $appState.isPresentingReflectSheet) {
            ReflectTaskSheet(appState: appState)
                .frame(minWidth: 520, minHeight: 420)
        }
        .sheet(isPresented: $appState.isPresentingDeferCandidateSheet) {
            DeferCandidateSheet(appState: appState)
                .frame(minWidth: 420, minHeight: 240)
        }
        .sheet(isPresented: $appState.isPresentingRunInspector) {
            RunInspectorSheet(appState: appState)
                .frame(minWidth: 720, minHeight: 560)
        }
        .overlay(alignment: .bottom) {
            if let errorMessage = appState.errorMessage {
                ErrorBanner(message: errorMessage)
                    .padding()
            } else if let successMessage = appState.successMessage {
                SuccessBanner(message: successMessage)
                    .padding()
            }
        }
        .task {
            await appState.initialLoadIfNeeded()
        }
        .task(id: appState.autoRefreshEnabled ? appState.refreshIntervalSeconds : 0) {
            await appState.autoRefreshLoop()
        }
        .background(MainWindowAccessor(appState: appState))
    }
}

private struct MainWindowAccessor: NSViewRepresentable {
    @ObservedObject var appState: AppState

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async {
            if let window = view.window {
                appState.registerMainWindow(window)
            }
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        DispatchQueue.main.async {
            if let window = nsView.window {
                appState.registerMainWindow(window)
            }
        }
    }
}

private struct SidebarView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        List(selection: $appState.selectedDestination) {
            Section(appState.text("Workspace", "工作区")) {
                ForEach(workspaceItems) { item in
                    NavigationLink(value: item) {
                        Label(localizedTitle(for: item), systemImage: icon(for: item))
                    }
                }
            }

            Section(appState.text("Developer", "开发者")) {
                ForEach(developerItems) { item in
                    NavigationLink(value: item) {
                        Label(localizedTitle(for: item), systemImage: icon(for: item))
                    }
                }
            }

            Section(appState.text("System", "系统")) {
                HStack {
                    Circle()
                        .fill(statusColor)
                        .frame(width: 10, height: 10)
                    Text(statusText)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(.vertical, 4)
            }
        }
        .listStyle(.sidebar)
    }

    private var workspaceItems: [AppState.SidebarDestination] {
        [.overview, .inbox, .tasks, .memory, .reminders, .candidates]
    }

    private var developerItems: [AppState.SidebarDestination] {
        [.capabilities, .runtimes, .plugins, .workflows, .events, .selfProfile]
    }

    private var statusText: String {
        if appState.isLoading {
            return appState.text("Syncing", "同步中")
        }
        switch appState.backendStatus {
        case .unknown:
            return appState.text("Unknown", "未知")
        case .connected:
            return appState.text("Connected", "已连接")
        case .disconnected:
            return appState.text("Disconnected", "未连接")
        }
    }

    private func localizedTitle(for item: AppState.SidebarDestination) -> String {
        switch item {
        case .overview:
            return appState.text("Overview", "总览")
        case .inbox:
            return appState.text("Conversation", "对话")
        case .tasks:
            return appState.text("Tasks", "任务")
        case .memory:
            return appState.text("Memory", "记忆")
        case .reminders:
            return appState.text("Reminders", "提醒")
        case .capabilities:
            return appState.text("Capabilities", "能力")
        case .runtimes:
            return appState.text("Runtimes", "运行时")
        case .plugins:
            return appState.text("Plugins", "插件")
        case .workflows:
            return appState.text("Workflows", "工作流")
        case .events:
            return appState.text("Events", "事件")
        case .selfProfile:
            return appState.text("Self", "自我")
        case .candidates:
            return appState.text("Candidates", "候选")
        }
    }

    private var statusColor: Color {
        switch appState.backendStatus {
        case .unknown:
            return .gray
        case .connected:
            return Brand.mint
        case .disconnected:
            return .red
        }
    }

    private func icon(for item: AppState.SidebarDestination) -> String {
        switch item {
        case .overview:
            return "square.grid.2x2"
        case .inbox:
            return "bubble.left.and.text.bubble.right"
        case .tasks:
            return "checklist"
        case .memory:
            return "brain"
        case .reminders:
            return "bell.badge"
        case .capabilities:
            return "switch.2"
        case .runtimes:
            return "server.rack"
        case .plugins:
            return "shippingbox"
        case .workflows:
            return "point.3.connected.trianglepath.dotted"
        case .events:
            return "waveform.path.ecg.rectangle"
        case .selfProfile:
            return "person.crop.circle"
        case .candidates:
            return "bolt.badge.clock"
        }
    }
}

private struct OverviewView: View {
    let appState: AppState
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                BrandHero(
                    eyebrow: appState.text("Today Workspace", "今日工作台"),
                    title: appState.text("Work With AI OS", "和 AI OS 一起工作"),
                    subtitle: appState.text("See what matters now, clear new requests, and move active work forward without living in backend screens.", "先看到当前重要事项，清空新请求，再推进活跃任务，而不是一直停留在后台页面。")
                )

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 16)], spacing: 16) {
                    MetricCard(title: appState.text("Focus Task", "当前焦点"), value: focusMetric, accent: Brand.active)
                    MetricCard(title: appState.text("Ready Now", "可立即开始"), value: "\(readyTasks.count)", accent: Brand.action)
                    MetricCard(title: appState.text("Needs Review", "等待处理"), value: "\(attentionTasks.count)", accent: Brand.waiting)
                    MetricCard(title: appState.text("Due Reminders", "即将提醒"), value: "\(dueReminders.count)", accent: Brand.reference)
                }

                HStack(alignment: .top, spacing: 16) {
                    SpotlightPanel(
                        title: appState.text("Focus Lane", "焦点任务"),
                        eyebrow: appState.text("Primary", "主视图"),
                        accentA: Brand.active,
                        accentB: Brand.action
                    ) {
                        if let task = focusTask {
                            VStack(alignment: .leading, spacing: 14) {
                                Text(task.objective)
                                    .font(.title3.weight(.semibold))
                                HStack {
                                    StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: Brand.active)
                                    StatusBadge(label: appState.displayToken(task.executionMode, category: .executionMode), color: Brand.waiting)
                                }
                                Text(task.blockerReason?.isEmpty == false ? task.blockerReason! : appState.text("This is the newest active task in your loop. Open it to keep momentum.", "这是你当前循环中最新的活跃任务。打开它继续推进。"))
                                    .foregroundStyle(.secondary)
                                HStack {
                                    Button(appState.text("Open Task", "打开任务")) {
                                        Task { await appState.openTask(id: task.id) }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    if ["captured", "planned"].contains(task.status) {
                                        Button(appState.text("Start Now", "立即开始")) {
                                            Task {
                                                await appState.openTask(id: task.id)
                                                await appState.startTask(id: task.id)
                                            }
                                        }
                                    }
                                }
                            }
                        } else {
                            EmptyWorkspaceState(
                                title: appState.text("No Active Focus", "当前没有活跃焦点"),
                                detail: appState.text("Create a task or start a new conversation to put something in motion.", "创建一个任务，或者发起一段新对话，让系统进入工作状态。")
                            )
                        }
                    }

                    GlassPanel(title: appState.text("Quick Start", "快速开始")) {
                        VStack(alignment: .leading, spacing: 12) {
                            QuickActionTile(
                                title: appState.text("Capture a New Task", "记录一个新任务"),
                                subtitle: appState.text("Jump straight into task creation with explicit success criteria.", "直接创建任务，并写清成功标准。"),
                                accent: Brand.action
                            ) {
                                appState.isPresentingCreateTask = true
                            }
                            QuickActionTile(
                                title: appState.text("Start A Conversation", "发起新对话"),
                                subtitle: appState.text("Tell AI OS what you want and let it decide whether to advise, plan, or create work.", "直接告诉 AI OS 你想做什么，让它判断是给建议、出计划，还是生成任务。"),
                                accent: Brand.active
                            ) {
                                appState.selectedDestination = .inbox
                            }
                            QuickActionTile(
                                title: appState.text("Review Candidates", "查看候选事项"),
                                subtitle: appState.text("See reminders and follow-up work waiting for a decision.", "查看提醒和等待决策的跟进事项。"),
                                accent: Brand.waiting
                            ) {
                                appState.selectedDestination = .candidates
                            }
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Next Actions", "下一步")) {
                        if readyTasks.isEmpty {
                            EmptyWorkspaceState(
                                title: appState.text("Nothing Ready Yet", "还没有可立即开始的任务"),
                                detail: appState.text("Use the conversation page or create a task to seed the next action queue.", "用对话页或新建任务来填充下一步队列。")
                            )
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(readyTasks.prefix(4)) { task in
                                    CompactTaskLine(appState: appState, task: task)
                                }
                            }
                        }
                    }

                    GlassPanel(title: appState.text("Decision Queue", "待决事项")) {
                        if dueReminders.isEmpty && appState.candidates.isEmpty {
                            EmptyWorkspaceState(
                                title: appState.text("No Pending Decisions", "当前没有待决事项"),
                                detail: appState.text("When reminders or candidate tasks need your attention, they will surface here first.", "当提醒或候选事项需要你处理时，会优先显示在这里。")
                            )
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(dueReminders.prefix(3))) { reminder in
                                    Button {
                                        appState.selectedDestination = .reminders
                                        appState.selectReminder(id: reminder.id)
                                    } label: {
                                        CompactReminderLine(reminder: reminder)
                                    }
                                    .buttonStyle(.plain)
                                }
                                ForEach(Array(appState.candidates.prefix(2))) { candidate in
                                    CompactCandidateDecisionLine(appState: appState, candidate: candidate)
                                }
                                if !appState.candidates.isEmpty {
                                    HStack {
                                        Spacer()
                                        Button(appState.text("Open Candidate Desk", "打开候选事项页")) {
                                            appState.selectedDestination = .candidates
                                        }
                                        .buttonStyle(.link)
                                    }
                                }
                            }
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Memory Context", "记忆上下文")) {
                        if let recall = appState.latestMemoryRecall, !recall.items.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(recall.items.prefix(3)) { item in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(item.title)
                                            .font(.headline)
                                        Text(item.reason)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                }
                            }
                        } else {
                            Text(appState.text("No memory recall snapshot yet.", "还没有记忆召回快照。"))
                                .foregroundStyle(.secondary)
                        }
                    }

                    GlassPanel(title: appState.text("Personal Rhythm", "个人节奏")) {
                        VStack(alignment: .leading, spacing: 10) {
                            overviewLine(appState.text("Current Phase", "当前阶段"), appState.selfProfile.currentPhase.capitalized)
                            overviewLine(appState.text("Risk Style", "风险风格"), appState.selfProfile.riskStyle.capitalized)
                            overviewLine(appState.text("Open Loops", "未完成事项"), "\(appState.selfProfile.sessionContext.openLoops.count)")
                            overviewLine(appState.text("Current Commitments", "当前承诺"), "\(appState.selfProfile.sessionContext.currentCommitments.count)")
                            overviewLine(appState.text("Active Goals", "活跃目标"), "\(activeGoalsCount)")
                        }
                    }

                    GlassPanel(title: appState.text("Today Guidance", "今日建议")) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(todayGuidance)
                                .foregroundStyle(.secondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            if !appState.selfProfile.sessionContext.activeFocus.isEmpty {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(appState.text("Session Focus", "当前关注"))
                                        .font(.headline)
                                    ForEach(appState.selfProfile.sessionContext.activeFocus.prefix(3), id: \.self) { focus in
                                        Text("• \(focus)")
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .padding(28)
        }
        .background(Brand.dashboardGradient(for: colorScheme))
    }

    private var sortedTasks: [TaskRecord] {
        appState.tasks.sorted { $0.updatedAt > $1.updatedAt }
    }

    private var readyTasks: [TaskRecord] {
        sortedTasks.filter { ["captured", "planned"].contains($0.status) }
    }

    private var attentionTasks: [TaskRecord] {
        sortedTasks.filter { ["blocked", "verifying"].contains($0.status) }
    }

    private var focusTask: TaskRecord? {
        sortedTasks.first(where: { ["executing", "planned", "captured", "blocked", "verifying"].contains($0.status) })
    }

    private var dueReminders: [ReminderRecord] {
        appState.reminders.sorted { $0.scheduledFor < $1.scheduledFor }
    }

    private var focusMetric: String {
        focusTask.map { String($0.objective.prefix(18)) } ?? appState.text("No focus", "暂无焦点")
    }

    private var activeGoalsCount: Int {
        appState.goals.filter { $0.status == "active" }.count
    }

    private var todayGuidance: String {
        if let task = focusTask {
            return task.blockerReason?.isEmpty == false
                ? task.blockerReason!
                : appState.text("Protect focus by moving the current task before opening too many new loops.", "先推进当前焦点任务，再避免同时打开过多新事项。")
        }
        if !readyTasks.isEmpty {
            return appState.text("You already have work that can start now. Pick one task and move it instead of opening new requests.", "你已经有可以立刻开始的工作了。先选一个推进，而不是继续打开新请求。")
        }
        if !appState.candidates.isEmpty || !dueReminders.isEmpty {
            return appState.text("Your next move is probably in the decision queue. Clear reminders and candidate work before creating more.", "你的下一步很可能就在待决事项里。先清理提醒和候选项，再决定要不要新增工作。")
        }
        return appState.text("The workspace is clear. This is a good moment to capture a new request or define one focused task.", "当前工作台比较干净，适合录入一个新请求，或者定义一个明确的焦点任务。")
    }

    private func overviewLine(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.headline)
            Text(value)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct InboxWorkbenchView: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme

    private let promptTemplates = [
        "把这周最重要的 3 件事整理成任务，并指出今天必须推进的那一件。",
        "帮我看一下今天有哪些提醒和待决事项需要先处理。",
        "在日历中增加日程：今天下午 1 点进行产品评审。",
        "判断这条需求的风险，并给出最稳妥的推进方式。"
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                BrandHero(
                    eyebrow: appState.text("Assistant Conversation", "助理对话"),
                    title: appState.text("Tell AI OS What You Need", "告诉 AI OS 你想做什么"),
                    subtitle: appState.text("Write the request the way you would message a capable assistant. This page is for plans, reminders, decisions, and turning concrete asks into tracked work.", "像给一个靠谱助理发消息一样写需求。这里适合做规划、提提醒、帮你判断，或者把明确事项转成可追踪任务。")
                )

                dialoguePanel
                guidanceStrip
                outcomePanels
            }
            .padding(24)
        }
        .background(Brand.dashboardGradient(for: colorScheme))
    }

    private var dialoguePanel: some View {
        SpotlightPanel(
            title: appState.text("Request Composer", "需求输入区"),
            eyebrow: appState.text("Step 1", "第 1 步"),
            accentA: Brand.active,
            accentB: Brand.action
        ) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(appState.text("Describe the outcome in plain language.", "直接用自然语言写你想达成的结果。"))
                            .font(.title3.weight(.semibold))
                        Text(appState.text("Good requests usually mention three things: what you want, what constraints matter, and whether it is urgent. AI OS will decide the right depth.", "好的需求一般包含三件事：你要什么、有哪些约束、这件事急不急。AI OS 会自己决定应该用多深的方式处理。"))
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    InboxSignalPill(
                        title: appState.text("Draft", "草稿"),
                        value: "\(draftLength) \(appState.text("chars", "字"))",
                        accent: Brand.ink
                    )
                }

                VStack(alignment: .leading, spacing: 12) {
                    InboxMessageBubble(
                        title: appState.text("You", "你"),
                        bodyText: conversationDraftOrLastRequest,
                        accent: Brand.ink,
                        inverted: false,
                        placeholder: conversationDraftOrLastRequest == appState.text("Ask for a plan, a decision, a reminder, a piece of work, or a safe recommendation.", "可以直接让它做规划、帮你判断、设置提醒、生成任务，或者给出稳妥建议。")
                    )

                    if appState.latestIntakeResponse != nil || appState.latestIntentEvaluation != nil {
                        InboxMessageBubble(
                            title: appState.text("AI OS", "AI OS"),
                            bodyText: conversationAssistantMessage,
                            accent: Brand.mint,
                            inverted: true,
                            placeholder: false
                        )
                    }
                }

                ZStack(alignment: .topLeading) {
                    TextEditor(text: $appState.inboxText)
                        .font(.body)
                        .frame(minHeight: 220)
                        .padding(12)
                        .background(
                            RoundedRectangle(cornerRadius: 20)
                                .fill(Color.primary.opacity(colorScheme == .dark ? 0.08 : 0.035))
                        )
                        .overlay {
                            RoundedRectangle(cornerRadius: 20)
                                .stroke(Color.secondary.opacity(0.18), lineWidth: 1)
                        }

                    if appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Text(appState.text("例如：在日历中增加日程：今天下午 1 点进行产品评审。", "For example: add a calendar event for a product review at 1 PM today."))
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 28)
                            .padding(.top, 22)
                            .allowsHitTesting(false)
                    }
                }

                HStack(spacing: 10) {
                    RequestStepBadge(
                        index: "1",
                        title: appState.text("Write", "写需求"),
                        detail: appState.text("State the outcome.", "说明想要的结果。"),
                        color: Brand.active
                    )
                    RequestStepBadge(
                        index: "2",
                        title: appState.text("Send", "发送"),
                        detail: appState.text("AI OS takes over from here.", "从这里开始交给 AI OS。"),
                        color: Brand.waiting
                    )
                    RequestStepBadge(
                        index: "3",
                        title: appState.text("Review", "看结果"),
                        detail: appState.text("See the result or blocker.", "查看结果或阻塞点。"),
                        color: Brand.action
                    )
                }

                GlassPanel(title: appState.text("Submit Request", "提交需求")) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(appState.text("Default behavior is automatic. Send the request once, and AI OS will create, plan, execute, and verify work when it is safe to do so.", "默认就是自动推进。你只要发送一次需求，AI OS 会在安全前提下自动创建、规划、执行并验证任务。"))
                            .foregroundStyle(.secondary)

                        HStack(alignment: .top, spacing: 12) {
                            inboxActionButton(
                                title: appState.text("Quick Read", "快速理解"),
                                subtitle: appState.text("Good for rough ideas, questions, and risk checks.", "适合模糊想法、咨询判断和风险检查。"),
                                systemImage: "text.magnifyingglass",
                                prominent: false,
                                disabled: !appState.canEvaluateInbox
                            ) {
                                Task { await appState.evaluateInboxIntent() }
                            }

                            inboxActionButton(
                                title: appState.text("Send Request", "发送需求"),
                                subtitle: appState.text("AI OS will automatically turn this into actions and stop only when confirmation is genuinely needed.", "AI OS 会自动把这条需求推进成动作，只有真的需要确认时才会停下来。"),
                                systemImage: "paperplane.fill",
                                prominent: true,
                                disabled: !appState.canProcessInbox
                            ) {
                                Task { await appState.processInbox() }
                            }
                        }

                        HStack {
                            Text(actionHint)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                            Spacer()
                            if !appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                                Button(appState.text("Clear", "清空")) {
                                    appState.inboxText = ""
                                }
                                .buttonStyle(.link)
                            }
                        }
                    }
                }

                HStack(alignment: .center) {
                    Label(appState.text("Try One", "试试这些"), systemImage: "sparkles.rectangle.stack")
                        .font(.headline)
                    Spacer()
                }

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 12)], spacing: 12) {
                    ForEach(promptTemplates, id: \.self) { template in
                        Button {
                            appState.inboxText = template
                        } label: {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(appState.text("Starter", "起始提示"))
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(Brand.mint)
                                Text(template)
                                    .font(.subheadline)
                                    .foregroundStyle(.primary)
                                    .multilineTextAlignment(.leading)
                                    .frame(maxWidth: .infinity, alignment: .topLeading)
                            }
                            .frame(maxWidth: .infinity, minHeight: 92, alignment: .topLeading)
                            .padding(14)
                            .background(
                                RoundedRectangle(cornerRadius: 18)
                                    .fill(Color.primary.opacity(colorScheme == .dark ? 0.05 : 0.022))
                                    .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }

                HStack {
                    StatusBadge(label: appState.isProcessingInbox ? appState.text("Working", "处理中") : appState.text("Ready", "就绪"), color: appState.isProcessingInbox ? Brand.waiting : Brand.action)
                    if let intent = appState.latestIntentEvaluation {
                        StatusBadge(label: appState.displayToken(intent.riskLevel, category: .riskLevel), color: riskColor(intent.riskLevel))
                    }
                    if let intake = appState.latestIntakeResponse, intake.task != nil {
                        StatusBadge(label: appState.text("Task Created", "已创建任务"), color: Brand.active)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .trailing)
            }
        }
    }

    private var guidanceStrip: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 16)], spacing: 16) {
            InboxMiniCard(
                title: appState.text("AI Read", "AI 理解"),
                value: appState.latestIntentEvaluation.map { appState.displayToken($0.intentType) } ?? appState.text("Pending", "待处理"),
                detail: appState.latestIntentEvaluation?.goal ?? appState.text("Run a quick read to understand what kind of ask this is.", "先轻读一次，看看这属于哪类请求。"),
                accent: Brand.active
            )
            InboxMiniCard(
                title: appState.text("Suggested Mode", "建议模式"),
                value: appState.latestIntakeResponse.map { appState.displayToken($0.cognition.suggestedExecutionMode, category: .executionMode) } ?? appState.text("Unscored", "未评估"),
                detail: conversationAssistantMessage,
                accent: Brand.waiting
            )
            InboxMiniCard(
                title: appState.text("Work Result", "工作结果"),
                value: appState.latestIntakeResponse?.task == nil ? appState.text("No Task Yet", "尚未生成任务") : appState.text("Task Created", "已创建任务"),
                detail: appState.latestIntakeResponse?.task?.objective ?? appState.text("Concrete requests can be turned into tracked work automatically.", "足够明确的请求会自动转成任务。"),
                accent: Brand.ink
            )
        }
    }

    private var outcomePanels: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 320), spacing: 16)], spacing: 16) {
            GlassPanel(title: appState.text("What AI OS Understood", "AI OS 的理解")) {
                if let intent = appState.latestIntentEvaluation {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            StatusBadge(label: appState.displayToken(intent.intentType), color: Brand.active)
                            StatusBadge(label: "Urgency \(intent.urgency)", color: Brand.waiting)
                            if intent.needsConfirmation {
                                StatusBadge(label: appState.text("Needs Confirmation", "需要确认"), color: Brand.danger)
                            }
                        }
                        inboxLine(appState.text("Main Goal", "核心目标"), intent.goal)
                        inboxLine(appState.text("Risk Level", "风险等级"), appState.displayToken(intent.riskLevel, category: .riskLevel))
                        inboxLine(appState.text("Why It Read It This Way", "这样理解的原因"), intent.rationale)
                        if !intent.relatedContextIDs.isEmpty {
                            inboxTagSection(appState.text("Related Context", "相关上下文"), items: intent.relatedContextIDs, empty: appState.text("No related context.", "没有相关上下文。"))
                        }
                    }
                } else {
                    inboxEmptyState(
                        title: appState.text("No AI Read Yet", "还没有 AI 理解结果"),
                        detail: appState.text("Use the light read first when you want a fast sense of intent, urgency, and confirmation risk before creating work.", "如果你想先快速判断意图、紧急度和确认风险，就先做一次轻读。")
                    )
                }
            }

            GlassPanel(title: appState.text("Suggested Next Move", "建议下一步")) {
                if let intake = appState.latestIntakeResponse {
                    VStack(alignment: .leading, spacing: 14) {
                        inboxLine(appState.text("Execution Mode", "执行模式"), appState.displayToken(intake.cognition.suggestedExecutionMode, category: .executionMode))
                        inboxLine(appState.text("Recommended Move", "推荐动作"), conversationAssistantMessage)
                        inboxLine(appState.text("Cost Note", "成本说明"), intake.cognition.commonsense.costNote)
                        inboxLine(appState.text("Strategic Position", "战略位置"), intake.cognition.insight.strategicPosition)
                        inboxLine(appState.text("Action Style", "行动风格"), intake.cognition.courage.actionMode)
                        inboxLine(appState.text("Why This Path", "为什么走这条路"), intake.cognition.courage.rationale)

                        if let betterPath = intake.cognition.insight.betterPath, !betterPath.isEmpty {
                            inboxLine(appState.text("Alternative Path", "替代路径"), betterPath)
                        }

                        inboxTagSection(appState.text("Suggested Tags", "建议标签"), items: intake.cognition.suggestedTaskTags, empty: appState.text("No suggested tags.", "没有建议标签。"))
                        inboxTagSection(appState.text("Success Criteria", "成功标准"), items: intake.cognition.suggestedSuccessCriteria, empty: appState.text("No suggested success criteria.", "没有建议的成功标准。"))
                        inboxTagSection(
                            appState.text("Planned Steps", "计划步骤"),
                            items: intake.cognition.suggestedExecutionPlan.steps.map { "\($0.capabilityName): \($0.action) - \($0.purpose)" },
                            empty: appState.text("No execution steps.", "没有执行步骤。")
                        )
                    }
                } else {
                    inboxEmptyState(
                        title: appState.text("No Full Processing Yet", "还没有完整处理结果"),
                        detail: appState.text("Run the full path when you want a stronger recommendation, success criteria, and a real task if the ask is concrete enough.", "如果你想拿到更完整的建议、成功标准，以及在条件充分时直接落成任务，就运行完整处理。")
                    )
                }
            }

            GlassPanel(title: appState.text("Work Created For You", "为你生成的工作")) {
                if let task = appState.latestIntakeResponse?.task {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(task.objective)
                                    .font(.headline)
                                Text(task.id)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: Brand.action)
                        }
                        inboxLine(appState.text("Risk", "风险"), appState.displayToken(task.riskLevel, category: .riskLevel))
                        inboxLine(appState.text("Execution Mode", "执行模式"), appState.displayToken(task.executionMode, category: .executionMode))
                        if !task.successCriteria.isEmpty {
                            inboxTagSection(appState.text("Task Success Criteria", "任务成功标准"), items: task.successCriteria, empty: appState.text("No success criteria.", "没有成功标准。"))
                        }
                        HStack {
                            Spacer()
                            Button(appState.text("Open Task", "打开任务")) {
                                Task { await appState.openTask(id: task.id) }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                } else {
                    inboxEmptyState(
                        title: appState.text("No Task Yet", "还没有生成任务"),
                        detail: appState.text("Not every request should become tracked work. Keep it lightweight for quick advice, or make the ask more concrete and process again.", "不是每条请求都应该变成任务。你可以先把它当成轻量咨询，也可以把请求写得更具体再处理一次。")
                    )
                }
            }
        }
    }

    private func inboxLine(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.headline)
            Text(value)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func inboxTagSection(_ title: String, items: [String], empty: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            if items.isEmpty {
                Text(empty)
                    .foregroundStyle(.secondary)
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(items, id: \.self) { item in
                        Text(item)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }

    private func inboxEmptyState(title: String, detail: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            Text(detail)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 18)
                .fill(Color.primary.opacity(colorScheme == .dark ? 0.05 : 0.025))
        )
    }

    private var conversationDraftOrLastRequest: String {
        let trimmedDraft = appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedDraft.isEmpty {
            return trimmedDraft
        }
        let submitted = appState.lastSubmittedConversationText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !submitted.isEmpty {
            return submitted
        }
        return appState.text("Ask for a plan, a decision, a reminder, a piece of work, or a safe recommendation.", "可以直接让它做规划、帮你判断、设置提醒、生成任务，或者给出稳妥建议。")
    }

    private var conversationAssistantMessage: String {
        if let task = appState.latestIntakeResponse?.task {
            switch task.status {
            case "done":
                switch task.executionMode {
                case "calendar_event":
                    return appState.text("AI OS has already placed this on your calendar. You can review the created task and schedule on the right.", "AI OS 已经把这件事放进日历了。你可以在右侧查看生成的任务和时间安排。")
                case "reminder":
                    return appState.text("AI OS has created the reminder and completed the request.", "AI OS 已经创建提醒并完成这条需求。")
                default:
                    return appState.text("AI OS has completed this request. You can review the result on the right.", "AI OS 已经完成这条需求。你可以在右侧查看结果。")
                }
            case "blocked":
                return appState.text("AI OS has taken over, but it still needs your confirmation or review before continuing.", "AI OS 已经接手，但继续前还需要你的确认或复核。")
            default:
                return appState.text("AI OS has taken over this request and is still moving it forward.", "AI OS 已经接手这条需求，并正在继续推进。")
            }
        }
        if let intent = appState.latestIntentEvaluation {
            return intent.rationale
        }
        return appState.text("AI OS will summarize what it understood here after you send the request.", "发送后，AI OS 会在这里说明它理解到的内容。")
    }

    private var actionHint: String {
        if appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return appState.text("Start with one concrete ask. Name the outcome, any boundary, and whether it matters today.", "先写一个具体请求，说明结果、边界，以及是不是今天就要推进。")
        }
        if appState.latestIntakeResponse?.task != nil {
            return appState.text("This request already ran through the workflow. Review the result below, or refine the request and send it again.", "这条请求已经走过自动流程。你可以直接看下面的结果，或者改写后重新发送。")
        }
        return appState.text("Send Request is the default path. AI OS will auto-run the workflow and stop only for real confirmation or policy blockers.", "发送需求是默认路径。AI OS 会自动跑完整流程，只有遇到真实确认或策略阻塞时才会停下。")
    }

    private var draftLength: Int {
        appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines).count
    }

    private func riskColor(_ riskLevel: String) -> Color {
        switch riskLevel {
        case "high":
            return Brand.danger
        case "medium":
            return Brand.waiting
        default:
            return Brand.action
        }
    }

    private func inboxActionButton(
        title: String,
        subtitle: String,
        systemImage: String,
        prominent: Bool,
        disabled: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: systemImage)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(prominent ? .white : Brand.pine)
                    .frame(width: 22)

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(prominent ? .white.opacity(0.8) : .secondary)
                        .multilineTextAlignment(.leading)
                }
                Spacer()
            }
            .padding(16)
            .frame(maxWidth: .infinity, minHeight: 96, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 20)
                    .fill(prominent ? AnyShapeStyle(Brand.mint.gradient) : AnyShapeStyle(Brand.panelFill(for: colorScheme)))
                    .stroke(prominent ? Color.clear : Brand.panelStroke(for: colorScheme), lineWidth: 1)
            )
            .foregroundStyle(prominent ? .white : .primary)
        }
        .buttonStyle(.plain)
        .opacity(disabled ? 0.45 : 1)
        .disabled(disabled)
    }
}

private struct InboxMessageBubble: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    let bodyText: String
    let accent: Color
    let inverted: Bool
    let placeholder: Bool

    var body: some View {
        HStack {
            if inverted { Spacer(minLength: 48) }
            VStack(alignment: .leading, spacing: 6) {
                Text(title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(inverted ? .white.opacity(0.8) : accent)
                Text(bodyText)
                    .foregroundStyle(inverted ? .white : (placeholder ? .secondary : .primary))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(16)
            .frame(maxWidth: 620, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(
                        inverted
                            ? AnyShapeStyle(accent.gradient)
                            : AnyShapeStyle(Color.primary.opacity(colorScheme == .dark ? 0.06 : 0.028))
                    )
                    .stroke(inverted ? Color.clear : Color.secondary.opacity(0.14), lineWidth: 1)
            )
            if !inverted { Spacer(minLength: 48) }
        }
    }
}

private struct InboxSignalPill: View {
    let title: String
    let value: String
    let accent: Color

    var body: some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text(title)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.weight(.semibold))
                .foregroundStyle(accent)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(
            Capsule(style: .continuous)
                .fill(accent.opacity(0.12))
        )
    }
}

private struct RequestStepBadge: View {
    let index: String
    let title: String
    let detail: String
    let color: Color

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Text(index)
                .font(.caption.weight(.bold))
                .foregroundStyle(.white)
                .frame(width: 22, height: 22)
                .background(Circle().fill(color))

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(color.opacity(0.08))
        )
    }
}

private struct InboxMiniCard: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    let value: String
    let detail: String
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Circle()
                    .fill(accent)
                    .frame(width: 8, height: 8)
            }
            Text(value)
                .font(.title3.weight(.semibold))
            Text(detail)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(Brand.panelFill(for: colorScheme))
                .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
        )
    }
}

private struct EmptyWorkspaceState: View {
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            Text(detail)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct QuickActionTile: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    let subtitle: String
    let accent: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 6) {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(accent.gradient)
                    .frame(width: 38, height: 38)
                Text(title)
                    .font(.headline)
                    .foregroundStyle(.primary)
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(Brand.panelFill(for: colorScheme))
                    .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

private struct CompactTaskLine: View {
    @ObservedObject var appState: AppState
    let task: TaskRecord

    var body: some View {
        Button {
            Task { await appState.openTask(id: task.id) }
        } label: {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(task.objective)
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text(task.updatedAt, style: .relative)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: Brand.pine)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
    }
}

private struct CompactReminderLine: View {
    let reminder: ReminderRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(reminder.title)
                    .font(.headline)
                Spacer()
                Text(reminder.scheduledFor, style: .relative)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text(reminder.dueHint)
                .foregroundStyle(.secondary)
        }
    }
}

private struct CompactCandidateLine: View {
    @ObservedObject var appState: AppState
    let candidate: CandidateTask

    var body: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text(candidate.title)
                    .font(.headline)
                Text(candidate.detail)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer()
            Button(appState.text("Review", "查看")) {
                appState.selectedDestination = .candidates
            }
            .buttonStyle(.link)
        }
    }
}

private struct CompactCandidateDecisionLine: View {
    @ObservedObject var appState: AppState
    let candidate: CandidateTask

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                Text(candidate.title)
                    .font(.headline)
                Text(candidate.detail)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                HStack {
                    StatusBadge(label: appState.displayToken(candidate.kind, category: .candidateKind), color: Brand.pine)
                    StatusBadge(label: "P\(candidate.priority)", color: Brand.amber)
                }
            }
            Spacer()
            Button(appState.text("Review", "处理")) {
                appState.selectedDestination = .candidates
            }
            .buttonStyle(.bordered)
        }
    }
}

private struct MemoryWorkspaceCard: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme
    let memory: MemoryRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(memory.title)
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text(memory.createdAt, style: .relative)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusBadge(label: appState.displayToken(memory.memoryType, category: .memoryType), color: Brand.pine)
            }

            Text(memory.content)
                .foregroundStyle(.secondary)
                .lineLimit(3)
                .frame(maxWidth: .infinity, alignment: .leading)

            if !memory.tags.isEmpty {
                FlowLayout(items: Array(memory.tags.prefix(4))) { tag in
                    StatusBadge(label: tag, color: Brand.ink)
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Brand.panelFill(for: colorScheme))
                .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
        )
    }
}

private struct ReminderWorkspaceCard: View {
    @Environment(\.colorScheme) private var colorScheme
    let reminder: ReminderRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(reminder.title)
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text(reminder.scheduledFor, style: .relative)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if reminder.sourceTaskID != nil {
                    StatusBadge(label: "task-linked", color: Brand.mint)
                }
            }

            Text(reminder.dueHint)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            if !reminder.note.isEmpty {
                Text(reminder.note)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Brand.panelFill(for: colorScheme))
                .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
        )
    }
}

private struct MemoryListView: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                BrandHero(
                    eyebrow: appState.text("Context Layer", "上下文层"),
                    title: appState.text("Memory Workspace", "记忆工作台"),
                    subtitle: appState.text("Keep the context that matters close to execution. Memory should help you decide and act, not disappear into an archive.", "把真正影响执行的上下文放在手边。记忆应该帮助你判断和行动，而不是沉到归档深处。")
                )

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 200), spacing: 16)], spacing: 16) {
                    MetricCard(title: appState.text("Total Memory", "总记忆"), value: "\(appState.memories.count)", accent: Brand.ink)
                    MetricCard(title: appState.text("Reflections", "复盘"), value: "\(reflectionMemories.count)", accent: Brand.active)
                    MetricCard(title: appState.text("Recent Captures", "最近记录"), value: "\(recentMemories.count)", accent: Brand.waiting)
                    MetricCard(title: appState.text("Tagged Context", "带标签上下文"), value: "\(taggedMemoryCount)", accent: Brand.action)
                }

                GlassPanel(title: appState.text("Memory Actions", "记忆操作")) {
                    HStack(alignment: .center, spacing: 12) {
                        Text(appState.text("Use memory as live context for planning, reflection, and turning old context into new work.", "把记忆当成活的上下文，用于规划、复盘和从旧信息里提炼新任务。"))
                            .foregroundStyle(.secondary)
                        Spacer()
                        if appState.backendStatus == .disconnected {
                            Button(appState.text("Retry", "重试")) {
                                Task { await appState.startupProbe() }
                            }
                        }
                        Button(appState.text("Refresh", "刷新")) {
                            Task { await appState.reloadMemories() }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }

                memorySection(
                    title: appState.text("Recent Context", "最近上下文"),
                    subtitle: appState.text("Fresh memory captures and reflections you may still need this week.", "这周仍可能用得上的最新记录和复盘。"),
                    memories: recentMemories
                )

                memorySection(
                    title: appState.text("Reflection Notes", "复盘笔记"),
                    subtitle: appState.text("Lessons, reviews, and perspective that can shape the next move.", "能影响下一步判断的复盘、经验和视角。"),
                    memories: reflectionMemories
                )

                memorySection(
                    title: appState.text("Reference Library", "参考库"),
                    subtitle: appState.text("Everything else that is stored and available when you need to reopen context.", "其他已经保存、需要时可以再打开的上下文。"),
                    memories: libraryMemories
                )
            }
        }
        .background(Brand.dashboardGradient(for: colorScheme))
        .task {
            if appState.memories.isEmpty {
                await appState.reloadMemories()
            }
        }
    }

    private var sortedMemories: [MemoryRecord] {
        appState.memories.sorted { $0.createdAt > $1.createdAt }
    }

    private var recentMemories: [MemoryRecord] {
        Array(sortedMemories.prefix(5))
    }

    private var reflectionMemories: [MemoryRecord] {
        sortedMemories.filter { $0.memoryType == "reflection" || $0.memoryType == "review" }
    }

    private var libraryMemories: [MemoryRecord] {
        sortedMemories.filter { !reflectionMemories.map(\.id).contains($0.id) }
    }

    private var taggedMemoryCount: Int {
        appState.memories.filter { !$0.tags.isEmpty }.count
    }

    private func memorySection(title: String, subtitle: String, memories: [MemoryRecord]) -> some View {
        GlassPanel(title: title) {
            VStack(alignment: .leading, spacing: 12) {
                Text(subtitle)
                    .foregroundStyle(.secondary)
                if memories.isEmpty {
                    EmptyWorkspaceState(
                        title: appState.text("No memory here yet", "这里还没有记忆"),
                        detail: appState.text("Once AI OS captures reflections or context, they will show up here for reuse.", "当 AI OS 开始积累上下文和复盘时，这里会出现可复用内容。")
                    )
                } else {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(memories.prefix(5)) { memory in
                            Button {
                                appState.selectMemory(id: memory.id)
                            } label: {
                                MemoryWorkspaceCard(appState: appState, memory: memory)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }
}

private struct CapabilityListView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(appState.text("Capabilities", "能力"))
                    .font(.title2.weight(.semibold))
                Spacer()
                if appState.backendStatus == .disconnected {
                    Button(appState.text("Retry", "重试")) {
                        Task { await appState.startupProbe() }
                    }
                }
                Button(appState.text("Refresh", "刷新")) {
                    Task { await appState.reloadCapabilities() }
                }
            }
            .padding(20)

            List(
                appState.capabilities,
                selection: Binding(
                    get: { appState.selectedCapabilityName },
                    set: { appState.selectCapability(name: $0) }
                )
            ) { capability in
                CapabilityRow(appState: appState, capability: capability)
                    .tag(capability.name)
            }
            .listStyle(.inset)
            .overlay {
                if appState.capabilities.isEmpty && !appState.isLoading {
                    ContentUnavailableView(
                        appState.text("No Capabilities Loaded", "还没有加载能力"),
                        systemImage: "switch.2",
                        description: Text(appState.backendStatus == .disconnected ? appState.text("Reconnect to the backend to load the capability bus.", "重新连接后端以加载能力总线。") : appState.text("Capability descriptors will appear here once the backend reports them.", "后端返回能力描述后会显示在这里。"))
                    )
                }
            }
        }
        .task {
            if appState.capabilities.isEmpty {
                await appState.reloadCapabilities()
            }
        }
    }
}

private struct RuntimeListView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(appState.text("Runtimes", "运行时"))
                    .font(.title2.weight(.semibold))
                Spacer()
                if appState.backendStatus == .disconnected {
                    Button(appState.text("Retry", "重试")) {
                        Task { await appState.startupProbe() }
                    }
                }
                Button(appState.text("Refresh", "刷新")) {
                    Task { await appState.reloadRuntimes() }
                }
            }
            .padding(20)

            List(
                appState.runtimes,
                selection: Binding(
                    get: { appState.selectedRuntimeName },
                    set: { appState.selectRuntime(name: $0) }
                )
            ) { runtime in
                RuntimeRow(appState: appState, runtime: runtime)
                    .tag(runtime.name)
            }
            .listStyle(.inset)
            .overlay {
                if appState.runtimes.isEmpty && !appState.isLoading {
                    ContentUnavailableView(
                        appState.text("No Runtimes Loaded", "还没有加载运行时"),
                        systemImage: "server.rack",
                        description: Text(appState.backendStatus == .disconnected ? appState.text("Reconnect to the backend to inspect runtime adapters.", "重新连接后端以查看运行时适配器。") : appState.text("Runtime adapters will appear here once the backend reports them.", "后端返回运行时描述后会显示在这里。"))
                    )
                }
            }
        }
        .task {
            if appState.runtimes.isEmpty {
                await appState.reloadRuntimes()
            }
        }
    }
}

private struct PluginListView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(appState.text("Plugins", "插件"))
                    .font(.title2.weight(.semibold))
                Spacer()
                if appState.backendStatus == .disconnected {
                    Button(appState.text("Retry", "重试")) {
                        Task { await appState.startupProbe() }
                    }
                }
                Button(appState.text("Refresh", "刷新")) {
                    Task { await appState.reloadPlugins() }
                }
            }
            .padding(20)

            List(
                appState.plugins,
                selection: Binding(
                    get: { appState.selectedPluginName },
                    set: { appState.selectPlugin(name: $0) }
                )
            ) { plugin in
                PluginRow(appState: appState, plugin: plugin)
                    .tag(plugin.name)
            }
            .listStyle(.inset)
            .overlay {
                if appState.plugins.isEmpty && !appState.isLoading {
                    ContentUnavailableView(
                        appState.text("No Plugins Loaded", "还没有加载插件"),
                        systemImage: "shippingbox",
                        description: Text(appState.backendStatus == .disconnected ? appState.text("Reconnect to the backend to inspect plugin manifests.", "重新连接后端以查看插件清单。") : appState.text("Plugin manifests will appear here once the backend reports them.", "后端返回插件描述后会显示在这里。"))
                    )
                }
            }
        }
        .task {
            if appState.plugins.isEmpty {
                await appState.reloadPlugins()
            }
        }
    }
}

private struct WorkflowListView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(appState.text("Workflows", "工作流"))
                    .font(.title2.weight(.semibold))
                Spacer()
                if appState.backendStatus == .disconnected {
                    Button(appState.text("Retry", "重试")) {
                        Task { await appState.startupProbe() }
                    }
                }
                Button(appState.text("Refresh", "刷新")) {
                    Task { await appState.reloadWorkflows() }
                }
            }
            .padding(20)

            List(
                appState.workflows,
                selection: Binding(
                    get: { appState.selectedWorkflowName },
                    set: { appState.selectWorkflow(name: $0) }
                )
            ) { workflow in
                WorkflowRow(workflow: workflow)
                    .tag(workflow.name)
            }
            .listStyle(.inset)
            .overlay {
                if appState.workflows.isEmpty && !appState.isLoading {
                    ContentUnavailableView(
                        appState.text("No Workflows Loaded", "还没有加载工作流"),
                        systemImage: "point.3.connected.trianglepath.dotted",
                        description: Text(appState.backendStatus == .disconnected ? appState.text("Reconnect to the backend to inspect workflow manifests.", "重新连接后端以查看工作流清单。") : appState.text("Workflow manifests will appear here once the backend reports them.", "后端返回工作流描述后会显示在这里。"))
                    )
                }
            }
        }
        .task {
            if appState.workflows.isEmpty {
                await appState.reloadWorkflows()
            }
        }
    }
}

private struct ReminderOperationsView: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                BrandHero(
                    eyebrow: appState.text("Personal Ops", "个人节奏"),
                    title: appState.text("Reminder Desk", "提醒桌面"),
                    subtitle: appState.text("See what is coming up, what needs attention today, and create lightweight reminders without leaving the flow.", "查看接下来要发生什么、今天需要注意什么，并在不中断流程的情况下快速创建提醒。")
                )

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 200), spacing: 16)], spacing: 16) {
                    MetricCard(title: appState.text("Total Reminders", "提醒总数"), value: "\(appState.reminders.count)", accent: Brand.ink)
                    MetricCard(title: appState.text("Due Today", "今天到期"), value: "\(todayReminders.count)", accent: Brand.waiting)
                    MetricCard(title: appState.text("Upcoming", "即将到来"), value: "\(upcomingReminders.count)", accent: Brand.active)
                    MetricCard(title: appState.text("Linked To Tasks", "关联任务"), value: "\(linkedReminderCount)", accent: Brand.action)
                }

                GlassPanel(title: appState.text("Quick Reminder", "快速提醒")) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(appState.text("Capture a title, a short note, and a due hint. Use this for personal pacing, follow-ups, or time-based nudges.", "写下标题、简短备注和到期提示。适合个人节奏管理、跟进提醒和时间触发的提示。"))
                            .foregroundStyle(.secondary)

                        TextField(appState.text("Title", "标题"), text: $appState.reminderDraft.title)
                            .textFieldStyle(.roundedBorder)
                        TextField(appState.text("Note", "备注"), text: $appState.reminderDraft.note)
                            .textFieldStyle(.roundedBorder)
                        TextField(appState.text("Due Hint", "到期提示"), text: $appState.reminderDraft.dueHint)
                            .textFieldStyle(.roundedBorder)

                        HStack {
                            if appState.backendStatus == .disconnected {
                                Button(appState.text("Retry", "重试")) {
                                    Task { await appState.startupProbe() }
                                }
                            }
                            Button(appState.text("Refresh", "刷新")) {
                                Task { await appState.reloadReminders() }
                            }
                            Spacer()
                            Button(appState.text("Create Reminder", "创建提醒")) {
                                Task { await appState.createReminder() }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                }

                reminderSection(
                    title: appState.text("Due Today", "今天到期"),
                    subtitle: appState.text("Things that should stay visible today.", "今天不应该被忽略的提醒。"),
                    reminders: todayReminders
                )

                reminderSection(
                    title: appState.text("Upcoming", "接下来"),
                    subtitle: appState.text("Scheduled reminders that are approaching soon.", "接下来会很快到来的计划提醒。"),
                    reminders: upcomingReminders
                )

                reminderSection(
                    title: appState.text("All Reminders", "全部提醒"),
                    subtitle: appState.text("The full reminder list, including slower-burn follow-ups.", "完整提醒列表，包括节奏更慢的后续事项。"),
                    reminders: sortedReminders
                )
            }
        }
        .background(Brand.dashboardGradient(for: colorScheme))
        .task {
            if appState.reminders.isEmpty {
                await appState.reloadReminders()
            }
        }
    }

    private var sortedReminders: [ReminderRecord] {
        appState.reminders.sorted { $0.scheduledFor < $1.scheduledFor }
    }

    private var todayReminders: [ReminderRecord] {
        sortedReminders.filter { Calendar.current.isDateInToday($0.scheduledFor) }
    }

    private var upcomingReminders: [ReminderRecord] {
        sortedReminders.filter { !Calendar.current.isDateInToday($0.scheduledFor) }.prefix(5).map { $0 }
    }

    private var linkedReminderCount: Int {
        appState.reminders.filter { $0.sourceTaskID != nil }.count
    }

    private func reminderSection(title: String, subtitle: String, reminders: [ReminderRecord]) -> some View {
        GlassPanel(title: title) {
            VStack(alignment: .leading, spacing: 12) {
                Text(subtitle)
                    .foregroundStyle(.secondary)
                if reminders.isEmpty {
                    EmptyWorkspaceState(
                        title: appState.text("No reminders here", "这里没有提醒"),
                        detail: appState.text("Create one above or wait for task-linked reminders to appear here automatically.", "可以在上方手动创建，也可以等待任务相关提醒自动出现在这里。")
                    )
                } else {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(reminders.prefix(6)) { reminder in
                            Button {
                                appState.selectReminder(id: reminder.id)
                            } label: {
                                ReminderWorkspaceCard(reminder: reminder)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }
}

private struct TaskListView: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                BrandHero(
                    eyebrow: appState.text("Execution Queue", "执行队列"),
                    title: appState.text("Task Workspace", "任务工作区"),
                    subtitle: appState.text("Keep active work moving, surface blocked items early, and avoid burying the next action in an admin list.", "保持活跃任务流动，尽早暴露阻塞项，不要把下一步埋在后台列表里。")
                )

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 200), spacing: 16)], spacing: 16) {
                    MetricCard(title: appState.text("Ready To Start", "可开始"), value: "\(readyTasks.count)", accent: Brand.action)
                    MetricCard(title: appState.text("In Motion", "进行中"), value: "\(inMotionTasks.count)", accent: Brand.active)
                    MetricCard(title: appState.text("Needs Attention", "待处理"), value: "\(attentionTasks.count)", accent: Brand.waiting)
                    MetricCard(title: appState.text("Done Recently", "最近完成"), value: "\(completedTasks.count)", accent: Brand.reference)
                }

                SpotlightPanel(
                    title: appState.text("Task Actions", "任务操作"),
                    eyebrow: appState.text("Control", "操作"),
                    accentA: Brand.waiting,
                    accentB: Brand.reference
                ) {
                    HStack(alignment: .center, spacing: 12) {
                        if appState.autoRefreshEnabled {
                            Label(appState.text("Auto \(appState.refreshIntervalSeconds)s", "自动 \(appState.refreshIntervalSeconds) 秒"), systemImage: "arrow.triangle.2.circlepath")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        if appState.backendStatus == .disconnected {
                            Button(appState.text("Retry", "重试")) {
                                Task { await appState.startupProbe() }
                            }
                        }
                        Button(appState.text("Verify", "验证")) {
                            appState.isPresentingVerifySheet = true
                        }
                        .disabled(!appState.canVerifySelectedTask)
                        Button(appState.text("Confirm", "确认")) {
                            appState.isPresentingConfirmSheet = true
                        }
                        .disabled(!appState.canConfirmSelectedTask)
                        Button(appState.text("Reflect", "复盘")) {
                            appState.isPresentingReflectSheet = true
                        }
                        .disabled(!appState.canReflectSelectedTask)
                        Button(appState.text("Plan", "规划")) {
                            Task { await appState.planSelectedTask() }
                        }
                        .disabled(!appState.canPlanSelectedTask)
                        Button(appState.text("Start", "开始")) {
                            Task { await appState.startSelectedTask() }
                        }
                        .disabled(!appState.canStartSelectedTask)
                        .buttonStyle(.borderedProminent)
                    }
                }

                taskSection(
                    title: appState.text("Ready Now", "现在可做"),
                    subtitle: appState.text("Captured and planned tasks that can be moved immediately.", "已经捕获或规划完成，可以立刻推进的任务。"),
                    tasks: readyTasks
                )

                taskSection(
                    title: appState.text("In Motion", "进行中"),
                    subtitle: appState.text("Execution and verification work currently underway.", "当前正在执行或验证中的任务。"),
                    tasks: inMotionTasks
                )

                taskSection(
                    title: appState.text("Needs Attention", "需要处理"),
                    subtitle: appState.text("Blocked or waiting items that should not disappear from view.", "被阻塞或等待确认的任务，不应该被埋没。"),
                    tasks: attentionTasks
                )

                taskSection(
                    title: appState.text("Done Recently", "最近完成"),
                    subtitle: appState.text("Recently closed work for quick review and reflection.", "最近关闭的工作项，适合快速回看和复盘。"),
                    tasks: completedTasks
                )
            }
            .padding(24)
        }
        .background(Brand.dashboardGradient(for: colorScheme))
    }

    private var sortedTasks: [TaskRecord] {
        appState.tasks.sorted { $0.updatedAt > $1.updatedAt }
    }

    private var readyTasks: [TaskRecord] {
        sortedTasks.filter { ["captured", "planned"].contains($0.status) }
    }

    private var inMotionTasks: [TaskRecord] {
        sortedTasks.filter { ["executing", "verifying"].contains($0.status) }
    }

    private var attentionTasks: [TaskRecord] {
        sortedTasks.filter { ["blocked"].contains($0.status) }
    }

    private var completedTasks: [TaskRecord] {
        sortedTasks.filter { ["done"].contains($0.status) }
    }

    private func taskSection(title: String, subtitle: String, tasks: [TaskRecord]) -> some View {
        GlassPanel(title: title) {
            VStack(alignment: .leading, spacing: 12) {
                Text(subtitle)
                    .foregroundStyle(.secondary)
                if tasks.isEmpty {
                    Text(appState.text("Nothing here right now.", "这里暂时没有内容。"))
                        .foregroundStyle(.secondary)
                } else {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(tasks.prefix(5)) { task in
                            Button {
                                appState.selectTask(id: task.id)
                            } label: {
                                TaskWorkspaceCard(appState: appState, task: task)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }
}

private struct MemoryDetailView: View {
    @ObservedObject var appState: AppState
    let memory: MemoryRecord?
    let relations: [EntityRelation]
    let isLoading: Bool
    let isLoadingContext: Bool

    var body: some View {
        Group {
            if let memory {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(memory.title)
                                    .font(.title2.weight(.semibold))
                                HStack {
                                    StatusBadge(label: appState.displayToken(memory.memoryType, category: .memoryType), color: Brand.reference)
                                    StatusBadge(label: memory.createdAt.formatted(date: .abbreviated, time: .shortened), color: Brand.waiting)
                                }
                            }
                            Spacer()
                        }

                        GlassPanel(title: appState.text("Memory Snapshot", "记忆摘要")) {
                            VStack(alignment: .leading, spacing: 12) {
                                Text(
                                    appState.text(
                                        "Use this record as active context for the next move. You can turn it into work, review its links, or keep it as reference.",
                                        "把这条记录当成下一步行动的上下文。你可以直接转成任务、查看它的关联，或把它作为参考保留。"
                                    )
                                )
                                .foregroundStyle(.secondary)

                                HStack(alignment: .top, spacing: 12) {
                                    summaryPill(
                                        title: appState.text("Type", "类型"),
                                        value: appState.displayToken(memory.memoryType, category: .memoryType),
                                        color: Brand.reference
                                    )
                                    summaryPill(
                                        title: appState.text("Tags", "标签"),
                                        value: "\(memory.tags.count)",
                                        color: Brand.ink
                                    )
                                    summaryPill(
                                        title: appState.text("Links", "关联"),
                                        value: "\(relations.count)",
                                        color: Brand.waiting
                                    )
                                }

                                HStack {
                                    Spacer()
                                    Button(appState.text("Create Task From Memory", "从记忆创建任务")) {
                                        appState.presentCreateTask(
                                            objective: memory.title,
                                            successCriteria: ["Review the memory context and define a concrete next step."],
                                            tags: ["memory", memory.memoryType],
                                            riskLevel: "low"
                                        )
                                    }
                                    .buttonStyle(.borderedProminent)
                                }
                            }
                        }

                        GlassPanel(title: appState.text("Memory Content", "记忆内容")) {
                            VStack(alignment: .leading, spacing: 12) {
                                Text(memory.content)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }

                        GlassPanel(title: appState.text("Tags", "标签")) {
                            if memory.tags.isEmpty {
                                Text(appState.text("No tags.", "没有标签。"))
                                    .foregroundStyle(.secondary)
                            } else {
                                TagCloud(items: memory.tags, emptyText: appState.text("No tags.", "没有标签。"))
                            }
                        }

                        GlassPanel(title: appState.text("Relations", "关联")) {
                            if isLoadingContext && relations.isEmpty {
                                ProgressView()
                            } else if relations.isEmpty {
                                Text(appState.text("No relations recorded.", "还没有关联记录。"))
                                    .foregroundStyle(.secondary)
                            } else {
                                VStack(alignment: .leading, spacing: 12) {
                                    ForEach(relations) { relation in
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(appState.displayToken(relation.relationType, category: .relationType))
                                                .font(.headline)
                                            Text("\(relation.sourceType):\(relation.sourceID) -> \(relation.targetType):\(relation.targetID)")
                                                .font(.subheadline)
                                            HStack(spacing: 12) {
                                                if relation.sourceType == "task" {
                                                    Button(appState.text("Open Source Task", "打开源任务")) {
                                                        Task { await appState.openTask(id: relation.sourceID) }
                                                    }
                                                    .buttonStyle(.link)
                                                }
                                                if relation.targetType == "task" {
                                                    Button(appState.text("Open Target Task", "打开目标任务")) {
                                                        Task { await appState.openTask(id: relation.targetID) }
                                                    }
                                                    .buttonStyle(.link)
                                                }
                                                if relation.sourceType == "memory" && relation.sourceID != memory.id {
                                                    Button(appState.text("Open Source Memory", "打开源记忆")) {
                                                        Task { await appState.openMemory(id: relation.sourceID) }
                                                    }
                                                    .buttonStyle(.link)
                                                }
                                                if relation.targetType == "memory" && relation.targetID != memory.id {
                                                    Button(appState.text("Open Target Memory", "打开目标记忆")) {
                                                        Task { await appState.openMemory(id: relation.targetID) }
                                                    }
                                                    .buttonStyle(.link)
                                                }
                                            }
                                            if !relation.metadata.isEmpty {
                                                Text(relation.metadata.keys.sorted().map { "\($0)=\(relation.metadata[$0]?.displayText ?? "")" }.joined(separator: ", "))
                                                    .foregroundStyle(.secondary)
                                            }
                                        }
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                }
                            }
                        }
                    }
                    .padding(24)
                }
            } else if isLoading {
                ProgressView(appState.text("Loading memory…", "正在加载记忆…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(appState.text("No Memory Selected", "未选择记忆"), systemImage: "brain", description: Text(appState.text("Select a memory record from the list.", "请从列表中选择一条记忆记录。")))
            }
        }
    }

    private func summaryPill(title: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline)
                .foregroundStyle(color)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(color.opacity(0.10))
        )
    }
}

private struct CapabilityDetailView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        Group {
            if let capability = appState.selectedCapability {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(capability.name)
                                    .font(.title2.weight(.semibold))
                                HStack {
                                    StatusBadge(label: appState.displayToken(capability.riskLevel, category: .riskLevel), color: capabilityRiskColor(capability.riskLevel))
                                }
                            }
                            Spacer()
                        }

                        GlassPanel(title: appState.text("Description", "描述")) {
                            Text(capability.description)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        GlassPanel(title: appState.text("Provided By Plugins", "来源插件")) {
                            if appState.pluginsForSelectedCapability.isEmpty {
                                Text(appState.text("No plugin bindings found.", "没有找到插件绑定。"))
                                    .foregroundStyle(.secondary)
                            } else {
                                FlowLayout(items: appState.pluginsForSelectedCapability) { plugin in
                                    Button(action: {
                                        Task { await appState.openPlugin(name: plugin.name) }
                                    }) {
                                        StatusBadge(label: plugin.name, color: Brand.ink)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }

                        GlassPanel(title: appState.text("Recent Task Usage", "最近任务使用")) {
                            RecentTaskUsageView(
                                appState: appState,
                                tasks: appState.capabilityUsage,
                                emptyText: appState.text("No recent tasks used this capability.", "最近没有任务使用这个能力。"),
                                openTask: { taskID in
                                    Task { await appState.openTask(id: taskID) }
                                }
                            )
                        }

                        GlassPanel(title: appState.text("Execute", "执行")) {
                            VStack(alignment: .leading, spacing: 12) {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(appState.text("Action", "动作"))
                                        .font(.headline)
                                    TextField(appState.text("Action", "动作"), text: $appState.capabilityActionText)
                                        .textFieldStyle(.roundedBorder)
                                }

                                VStack(alignment: .leading, spacing: 6) {
                                    Text(appState.text("Parameters JSON", "参数 JSON"))
                                        .font(.headline)
                                    TextEditor(text: $appState.capabilityParametersText)
                                        .font(.body.monospaced())
                                        .frame(minHeight: 180)
                                        .overlay {
                                            RoundedRectangle(cornerRadius: 8)
                                                .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                                        }
                                }

                                HStack {
                                    Spacer()
                                    Button(appState.text("Run Capability", "运行能力")) {
                                        Task { await appState.executeSelectedCapability() }
                                    }
                                    .buttonStyle(.borderedProminent)
                                }
                            }
                        }

                        if let result = appState.latestCapabilityExecutionResult,
                           result.capabilityName == capability.name {
                            GlassPanel(title: appState.text("Latest Result", "最近结果")) {
                                VStack(alignment: .leading, spacing: 10) {
                                    HStack {
                                        StatusBadge(label: appState.displayToken(result.status, category: .capabilityStatus), color: result.status == "ok" ? Brand.mint : Brand.amber)
                                        if result.requiresConfirmation {
                                            StatusBadge(label: appState.text("Needs Confirmation", "需要确认"), color: .red)
                                        }
                                    }
                                    capabilityLine(appState.text("Action", "动作"), result.action)
                                    capabilityLine(appState.text("Output", "输出"), result.output)
                                }
                            }
                        }
                    }
                    .padding(24)
                }
            } else if appState.isLoading {
                ProgressView(appState.text("Loading capabilities…", "正在加载能力…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(appState.text("No Capability Selected", "未选择能力"), systemImage: "switch.2", description: Text(appState.text("Select a capability from the list.", "请从列表中选择一个能力。")))
            }
        }
    }

    private func capabilityLine(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.headline)
            Text(value)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func capabilityRiskColor(_ riskLevel: String) -> Color {
        switch riskLevel {
        case "high":
            return Brand.danger
        case "medium":
            return Brand.waiting
        default:
            return Brand.action
        }
    }
}

private struct RuntimeDetailView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        Group {
            if let runtime = appState.selectedRuntime {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(runtime.name)
                                    .font(.title2.weight(.semibold))
                                HStack {
                                    StatusBadge(label: appState.displayToken(runtime.status, category: .capabilityStatus), color: runtime.status == "available" ? Brand.action : Brand.waiting)
                                    StatusBadge(label: runtime.runtimeType, color: Brand.reference)
                                }
                            }
                            Spacer()
                            Button(appState.text("Refresh", "刷新")) {
                                Task { await appState.reloadRuntimes() }
                            }
                        }

                        GlassPanel(title: appState.text("Description", "描述")) {
                            Text(runtime.description)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        GlassPanel(title: appState.text("Runtime Root", "运行时根目录")) {
                            Text(runtime.rootPath ?? appState.text("Unavailable", "不可用"))
                                .foregroundStyle(.secondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        GlassPanel(title: appState.text("Provided By Plugins", "来源插件")) {
                            if appState.pluginsForSelectedRuntime.isEmpty {
                                Text(appState.text("No plugin bindings found.", "没有找到插件绑定。"))
                                    .foregroundStyle(.secondary)
                            } else {
                                FlowLayout(items: appState.pluginsForSelectedRuntime) { plugin in
                                    Button(action: {
                                        Task { await appState.openPlugin(name: plugin.name) }
                                    }) {
                                        StatusBadge(label: plugin.name, color: Brand.ink)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }

                        GlassPanel(title: appState.text("Recent Task Usage", "最近任务使用")) {
                            RecentTaskUsageView(
                                appState: appState,
                                tasks: appState.runtimeUsage,
                                emptyText: appState.text("No recent tasks selected this runtime.", "最近没有任务选择这个运行时。"),
                                openTask: { taskID in
                                    Task { await appState.openTask(id: taskID) }
                                }
                            )
                        }

                        if !runtime.supportedCapabilities.isEmpty {
                            GlassPanel(title: appState.text("Supported Capabilities", "支持的能力")) {
                                FlowLayout(items: runtime.supportedCapabilities) { capability in
                                    StatusBadge(label: capability, color: Brand.pine)
                                }
                            }
                        }

                        if !runtime.notes.isEmpty {
                            GlassPanel(title: appState.text("Notes", "说明")) {
                                VStack(alignment: .leading, spacing: 8) {
                                    ForEach(runtime.notes, id: \.self) { note in
                                        Text("• \(note)")
                                            .foregroundStyle(.secondary)
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                }
                            }
                        }

                        GlassPanel(title: appState.text("Task Preview", "任务预览")) {
                            VStack(alignment: .leading, spacing: 12) {
                                if let task = appState.selectedTask {
                                    Text(appState.text("Selected task", "当前任务") + ": \(task.objective)")
                                        .font(.headline)
                                } else {
                                    Text(appState.text("Select a task to preview runtime preparation.", "请选择一个任务以预览运行时准备结果。"))
                                        .foregroundStyle(.secondary)
                                }

                                if let preview = appState.latestRuntimePreview, preview.runtime == runtime.name {
                                    runtimeLine(appState.text("Command", "命令"), preview.commandPreview)
                                    runtimeLine(appState.text("Workspace", "工作区"), preview.workspaceRoot)
                                    runtimeLine(appState.text("Runtime Root", "运行时根目录"), preview.runtimeRoot)

                                    VStack(alignment: .leading, spacing: 6) {
                                        Text(appState.text("Prompt Preview", "提示预览"))
                                            .font(.headline)
                                        Text(preview.promptPreview)
                                            .font(.body.monospaced())
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                            .padding(12)
                                            .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                                    }
                                } else {
                                    Text(appState.text("Runtime preview is unavailable for the current selection.", "当前选择没有可用的运行时预览。"))
                                        .foregroundStyle(.secondary)
                                }

                                if let invocation = appState.latestRuntimeInvocation, invocation.runtime == runtime.name {
                                    Divider()
                                    runtimeLine(appState.text("Launch Mode", "启动模式"), invocation.invocationMode)
                                    runtimeLine(
                                        appState.text("Working Directory", "工作目录"),
                                        invocation.workingDirectory
                                    )

                                    VStack(alignment: .leading, spacing: 6) {
                                        Text(appState.text("Environment Hints", "环境提示"))
                                            .font(.headline)
                                        ForEach(invocation.environmentHints.keys.sorted(), id: \.self) { key in
                                            Text("\(key)=\(invocation.environmentHints[key] ?? "")")
                                                .font(.body.monospaced())
                                                .frame(maxWidth: .infinity, alignment: .leading)
                                        }
                                    }

                                    VStack(alignment: .leading, spacing: 6) {
                                        Text(appState.text("Invocation Notes", "调用说明"))
                                            .font(.headline)
                                        ForEach(invocation.notes, id: \.self) { note in
                                            Text("• \(note)")
                                                .foregroundStyle(.secondary)
                                                .frame(maxWidth: .infinity, alignment: .leading)
                                        }
                                    }
                                }

                                HStack {
                                    Spacer()
                                    if let task = appState.selectedTask, appState.canStartSelectedTask {
                                        Button(appState.text("Start Task", "执行任务")) {
                                            Task { await appState.startTask(id: task.id) }
                                        }
                                        .buttonStyle(.bordered)
                                    }
                                    Button(appState.text("Reload Preview", "刷新预览")) {
                                        Task { await appState.loadSelectedRuntimePreview() }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(appState.selectedTask == nil)
                                }
                            }
                        }
                    }
                    .padding(24)
                }
            } else if appState.isLoading {
                ProgressView(appState.text("Loading runtimes…", "正在加载运行时…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(appState.text("No Runtime Selected", "未选择运行时"), systemImage: "server.rack", description: Text(appState.text("Select a runtime from the list.", "请从列表中选择一个运行时。")))
            }
        }
    }

    private func runtimeLine(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.headline)
            Text(value)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct PluginDetailView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        Group {
            if let plugin = appState.selectedPlugin {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(plugin.name)
                                    .font(.title2.weight(.semibold))
                                HStack {
                                    StatusBadge(label: plugin.version, color: Brand.reference)
                                    StatusBadge(label: appState.displayToken(plugin.status, category: .capabilityStatus), color: plugin.status == "available" ? Brand.action : Brand.waiting)
                                }
                            }
                            Spacer()
                            Button(appState.text("Refresh", "刷新")) {
                                Task { await appState.reloadPlugins() }
                            }
                        }

                        GlassPanel(title: appState.text("Description", "描述")) {
                            Text(plugin.description)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        GlassPanel(title: appState.text("Contributions", "贡献")) {
                            VStack(alignment: .leading, spacing: 14) {
                                pluginContributionSection(
                                    title: appState.text("Runtimes", "运行时"),
                                    items: plugin.runtimes,
                                    emptyText: appState.text("No runtimes contributed.", "没有贡献运行时。"),
                                    color: Brand.ink,
                                    action: { item in
                                        Task { await appState.openRuntime(name: item) }
                                    }
                                )
                                pluginContributionSection(
                                    title: appState.text("Capabilities", "能力"),
                                    items: plugin.capabilities,
                                    emptyText: appState.text("No capabilities contributed.", "没有贡献能力。"),
                                    color: Brand.pine,
                                    action: { item in
                                        Task { await appState.openCapability(name: item) }
                                    }
                                )
                                pluginContributionSection(
                                    title: appState.text("Workflows", "工作流"),
                                    items: plugin.workflows,
                                    emptyText: appState.text("No workflows contributed.", "没有贡献工作流。"),
                                    color: Brand.amber,
                                    action: { item in
                                        Task { await appState.openWorkflow(name: item) }
                                    }
                                )
                            }
                        }

                        if !plugin.notes.isEmpty {
                            GlassPanel(title: appState.text("Notes", "说明")) {
                                VStack(alignment: .leading, spacing: 8) {
                                    ForEach(plugin.notes, id: \.self) { note in
                                        Text("• \(note)")
                                            .foregroundStyle(.secondary)
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                }
                            }
                        }

                        GlassPanel(title: appState.text("Recent Task Usage", "最近任务使用")) {
                            RecentTaskUsageView(
                                appState: appState,
                                tasks: appState.pluginUsage,
                                emptyText: appState.text("No recent tasks matched this plugin.", "最近没有任务命中这个插件。"),
                                openTask: { taskID in
                                    Task { await appState.openTask(id: taskID) }
                                }
                            )
                        }
                    }
                    .padding(24)
                }
            } else if appState.isLoading {
                ProgressView(appState.text("Loading plugins…", "正在加载插件…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(appState.text("No Plugin Selected", "未选择插件"), systemImage: "shippingbox", description: Text(appState.text("Select a plugin from the list.", "请从列表中选择一个插件。")))
            }
        }
    }

    @ViewBuilder
    private func pluginContributionSection(
        title: String,
        items: [String],
        emptyText: String,
        color: Color,
        action: @escaping (String) -> Void
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.headline)
            if items.isEmpty {
                Text(emptyText)
                    .foregroundStyle(.secondary)
            } else {
                FlowLayout(items: items) { item in
                    Button(action: { action(item) }) {
                        StatusBadge(label: item, color: color)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

}

private struct RecentTaskUsageView: View {
    @ObservedObject var appState: AppState
    let tasks: [UsageTaskSummary]
    let emptyText: String
    let openTask: (String) -> Void

    var body: some View {
        if tasks.isEmpty {
            Text(emptyText)
                .foregroundStyle(.secondary)
        } else {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(tasks) { task in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(task.objective)
                                    .font(.headline)
                                Text(task.id)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: taskStatusColor(task.status))
                        }
                        HStack {
                            Text(task.updatedAt, style: .relative)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Spacer()
                            Button(appState.text("Open Task", "打开任务")) {
                                openTask(task.id)
                            }
                            .buttonStyle(.link)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    private func taskStatusColor(_ status: String) -> Color {
        switch status {
        case "done":
            return Brand.action
        case "blocked":
            return Brand.danger
        case "executing", "verifying":
            return Brand.waiting
        default:
            return Brand.ink
        }
    }
}

private struct WorkflowDetailView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        Group {
            if let workflow = appState.selectedWorkflow {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(workflow.name)
                                    .font(.title2.weight(.semibold))
                                HStack {
                                    StatusBadge(label: workflow.handler, color: Brand.reference)
                                }
                            }
                            Spacer()
                            Button(appState.text("Refresh", "刷新")) {
                                Task { await appState.reloadWorkflows() }
                            }
                        }

                        GlassPanel(title: appState.text("Description", "描述")) {
                            Text(workflow.description)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        GlassPanel(title: appState.text("Entrypoint", "入口")) {
                            Text(workflow.entrypoint)
                                .font(.body.monospaced())
                                .foregroundStyle(.secondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        GlassPanel(title: appState.text("Tags", "标签")) {
                            if workflow.tags.isEmpty {
                                Text(appState.text("No workflow tags.", "没有工作流标签。"))
                                    .foregroundStyle(.secondary)
                            } else {
                                FlowLayout(items: workflow.tags) { tag in
                                    StatusBadge(label: tag, color: Brand.amber)
                                }
                            }
                        }

                        GlassPanel(title: appState.text("Provided By Plugins", "来源插件")) {
                            if appState.pluginsForSelectedWorkflow.isEmpty {
                                Text(appState.text("No plugin bindings found.", "没有找到插件绑定。"))
                                    .foregroundStyle(.secondary)
                            } else {
                                FlowLayout(items: appState.pluginsForSelectedWorkflow) { plugin in
                                    Button(action: {
                                        Task { await appState.openPlugin(name: plugin.name) }
                                    }) {
                                        StatusBadge(label: plugin.name, color: Brand.ink)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                    }
                    .padding(24)
                }
            } else if appState.isLoading {
                ProgressView(appState.text("Loading workflows…", "正在加载工作流…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(appState.text("No Workflow Selected", "未选择工作流"), systemImage: "point.3.connected.trianglepath.dotted", description: Text(appState.text("Select a workflow from the list.", "请从列表中选择一个工作流。")))
            }
        }
    }
}

private struct ReminderDetailView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let result = appState.latestSchedulerResult {
                    GlassPanel(title: appState.text("Reminder Flow", "提醒流状态")) {
                        VStack(alignment: .leading, spacing: 10) {
                            schedulerLine(appState.text("Discovered", "发现"), "\(result.discoveredCount)")
                            schedulerLine(appState.text("Auto Accepted", "自动接受"), "\(result.autoAcceptedCount)")
                            schedulerLine(appState.text("Auto Started", "自动启动"), "\(result.autoStartedCount)")
                            schedulerLine(appState.text("Auto Verified", "自动验证"), "\(result.autoVerifiedCount)")
                            schedulerLine(appState.text("Stalled Reminders", "停滞提醒"), "\(result.stalledReminderCount)")
                            schedulerLine(appState.text("Escalations", "升级"), "\(result.escalatedCount)")
                        }
                    }
                }

                GlassPanel(title: appState.text("Quick Reminder", "快速提醒")) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(appState.text("Capture a follow-up quickly without leaving the current context.", "不用离开当前页面，也可以快速记下一条后续提醒。"))
                            .foregroundStyle(.secondary)
                        TextField(appState.text("Title", "标题"), text: $appState.reminderDraft.title)
                            .textFieldStyle(.roundedBorder)
                        TextField(appState.text("Note", "备注"), text: $appState.reminderDraft.note)
                            .textFieldStyle(.roundedBorder)
                        TextField(appState.text("Due Hint", "到期提示"), text: $appState.reminderDraft.dueHint)
                            .textFieldStyle(.roundedBorder)

                        HStack {
                            Spacer()
                            Button(appState.text("Create Reminder", "创建提醒")) {
                                Task { await appState.createReminder() }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                }

                if let reminder = appState.selectedReminder {
                    GlassPanel(title: appState.text("Reminder Snapshot", "提醒摘要")) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(reminder.title)
                                .font(.title3.weight(.semibold))

                            Text(appState.text("This reminder is a pacing tool. You can acknowledge it, move it, turn it into work, or follow the task it came from.", "这条提醒是节奏管理工具。你可以确认它、重新安排、转成任务，或者回到它关联的原始任务。"))
                                .foregroundStyle(.secondary)

                            HStack(alignment: .top, spacing: 12) {
                                reminderSummaryPill(
                                    title: appState.text("Due Hint", "到期提示"),
                                    value: reminder.dueHint,
                                    color: Brand.waiting
                                )
                                reminderSummaryPill(
                                    title: appState.text("Scheduled", "计划时间"),
                                    value: reminder.scheduledFor.formatted(date: .abbreviated, time: .shortened),
                                    color: Brand.pine
                                )
                                reminderSummaryPill(
                                    title: appState.text("Origin", "来源"),
                                    value: reminder.origin ?? "n/a",
                                    color: Brand.ink
                                )
                            }

                            if let sourceTaskID = reminder.sourceTaskID {
                                HStack {
                                    Text(appState.text("Source Task", "源任务"))
                                    Spacer()
                                    Button(sourceTaskID) {
                                        Task { await appState.openTask(id: sourceTaskID) }
                                    }
                                    .buttonStyle(.link)
                                }
                            }
                            if let lastSeenAt = reminder.lastSeenAt {
                                schedulerLine(appState.text("Last Seen", "最近查看"), lastSeenAt.formatted(date: .abbreviated, time: .shortened))
                            }

                            HStack {
                                Button(appState.text("Mark Seen", "标记已读")) {
                                    Task { await appState.markSelectedReminderSeen() }
                                }
                                Button(appState.text("Reschedule", "重新安排")) {
                                    Task { await appState.rescheduleSelectedReminder() }
                                }
                                Spacer()
                                Button(appState.text("Create Task From Reminder", "从提醒创建任务")) {
                                    appState.presentCreateTask(
                                        objective: reminder.title,
                                        successCriteria: ["Resolve or acknowledge the reminder."],
                                        tags: ["reminder", reminder.origin ?? "scheduler"],
                                        riskLevel: "low"
                                    )
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        }
                    }

                    GlassPanel(title: appState.text("Reminder Note", "提醒备注")) {
                        if reminder.note.isEmpty {
                            Text(appState.text("No note attached to this reminder.", "这条提醒还没有备注。"))
                                .foregroundStyle(.secondary)
                        } else {
                            Text(reminder.note)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }

                    GlassPanel(title: appState.text("Adjust Timing", "调整时间")) {
                        VStack(alignment: .leading, spacing: 12) {
                            Text(appState.text("Edit the due hint and reschedule when the current pacing no longer fits.", "当当前节奏不合适时，修改到期提示并重新安排。"))
                                .foregroundStyle(.secondary)

                            TextField(appState.text("New Due Hint", "新的到期提示"), text: $appState.reminderDraft.dueHint)
                                .textFieldStyle(.roundedBorder)

                            HStack {
                                Button(appState.text("Delete", "删除")) {
                                    Task { await appState.deleteSelectedReminder() }
                                }
                                .foregroundStyle(Brand.danger)
                                Spacer()
                                Button(appState.text("Reschedule", "重新安排")) {
                                    Task { await appState.rescheduleSelectedReminder() }
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        }
                    }
                } else {
                    GlassPanel(title: appState.text("Reminder Detail", "提醒详情")) {
                        Text(appState.text("Select a reminder from the workspace to inspect it and decide whether to acknowledge, reschedule, or turn it into work.", "请从工作台选择一条提醒，再决定是确认、重排还是转成任务。"))
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(24)
        }
    }

    private func schedulerLine(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value)
                .foregroundStyle(.secondary)
        }
    }

    private func reminderSummaryPill(title: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline)
                .foregroundStyle(color)
                .lineLimit(2)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(color.opacity(0.10))
        )
    }
}

private struct EventStreamView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        List(appState.events) { event in
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(event.eventType)
                        .font(.headline)
                    Spacer()
                    Text(event.createdAt.formatted(date: .abbreviated, time: .shortened))
                        .foregroundStyle(.secondary)
                }
                if let taskID = event.taskReferenceID {
                    Button(appState.text("Open Related Task", "打开关联任务")) {
                        Task { await appState.openTask(id: taskID) }
                    }
                    .buttonStyle(.link)
                }
                Button(appState.text("Create Task From Event", "从事件创建任务")) {
                    appState.presentCreateTask(
                        objective: "Follow up: \(event.eventType)",
                        successCriteria: ["Review the event payload and decide the next action."],
                        tags: ["event_followup", event.eventType],
                        riskLevel: "low"
                    )
                }
                .buttonStyle(.link)
                if event.payload.isEmpty {
                    Text(appState.text("No payload", "没有载荷"))
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(event.payload.keys.sorted(), id: \.self) { key in
                        HStack(alignment: .top) {
                            Text(key)
                                .foregroundStyle(.secondary)
                                .frame(width: 120, alignment: .leading)
                            if let taskID = event.taskReferenceID(forKey: key),
                               let label = event.payload[key]?.displayText {
                                Button(label) {
                                    Task { await appState.openTask(id: taskID) }
                                }
                                .buttonStyle(.link)
                            } else {
                                Text(event.payload[key]?.displayText ?? "")
                            }
                        }
                    }
                }
            }
            .padding(.vertical, 6)
        }
        .listStyle(.inset)
        .overlay {
            if appState.events.isEmpty && !appState.isLoading {
                ContentUnavailableView(
                    appState.text("No Events Yet", "还没有事件"),
                    systemImage: "waveform.path.ecg.rectangle",
                    description: Text(appState.backendStatus == .disconnected ? appState.text("Reconnect to the backend to load the event stream.", "重新连接后端以加载事件流。") : appState.text("Event history will appear here after the system records activity.", "系统记录活动后，事件历史会显示在这里。"))
                )
            }
        }
    }
}

private struct SelfProfileView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    BrandSectionTitle(
                        title: appState.text("Self Profile", "自我画像"),
                        subtitle: appState.text("Persistent goals, boundaries, and operating preferences.", "持久化的目标、边界和运行偏好。")
                    )
                    Spacer()
                    Button(appState.text("Reset", "重置")) {
                        appState.selfProfileDraft = appState.selfProfile
                        appState.selfPreferencesText = {
                            let encoder = JSONEncoder()
                            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
                            let data = try? encoder.encode(appState.selfProfile.preferences)
                            return data.flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
                        }()
                    }
                    Button(appState.text("Save", "保存")) {
                        Task { await appState.saveSelfProfile() }
                    }
                    .buttonStyle(.borderedProminent)
                }

                GlassPanel(title: appState.text("Identity", "身份")) {
                    VStack(alignment: .leading, spacing: 12) {
                        labeledTextField(appState.text("Current Phase", "当前阶段"), text: $appState.selfProfileDraft.currentPhase)
                        labeledTextField(appState.text("Risk Style", "风险风格"), text: $appState.selfProfileDraft.riskStyle)
                        labeledTextField(appState.text("Persona Identity", "人格身份"), text: $appState.selfProfileDraft.personaAnchor.identityStatement)
                        labeledTextField(appState.text("Persona Tone", "人格语气"), text: $appState.selfProfileDraft.personaAnchor.tone)
                        labeledTextField(appState.text("Planning Style", "规划风格"), text: $appState.selfProfileDraft.personaAnchor.defaultPlanningStyle)
                        labeledTextField(appState.text("Autonomy Preference", "自治偏好"), text: $appState.selfProfileDraft.personaAnchor.autonomyPreference)
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Long-Term Goals", "长期目标")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.longTermGoals },
                            set: { appState.selfProfileDraft.longTermGoals = $0 }
                        ))
                    }
                    GlassPanel(title: appState.text("Values", "价值观")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.values },
                            set: { appState.selfProfileDraft.values = $0 }
                        ))
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Session Focus", "会话焦点")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.sessionContext.activeFocus },
                            set: { appState.selfProfileDraft.sessionContext.activeFocus = $0 }
                        ))
                    }
                    GlassPanel(title: appState.text("Open Loops", "未完成回路")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.sessionContext.openLoops },
                            set: { appState.selfProfileDraft.sessionContext.openLoops = $0 }
                        ))
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Recent Decisions", "最近决策")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.sessionContext.recentDecisions },
                            set: { appState.selfProfileDraft.sessionContext.recentDecisions = $0 }
                        ))
                    }
                    GlassPanel(title: appState.text("Current Commitments", "当前承诺")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.sessionContext.currentCommitments },
                            set: { appState.selfProfileDraft.sessionContext.currentCommitments = $0 }
                        ))
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Goal Graph", "目标图谱")) {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(appState.goals) { goal in
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(goal.title)
                                                .font(.headline)
                                            Text("\(goal.kind) • \(goal.status)")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        Button(appState.text("Plan", "规划")) {
                                            Task { await appState.planGoal(goal) }
                                        }
                                        Button(appState.text("Advance", "推进")) {
                                            Task {
                                                await appState.refreshGoalProgress(goal, progress: min(goal.progress + 0.1, 1.0))
                                            }
                                        }
                                    }
                                    if !goal.successMetrics.isEmpty {
                                        Text(goal.successMetrics.joined(separator: " · "))
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                }
                                Divider()
                            }

                            TextField(appState.text("Goal Title", "目标标题"), text: $appState.createGoalDraft.title)
                                .textFieldStyle(.roundedBorder)
                            TextField(appState.text("Goal Summary", "目标摘要"), text: $appState.createGoalDraft.summary, axis: .vertical)
                                .textFieldStyle(.roundedBorder)
                            TextField(appState.text("Success Metrics (one per line)", "成功指标（每行一个）"), text: $appState.createGoalDraft.successMetricsText, axis: .vertical)
                                .textFieldStyle(.roundedBorder)
                            HStack {
                                Picker(appState.text("Kind", "类型"), selection: $appState.createGoalDraft.kind) {
                                    Text("Project").tag("project")
                                    Text("Initiative").tag("initiative")
                                    Text("North Star").tag("north_star")
                                }
                                Picker(appState.text("Status", "状态"), selection: $appState.createGoalDraft.status) {
                                    Text("Active").tag("active")
                                    Text("On Hold").tag("on_hold")
                                }
                            }
                            Button(appState.text("Create Goal", "创建目标")) {
                                Task { await appState.createGoal() }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }

                    GlassPanel(title: appState.text("Device Registry", "设备注册")) {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(appState.devices) { device in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(device.name)
                                        .font(.headline)
                                    Text("\(device.deviceClass) • \(device.status)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    if !device.capabilities.isEmpty {
                                        Text(device.capabilities.joined(separator: ", "))
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                }
                                Divider()
                            }

                            TextField(appState.text("Device ID", "设备 ID"), text: $appState.deviceDraft.id)
                                .textFieldStyle(.roundedBorder)
                            TextField(appState.text("Device Name", "设备名称"), text: $appState.deviceDraft.name)
                                .textFieldStyle(.roundedBorder)
                            HStack {
                                TextField(appState.text("Device Class", "设备类型"), text: $appState.deviceDraft.deviceClass)
                                    .textFieldStyle(.roundedBorder)
                                TextField(appState.text("Status", "状态"), text: $appState.deviceDraft.status)
                                    .textFieldStyle(.roundedBorder)
                            }
                            TextField(appState.text("Capabilities csv", "能力 csv"), text: $appState.deviceDraft.capabilitiesText)
                                .textFieldStyle(.roundedBorder)
                            Button(appState.text("Register Device", "注册设备")) {
                                Task { await appState.upsertDevice() }
                            }
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Boundaries", "边界")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.boundaries },
                            set: { appState.selfProfileDraft.boundaries = $0 }
                        ))
                    }
                    GlassPanel(title: appState.text("Relationship Network", "关系网络")) {
                        multiLineEditor(text: listBinding(
                            get: { appState.selfProfileDraft.relationshipNetwork },
                            set: { appState.selfProfileDraft.relationshipNetwork = $0 }
                        ))
                    }
                }

                GlassPanel(title: appState.text("Preferences JSON", "偏好 JSON")) {
                    TextEditor(text: $appState.selfPreferencesText)
                        .font(.body.monospaced())
                        .frame(minHeight: 220)
                        .overlay {
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                        }
                }
            }
            .padding(24)
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private func labeledTextField(_ title: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.headline)
            TextField(title, text: text)
                .textFieldStyle(.roundedBorder)
        }
    }

    private func multiLineEditor(text: Binding<String>) -> some View {
        TextEditor(text: text)
            .frame(minHeight: 160)
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
            }
    }

    private func listBinding(get: @escaping () -> [String], set: @escaping ([String]) -> Void) -> Binding<String> {
        Binding(
            get: { get().joined(separator: "\n") },
            set: { newValue in
                set(
                    newValue
                        .split(whereSeparator: \.isNewline)
                        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                        .filter { !$0.isEmpty }
                )
            }
        )
    }
}

private struct CandidateControlView: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                BrandHero(
                    eyebrow: appState.text("Decision Support", "决策支持"),
                    title: appState.text("Candidate Desk", "候选事项页"),
                    subtitle: appState.text("Review proactive suggestions, decide what should turn into real work, and keep follow-up items from going stale.", "查看系统主动提出的建议，决定哪些应该转成正式任务，并防止后续事项长期搁置。")
                )

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 200), spacing: 16)], spacing: 16) {
                    MetricCard(title: appState.text("Open Candidates", "当前候选"), value: "\(appState.candidates.count)", accent: Brand.active)
                    MetricCard(title: appState.text("Auto Acceptable", "可自动接受"), value: "\(autoAcceptableCandidates)", accent: Brand.action)
                    MetricCard(title: appState.text("Need Confirmation", "需要确认"), value: "\(needsConfirmationCandidates)", accent: Brand.waiting)
                    MetricCard(title: appState.text("High Priority", "高优先级"), value: "\(highPriorityCandidates)", accent: Brand.reference)
                }

                GlassPanel(title: appState.text("Candidate Actions", "候选操作")) {
                    HStack {
                        Text(appState.text("Use this page to decide what should become tracked work now, what can wait, and what the scheduler should keep watching.", "在这里判断哪些应该立刻变成任务，哪些可以延后，以及哪些继续由调度器观察。"))
                            .foregroundStyle(.secondary)
                        Spacer()
                        if appState.autoRefreshEnabled {
                            Label(appState.text("Auto \(appState.refreshIntervalSeconds)s", "自动 \(appState.refreshIntervalSeconds) 秒"), systemImage: "clock.arrow.trianglehead.counterclockwise.rotate.90")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        if appState.backendStatus == .disconnected {
                            Button(appState.text("Retry", "重试")) {
                                Task { await appState.startupProbe() }
                            }
                        }
                        Button(appState.text("Refresh", "刷新")) {
                            Task { await appState.reloadCandidates() }
                        }
                        Button(appState.text("Auto Accept Eligible", "自动接受可处理项")) {
                            Task { await appState.autoAcceptEligibleCandidates() }
                        }
                        Button(appState.text("Run Scheduler", "运行调度")) {
                            Task { await appState.runSchedulerTick() }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }

                GlassPanel(title: appState.text("Scheduler Tuning", "调度器设置")) {
                    HStack(spacing: 16) {
                        Stepper(appState.text("Candidate Limit: \(appState.schedulerDraft.candidateLimit)", "候选上限：\(appState.schedulerDraft.candidateLimit)"), value: $appState.schedulerDraft.candidateLimit, in: 1...100)
                        Stepper(appState.text("Stale After: \(appState.schedulerDraft.staleAfterMinutes)m", "停滞阈值：\(appState.schedulerDraft.staleAfterMinutes) 分钟"), value: $appState.schedulerDraft.staleAfterMinutes, in: 1...10080)
                        Stepper(appState.text("Escalate After Hits: \(appState.schedulerDraft.escalateAfterHits)", "升级触发次数：\(appState.schedulerDraft.escalateAfterHits)"), value: $appState.schedulerDraft.escalateAfterHits, in: 1...20)
                    }
                }

                if let result = appState.latestSchedulerResult {
                    GlassPanel(title: appState.text("Latest Scheduler Pass", "最近一次调度结果")) {
                        VStack(alignment: .leading, spacing: 8) {
                            summaryLine(appState.text("Discovered", "发现"), "\(result.discoveredCount)")
                            summaryLine(appState.text("Auto Accepted", "自动接受"), "\(result.autoAcceptedCount)")
                            summaryLine(appState.text("Auto Started", "自动启动"), "\(result.autoStartedCount)")
                            summaryLine(appState.text("Auto Verified", "自动验证"), "\(result.autoVerifiedCount)")
                            summaryLine(appState.text("Escalated", "升级"), "\(result.escalatedCount)")
                            summaryLine(appState.text("Skipped", "跳过"), "\(result.skippedCount)")
                            summaryLine(appState.text("Errors", "错误"), "\(result.errorCount)")
                        }
                    }
                }

                candidateSection(
                    title: appState.text("Review Now", "现在处理"),
                    subtitle: appState.text("High-signal or high-priority items that should be decided first.", "信号最强或优先级最高、应该先做决定的事项。"),
                    candidates: reviewNowCandidates
                )

                candidateSection(
                    title: appState.text("Auto-Ready", "适合自动接受"),
                    subtitle: appState.text("Candidates the system already believes are safe to accept automatically.", "系统已经认为可以安全自动接受的候选项。"),
                    candidates: autoReadyCandidates
                )

                candidateSection(
                    title: appState.text("Later Or Watch", "稍后处理"),
                    subtitle: appState.text("Items worth keeping visible, but not urgent enough to force into work right now.", "值得保留可见性，但还不需要立刻转成任务的事项。"),
                    candidates: laterCandidates
                )

                GlassPanel(title: appState.text("All Candidate Queue", "全部候选队列")) {
                    if appState.candidates.isEmpty {
                        Text(appState.text("No candidates loaded.", "还没有候选项。"))
                            .foregroundStyle(.secondary)
                    } else {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(appState.candidates) { candidate in
                                CandidateDecisionCard(appState: appState, candidate: candidate)
                            }
                        }
                    }
                }

                if let result = appState.latestAutoAcceptResult, (!result.skipDetails.isEmpty || !result.errors.isEmpty) {
                    GlassPanel(title: appState.text("Last Auto Accept Details", "最近一次自动接受详情")) {
                        VStack(alignment: .leading, spacing: 12) {
                            if !result.skipDetails.isEmpty {
                                Text(appState.text("Skipped", "跳过"))
                                    .font(.headline)
                                ForEach(result.skipDetails) { detail in
                                    Text("\(detail.title): \(detail.reason)")
                                        .foregroundStyle(.secondary)
                                }
                            }
                            if !result.errors.isEmpty {
                                Text(appState.text("Errors", "错误"))
                                    .font(.headline)
                                ForEach(result.errors, id: \.self) { error in
                                    Text(error)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }

                if let result = appState.latestSchedulerResult, (!result.skipDetails.isEmpty || !result.errors.isEmpty || !result.escalations.isEmpty) {
                    GlassPanel(title: appState.text("Scheduler Details", "调度详情")) {
                        VStack(alignment: .leading, spacing: 12) {
                            if !result.escalations.isEmpty {
                                Text(appState.text("Escalations", "升级"))
                                    .font(.headline)
                                ForEach(result.escalations) { escalation in
                                    HStack {
                                        Text("\(escalation.policyName):")
                                            .foregroundStyle(.secondary)
                                        Button(escalation.taskID) {
                                            Task { await appState.openTask(id: escalation.taskID) }
                                        }
                                        .buttonStyle(.link)
                                        if let escalationTaskID = escalation.escalationTaskID {
                                            Text("->")
                                                .foregroundStyle(.secondary)
                                            Button(escalationTaskID) {
                                                Task { await appState.openTask(id: escalationTaskID) }
                                            }
                                            .buttonStyle(.link)
                                        }
                                    }
                                }
                            }
                            if !result.skipDetails.isEmpty {
                                Text(appState.text("Skipped", "跳过"))
                                    .font(.headline)
                                ForEach(result.skipDetails) { detail in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("\(detail.title): \(detail.reason)")
                                            .foregroundStyle(.secondary)
                                        if let sourceTaskID = detail.sourceTaskID {
                                            Button(appState.text("Open Source Task", "打开源任务")) {
                                                Task { await appState.openTask(id: sourceTaskID) }
                                            }
                                            .buttonStyle(.link)
                                        }
                                    }
                                }
                            }
                            if !result.errors.isEmpty {
                                Text(appState.text("Errors", "错误"))
                                    .font(.headline)
                                ForEach(result.errors, id: \.self) { error in
                                    Text(error)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .padding(24)
        }
        .background(Brand.dashboardGradient(for: colorScheme))
        .task {
            if appState.candidates.isEmpty {
                await appState.reloadCandidates()
            }
        }
    }

    private var reviewNowCandidates: [CandidateTask] {
        appState.candidates.filter { $0.priority >= 7 || $0.needsConfirmation }.sorted { $0.priority > $1.priority }
    }

    private var autoReadyCandidates: [CandidateTask] {
        appState.candidates.filter(\.autoAcceptable).sorted { $0.priority > $1.priority }
    }

    private var laterCandidates: [CandidateTask] {
        appState.candidates.filter { !$0.autoAcceptable && $0.priority < 7 && !$0.needsConfirmation }
            .sorted { $0.priority > $1.priority }
    }

    private var autoAcceptableCandidates: Int {
        appState.candidates.filter(\.autoAcceptable).count
    }

    private var needsConfirmationCandidates: Int {
        appState.candidates.filter(\.needsConfirmation).count
    }

    private var highPriorityCandidates: Int {
        appState.candidates.filter { $0.priority >= 7 }.count
    }

    private func candidateSection(title: String, subtitle: String, candidates: [CandidateTask]) -> some View {
        GlassPanel(title: title) {
            VStack(alignment: .leading, spacing: 12) {
                Text(subtitle)
                    .foregroundStyle(.secondary)
                if candidates.isEmpty {
                    EmptyWorkspaceState(
                        title: appState.text("Nothing here right now", "这里暂时没有内容"),
                        detail: appState.text("When the scheduler finds something that fits this lane, it will appear here.", "当调度器发现适合这条分区的事项时，会显示在这里。")
                    )
                } else {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(candidates.prefix(4)) { candidate in
                            CandidateDecisionCard(appState: appState, candidate: candidate)
                        }
                    }
                }
            }
        }
    }

    private func summaryLine(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value)
                .foregroundStyle(.secondary)
        }
    }
}

private struct CandidateDecisionCard: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme
    let candidate: CandidateTask

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(candidate.title)
                        .font(.headline)
                    Text(candidate.detail)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                Spacer()
                Button(appState.text("Defer", "延后")) {
                    appState.openDeferSheet(for: candidate)
                }
                Button(appState.text("Accept", "接受")) {
                    Task { await appState.acceptCandidate(candidate) }
                }
                .buttonStyle(.borderedProminent)
            }

            HStack {
                StatusBadge(label: appState.displayToken(candidate.kind, category: .candidateKind), color: Brand.active)
                StatusBadge(label: "P\(candidate.priority)", color: Brand.waiting)
                if candidate.autoAcceptable {
                    StatusBadge(label: appState.text("Auto", "自动"), color: Brand.action)
                }
                if candidate.needsConfirmation {
                    StatusBadge(label: appState.text("Needs Confirmation", "需要确认"), color: Brand.danger)
                }
            }

            if let sourceTaskID = candidate.sourceTaskID {
                HStack {
                    Text(appState.text("Source Task", "源任务"))
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button(sourceTaskID) {
                        Task { await appState.openTask(id: sourceTaskID) }
                    }
                    .buttonStyle(.link)
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Brand.panelFill(for: colorScheme))
                .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
        )
    }
}

private struct DeferCandidateSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(appState.text("Defer Candidate", "延后候选项"))
                .font(.title2.weight(.semibold))

            if let candidate = appState.selectedCandidateForDefer {
                Text(candidate.title)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text(appState.text("Due Hint", "到期提示"))
                    .font(.headline)
                TextField(appState.text("later today", "比如今天稍后"), text: $appState.candidateDeferDraft.dueHint)
                    .textFieldStyle(.roundedBorder)
            }

            Spacer()

            HStack {
                Spacer()
                Button(appState.text("Cancel", "取消")) {
                    dismiss()
                }
                Button(appState.text("Defer", "延后")) {
                    Task { await appState.deferSelectedCandidate() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
    }
}

private struct TaskDetailView: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme
    @Binding var selection: AppState.TaskDetailSection
    let task: TaskRecord?
    let timeline: [TimelineItem]
    let relations: [EntityRelation]
    let runs: [ExecutionRunRecord]
    let isLoading: Bool
    let isLoadingContext: Bool

    var body: some View {
        Group {
            if let task {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(task.objective)
                                    .font(.title2.weight(.semibold))
                                HStack {
                                    StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: color(for: task.status))
                                    StatusBadge(label: appState.displayToken(task.riskLevel, category: .riskLevel), color: Brand.waiting)
                                    StatusBadge(label: appState.displayToken(task.executionMode, category: .executionMode), color: Brand.active)
                                }
                            }
                            Spacer()
                        }

                        SpotlightPanel(
                            title: appState.text("Execution Summary", "执行摘要"),
                            eyebrow: appState.text("Live Task", "执行中任务"),
                            accentA: Brand.active,
                            accentB: Brand.waiting
                        ) {
                            VStack(alignment: .leading, spacing: 12) {
                                executionLine(appState.text("Owner", "执行者"), task.owner)
                                executionLine(appState.text("Updated", "最近更新"), task.updatedAt.formatted(date: .abbreviated, time: .shortened))
                                executionLine(appState.text("Runtime", "运行时"), task.runtimeName ?? task.executionPlan.runtimeName ?? appState.text("Automatic", "自动选择"))
                                if let blockerReason = task.blockerReason, !blockerReason.isEmpty {
                                    executionLine(appState.text("Current Blocker", "当前阻塞"), blockerReason)
                                } else {
                                    executionLine(appState.text("Current Guidance", "当前建议"), currentGuidance(for: task))
                                }
                                HStack {
                                    if appState.canPlanSelectedTask {
                                        Button(appState.text("Plan Task", "规划任务")) {
                                            Task { await appState.planSelectedTask() }
                                        }
                                    }
                                    if appState.canStartSelectedTask {
                                        Button(appState.text("Start Task", "开始任务")) {
                                            Task { await appState.startSelectedTask() }
                                        }
                                        .buttonStyle(.borderedProminent)
                                    }
                                    if appState.canConfirmSelectedTask {
                                        Button(appState.text("Review Confirmation", "处理确认")) {
                                            appState.isPresentingConfirmSheet = true
                                        }
                                    }
                                    if appState.canVerifySelectedTask {
                                        Button(appState.text("Verify Output", "验证输出")) {
                                            appState.isPresentingVerifySheet = true
                                        }
                                    }
                                }
                            }
                        }

                        Picker(appState.text("Section", "分区"), selection: $selection) {
                            ForEach(AppState.TaskDetailSection.allCases) { section in
                                Text(localizedSectionTitle(section)).tag(section)
                            }
                        }
                        .pickerStyle(.segmented)

                        switch selection {
                        case .summary:
                            detailSection(appState.text("Success Criteria", "成功标准"), items: task.successCriteria, empty: appState.text("No success criteria.", "没有成功标准。"))
                            detailSection(appState.text("Immediate Plan", "当前计划"), items: task.executionPlan.steps.map { "\($0.capabilityName): \($0.purpose)" }, empty: appState.text("No plan steps yet.", "还没有计划步骤。"))
                            detailSection(appState.text("Artifacts", "产物"), items: task.artifactPaths, empty: appState.text("No artifacts produced yet.", "还没有生成产物。"))
                            detailSection(appState.text("Verification Notes", "验证说明"), items: task.verificationNotes, empty: appState.text("还没有验证说明。", "还没有验证说明。"))
                            detailSection(appState.text("Tags", "标签"), items: task.tags, empty: appState.text("No tags attached.", "没有附加标签。"))
                        case .timeline:
                            timelineSection
                        case .relations:
                            relationsSection
                        case .runs:
                            runsSection
                        }

                        if let blockerReason = task.blockerReason, !blockerReason.isEmpty {
                            GlassPanel(title: appState.text("Blocker", "阻塞原因")) {
                                Text(blockerReason)
                            }
                        }
                    }
                    .padding(24)
                }
                .background(Brand.dashboardGradient(for: colorScheme))
            } else if isLoading {
                ProgressView(appState.text("Loading task details…", "正在加载任务详情…"))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(appState.text("No Task Selected", "未选择任务"), systemImage: "square.and.pencil", description: Text(appState.text("Create a task or select one from the list.", "创建一个任务，或从列表中选择一个任务。")))
            }
        }
    }

    private func executionLine(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.headline)
            Text(value)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func currentGuidance(for task: TaskRecord) -> String {
        if let firstStep = task.executionPlan.steps.first {
            return "\(firstStep.capabilityName): \(firstStep.purpose)"
        }
        switch task.status {
        case "captured":
            return appState.text("Plan the task to create a concrete execution path.", "先规划任务，形成明确执行路径。")
        case "planned":
            return appState.text("Start execution and produce the first artifact or side effect.", "开始执行，生成第一个产物或外部动作。")
        case "executing":
            return appState.text("Keep the task moving until there is something to verify.", "继续推进任务，直到产出可验证结果。")
        case "verifying":
            return appState.text("Review outputs and mark whether the task really met the goal.", "检查产出，并确认任务是否真的达到目标。")
        case "done":
            return appState.text("Consider reflecting if this task taught something reusable.", "如果这个任务带来了可复用经验，可以考虑复盘。")
        default:
            return appState.text("Review the task context and decide the next safe action.", "查看任务上下文，再决定下一步安全动作。")
        }
    }

    private func detailSection(_ title: String, items: [String], empty: String) -> some View {
        GlassPanel(title: title) {
            if items.isEmpty {
                Text(empty)
                    .foregroundStyle(.secondary)
            } else {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(items, id: \.self) { item in
                        Text(item)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }

    private var timelineSection: some View {
        GlassPanel(title: appState.text("Timeline", "时间线")) {
            if isLoadingContext && timeline.isEmpty {
                ProgressView()
            } else if timeline.isEmpty {
                Text(appState.text("No timeline yet.", "还没有时间线。"))
                    .foregroundStyle(.secondary)
            } else {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(timeline) { item in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(item.title)
                                    .font(.headline)
                                Spacer()
                                Text(item.timestamp.formatted(date: .abbreviated, time: .shortened))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Text(item.phase.capitalized)
                                .font(.caption.weight(.medium))
                                .foregroundStyle(Brand.mint)
                            Text(item.detail)
                                .foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.bottom, 8)
                    }
                }
            }
        }
    }

    private var relationsSection: some View {
        GlassPanel(title: appState.text("Relations", "关联")) {
            if isLoadingContext && relations.isEmpty {
                ProgressView()
            } else if relations.isEmpty {
                Text(appState.text("No relations recorded.", "还没有关联记录。"))
                    .foregroundStyle(.secondary)
            } else {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(relations) { relation in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(appState.displayToken(relation.relationType, category: .relationType))
                                .font(.headline)
                            Text("\(relation.sourceType):\(relation.sourceID) -> \(relation.targetType):\(relation.targetID)")
                                .font(.subheadline)
                            HStack(spacing: 12) {
                                if relation.sourceType == "task" {
                                    Button(appState.text("Open Source Task", "打开源任务")) {
                                        Task { await appState.openTask(id: relation.sourceID) }
                                    }
                                    .buttonStyle(.link)
                                }
                                if relation.targetType == "task" {
                                    Button(appState.text("Open Target Task", "打开目标任务")) {
                                        Task { await appState.openTask(id: relation.targetID) }
                                    }
                                    .buttonStyle(.link)
                                }
                            }
                            if !relation.metadata.isEmpty {
                                Text(relation.metadata.keys.sorted().map { "\($0)=\(relation.metadata[$0]?.displayText ?? "")" }.joined(separator: ", "))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }

    private var runsSection: some View {
        GlassPanel(title: appState.text("Execution Runs", "执行运行")) {
            if isLoadingContext && runs.isEmpty {
                ProgressView()
            } else if runs.isEmpty {
                Text(appState.text("No execution runs yet.", "还没有执行记录。"))
                    .foregroundStyle(.secondary)
            } else {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(runs) { run in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(run.status.capitalized)
                                    .font(.headline)
                                Spacer()
                                Text(run.startedAt.formatted(date: .abbreviated, time: .shortened))
                                    .foregroundStyle(.secondary)
                            }
                            Text(run.id)
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                            Button(run.taskID) {
                                Task { await appState.openTask(id: run.taskID) }
                            }
                            .buttonStyle(.link)
                            Button(appState.text("Inspect Run", "查看运行")) {
                                appState.presentRunInspector(for: run)
                            }
                            .buttonStyle(.link)
                            if let completedAt = run.completedAt {
                                Text(appState.text("Completed: \(completedAt.formatted(date: .abbreviated, time: .shortened))", "完成于：\(completedAt.formatted(date: .abbreviated, time: .shortened))"))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            if !run.metadata.isEmpty {
                                VStack(alignment: .leading, spacing: 4) {
                                    if let runtimeName = run.metadata["runtime_name"]?.stringValue {
                                        Text("runtime=\(runtimeName)")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    if let artifactPath = run.metadata["artifact_path"]?.stringValue {
                                        Text("artifact=\(artifactPath)")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(1)
                                    }
                                    let remaining = run.metadataSummaryExcludingRuntime
                                    if !remaining.isEmpty {
                                        Text(remaining)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }

    private func color(for status: String) -> Color {
        switch status {
        case "done":
            return Brand.action
        case "blocked":
            return Brand.danger
        case "executing":
            return Brand.active
        case "planned":
            return Brand.waiting
        default:
            return .gray
        }
    }

    private func localizedSectionTitle(_ section: AppState.TaskDetailSection) -> String {
        switch section {
        case .summary:
            return appState.text("Summary", "摘要")
        case .timeline:
            return appState.text("Timeline", "时间线")
        case .relations:
            return appState.text("Relations", "关联")
        case .runs:
            return appState.text("Runs", "运行")
        }
    }
}

private struct RunInspectorSheet: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if let run = appState.selectedRun {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(appState.text("Execution Run", "执行运行"))
                            .font(.title2.weight(.semibold))
                        Text(run.id)
                            .font(.caption.monospaced())
                            .foregroundStyle(.secondary)
                        HStack {
                            StatusBadge(label: appState.displayToken(run.status, category: .taskStatus), color: run.status == "done" ? Brand.action : Brand.active)
                            Button(run.taskID) {
                                Task { await appState.openTask(id: run.taskID) }
                            }
                            .buttonStyle(.link)
                        }
                    }
                    Spacer()
                    HStack {
                        Button(appState.text("Open Task", "打开任务")) {
                            Task { await appState.openTask(id: run.taskID) }
                        }
                        .buttonStyle(.link)
                        if let task = appState.tasks.first(where: { $0.id == run.taskID }), ["captured", "planned"].contains(task.status) {
                            Button(appState.text("Re-run Task", "重新执行")) {
                                Task { await appState.startTask(id: run.taskID) }
                            }
                            .buttonStyle(.bordered)
                        }
                        Button(appState.text("Refresh", "刷新")) {
                            Task { await appState.loadSelectedRunContext() }
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Run Context", "运行上下文")) {
                        VStack(alignment: .leading, spacing: 12) {
                            runtimeMetadataSection(for: run)
                        }
                    }

                    GlassPanel(title: appState.text("Timeline", "时间线")) {
                        if appState.isLoadingRunContext && appState.selectedRunTimeline.isEmpty {
                            ProgressView()
                        } else if appState.selectedRunTimeline.isEmpty {
                            Text(appState.text("No run timeline yet.", "还没有运行时间线。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(appState.selectedRunTimeline) { item in
                                    VStack(alignment: .leading, spacing: 4) {
                                        HStack {
                                            Text(item.title)
                                                .font(.headline)
                                            Spacer()
                                            Text(item.timestamp.formatted(date: .abbreviated, time: .shortened))
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        Text(item.phase.capitalized)
                                            .font(.caption.weight(.medium))
                                            .foregroundStyle(Brand.mint)
                                        Text(item.detail)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                    }

                    GlassPanel(title: appState.text("Events", "事件")) {
                        if appState.isLoadingRunContext && appState.selectedRunEvents.isEmpty {
                            ProgressView()
                        } else if appState.selectedRunEvents.isEmpty {
                            Text(appState.text("No run events yet.", "还没有运行事件。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(appState.selectedRunEvents) { event in
                                    VStack(alignment: .leading, spacing: 6) {
                                        HStack {
                                            Text(event.eventType)
                                                .font(.headline)
                                            Spacer()
                                            Text(event.createdAt.formatted(date: .abbreviated, time: .shortened))
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        ForEach(event.payload.keys.sorted(), id: \.self) { key in
                                            HStack(alignment: .top) {
                                                Text(key)
                                                    .foregroundStyle(.secondary)
                                                    .frame(width: 120, alignment: .leading)
                                                Text(event.payload[key]?.displayText ?? "")
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .frame(maxHeight: .infinity, alignment: .top)
            } else {
                ContentUnavailableView(
                    appState.text("No Run Selected", "未选择运行记录"),
                    systemImage: "play.square.stack",
                    description: Text(appState.text("Pick a run from task details to inspect its timeline and event stream.", "请从任务详情中选择一个运行记录，以查看它的时间线和事件流。"))
                )
            }
        }
        .padding(24)
    }

    @ViewBuilder
    private func runtimeMetadataSection(for run: ExecutionRunRecord) -> some View {
        Group {
            if run.metadata.isEmpty {
                Text(appState.text("No run metadata recorded yet.", "还没有记录运行元数据。"))
                    .foregroundStyle(.secondary)
            } else {
                if let runtimeName = run.metadata["runtime_name"]?.stringValue {
                    inspectorLine(appState.text("Runtime", "运行时"), runtimeName)
                }
                if let command = run.metadata["runtime_command_preview"]?.stringValue {
                    inspectorLine(appState.text("Command", "命令"), command)
                }
                if let executedCommand = run.metadata["runtime_executed_command"]?.stringValue, !executedCommand.isEmpty {
                    inspectorLine(appState.text("Executed Command", "执行命令"), executedCommand)
                }
                if let summary = run.metadata["runtime_summary"]?.stringValue, !summary.isEmpty {
                    inspectorLine(appState.text("Summary", "摘要"), summary)
                }
                if let executionStatus = run.metadata["runtime_execution_status"]?.stringValue, !executionStatus.isEmpty {
                    inspectorLine(appState.text("Execution Status", "执行状态"), executionStatus)
                }
                if let exitCode = run.metadata["runtime_exit_code"]?.stringValue {
                    inspectorLine(appState.text("Exit Code", "退出码"), exitCode)
                }
                if let liveExecution = run.metadata["runtime_live_execution"]?.stringValue {
                    inspectorLine(appState.text("Live Execution", "实时执行"), liveExecution)
                }
                if let artifactPath = run.metadata["artifact_path"]?.stringValue {
                    inspectorLine(appState.text("Artifact", "产物"), artifactPath)
                }

                if case .object(let invocationObject) = run.metadata["runtime_invocation"] {
                    if let workingDirectory = invocationObject["working_directory"]?.stringValue {
                        inspectorLine(appState.text("Working Directory", "工作目录"), workingDirectory)
                    }
                    if let mode = invocationObject["invocation_mode"]?.stringValue {
                        inspectorLine(appState.text("Launch Mode", "启动模式"), mode)
                    }
                    if case .object(let envHints) = invocationObject["environment_hints"], !envHints.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(appState.text("Environment Hints", "环境提示"))
                                .font(.headline)
                            ForEach(envHints.keys.sorted(), id: \.self) { key in
                                Text("\(key)=\(envHints[key]?.displayText ?? "")")
                                    .font(.body.monospaced())
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                    }
                    if let prompt = invocationObject["prompt"]?.stringValue, !prompt.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(appState.text("Prompt", "提示"))
                                .font(.headline)
                            Text(prompt)
                                .font(.body.monospaced())
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(12)
                                .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                        }
                    }
                }

                if let stdout = run.metadata["runtime_stdout"]?.stringValue, !stdout.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(appState.text("Stdout", "标准输出"))
                            .font(.headline)
                        Text(stdout)
                            .font(.body.monospaced())
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                            .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                    }
                }

                if let stderr = run.metadata["runtime_stderr"]?.stringValue, !stderr.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(appState.text("Stderr", "标准错误"))
                            .font(.headline)
                        Text(stderr)
                            .font(.body.monospaced())
                            .foregroundStyle(.red)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                            .background(Color.red.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                    }
                }

                let remaining = run.metadataSummaryExcludingRuntime
                if !remaining.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(appState.text("Additional Metadata", "附加元数据"))
                            .font(.headline)
                        Text(remaining)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }

    private func inspectorLine(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.headline)
            Text(value)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private extension ExecutionRunRecord {
    var metadataSummaryExcludingRuntime: String {
        metadata
            .filter { key, _ in
                ![
                    "runtime_name",
                    "runtime_command_preview",
                    "runtime_executed_command",
                    "runtime_summary",
                    "runtime_execution_status",
                    "runtime_exit_code",
                    "runtime_live_execution",
                    "runtime_stdout",
                    "runtime_stderr",
                    "runtime_invocation",
                    "artifact_path",
                ].contains(key)
            }
            .keys
            .sorted()
            .map { "\($0)=\(metadata[$0]?.displayText ?? "")" }
            .joined(separator: ", ")
    }
}

private extension EventRecord {
    var taskReferenceID: String? {
        EventRecord.taskReferenceID(in: payload)
    }

    func taskReferenceID(forKey key: String) -> String? {
        guard ["task_id", "source_task_id", "escalation_task_id"].contains(key) else {
            return nil
        }
        return payload[key]?.stringValue
    }

    static func taskReferenceID(in payload: [String: JSONValue]) -> String? {
        for key in ["task_id", "source_task_id", "escalation_task_id"] {
            if let value = payload[key]?.stringValue, !value.isEmpty {
                return value
            }
        }
        return nil
    }
}

private struct TaskRow: View {
    @ObservedObject var appState: AppState
    let task: TaskRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(task.objective)
                    .font(.headline)
                    .lineLimit(2)
                Spacer()
                Text(task.updatedAt, style: .relative)
                    .foregroundStyle(.secondary)
            }
            HStack {
                StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: Brand.pine)
                StatusBadge(label: appState.displayToken(task.riskLevel, category: .riskLevel), color: Brand.amber)
                if let firstTag = task.tags.first {
                    StatusBadge(label: firstTag, color: .gray.opacity(0.7))
                }
            }
        }
        .padding(.vertical, 6)
    }
}

private struct TaskWorkspaceCard: View {
    @ObservedObject var appState: AppState
    let task: TaskRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(task.objective)
                        .font(.headline)
                        .foregroundStyle(.primary)
                        .lineLimit(2)
                    Text(task.updatedAt, style: .relative)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: taskStatusColor)
            }
            HStack {
                StatusBadge(label: appState.displayToken(task.executionMode, category: .executionMode), color: Brand.pine)
                StatusBadge(label: appState.displayToken(task.riskLevel, category: .riskLevel), color: Brand.amber)
                if let runtimeName = task.runtimeName, !runtimeName.isEmpty {
                    StatusBadge(label: runtimeName, color: Brand.ink)
                }
            }
            if let blocker = task.blockerReason, !blocker.isEmpty {
                Text(blocker)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            } else if let firstStep = task.executionPlan.steps.first {
                Text("\(firstStep.capabilityName): \(firstStep.purpose)")
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(Color.primary.opacity(0.035))
        )
    }

    private var taskStatusColor: Color {
        switch task.status {
        case "done":
            return Brand.mint
        case "blocked":
            return .red
        case "executing", "verifying":
            return Brand.amber
        default:
            return Brand.pine
        }
    }
}

private struct MemoryRow: View {
    @ObservedObject var appState: AppState
    let memory: MemoryRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(memory.title)
                    .font(.headline)
                    .lineLimit(2)
                Spacer()
                Text(memory.createdAt, style: .relative)
                    .foregroundStyle(.secondary)
            }
            HStack {
                StatusBadge(label: appState.displayToken(memory.memoryType, category: .memoryType), color: Brand.pine)
                if let firstTag = memory.tags.first {
                    StatusBadge(label: firstTag, color: Brand.amber)
                }
            }
            Text(memory.content)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 6)
    }
}

private struct CapabilityRow: View {
    @ObservedObject var appState: AppState
    let capability: CapabilityDescriptor

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(capability.name)
                    .font(.headline)
                Spacer()
                StatusBadge(label: appState.displayToken(capability.riskLevel, category: .riskLevel), color: riskColor)
            }
            Text(capability.description)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 6)
    }

    private var riskColor: Color {
        switch capability.riskLevel {
        case "high":
            return .red
        case "medium":
            return Brand.amber
        default:
            return Brand.mint
        }
    }
}

private struct RuntimeRow: View {
    @ObservedObject var appState: AppState
    let runtime: RuntimeDescriptor

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(runtime.name)
                    .font(.headline)
                Spacer()
                StatusBadge(label: runtime.status, color: runtime.status == "available" ? Brand.mint : Brand.amber)
            }
            Text(runtime.description)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            HStack {
                StatusBadge(label: runtime.runtimeType, color: Brand.ink)
                if let rootPath = runtime.rootPath, !rootPath.isEmpty {
                    StatusBadge(label: "root", color: Brand.pine)
                }
            }
        }
        .padding(.vertical, 6)
    }
}

private struct PluginRow: View {
    @ObservedObject var appState: AppState
    let plugin: PluginDescriptor

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(plugin.name)
                    .font(.headline)
                Spacer()
                StatusBadge(
                    label: appState.displayToken(plugin.status, category: .capabilityStatus),
                    color: plugin.status == "available" ? Brand.mint : Brand.amber
                )
            }
            Text(plugin.description)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            HStack {
                StatusBadge(label: "v\(plugin.version)", color: Brand.ink)
                if !plugin.runtimes.isEmpty {
                    StatusBadge(label: "\(plugin.runtimes.count) runtime", color: Brand.ink)
                }
                if !plugin.capabilities.isEmpty {
                    StatusBadge(label: "\(plugin.capabilities.count) capability", color: Brand.pine)
                }
                if !plugin.workflows.isEmpty {
                    StatusBadge(label: "\(plugin.workflows.count) workflow", color: Brand.amber)
                }
            }
        }
        .padding(.vertical, 6)
    }
}

private struct WorkflowRow: View {
    let workflow: WorkflowManifest

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(workflow.name)
                    .font(.headline)
                Spacer()
                StatusBadge(label: workflow.handler, color: Brand.ink)
            }
            Text(workflow.description)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            if !workflow.tags.isEmpty {
                HStack {
                    ForEach(Array(workflow.tags.prefix(2)), id: \.self) { tag in
                        StatusBadge(label: tag, color: Brand.amber)
                    }
                }
            }
        }
        .padding(.vertical, 6)
    }
}

private struct ReminderRow: View {
    let reminder: ReminderRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(reminder.title)
                    .font(.headline)
                    .lineLimit(2)
                Spacer()
                Text(reminder.scheduledFor, style: .relative)
                    .foregroundStyle(.secondary)
            }
            HStack {
                StatusBadge(label: reminder.dueHint, color: Brand.amber)
                if let origin = reminder.origin {
                    StatusBadge(label: origin, color: Brand.pine)
                }
                if reminder.lastSeenAt == nil {
                    StatusBadge(label: "Unseen", color: Brand.mint)
                }
            }
            if !reminder.note.isEmpty {
                Text(reminder.note)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 6)
    }
}

private struct MetricCard: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    let value: String
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                RoundedRectangle(cornerRadius: 16)
                    .fill(accent.gradient)
                    .frame(width: 42, height: 42)
                    .overlay {
                        Image("StatusGlyph")
                            .resizable()
                            .scaledToFit()
                            .padding(9)
                            .foregroundStyle(.white)
                    }
                Spacer()
                Capsule(style: .continuous)
                    .fill(accent.opacity(0.16))
                    .frame(width: 52, height: 10)
            }
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 28, weight: .semibold, design: .rounded))
                .foregroundStyle(.primary)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(
                    LinearGradient(
                        colors: [
                            Brand.panelFill(for: colorScheme),
                            accent.opacity(colorScheme == .dark ? 0.10 : 0.08)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
                }
        )
    }
}

private struct BrandHero: View {
    @Environment(\.colorScheme) private var colorScheme
    let eyebrow: String
    let title: String
    let subtitle: String

    var body: some View {
        HStack(alignment: .center, spacing: 18) {
            ZStack {
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [Brand.pine, Brand.mint],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 84, height: 84)
                Circle()
                    .fill(Color.white.opacity(0.18))
                    .frame(width: 28, height: 28)
                    .offset(x: 22, y: -22)
                Circle()
                    .fill(Color.black.opacity(0.10))
                    .frame(width: 20, height: 20)
                    .offset(x: -20, y: 24)
                Image("StatusGlyph")
                    .resizable()
                    .scaledToFit()
                    .padding(16)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text(eyebrow.uppercased())
                    .font(.caption.weight(.semibold))
                    .tracking(1.2)
                    .foregroundStyle(Brand.mint)
                Text(title)
                    .font(.system(size: 34, weight: .semibold, design: .rounded))
                    .foregroundStyle(.primary)
                Text(subtitle)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(24)
        .background(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: colorScheme == .dark
                            ? [Color.white.opacity(0.05), Brand.pine.opacity(0.18)]
                            : [Color.white.opacity(0.90), Brand.mint.opacity(0.12)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay {
                    RoundedRectangle(cornerRadius: 30, style: .continuous)
                        .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
                }
                .shadow(color: Brand.panelShadow(for: colorScheme), radius: 18, y: 8)
        )
    }
}

private struct SpotlightPanel<Content: View>: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    let eyebrow: String
    let accentA: Color
    let accentB: Color
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                Text(eyebrow.uppercased())
                    .font(.caption.weight(.semibold))
                    .tracking(1.1)
                    .foregroundStyle(accentB)
                Text(title)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(.primary)
            }
            content
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 26, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: colorScheme == .dark
                            ? [Color.white.opacity(0.06), accentA.opacity(0.22), accentB.opacity(0.16)]
                            : [Color.white.opacity(0.96), accentA.opacity(0.12), accentB.opacity(0.09)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(alignment: .topTrailing) {
                    Circle()
                        .fill(accentB.opacity(colorScheme == .dark ? 0.24 : 0.18))
                        .frame(width: 84, height: 84)
                        .blur(radius: 2)
                        .offset(x: 10, y: -12)
                }
                .overlay {
                    RoundedRectangle(cornerRadius: 26, style: .continuous)
                        .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
                }
                .shadow(color: Brand.panelShadow(for: colorScheme), radius: 20, y: 10)
        )
    }
}

private struct BrandSectionTitle: View {
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.title2.weight(.semibold))
                .foregroundStyle(.primary)
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }
}

private struct GlassPanel<Content: View>: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title)
                .font(.headline)
            content
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Brand.panelFill(for: colorScheme))
                .overlay(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
                }
                .shadow(color: Brand.panelShadow(for: colorScheme), radius: 18, y: 8)
        )
    }
}

private struct TagCloud: View {
    let items: [String]
    let emptyText: String

    var body: some View {
        if items.isEmpty {
            Text(emptyText)
                .foregroundStyle(.secondary)
        } else {
            FlowLayout(items: items) { item in
                Text(item)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Capsule().fill(Brand.pine.opacity(0.12)))
            }
        }
    }
}

private struct FlowLayout<Data: RandomAccessCollection, Content: View>: View where Data.Element: Hashable {
    let items: Data
    let content: (Data.Element) -> Content

    init(items: Data, @ViewBuilder content: @escaping (Data.Element) -> Content) {
        self.items = items
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading) {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 120), alignment: .leading)], alignment: .leading, spacing: 10) {
                ForEach(Array(items), id: \.self) { item in
                    content(item)
                }
            }
        }
    }
}

private struct StatusBadge: View {
    let label: String
    let color: Color

    var body: some View {
        Text(label.replacingOccurrences(of: "_", with: " ").capitalized)
            .font(.caption.weight(.medium))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(color.opacity(0.14))
            )
            .foregroundStyle(color)
    }
}

private struct ErrorBanner: View {
    let message: String

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
            Text(message)
                .lineLimit(3)
        }
        .font(.subheadline)
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill(Color.red.opacity(0.12))
        )
    }
}

private struct SuccessBanner: View {
    let message: String

    var body: some View {
        HStack {
            Image(systemName: "checkmark.circle.fill")
            Text(message)
                .lineLimit(3)
        }
        .font(.subheadline)
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill(Brand.mint.opacity(0.15))
        )
    }
}
