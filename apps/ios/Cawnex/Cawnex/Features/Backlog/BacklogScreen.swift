import SwiftUI

struct BacklogScreen: View {
    let projectId: String
    @State var viewModel: BacklogViewModel
    @Environment(TabRouter.self) private var tabRouter

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                CawnexNavBar(
                    title: "Backlog",
                    onBack: { tabRouter.projectPath.removeLast() }
                ) {
                    NavBarActionButton(icon: "plus", label: "Milestone")
                }

                ForEach(viewModel.milestones) { milestone in
                    milestoneCard(milestone)
                }
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, CawnexSpacing.xl)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId) }
    }

    // MARK: - Milestone Card

    private func milestoneCard(_ milestone: Milestone) -> some View {
        let expanded = viewModel.isExpanded(milestone.id)

        return VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            milestoneHeader(milestone, expanded: expanded)

            Text(milestone.description)
                .font(.custom("Inter", size: 12))
                .foregroundStyle(CawnexColors.mutedForeground)

            tasksSection(milestone)
            budgetSection(milestone)

            if expanded && !milestone.goals.isEmpty {
                goalsSection(milestone)
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Milestone Header

    private func milestoneHeader(_ milestone: Milestone, expanded: Bool) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                viewModel.toggleExpanded(milestone.id)
            }
        } label: {
            HStack {
                HStack(spacing: 8) {
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(CawnexColors.mutedForeground)
                        .frame(width: 16, height: 16)
                    Text(milestone.name)
                        .font(.custom("Inter", size: 15).weight(.bold))
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                Spacer()
                milestoneTrailing(milestone)
            }
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func milestoneTrailing(_ milestone: Milestone) -> some View {
        if milestone.status == .inProgress {
            Text("\(milestone.progress)%")
                .font(.custom("Inter", size: 13).weight(.bold))
                .foregroundStyle(CawnexColors.primary)
        } else {
            Text(milestone.status.rawValue)
                .font(.custom("Inter", size: 10).weight(.medium))
                .foregroundStyle(CawnexColors.mutedForeground)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
        }
    }

    // MARK: - Tasks Section

    private func tasksSection(_ milestone: Milestone) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Tasks")
                    .font(.custom("Inter", size: 11).weight(.semibold))
                    .foregroundStyle(CawnexColors.mutedForeground)
                Spacer()
                if milestone.tasks.total > 0 {
                    Text("\(milestone.tasks.done) done · \(milestone.tasks.active) active · \(milestone.tasks.refined) refined · \(milestone.tasks.draft) draft")
                        .font(.custom("Inter", size: 10))
                        .foregroundStyle(CawnexColors.mutedForeground)
                } else {
                    Text("0 tasks")
                        .font(.custom("Inter", size: 10))
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

    // MARK: - Budget Section

    private func budgetSection(_ milestone: Milestone) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Budget")
                    .font(.custom("Inter", size: 11).weight(.semibold))
                    .foregroundStyle(CawnexColors.mutedForeground)
                Spacer()
                if milestone.roi > 0 {
                    Text("\(milestone.roi)x ROI")
                        .font(.custom("JetBrains Mono", size: 10).weight(.bold))
                        .foregroundStyle(Color(hex: 0xF97316))
                } else {
                    Text("No data yet")
                        .font(.custom("Inter", size: 10))
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
                .font(.custom("JetBrains Mono", size: 11).weight(.semibold))
                .foregroundStyle(CawnexColors.mutedForeground)
            RoundedRectangle(cornerRadius: 3)
                .fill(CawnexColors.muted)
                .frame(height: 6)
            Text("~$0")
                .font(.custom("JetBrains Mono", size: 11).weight(.semibold))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Goals Section

    private func goalsSection(_ milestone: Milestone) -> some View {
        VStack(spacing: 6) {
            Rectangle()
                .fill(CawnexColors.border)
                .frame(height: 1)
                .padding(.vertical, 4)

            ForEach(milestone.goals) { goal in
                goalRow(goal, milestone: milestone)
            }
        }
    }

    private func goalRow(_ goal: Goal, milestone: Milestone) -> some View {
        Button {
            tabRouter.pushGoal(projectId, goalId: goal.id)
        } label: {
            HStack {
                HStack(spacing: 8) {
                    Circle()
                        .fill(goalDotColor(goal.status))
                        .frame(width: 8, height: 8)
                    Text(goal.name)
                        .font(.custom("Inter", size: 13).weight(.medium))
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                Spacer()
                Text("\(goal.mvisComplete)/\(goal.mviCount) MVIs")
                    .font(.custom("Inter", size: 11))
                    .foregroundStyle(CawnexColors.mutedForeground)
                Image(systemName: "chevron.right")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(.vertical, 6)
        }
        .buttonStyle(.plain)
    }

    private func goalDotColor(_ status: GoalStatus) -> Color {
        switch status {
        case .active: CawnexColors.success
        case .planned: CawnexColors.mutedForeground
        case .complete: CawnexColors.primary
        }
    }
}

// MARK: - Preview

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        BacklogScreen(
            projectId: "1",
            viewModel: BacklogViewModel(
                backlogService: InMemoryBacklogService(store: store)
            )
        )
    }
    .environment(store)
    .environment(TabRouter())
}
