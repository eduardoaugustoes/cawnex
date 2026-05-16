import SwiftUI

/// Minimal confirmation sheet for Approve & Merge.
///
/// No free-form input — confirmation is the entire UX. The Steer chat
/// (Phase 2) is where nuance gets captured. This sheet exists to
/// prevent accidental taps on the merge button.
struct MergeConfirmSheet: View {
    let prNumber: Int
    let prTitle: String
    let isMerging: Bool
    let onConfirm: () -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("Approve & Merge PR #\(prNumber)")
                    .font(CawnexTypography.heading2)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text(prTitle)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .lineLimit(3)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("This will:")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text("• Rebase the PR onto main on GitHub")
                Text("• Mark this MVI as shipped in Cawnex")
            }
            .font(CawnexTypography.footnote)
            .foregroundStyle(CawnexColors.mutedForeground)

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
                .disabled(isMerging)

                Button(action: onConfirm) {
                    HStack(spacing: 6) {
                        if isMerging {
                            ProgressView().tint(.white)
                        }
                        Text("Approve & Merge")
                            .font(CawnexTypography.captionBold)
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(CawnexColors.success)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                }
                .buttonStyle(.plain)
                .disabled(isMerging)
            }
        }
        .padding(CawnexSpacing.xl)
        .background(CawnexColors.background)
    }
}
