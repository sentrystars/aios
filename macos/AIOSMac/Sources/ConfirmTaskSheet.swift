import SwiftUI

struct ConfirmTaskSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Confirm Message Task")
                .font(.title2.weight(.semibold))

            if let task = appState.selectedTask {
                Text(task.objective)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Decision Note")
                    .font(.headline)
                TextEditor(text: $appState.confirmationDraft.note)
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
                Button("Reject") {
                    Task { await appState.confirmSelectedTask(approved: false) }
                }
                Button("Approve") {
                    Task { await appState.confirmSelectedTask(approved: true) }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
    }
}
