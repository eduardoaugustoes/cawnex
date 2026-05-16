import SwiftUI

/// Sheet for Reject — collects a required reason and confirms.
///
/// The reason becomes a GitHub PR comment before the PR is closed, so
/// it's permanently attached to the PR's history.
struct RejectSheet: View {
    let prNumber: Int
    @Binding var reason: String
    let isRejecting: Bool
    let onConfirm: () -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Reject PR #\(prNumber)")
                    .font(CawnexTypography.heading2)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text(
                    "This closes the PR on GitHub with your reason as a comment, then marks the MVI as rejected in Cawnex."
                )
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Reason")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                TextEditor(text: $reason)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .scrollContentBackground(.hidden)
                    .background(CawnexColors.card)
                    .frame(minHeight: 120)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(CawnexColors.border, lineWidth: 1)
                    )
            }

            HStack(spacing: CawnexSpacing.md) {
                Button(action: onCancel) {
                    Text("Cancel")
                        .font(CawnexTypography.captionBold)
                        .frame(maxWidth: .infinity)
                        .frame(height: 48)
                        .background(CawnexColors.card)
                        .foregroundStyle(CawnexColors.cardForeground)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                        .overlay(
                            RoundedRectangle(cornerRadius: CawnexRadius.md)
                                .stroke(CawnexColors.border, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
                .disabled(isRejecting)

                Button(action: onConfirm) {
                    HStack(spacing: 6) {
                        if isRejecting {
                            ProgressView().tint(.white)
                        }
                        Text("Reject")
                            .font(CawnexTypography.captionBold)
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(CawnexColors.destructive)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                }
                .buttonStyle(.plain)
                .disabled(
                    isRejecting || reason.trimmingCharacters(in: .whitespaces).isEmpty
                )
            }
        }
        .padding(CawnexSpacing.xl)
        .background(CawnexColors.background)
    }
}
