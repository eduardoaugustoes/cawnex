import SwiftUI

struct MilestoneCard: View {
    let milestone: Milestone
    let isExpanded: Bool
    let onToggle: () -> Void
    let onGoalTap: (Goal) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            milestoneHeader
            Text(milestone.description)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
            tasksSection
            budgetSection
            if isExpanded && !milestone.goals.isEmpty {
                GoalsSection(goals: milestone.goals, onGoalTap: onGoalTap)
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    private var milestoneHeader: some View {
        Button(action: onToggle) {
            HStack {
                HStack(spacing: 8) {
                    Image(systemName: isExpanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(CawnexColors.mutedForeground)
                        .frame(width: 16, height: 16)
                    Text(milestone.name)
                        .font(CawnexTypography.bodyBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                Spacer()
                milestoneTrailing
            }
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var milestoneTrailing: some View {
        if milestone.status == .inProgress {
            Text("\(milestone.progress)%")
                .font(CawnexTypography.captionBold)
                .foregroundStyle(CawnexColors.primary)
        } else {
            Text(milestone.status.rawValue)
                .font(CawnexTypography.tinyMedium)
                .foregroundStyle(CawnexColors.mutedForeground)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
        }
    }

    private var tasksSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Tasks")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                Spacer()
                if milestone.tasks.total > 0 {
                    Text("\(milestone.tasks.done) done · \(milestone.tasks.active) active · \(milestone.tasks.refined) refined · \(milestone.tasks.draft) draft")
                        .font(CawnexTypography.tiny)
                        .foregroundStyle(CawnexColors.mutedForeground)
                } else {
                    Text("0 tasks")
                        .font(CawnexTypography.tiny)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }

            PipelineBar(
                done: milestone.tasks.done,
                active: milestone.tasks.active,
                refined: milestone.tasks.refined,
                draft: milestone.tasks.draft
            )
        }
    }

    private var budgetSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Budget")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                Spacer()
                if milestone.roi > 0 {
                    Text("\(milestone.roi)x ROI")
                        .font(CawnexTypography.monoBold)
                        .foregroundStyle(CawnexColors.accent)
                } else {
                    Text("No data yet")
                        .font(CawnexTypography.tiny)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }

            if milestone.creditsSpent > 0 || milestone.humanEquivSaved > 0 {
                BudgetBar(spent: milestone.creditsSpent, saved: milestone.humanEquivSaved)
            } else {
                emptyBudgetBar
            }
        }
    }

    private var emptyBudgetBar: some View {
        HStack(spacing: 8) {
            Text("$0")
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.mutedForeground)
            RoundedRectangle(cornerRadius: 3)
                .fill(CawnexColors.muted)
                .frame(height: 6)
            Text("~$0")
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }
}
