import SwiftUI

struct SettingsView: View {
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 14) {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [Brand.pine, Brand.mint],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 64, height: 64)
                    .overlay {
                        Image("StatusGlyph")
                            .resizable()
                            .scaledToFit()
                            .padding(12)
                    }

                VStack(alignment: .leading, spacing: 4) {
                    Text(appState.text("AIOSMac Settings", "AIOSMac 设置"))
                        .font(.title2.weight(.semibold))
                        .foregroundStyle(.primary)
                    Text(appState.text("Backend connectivity, refresh behavior, and local app runtime controls.", "管理后端连接、自动刷新和本地应用运行控制。"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Form {
                Section(appState.text("Language", "语言")) {
                    Picker(appState.text("App Language", "应用语言"), selection: $appState.appLanguage) {
                        ForEach(AppState.AppLanguage.allCases) { language in
                            Text(language.label(in: appState.appLanguage))
                                .tag(language)
                        }
                    }
                    .pickerStyle(.segmented)

                    Text(appState.text("The sidebar and core controls update immediately after switching.", "切换后，侧边栏和核心操作文案会立即更新。"))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Section(appState.text("Backend", "后端")) {
                    TextField(appState.text("Base URL", "基础地址"), text: $appState.backendURLString)
                        .textFieldStyle(.roundedBorder)
                    Text(appState.text("Recommended local default: http://127.0.0.1:8787", "推荐本地默认地址：http://127.0.0.1:8787"))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextField(appState.text("Launch Command", "启动命令"), text: $appState.backendLaunchCommand)
                        .textFieldStyle(.roundedBorder)
                    TextField(appState.text("Working Directory", "工作目录"), text: $appState.backendWorkingDirectory)
                        .textFieldStyle(.roundedBorder)
                    HStack {
                        if appState.backendProcessState == .running {
                            Button(appState.text("Stop Local Backend", "停止本地后端")) {
                                appState.stopBackendProcess()
                            }
                        } else {
                            Button(appState.text("Start Local Backend", "启动本地后端")) {
                                appState.startBackendProcess()
                            }
                        }
                    }
                }

                Section(appState.text("Refresh", "刷新")) {
                    Toggle(appState.text("Enable Auto Refresh", "启用自动刷新"), isOn: $appState.autoRefreshEnabled)
                    Stepper(
                        appState.text("Refresh Interval: \(appState.refreshIntervalSeconds)s", "刷新间隔：\(appState.refreshIntervalSeconds) 秒"),
                        value: $appState.refreshIntervalSeconds,
                        in: 5...300,
                        step: 5
                    )
                }

                Section(appState.text("Notes", "说明")) {
                    Text(appState.text("This macOS client now supports task operations, self-profile editing, candidate controls, scheduler runs, local backend control, and optional background refresh polling.", "当前 macOS 客户端已经支持任务操作、自我画像编辑、候选控制、调度运行、本地后端控制，以及可选的后台轮询刷新。"))
                        .foregroundStyle(.secondary)
                }
            }
            .formStyle(.grouped)
        }
    }
}
