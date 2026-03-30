import SwiftUI
import AppKit
import UserNotifications

@main
struct AIOSMacApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var appState = AppState()

    var body: some Scene {
        Window("AI OS", id: "main") {
            RootView(appState: appState)
                .frame(minWidth: 1180, minHeight: 760)
                .task {
                    appDelegate.appState = appState
                    await appState.requestNotificationPermissionIfNeeded()
                    await appState.startupProbe()
                }
        }
        .windowResizability(.contentSize)
        .commands {
            AIOSCommands(appState: appState)
        }

        Settings {
            SettingsView(appState: appState)
                .frame(width: 480)
                .padding(24)
        }

        MenuBarExtra {
            MenuBarControlView(appState: appState)
        } label: {
            HStack(spacing: 6) {
                Image("StatusGlyph")
                    .resizable()
                    .interpolation(.high)
                    .frame(width: 16, height: 16)
                Text("AI OS")
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    weak var appState: AppState?

    func applicationDidFinishLaunching(_ notification: Notification) {
        UNUserNotificationCenter.current().delegate = self
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        appState?.showMainWindow()
        return false
    }

    func applicationDockMenu(_ sender: NSApplication) -> NSMenu? {
        let menu = NSMenu()

        let openItem = NSMenuItem(
            title: "Open Dashboard",
            action: #selector(openDashboardFromDock),
            keyEquivalent: ""
        )
        openItem.target = self
        menu.addItem(openItem)

        let newTaskItem = NSMenuItem(
            title: "New Task",
            action: #selector(createTaskFromDock),
            keyEquivalent: ""
        )
        newTaskItem.target = self
        menu.addItem(newTaskItem)

        menu.addItem(.separator())

        let refreshItem = NSMenuItem(
            title: "Refresh All",
            action: #selector(refreshAllFromDock),
            keyEquivalent: ""
        )
        refreshItem.target = self
        menu.addItem(refreshItem)

        let schedulerItem = NSMenuItem(
            title: "Run Scheduler Tick",
            action: #selector(runSchedulerFromDock),
            keyEquivalent: ""
        )
        schedulerItem.target = self
        menu.addItem(schedulerItem)

        return menu
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let userInfo = response.notification.request.content.userInfo
        let route = userInfo[AppState.NotificationUserInfoKey.route] as? String
        let taskID = userInfo[AppState.NotificationUserInfoKey.taskID] as? String
        await appState?.showMainWindow()
        await appState?.handleNotificationResponse(route: route, taskID: taskID)
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }

    @MainActor @objc private func openDashboardFromDock() {
        appState?.showMainWindow()
    }

    @MainActor @objc private func createTaskFromDock() {
        appState?.showMainWindow()
        appState?.isPresentingCreateTask = true
    }

    @MainActor @objc private func refreshAllFromDock() {
        Task { await appState?.reloadAll() }
    }

    @MainActor @objc private func runSchedulerFromDock() {
        Task { await appState?.runSchedulerTick() }
    }
}

private struct AIOSCommands: Commands {
    @ObservedObject var appState: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some Commands {
        CommandMenu("AI OS") {
            Button(appState.text("Open Dashboard", "打开主面板")) {
                appState.showMainWindow()
                openWindow(id: "main")
            }
            .keyboardShortcut("1", modifiers: [.command, .option])

            Divider()

            Button(appState.text("Refresh All", "刷新全部")) {
                Task { await appState.reloadAll() }
            }
            .keyboardShortcut("r")

            Button(appState.text("Refresh Candidates", "刷新候选")) {
                Task { await appState.reloadCandidates() }
            }
            .keyboardShortcut("r", modifiers: [.command, .shift])

            Divider()

            Button(appState.text("New Task", "新任务")) {
                appState.showMainWindow()
                openWindow(id: "main")
                appState.isPresentingCreateTask = true
            }
            .keyboardShortcut("n")

            Button(appState.text("Run Scheduler Tick", "执行调度轮询")) {
                Task { await appState.runSchedulerTick() }
            }
            .keyboardShortcut("k", modifiers: [.command, .shift])

            Divider()

            Toggle(appState.text("Auto Refresh", "自动刷新"), isOn: $appState.autoRefreshEnabled)
        }
    }
}

private struct MenuBarControlView: View {
    @ObservedObject var appState: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Image("StatusGlyph")
                    .resizable()
                    .interpolation(.high)
                    .frame(width: 22, height: 22)
                VStack(alignment: .leading, spacing: 2) {
                    Text("AI OS")
                        .font(.headline)
                    Label(connectionText, systemImage: menuBarIcon)
                        .foregroundStyle(connectionColor)
                        .font(.subheadline)
                }
                Spacer()
            }

            Button(appState.text("Open Dashboard", "打开主面板")) {
                appState.showMainWindow()
                openWindow(id: "main")
            }
            .buttonStyle(.borderedProminent)

            TextField(appState.text("Quick task", "快速任务"), text: $appState.menuBarQuickTaskTitle)
                .textFieldStyle(.roundedBorder)

            Button(appState.text("Create Quick Task", "创建快速任务")) {
                appState.showMainWindow()
                openWindow(id: "main")
                Task { await appState.createQuickTaskFromMenuBar() }
            }
            .disabled(appState.menuBarQuickTaskTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

            Divider()

            Button(appState.text("Refresh All", "刷新全部")) {
                Task { await appState.reloadAll() }
            }
            Button(appState.text("Refresh Candidates", "刷新候选")) {
                Task { await appState.reloadCandidates() }
            }
            Button(appState.text("Retry Backend Connection", "重试后端连接")) {
                Task { await appState.startupProbe() }
            }
            if appState.backendProcessState == .running {
                Button(appState.text("Stop Local Backend", "停止本地后端")) {
                    appState.stopBackendProcess()
                }
            } else {
                Button(appState.text("Start Local Backend", "启动本地后端")) {
                    appState.startBackendProcess()
                }
            }
            Button(appState.text("Run Scheduler Tick", "执行调度轮询")) {
                Task { await appState.runSchedulerTick() }
            }

            Divider()

            Text("Tasks: \(appState.tasks.count)")
                .foregroundStyle(.secondary)
            Text("Candidates: \(appState.candidates.count)")
                .foregroundStyle(.secondary)
            Text(processText)
                .foregroundStyle(.secondary)
        }
        .padding(12)
        .frame(minWidth: 280)
    }

    private var menuBarIcon: String {
        switch appState.backendStatus {
        case .unknown:
            return "circle.dashed"
        case .connected:
            return "bolt.circle.fill"
        case .disconnected:
            return "exclamationmark.circle.fill"
        }
    }

    private var connectionText: String {
        switch appState.backendStatus {
        case .unknown:
            return appState.text("Backend unknown", "后端状态未知")
        case .connected:
            return appState.text("Backend connected", "后端已连接")
        case .disconnected:
            return appState.text("Backend disconnected", "后端未连接")
        }
    }

    private var connectionColor: Color {
        switch appState.backendStatus {
        case .unknown:
            return .secondary
        case .connected:
            return Brand.mint
        case .disconnected:
            return .red
        }
    }

    private var processText: String {
        switch appState.backendProcessState {
        case .idle:
            return appState.text("Local backend idle", "本地后端空闲")
        case .running:
            return appState.text("Local backend running", "本地后端运行中")
        case .stopped(let code):
            return appState.text("Local backend stopped (\(code))", "本地后端已停止（\(code)）")
        case .failed:
            return appState.text("Local backend failed", "本地后端启动失败")
        }
    }
}
