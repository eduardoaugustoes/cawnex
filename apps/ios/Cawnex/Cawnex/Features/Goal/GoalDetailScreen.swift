import SwiftUI

struct GoalDetailScreen: View {
    let projectId: String
    let goalId: String
    @State var viewModel: GoalDetailViewModel
    var onBack: () -> Void = {}
    var onMVITap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                CawnexNavBar(title: viewModel.detail?.goal.name ?? "Goal", onBack: onBack)

                if case .loading = viewModel.state {
                    loadingView
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                }

                if let detail = viewModel.detail {
                    breadcrumb(detail: detail)
                    summaryCard(detail: detail)
                    murderCard(detail: detail)
                    mviSection(detail: detail)
                }
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, CawnexSpacing.xl)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId, goalId: goalId) }
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading goal…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - Breadcrumb

    private func breadcrumb(detail: GoalDetail) -> some View {
        Text("\(detail.projectName) › \(detail.milestoneName)")
            .font(CawnexTypography.footnote)
            .foregroundStyle(CawnexColors.mutedForeground)
            .lineLimit(1)
    }

    // MARK: - Summary Card

    private func summaryCard(detail: GoalDetail) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            HStack {
                StatusChip(
                    label: detail.goal.status.rawValue,
                    color: detail.goal.status.color,
                    icon: detail.goal.status.icon,
                    transitions: [StatusTransition<GoalStatus>](),
                    onTransition: { _ in }
                )
                Spacer()
                Text("\(detail.mvis.count) MVIs")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            BudgetBar(spent: detail.creditsSpent, saved: detail.humanEquivSaved)

            if detail.roi > 0 {
                HStack(spacing: CawnexSpacing.xs) {
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(CawnexColors.accent)
                    Text("\(detail.roi)x ROI")
                        .font(CawnexTypography.monoBold)
                        .foregroundStyle(CawnexColors.accent)
                }
            }
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Murder Card

    private func murderCard(detail: GoalDetail) -> some View {
        HStack(spacing: CawnexSpacing.md) {
            Image(systemName: "bird.fill")
                .font(.system(size: 18))
                .foregroundStyle(CawnexColors.primaryLight)
                .frame(width: 36, height: 36)
                .background(CawnexColors.primary.opacity(0.15))
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))

            VStack(alignment: .leading, spacing: 2) {
                Text(detail.murderName)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text("\(detail.crowCount) crows assigned")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - MVI Section

    private func mviSection(detail: GoalDetail) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            Text("MVIs")
                .font(CawnexTypography.sectionTitle)
                .foregroundStyle(CawnexColors.cardForeground)

            ForEach(detail.mvis) { mvi in
                MVICard(
                    mvi: mvi,
                    onTap: { onMVITap(mvi.id) },
                    onStatusChange: { _ in }
                )
            }
        }
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        GoalDetailScreen(
            projectId: "1",
            goalId: "g1",
            viewModel: GoalDetailViewModel(
                goalService: InMemoryGoalService(store: store)
            )
        )
    }
    .environment(store)
}
