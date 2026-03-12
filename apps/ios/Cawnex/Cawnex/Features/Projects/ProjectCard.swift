import SwiftUI

struct ProjectCard: View {
    let project: Project
    var onTap: () -> Void = {}

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                topRow
                description
                pipelineBar
                summary
                budgetBar
            }
            .padding(CawnexSpacing.lg)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Top Row

    private var topRow: some View {
        HStack(spacing: CawnexSpacing.sm) {
            HStack(spacing: CawnexSpacing.sm) {
                Circle()
                    .fill(project.isActive ? CawnexColors.success : CawnexColors.mutedForeground)
                    .frame(width: 8, height: 8)

                Text(project.name)
                    .font(CawnexTypography.sectionTitle)
                    .foregroundStyle(CawnexColors.cardForeground)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Description

    private var description: some View {
        Text(project.description)
            .font(CawnexTypography.caption)
            .foregroundStyle(CawnexColors.mutedForeground)
    }

    // MARK: - Pipeline

    private var pipelineBar: some View {
        PipelineBar(
            done: project.tasks.done,
            active: project.tasks.active,
            refined: project.tasks.refined,
            draft: project.tasks.draft
        )
    }

    // MARK: - Summary

    private var summary: some View {
        Text(project.tasks.summary)
            .font(CawnexTypography.label)
            .foregroundStyle(CawnexColors.mutedForeground)
    }

    // MARK: - Budget

    private var budgetBar: some View {
        BudgetBar(spent: project.creditsSpent, saved: project.humanEquivSaved)
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        ProjectCard(project: .preview)
            .padding()
    }
}
