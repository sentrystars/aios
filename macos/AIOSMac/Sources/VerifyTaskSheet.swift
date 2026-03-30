import SwiftUI

struct VerifyTaskSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Verify Task")
                .font(.title2.weight(.semibold))

            if let task = appState.selectedTask {
                Text(task.objective)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Checks")
                    .font(.headline)
                Text("One line per verification check or evidence item.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                TextEditor(text: $appState.verificationDraft.checksText)
                    .frame(minHeight: 140)
                    .overlay {
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                    }
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Verifier Notes")
                    .font(.headline)
                TextEditor(text: $appState.verificationDraft.verifierNotes)
                    .frame(minHeight: 100)
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
                Button("Submit Verification") {
                    Task { await appState.verifySelectedTask() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
    }
}
