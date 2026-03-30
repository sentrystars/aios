import SwiftUI

struct ReflectTaskSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Store Reflection")
                .font(.title2.weight(.semibold))

            if let task = appState.selectedTask {
                Text(task.objective)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Summary")
                    .font(.headline)
                TextEditor(text: $appState.reflectionDraft.summary)
                    .frame(minHeight: 120)
                    .overlay {
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                    }
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Lessons")
                    .font(.headline)
                Text("One line per lesson.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                TextEditor(text: $appState.reflectionDraft.lessonsText)
                    .frame(minHeight: 120)
                    .overlay {
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                    }
            }

            Spacer()

            HStack {
                Spacer()
                Button("Cancel") {
                    dismiss()
                }
                Button("Save Reflection") {
                    Task { await appState.reflectSelectedTask() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
    }
}
