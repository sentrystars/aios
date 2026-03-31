import SwiftUI

struct CreateTaskSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Create Task")
                .font(.title2.weight(.semibold))

            TextField("Objective", text: $appState.createTaskDraft.objective, axis: .vertical)
                .textFieldStyle(.roundedBorder)

            VStack(alignment: .leading, spacing: 8) {
                Text("Success Criteria")
                    .font(.headline)
                Text("One line per criterion.")
                    .foregroundStyle(.secondary)
                    .font(.caption)
                TextEditor(text: $appState.createTaskDraft.successCriteriaText)
                    .frame(minHeight: 120)
                    .overlay {
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                    }
            }

            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Tags")
                        .font(.headline)
                    TextField("ui, macos, desktop", text: $appState.createTaskDraft.tagsText)
                        .textFieldStyle(.roundedBorder)
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Risk")
                        .font(.headline)
                    Picker("Risk", selection: $appState.createTaskDraft.riskLevel) {
                        Text("Low").tag("low")
                        Text("Medium").tag("medium")
                        Text("High").tag("high")
                    }
                    .pickerStyle(.segmented)
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Linked Goals")
                    .font(.headline)
                if appState.goals.isEmpty {
                    Text("No structured goals available.")
                        .foregroundStyle(.secondary)
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(appState.goals) { goal in
                                Toggle(
                                    isOn: Binding(
                                        get: { appState.createTaskDraft.linkedGoalIDs.contains(goal.id) },
                                        set: { isOn in
                                            if isOn {
                                                appState.createTaskDraft.linkedGoalIDs.append(goal.id)
                                            } else {
                                                appState.createTaskDraft.linkedGoalIDs.removeAll { $0 == goal.id }
                                            }
                                        }
                                    )
                                ) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(goal.title)
                                        Text("\(goal.kind) • \(goal.status)")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                .toggleStyle(.checkbox)
                            }
                        }
                    }
                    .frame(maxHeight: 140)
                }
            }

            Spacer()

            HStack {
                Spacer()
                Button("Cancel") {
                    dismiss()
                }
                Button("Create") {
                    Task { await appState.createTask() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
    }
}
