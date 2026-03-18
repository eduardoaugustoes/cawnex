import SwiftUI

struct AutopilotPlanReviewScreen: View {
    let plan: AutopilotPlan
    let sessionId: String
    @State var viewModel: AutopilotChatViewModel
    var onBack: () -> Void = {}
    var onLaunchComplete: (String, String) -> Void = { _, _ in }

    @State private var launchStep: String? = nil
    @State private var launchError: String? = nil

    private let loadingSteps = [
        "Creating project...",
        "Generating documents...",
        "Planning milestones...",
        "Launching wave..."
    ]

    var body: some View {
        ZStack(alignment: .bottom) {
            CawnexColors.background.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.xxl) {
                    projectHeader
                    repoRow
                    milestonesSection
                    summaryStats
                    firstWaveCard
                }
                .padding(.horizontal, CawnexSpacing.xl)
                .padding(.top, CawnexSpacing.lg)
                .padding(.bottom, 140)
            }

            launchBar
        }
        .navigationBarBackButtonHidden()
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    onBack()
                } label: {
                    HStack(spacing: CawnexSpacing.xs) {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 14, weight: .semibold))
                        Text("Review Plan")
                            .font(CawnexTypography.body)
                    }
                    .foregroundStyle(CawnexColors.cardForeground)
                }
            }
        }
    }

    // MARK: - Project Header

    private var projectHeader: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
            Text(plan.project_name ?? "New Project")
                .font(CawnexTypography.heading2)
                .foregroundStyle(CawnexColors.cardForeground)

            if let description = plan.description, !description.isEmpty {
                Text(description)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .lineSpacing(4)
            }
        }
    }

    // MARK: - Repo Row

    @ViewBuilder
    private var repoRow: some View {
        if let repo = plan.repo, !repo.isEmpty {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "arrow.triangle.branch")
                    .font(.system(size: 16))
                    .foregroundStyle(CawnexColors.primary)
                Text(repo)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
        }
    }

    // MARK: - Milestones

    @ViewBuilder
    private var milestonesSection: some View {
        if let milestones = plan.milestones, !milestones.isEmpty {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                ForEach(Array(milestones.enumerated()), id: \.offset) { index, milestone in
                    milestoneCard(milestone, index: index)
                }
            }
        }
    }

    private func milestoneCard(_ milestone: AutopilotMilestone, index: Int) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            Text("MILESTONE \(index + 1)")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(2)

            Text(milestone.name ?? "Untitled")
                .font(CawnexTypography.sectionTitle)
                .foregroundStyle(CawnexColors.cardForeground)

            if let goals = milestone.goals, !goals.isEmpty {
                VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                    ForEach(Array(goals.enumerated()), id: \.offset) { gIndex, goal in
                        goalRow(goal, isFirst: gIndex == 0)
                    }
                }
            }
        }
        .padding(CawnexSpacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    private func goalRow(_ goal: AutopilotGoal, isFirst: Bool) -> some View {
        HStack(alignment: .top, spacing: CawnexSpacing.sm) {
            Circle()
                .fill(isFirst ? CawnexColors.primary : CawnexColors.mutedForeground)
                .frame(width: 8, height: 8)
                .padding(.top, 4)

            VStack(alignment: .leading, spacing: 2) {
                Text(goal.name ?? "")
                    .font(CawnexTypography.captionMedium)
                    .foregroundStyle(CawnexColors.cardForeground)

                let mviPart = goal.mvi_count.map { "\($0) MVIs" } ?? ""
                let hoursPart = goal.human_hours ?? ""
                let meta = [mviPart, hoursPart].filter { !$0.isEmpty }.joined(separator: " · ")
                if !meta.isEmpty {
                    Text(meta)
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }
        }
    }

    // MARK: - Summary Stats

    private var summaryStats: some View {
        let totalMVIs = plan.milestones?.flatMap { $0.goals ?? [] }.compactMap { $0.mvi_count }.reduce(0, +) ?? 0

        return HStack(spacing: 0) {
            statItem(value: "\(totalMVIs)", label: "MVIs", color: CawnexColors.primary)
            Divider().background(CawnexColors.border).frame(height: 40)
            statItem(value: "~?h", label: "Human equiv", color: CawnexColors.cardForeground)
            Divider().background(CawnexColors.border).frame(height: 40)
            statItem(value: "~$?", label: "Est. cost", color: CawnexColors.success)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    private func statItem(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(CawnexTypography.heading2)
                .foregroundStyle(color)
            Text(label)
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - First Wave Card

    @ViewBuilder
    private var firstWaveCard: some View {
        if let first = plan.milestones?.first {
            let goalCount = first.goals?.count ?? 0
            let mviCount = first.goals?.compactMap { $0.mvi_count }.reduce(0, +) ?? 0

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("FIRST WAVE")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.primary)
                    .tracking(2)

                Text(first.name ?? "Milestone 1")
                    .font(CawnexTypography.captionMedium)
                    .foregroundStyle(CawnexColors.cardForeground)

                Text("\(goalCount) goals · \(mviCount) MVIs")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(CawnexSpacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.primary, lineWidth: 1)
            )
        }
    }

    // MARK: - Launch Bar

    private var launchBar: some View {
        VStack(spacing: CawnexSpacing.md) {
            Button {
                Task { await launch() }
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    if viewModel.isLoading {
                        ProgressView().tint(.white).scaleEffect(0.85)
                    } else {
                        Image(systemName: "rocket")
                            .font(.system(size: 15, weight: .bold))
                    }
                    Text(launchStep ?? "Launch Wave")
                        .font(CawnexTypography.sectionTitle)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(viewModel.isLoading ? CawnexColors.muted : CawnexColors.primary)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)
            .disabled(viewModel.isLoading)

            if let error = launchError {
                Text(error)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.destructive)
                    .multilineTextAlignment(.center)
            } else {
                Text("Monarch will create your project, documents, backlog and launch the first wave")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .multilineTextAlignment(.center)
            }
        }
        .padding(.horizontal, CawnexSpacing.xl)
        .padding(.top, CawnexSpacing.lg)
        .padding(.bottom, 34)
        .background(CawnexColors.background)
    }

    // MARK: - Launch Action

    private func launch() async {
        launchError = nil
        launchStep = loadingSteps[0]

        let result = await viewModel.launch()

        if let result, let projectId = result.project_id, let waveId = result.wave_id {
            launchStep = nil
            onLaunchComplete(projectId, waveId)
        } else {
            launchStep = nil
            launchError = viewModel.error ?? "Launch failed. Please try again."
        }
    }
}
