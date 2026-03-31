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
            Section("AI OS") {
                ForEach(AppState.SidebarDestination.allCases) { item in
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
            return appState.text("Inbox", "收件箱")
        case .tasks:
            return appState.text("Tasks", "任务")
        case .memory:
            return appState.text("Memory", "记忆")
        case .reminders:
            return appState.text("Reminders", "提醒")
        case .capabilities:
            return appState.text("Capabilities", "能力")
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
            return "tray.and.arrow.down"
        case .tasks:
            return "checklist"
        case .memory:
            return "brain"
        case .reminders:
            return "bell.badge"
        case .capabilities:
            return "switch.2"
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
                    eyebrow: appState.text("Desktop Control", "桌面控制"),
                    title: appState.text("AI OS Control Surface", "AI OS 控制面板"),
                    subtitle: appState.text("Local-first orchestration for tasks, memory, scheduling, and backend operations.", "面向任务、记忆、调度和后端运行的本地优先控制台。")
                )

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 16)], spacing: 16) {
                    MetricCard(title: appState.text("Current Phase", "当前阶段"), value: appState.selfProfile.currentPhase.capitalized, accent: Brand.pine)
                    MetricCard(title: appState.text("Risk Style", "风险风格"), value: appState.selfProfile.riskStyle.capitalized, accent: Brand.amber)
                    MetricCard(title: appState.text("Goal Graph", "目标图谱"), value: "\(appState.goals.count)", accent: Brand.pine)
                    MetricCard(title: appState.text("Devices", "设备"), value: "\(appState.devices.count)", accent: Brand.mint)
                    MetricCard(title: appState.text("Open Tasks", "进行中任务"), value: "\(appState.tasks.filter { $0.status != "done" && $0.status != "archived" }.count)", accent: Brand.mint)
                    MetricCard(title: appState.text("Memory Records", "记忆记录"), value: "\(appState.memories.count)", accent: Brand.ink)
                    MetricCard(title: appState.text("Capabilities", "能力"), value: "\(appState.capabilities.count)", accent: Brand.pine)
                    MetricCard(title: appState.text("Candidates", "候选项"), value: "\(appState.candidates.count)", accent: Brand.amber)
                    MetricCard(title: appState.text("Recent Events", "最近事件"), value: "\(appState.events.count)", accent: Brand.ink)
                    MetricCard(title: appState.text("Backend", "后端"), value: backendLabel, accent: backendAccent)
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Goals", "目标")) {
                        TagCloud(items: appState.selfProfile.longTermGoals, emptyText: appState.text("No long-term goals recorded yet.", "还没有记录长期目标。"))
                    }
                    GlassPanel(title: appState.text("Values", "价值观")) {
                        TagCloud(items: appState.selfProfile.values, emptyText: appState.text("No values recorded yet.", "还没有记录价值观。"))
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Persona Anchor", "人格锚点")) {
                        VStack(alignment: .leading, spacing: 10) {
                            overviewLine(appState.text("Identity", "身份"), appState.selfProfile.personaAnchor.identityStatement)
                            overviewLine(appState.text("Tone", "语气"), appState.selfProfile.personaAnchor.tone)
                            overviewLine(appState.text("Planning Style", "规划风格"), appState.selfProfile.personaAnchor.defaultPlanningStyle)
                            overviewLine(appState.text("Autonomy", "自治方式"), appState.selfProfile.personaAnchor.autonomyPreference)
                        }
                    }
                    GlassPanel(title: appState.text("Session Runtime", "会话运行时")) {
                        VStack(alignment: .leading, spacing: 10) {
                            TagCloud(items: appState.selfProfile.sessionContext.activeFocus, emptyText: appState.text("No active focus.", "当前没有焦点。"))
                            TagCloud(items: appState.selfProfile.sessionContext.currentCommitments, emptyText: appState.text("No commitments.", "当前没有承诺。"))
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Recent Intake", "最近 Intake")) {
                        if let intake = appState.latestIntakeResponse {
                            VStack(alignment: .leading, spacing: 10) {
                                overviewLine(appState.text("Intent", "意图"), appState.displayToken(intake.intent.intentType))
                                overviewLine(appState.text("Goal", "目标"), intake.intent.goal)
                                overviewLine(appState.text("Requested Outcome", "期望结果"), intake.cognition.understanding.requestedOutcome)
                                overviewLine(appState.text("Time Horizon", "时间跨度"), intake.cognition.understanding.timeHorizon)
                                overviewLine(appState.text("Mode", "模式"), appState.displayToken(intake.cognition.suggestedExecutionMode, category: .executionMode))
                                overviewLine(appState.text("Next Step", "下一步"), intake.cognition.suggestedNextStep)
                                if !intake.cognition.suggestedTaskTags.isEmpty {
                                    TagCloud(items: intake.cognition.suggestedTaskTags, emptyText: appState.text("No tags.", "没有标签。"))
                                }
                            }
                        } else if let intent = appState.latestIntentEvaluation {
                            VStack(alignment: .leading, spacing: 10) {
                                overviewLine(appState.text("Intent", "意图"), appState.displayToken(intent.intentType))
                                overviewLine(appState.text("Goal", "目标"), intent.goal)
                                overviewLine(appState.text("Risk", "风险"), appState.displayToken(intent.riskLevel, category: .riskLevel))
                                overviewLine(appState.text("Rationale", "理由"), intent.rationale)
                            }
                        } else {
                            Text(appState.text("No intake activity yet.", "还没有 intake 活动。"))
                                .foregroundStyle(.secondary)
                        }
                    }

                    GlassPanel(title: appState.text("Scheduler Loop", "调度循环")) {
                        if let result = appState.latestSchedulerResult {
                            VStack(alignment: .leading, spacing: 10) {
                                overviewLine(appState.text("Discovered", "发现"), "\(result.discoveredCount)")
                                overviewLine(appState.text("Accepted", "接受"), "\(result.autoAcceptedCount)")
                                overviewLine(appState.text("Started", "启动"), "\(result.autoStartedCount)")
                                overviewLine(appState.text("Verified", "验证"), "\(result.autoVerifiedCount)")
                                overviewLine(appState.text("Escalated", "升级"), "\(result.escalatedCount)")
                            }
                        } else {
                            Text(appState.text("No scheduler run captured yet.", "还没有记录调度运行。"))
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Memory Snapshot", "记忆快照")) {
                        if appState.memories.isEmpty {
                            Text(appState.text("No memory records yet.", "还没有记忆记录。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(appState.memories.prefix(3))) { memory in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(memory.title)
                                            .font(.headline)
                                        Text(appState.displayToken(memory.memoryType, category: .memoryType))
                                            .font(.caption)
                                            .foregroundStyle(Brand.mint)
                                        Text(memory.content)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                }
                            }
                        }
                    }

                    GlassPanel(title: appState.text("Capability Bus", "能力总线")) {
                        if appState.capabilities.isEmpty {
                            Text(appState.text("No capabilities loaded.", "还没有加载能力。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(appState.capabilities) { capability in
                                    HStack(alignment: .top) {
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(capability.name)
                                                .font(.headline)
                                            Text(capability.description)
                                                .foregroundStyle(.secondary)
                                                .lineLimit(2)
                                            if !capability.scopes.isEmpty {
                                                Text(capability.scopes.joined(separator: ", "))
                                                    .font(.caption)
                                                    .foregroundStyle(.secondary)
                                            }
                                        }
                                        Spacer()
                                        StatusBadge(label: appState.displayToken(capability.riskLevel, category: .riskLevel), color: capabilityRiskColor(capability.riskLevel))
                                    }
                                }
                            }
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Goal Graph", "目标图谱")) {
                        if appState.goals.isEmpty {
                            Text(appState.text("No structured goals yet.", "还没有结构化目标。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(appState.goals.prefix(4))) { goal in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(goal.title)
                                            .font(.headline)
                                        Text("\(appState.displayToken(goal.kind)) • \(appState.displayToken(goal.status)) • \(Int(goal.progress * 100))%")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                        if !goal.successMetrics.isEmpty {
                                            Text(goal.successMetrics.joined(separator: " · "))
                                                .foregroundStyle(.secondary)
                                                .lineLimit(2)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    GlassPanel(title: appState.text("Device Mesh", "设备网格")) {
                        if appState.devices.isEmpty {
                            Text(appState.text("No devices registered.", "还没有注册设备。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(appState.devices) { device in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(device.name)
                                            .font(.headline)
                                        Text("\(appState.displayToken(device.deviceClass)) • \(appState.displayToken(device.status))")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                        if !device.capabilities.isEmpty {
                                            Text(device.capabilities.joined(separator: ", "))
                                                .foregroundStyle(.secondary)
                                                .lineLimit(2)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    GlassPanel(title: appState.text("Task Flow", "任务流")) {
                        if appState.taskStatusCounts.isEmpty {
                            Text(appState.text("No tasks yet.", "还没有任务。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(appState.taskStatusCounts, id: \.0) { status, count in
                                    HStack {
                                        Text(status.replacingOccurrences(of: "_", with: " ").capitalized)
                                        Spacer()
                                        Text("\(count)")
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                    }

                    GlassPanel(title: appState.text("Memory Recall", "记忆召回")) {
                        if let recall = appState.latestMemoryRecall, !recall.items.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(recall.items) { item in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(item.title)
                                            .font(.headline)
                                        Text("\(appState.displayToken(item.layer)) • \(Int(item.score * 100))%")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                        Text(item.reason)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                }
                            }
                        } else {
                            Text(appState.text("No recall snapshot available.", "当前没有召回快照。"))
                                .foregroundStyle(.secondary)
                        }
                    }

                GlassPanel(title: appState.text("Recent Activity", "最近活动")) {
                        if appState.events.isEmpty {
                            Text(appState.text("No recent events.", "还没有最近事件。"))
                                .foregroundStyle(.secondary)
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(appState.events.prefix(5))) { event in
                                    VStack(alignment: .leading, spacing: 4) {
                                        HStack {
                                            Text(event.eventType)
                                                .font(.headline)
                                            Spacer()
                                            Text(event.createdAt.formatted(date: .omitted, time: .shortened))
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        if let taskID = event.taskReferenceID {
                                            Button(appState.text("Open Related Task", "打开关联任务")) {
                                                Task { await appState.openTask(id: taskID) }
                                            }
                                            .buttonStyle(.link)
                                        }
                                        if let firstKey = event.payload.keys.sorted().first,
                                           let value = event.payload[firstKey] {
                                            Text("\(firstKey): \(value.displayText)")
                                                .foregroundStyle(.secondary)
                                                .lineLimit(2)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                GlassPanel(title: appState.text("Local Backend", "本地后端")) {
                    HStack {
                        Text(processLabel)
                        Spacer()
                        if appState.backendProcessState == .running {
                            Button(appState.text("Stop", "停止")) {
                                appState.stopBackendProcess()
                            }
                        } else {
                            Button(appState.text("Start", "启动")) {
                                appState.startBackendProcess()
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                }
            }
            .padding(28)
        }
        .background(
            Brand.dashboardGradient(for: colorScheme)
        )
    }

    private var backendLabel: String {
        switch appState.backendStatus {
        case .unknown:
            return appState.text("Unknown", "未知")
        case .connected:
            return appState.text("Connected", "已连接")
        case .disconnected:
            return appState.text("Disconnected", "未连接")
        }
    }

    private var backendAccent: Color {
        switch appState.backendStatus {
        case .unknown:
            return .gray
        case .connected:
            return Brand.mint
        case .disconnected:
            return .red
        }
    }

    private var processLabel: String {
        switch appState.backendProcessState {
        case .idle:
            return appState.text("No local backend process running.", "当前没有本地后端进程运行。")
        case .running:
            return appState.text("Local backend process is running.", "本地后端进程正在运行。")
        case .stopped(let code):
            return appState.text("Local backend exited with code \(code).", "本地后端已退出，代码 \(code)。")
        case .failed:
            return appState.text("Local backend failed to start.", "本地后端启动失败。")
        }
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

    private func capabilityRiskColor(_ riskLevel: String) -> Color {
        switch riskLevel {
        case "high":
            return .red
        case "medium":
            return Brand.amber
        default:
            return Brand.mint
        }
    }
}

private struct InboxWorkbenchView: View {
    @ObservedObject var appState: AppState
    @Environment(\.colorScheme) private var colorScheme

    private let promptTemplates = [
        "Draft the first AI OS milestone plan and break it into concrete delivery steps.",
        "Review the latest reminders and decide what needs action today.",
        "Turn this rough idea into a tracked task with clear success criteria.",
        "Analyze the risk of this request and suggest the safest next step."
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                BrandHero(
                    eyebrow: appState.text("Intent Intake", "意图 Intake"),
                    title: appState.text("Inbox Workbench", "收件箱工作台"),
                    subtitle: appState.text("Capture a natural-language request, inspect governance and cognition, then push it into the task loop with one controlled action.", "输入自然语言请求，检查治理与认知结果，再通过一次受控操作推进到任务流。")
                )

                composerPanel
                actionRail
                intakeStatusStrip
                resultsColumn
            }
            .padding(24)
        }
        .background(Brand.dashboardGradient(for: colorScheme))
    }

    private var composerPanel: some View {
        GlassPanel(title: appState.text("Request Composer", "请求编辑器")) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(appState.text("Describe the request in one place.", "在这里完整描述请求。"))
                            .font(.title3.weight(.semibold))
                        Text(appState.text("State the outcome, constraints, and urgency. This page should feel like drafting a work item, not filling a dashboard.", "写清目标、约束和紧急度。这个页面应该像起草工作项，而不是填写仪表盘。"))
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text("\(draftLength) chars")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.secondary)
                }

                TextEditor(text: $appState.inboxText)
                    .font(.body)
                    .frame(minHeight: 320)
                    .padding(12)
                    .background(
                        RoundedRectangle(cornerRadius: 20)
                            .fill(Color.primary.opacity(colorScheme == .dark ? 0.08 : 0.035))
                    )
                    .overlay {
                        RoundedRectangle(cornerRadius: 20)
                            .stroke(Color.secondary.opacity(0.18), lineWidth: 1)
                    }

                HStack {
                    Label(appState.text("Starting Points", "起始模板"), systemImage: "sparkles.rectangle.stack")
                        .font(.headline)
                    Spacer()
                    if !appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Button(appState.text("Clear Draft", "清空草稿")) {
                            appState.inboxText = ""
                        }
                        .buttonStyle(.link)
                    }
                }

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 12)], spacing: 12) {
                    ForEach(promptTemplates, id: \.self) { template in
                        Button {
                            appState.inboxText = template
                        } label: {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(appState.text("Template", "模板"))
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
                                    .fill(Color.primary.opacity(colorScheme == .dark ? 0.05 : 0.025))
                                    .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }

    private var actionRail: some View {
        GlassPanel(title: appState.text("Action Rail", "操作区")) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 16) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(appState.text("Run the intake in two stages.", "分两步运行 intake。"))
                            .font(.title3.weight(.semibold))
                        Text(actionHint)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    HStack {
                        StatusBadge(label: appState.isProcessingInbox ? appState.text("Working", "处理中") : appState.text("Ready", "就绪"), color: appState.isProcessingInbox ? Brand.amber : Brand.mint)
                        if let intent = appState.latestIntentEvaluation {
                            StatusBadge(label: appState.displayToken(intent.riskLevel, category: .riskLevel), color: riskColor(intent.riskLevel))
                        }
                        if let intake = appState.latestIntakeResponse, intake.task != nil {
                            StatusBadge(label: appState.text("Task Created", "已创建任务"), color: Brand.pine)
                        }
                    }
                }

                HStack(alignment: .top, spacing: 12) {
                    inboxActionButton(
                        title: appState.text("Evaluate Intent", "评估意图"),
                        subtitle: appState.text("Lightweight governance and intent pass.", "先做一轮轻量治理和意图分析。"),
                        systemImage: "waveform.badge.magnifyingglass",
                        prominent: false,
                        disabled: !appState.canEvaluateInbox
                    ) {
                        Task { await appState.evaluateInboxIntent() }
                    }

                    inboxActionButton(
                        title: appState.text("Process Into Task Loop", "处理并进入任务流"),
                        subtitle: appState.text("Run full intake and create work when appropriate.", "执行完整 intake，并在合适时生成任务。"),
                        systemImage: "arrow.triangle.branch",
                        prominent: true,
                        disabled: !appState.canProcessInbox
                    ) {
                        Task { await appState.processInbox() }
                    }
                }
            }
        }
    }

    private var intakeStatusStrip: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 16)], spacing: 16) {
            InboxMiniCard(
                title: appState.text("Intent", "意图"),
                value: appState.latestIntentEvaluation.map { appState.displayToken($0.intentType) } ?? appState.text("Pending", "待处理"),
                detail: appState.latestIntentEvaluation?.goal ?? appState.text("Run Evaluate to classify the request.", "先运行评估来识别请求类型。"),
                accent: Brand.pine
            )
            InboxMiniCard(
                title: appState.text("Execution Mode", "执行模式"),
                value: appState.latestIntakeResponse.map { appState.displayToken($0.cognition.suggestedExecutionMode, category: .executionMode) } ?? appState.text("Unscored", "未评估"),
                detail: appState.latestIntakeResponse?.cognition.suggestedNextStep ?? appState.text("Process the request to score execution.", "处理请求后会得到执行建议。"),
                accent: Brand.amber
            )
            InboxMiniCard(
                title: appState.text("Task Output", "任务输出"),
                value: appState.latestIntakeResponse?.task == nil ? appState.text("No Task Yet", "尚未生成任务") : appState.text("Task Created", "已创建任务"),
                detail: appState.latestIntakeResponse?.task?.objective ?? appState.text("A concrete request can materialize into tracked work.", "明确的请求可以转化为可追踪任务。"),
                accent: Brand.ink
            )
        }
    }

    private var resultsColumn: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 320), spacing: 16)], spacing: 16) {
            GlassPanel(title: appState.text("Intent Snapshot", "意图快照")) {
                if let intent = appState.latestIntentEvaluation {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            StatusBadge(label: appState.displayToken(intent.intentType), color: Brand.pine)
                            StatusBadge(label: "Urgency \(intent.urgency)", color: Brand.amber)
                            if intent.needsConfirmation {
                                StatusBadge(label: appState.text("Needs Confirmation", "需要确认"), color: .red)
                            }
                        }
                        inboxLine(appState.text("Goal", "目标"), intent.goal)
                        inboxLine(appState.text("Risk", "风险"), appState.displayToken(intent.riskLevel, category: .riskLevel))
                        inboxLine(appState.text("Rationale", "理由"), intent.rationale)
                        if !intent.relatedContextIDs.isEmpty {
                            inboxTagSection(appState.text("Related Context", "关联上下文"), items: intent.relatedContextIDs, empty: appState.text("No related context.", "没有关联上下文。"))
                        }
                    }
                } else {
                    inboxEmptyState(
                        title: appState.text("No Intent Evaluation Yet", "还没有意图评估"),
                        detail: appState.text("Run Evaluate to see intent type, urgency, and governance hints before committing to task creation.", "先运行评估，再决定是否进入任务创建。")
                    )
                }
            }

            GlassPanel(title: appState.text("Cognition", "认知结果")) {
                if let intake = appState.latestIntakeResponse {
                    VStack(alignment: .leading, spacing: 14) {
                        inboxLine(appState.text("Execution Mode", "执行模式"), appState.displayToken(intake.cognition.suggestedExecutionMode, category: .executionMode))
                        inboxLine(appState.text("Next Step", "下一步"), intake.cognition.suggestedNextStep)
                        inboxLine(appState.text("Cost Note", "成本说明"), intake.cognition.commonsense.costNote)
                        inboxLine(appState.text("Strategic Position", "战略位置"), intake.cognition.insight.strategicPosition)
                        inboxLine(appState.text("Action Mode", "行动模式"), intake.cognition.courage.actionMode)
                        inboxLine(appState.text("Courage Rationale", "行动理由"), intake.cognition.courage.rationale)

                        if let betterPath = intake.cognition.insight.betterPath, !betterPath.isEmpty {
                            inboxLine(appState.text("Better Path", "更优路径"), betterPath)
                        }

                        inboxTagSection(appState.text("Suggested Tags", "建议标签"), items: intake.cognition.suggestedTaskTags, empty: appState.text("No suggested tags.", "没有建议标签。"))
                        inboxTagSection(appState.text("Success Criteria", "成功标准"), items: intake.cognition.suggestedSuccessCriteria, empty: appState.text("No suggested success criteria.", "没有建议的成功标准。"))
                        inboxTagSection(
                            appState.text("Execution Steps", "执行步骤"),
                            items: intake.cognition.suggestedExecutionPlan.steps.map { "\($0.capabilityName): \($0.action) - \($0.purpose)" },
                            empty: appState.text("No execution steps.", "没有执行步骤。")
                        )
                    }
                } else {
                    inboxEmptyState(
                        title: appState.text("No Intake Output Yet", "还没有 Intake 输出"),
                        detail: appState.text("Run Process to generate cognition, execution guidance, and optionally a tracked task.", "运行处理后会生成认知结果、执行建议，以及可选的任务。")
                    )
                }
            }

            GlassPanel(title: appState.text("Task Result", "任务结果")) {
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
                            StatusBadge(label: appState.displayToken(task.status, category: .taskStatus), color: Brand.mint)
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
                        title: appState.text("Nothing Materialized Yet", "尚未生成结果"),
                        detail: appState.text("The current inbox draft has not produced a task. Evaluate first or process a more concrete request.", "当前草稿还没有生成任务。可以先评估，或者输入更具体的请求。")
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

    private var actionHint: String {
        if appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return appState.text("Start with a concrete request. A good inbox item names the outcome, the boundary, and the urgency.", "先写一个具体请求。好的 inbox 输入应该包含目标、边界和紧急度。")
        }
        if appState.latestIntakeResponse?.task != nil {
            return appState.text("This draft has already produced a task. You can reopen it or refine the request and process again.", "这个草稿已经生成任务。你可以重新打开它，或继续调整请求后再次处理。")
        }
        return appState.text("Evaluate is the lightweight pass. Process runs the full intake flow and may create a tracked task.", "评估是轻量分析，处理会执行完整 intake，并可能生成可追踪任务。")
    }

    private var draftLength: Int {
        appState.inboxText.trimmingCharacters(in: .whitespacesAndNewlines).count
    }

    private func riskColor(_ riskLevel: String) -> Color {
        switch riskLevel {
        case "high":
            return .red
        case "medium":
            return Brand.amber
        default:
            return Brand.mint
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

private struct MemoryListView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(appState.text("Memory", "记忆"))
                    .font(.title2.weight(.semibold))
                Spacer()
                if appState.backendStatus == .disconnected {
                    Button(appState.text("Retry", "重试")) {
                        Task { await appState.startupProbe() }
                    }
                }
                Button(appState.text("Refresh", "刷新")) {
                    Task { await appState.reloadMemories() }
                }
            }
            .padding(20)

            List(
                appState.memories,
                selection: Binding(
                    get: { appState.selectedMemoryID },
                    set: { appState.selectMemory(id: $0) }
                )
            ) { memory in
                MemoryRow(appState: appState, memory: memory)
                    .tag(memory.id)
            }
            .listStyle(.inset)
            .overlay {
                if appState.memories.isEmpty && !appState.isLoading {
                    ContentUnavailableView(
                        appState.text("No Memory Yet", "还没有记忆"),
                        systemImage: "brain",
                        description: Text(appState.text("Reflection and captured memory will appear here.", "反思和已捕获的记忆会显示在这里。"))
                    )
                }
            }
        }
        .task {
            if appState.memories.isEmpty {
                await appState.reloadMemories()
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

private struct ReminderOperationsView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(appState.text("Reminders", "提醒"))
                    .font(.title2.weight(.semibold))
                Spacer()
                if appState.backendStatus == .disconnected {
                    Button(appState.text("Retry", "重试")) {
                        Task { await appState.startupProbe() }
                    }
                }
                Button(appState.text("Refresh", "刷新")) {
                    Task { await appState.reloadReminders() }
                }
            }
            .padding(20)

            List(
                appState.reminders,
                selection: Binding(
                    get: { appState.selectedReminderID },
                    set: { appState.selectReminder(id: $0) }
                )
            ) { reminder in
                ReminderRow(reminder: reminder)
                    .tag(reminder.id)
            }
            .listStyle(.inset)
            .overlay {
                if appState.reminders.isEmpty && !appState.isLoading {
                    ContentUnavailableView(appState.text("No Reminders", "还没有提醒"), systemImage: "bell.slash", description: Text(appState.text("Reminder operations will appear here once reminders are created.", "创建提醒后，相关操作会显示在这里。")))
                }
            }
        }
        .task {
            if appState.reminders.isEmpty {
                await appState.reloadReminders()
            }
        }
    }
}

private struct TaskListView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(appState.text("Tasks", "任务"))
                    .font(.title2.weight(.semibold))
                Spacer()
                if appState.autoRefreshEnabled {
                    Label(appState.text("Auto \(appState.refreshIntervalSeconds)s", "自动 \(appState.refreshIntervalSeconds) 秒"), systemImage: "arrow.triangle.2.circlepath")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
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
            .padding(20)

            List(
                appState.tasks,
                selection: Binding(
                    get: { appState.selectedTaskID },
                    set: { appState.selectTask(id: $0) }
                )
            ) { task in
                TaskRow(appState: appState, task: task)
                    .tag(task.id)
            }
            .listStyle(.inset)
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
                                    StatusBadge(label: appState.displayToken(memory.memoryType, category: .memoryType), color: Brand.pine)
                                    StatusBadge(label: memory.createdAt.formatted(date: .abbreviated, time: .shortened), color: Brand.amber)
                                }
                            }
                            Spacer()
                        }

                        GlassPanel(title: appState.text("Content", "内容")) {
                            VStack(alignment: .leading, spacing: 12) {
                                Text(memory.content)
                                    .frame(maxWidth: .infinity, alignment: .leading)
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
                                }
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
            return .red
        case "medium":
            return Brand.amber
        default:
            return Brand.mint
        }
    }
}

private struct ReminderDetailView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let result = appState.latestSchedulerResult {
                    GlassPanel(title: appState.text("Scheduler Operations", "调度操作")) {
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

                        GlassPanel(title: appState.text("Create Reminder", "创建提醒")) {
                    VStack(alignment: .leading, spacing: 12) {
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
                    GlassPanel(title: appState.text("Selected Reminder", "当前提醒")) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(reminder.title)
                                .font(.headline)
                            schedulerLine(appState.text("Due Hint", "到期提示"), reminder.dueHint)
                            schedulerLine(appState.text("Scheduled For", "计划时间"), reminder.scheduledFor.formatted(date: .abbreviated, time: .shortened))
                            schedulerLine(appState.text("Origin", "来源"), reminder.origin ?? "n/a")
                            if let sourceTaskID = reminder.sourceTaskID {
                                HStack {
                                    Text(appState.text("Source Task", "源任务"))
                                    Spacer()
                                    Button(sourceTaskID) {
                                        Task { await appState.openTask(id: sourceTaskID) }
                                    }
                                    .buttonStyle(.link)
                                }
                            } else {
                                schedulerLine(appState.text("Source Task", "源任务"), "n/a")
                            }
                            if let lastSeenAt = reminder.lastSeenAt {
                                schedulerLine(appState.text("Last Seen", "最近查看"), lastSeenAt.formatted(date: .abbreviated, time: .shortened))
                            }
                            if !reminder.note.isEmpty {
                                Text(reminder.note)
                                    .foregroundStyle(.secondary)
                            }

                            HStack {
                                Spacer()
                                Button(appState.text("Create Task From Reminder", "从提醒创建任务")) {
                                    appState.presentCreateTask(
                                        objective: reminder.title,
                                        successCriteria: ["Resolve or acknowledge the reminder."],
                                        tags: ["reminder", reminder.origin ?? "scheduler"],
                                        riskLevel: "low"
                                    )
                                }
                            }

                            Divider()

                            TextField(appState.text("New Due Hint", "新的到期提示"), text: $appState.reminderDraft.dueHint)
                                .textFieldStyle(.roundedBorder)

                            HStack {
                                Button(appState.text("Mark Seen", "标记已读")) {
                                    Task { await appState.markSelectedReminderSeen() }
                                }
                                Button(appState.text("Reschedule", "重新安排")) {
                                    Task { await appState.rescheduleSelectedReminder() }
                                }
                                Button(appState.text("Delete", "删除")) {
                                    Task { await appState.deleteSelectedReminder() }
                                }
                                .foregroundStyle(.red)
                            }
                        }
                    }
                } else {
                    GlassPanel(title: appState.text("Selected Reminder", "当前提醒")) {
                        Text(appState.text("Select a reminder from the list to inspect and operate on it.", "请从列表中选择一个提醒进行查看和操作。"))
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

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    BrandSectionTitle(
                        title: appState.text("Candidates", "候选项"),
                        subtitle: appState.text("Proactive next steps, scheduler output, and queue control.", "主动建议的下一步、调度输出和队列控制。")
                    )
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

                GlassPanel(title: appState.text("Scheduler", "调度器")) {
                    HStack(spacing: 16) {
                        Stepper(appState.text("Candidate Limit: \(appState.schedulerDraft.candidateLimit)", "候选上限：\(appState.schedulerDraft.candidateLimit)"), value: $appState.schedulerDraft.candidateLimit, in: 1...100)
                        Stepper(appState.text("Stale After: \(appState.schedulerDraft.staleAfterMinutes)m", "停滞阈值：\(appState.schedulerDraft.staleAfterMinutes) 分钟"), value: $appState.schedulerDraft.staleAfterMinutes, in: 1...10080)
                        Stepper(appState.text("Escalate After Hits: \(appState.schedulerDraft.escalateAfterHits)", "升级触发次数：\(appState.schedulerDraft.escalateAfterHits)"), value: $appState.schedulerDraft.escalateAfterHits, in: 1...20)
                    }
                }

                if let result = appState.latestSchedulerResult {
                    GlassPanel(title: appState.text("Last Scheduler Tick", "最近一次调度")) {
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

                GlassPanel(title: appState.text("Candidate Queue", "候选队列")) {
                    if appState.candidates.isEmpty {
                        Text(appState.text("No candidates loaded.", "还没有候选项。"))
                            .foregroundStyle(.secondary)
                    } else {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(appState.candidates) { candidate in
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack(alignment: .top) {
                                        VStack(alignment: .leading, spacing: 6) {
                                            Text(candidate.title)
                                                .font(.headline)
                                            Text(candidate.detail)
                                                .foregroundStyle(.secondary)
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
                                        StatusBadge(label: appState.displayToken(candidate.kind, category: .candidateKind), color: Brand.pine)
                                        StatusBadge(label: "P\(candidate.priority)", color: Brand.amber)
                                        if candidate.autoAcceptable {
                                            StatusBadge(label: appState.text("Auto", "自动"), color: Brand.mint)
                                        }
                                        if candidate.needsConfirmation {
                                            StatusBadge(label: appState.text("Needs Confirmation", "需要确认"), color: .red)
                                        }
                                        if let sourceTaskID = candidate.sourceTaskID {
                                            Button(appState.text("Open Source Task", "打开源任务")) {
                                                Task { await appState.openTask(id: sourceTaskID) }
                                            }
                                            .buttonStyle(.link)
                                        }
                                    }
                                }
                                .padding(.vertical, 8)
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
        .task {
            if appState.candidates.isEmpty {
                await appState.reloadCandidates()
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
                                    StatusBadge(label: appState.displayToken(task.riskLevel, category: .riskLevel), color: Brand.amber)
                                    StatusBadge(label: appState.displayToken(task.executionMode, category: .executionMode), color: Brand.pine)
                                }
                            }
                            Spacer()
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
                            detailSection(appState.text("Plan Steps", "计划步骤"), items: task.executionPlan.steps.map { "\($0.capabilityName):\($0.action) - \($0.purpose)" }, empty: appState.text("No plan steps yet.", "还没有计划步骤。"))
                            detailSection(appState.text("Artifacts", "产物"), items: task.artifactPaths, empty: appState.text("No artifacts produced yet.", "还没有生成产物。"))
                            detailSection(appState.text("Verification Notes", "验证说明"), items: task.verificationNotes, empty: appState.text("No verification notes.", "还没有验证说明。"))
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
                                Text(run.metadata.keys.sorted().map { "\($0)=\(run.metadata[$0]?.displayText ?? "")" }.joined(separator: ", "))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
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
            return Brand.mint
        case "blocked":
            return .red
        case "executing":
            return Brand.pine
        case "planned":
            return Brand.amber
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
                            StatusBadge(label: appState.displayToken(run.status, category: .taskStatus), color: run.status == "done" ? Brand.mint : Brand.pine)
                            Button(run.taskID) {
                                Task { await appState.openTask(id: run.taskID) }
                            }
                            .buttonStyle(.link)
                        }
                    }
                    Spacer()
                    Button(appState.text("Refresh", "刷新")) {
                        Task { await appState.loadSelectedRunContext() }
                    }
                }

                HStack(alignment: .top, spacing: 16) {
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
            Text(title)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title2.weight(.semibold))
                .foregroundStyle(.primary)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(Brand.panelFill(for: colorScheme))
                .stroke(Brand.panelStroke(for: colorScheme), lineWidth: 1)
        )
    }
}

private struct BrandHero: View {
    let eyebrow: String
    let title: String
    let subtitle: String

    var body: some View {
        HStack(alignment: .center, spacing: 18) {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [Brand.pine, Brand.mint],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 84, height: 84)
                .overlay {
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
        }
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
                .overlay {
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
