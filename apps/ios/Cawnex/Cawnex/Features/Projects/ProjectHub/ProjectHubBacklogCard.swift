import SwiftUI

struct ProjectHubBacklogCard: View {
    let backlog: BacklogSummary
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                cardHeader
                PipelineBar(
                    done: backlog.pipeline.done,
                    active: backlog.pipeline.active,
                    refined: backlog.pipeline.refined,
                    draft: backlog.pipeline.draft,
                    baseColor: CawnexColors.success
                )
                legend
                Text("\(backlog.activeMilestones) active · \(backlog.mvisShipped) of \(backlog.mvisTotal) MVIs shipped")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(CawnexSpacing.lg)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.success.opacity(0.27), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private var cardHeader: some View {
        HStack {
            HStack(spacing: 10) {
                Image(systemName: "target")
                    .font(.system(size: 18))
                    .foregroundStyle(CawnexColors.success)
                Text("Backlog")
                    .font(CawnexTypography.sectionTitle)
                    .foregroundStyle(CawnexColors.cardForeground)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.system(size: 14))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private var legend: some View {
        HStack(spacing: 6) {
            legendItem("\(backlog.pipeline.done) done", color: CawnexColors.success)
            legendItem("\(backlog.pipeline.active) active", color: CawnexColors.success.opacity(0.6))
            legendItem("\(backlog.pipeline.refined) refined", color: CawnexColors.success.opacity(0.33))
            legendItem("\(backlog.pipeline.draft) draft", color: CawnexColors.success.opacity(0.13))
        }
    }

    private func legendItem(_ text: String, color: Color) -> some View {
        HStack(spacing: 4) {
            RoundedRectangle(cornerRadius: 4)
                .fill(color)
                .frame(width: 8, height: 8)
            Text(text)
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }
}
