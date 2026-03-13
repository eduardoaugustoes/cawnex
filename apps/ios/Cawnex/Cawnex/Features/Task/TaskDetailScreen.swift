import SwiftUI

struct TaskDetailScreen: View {
    let projectId: String
    let taskId: String
    @State var viewModel: TaskDetailViewModel
    var onBack: () -> Void = {}
    var onPRTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                navRow
                    .padding(.horizontal, CawnexSpacing.xl)

                if case .loading = viewModel.state {
                    loadingView
                        .padding(.horizontal, CawnexSpacing.xl)
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                        .padding(.horizontal, CawnexSpacing.xl)
                }

                if let detail = viewModel.detail {
                    VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                        breadcrumbRow(detail.breadcrumb)
                        titleRow(detail: detail)
                        descriptionRow(detail.description)
                        statsRow(detail: detail)
                        crowSection(crow: detail.assignedCrow)
                        implementationSection(steps: detail.implementationSteps)
                        acceptanceCriteriaSection(criteria: detail.acceptanceCriteria)
                        if let pr = detail.pr {
                            prSection(pr: pr)
                        }
                    }
                    .padding(.horizontal, CawnexSpacing.xl)
                }
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.bottom, CawnexSpacing.xl)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId, taskId: taskId) }
    }

    // MARK: - Nav

    private var navRow: some View {
        CawnexNavBar(title: "Task Detail", onBack: onBack)
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading task…")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, CawnexSpacing.xxxl)
    }

    // MARK: - Breadcrumb

    private func breadcrumbRow(_ text: String) -> some View {
        Text(text)
            .font(CawnexTypography.footnote)
            .foregroundStyle(CawnexColors.mutedForeground)
            .lineLimit(1)
    }

    // MARK: - Title Row

    private func titleRow(detail: TaskDetail) -> some View {
        HStack {
            Text(detail.name)
                .font(CawnexTypography.heading2)
                .foregroundStyle(CawnexColors.cardForeground)
                .lineLimit(2)

            Spacer()

            Text(detail.status.rawValue)
                .font(CawnexTypography.label)
                .foregroundStyle(detail.status.color)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(detail.status.color.opacity(0.13))
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.lg))
        }
    }

    // MARK: - Description

    private func descriptionRow(_ text: String) -> some View {
        Text(text)
            .font(CawnexTypography.caption)
            .foregroundStyle(CawnexColors.mutedForeground)
            .fixedSize(horizontal: false, vertical: true)
    }

    // MARK: - Stats Row

    private func statsRow(detail: TaskDetail) -> some View {
        HStack(spacing: CawnexSpacing.sm) {
            statCard(value: detail.humanEstimate, label: "Human equiv")
            statCard(value: "$\(detail.aiCost as NSDecimalNumber)", label: "Credits used")
            statCard(
                value: "\(detail.roi)x",
                label: "ROI",
                valueColor: CawnexColors.warning
            )
        }
    }

    private func statCard(value: String, label: String, valueColor: Color = CawnexColors.cardForeground) -> some View {
        VStack(spacing: CawnexSpacing.xs) {
            Text(value)
                .font(CawnexTypography.sectionTitle)
                .foregroundStyle(valueColor)
            Text(label)
                .font(CawnexTypography.tiny)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Assigned Crow

    private func crowSection(crow: AssignedCrow) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("ASSIGNED CROW")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.5)

            HStack(spacing: CawnexSpacing.md) {
                Circle()
                    .fill(crow.behaviorState.color)
                    .frame(width: 10, height: 10)

                VStack(alignment: .leading, spacing: 2) {
                    Text("\(crow.name) · \(crow.role)")
                        .font(CawnexTypography.captionBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text("\(crow.behaviorState.rawValue) · \(crow.executionMinutes) min execution · \(crow.filesChanged) files changed")
                        .font(CawnexTypography.footnote)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }
            .padding(CawnexSpacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - Implementation Steps

    private func implementationSection(steps: [ImplementationStep]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("IMPLEMENTATION")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.5)

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                ForEach(steps) { step in
                    HStack(alignment: .top, spacing: CawnexSpacing.sm) {
                        Circle()
                            .fill(CawnexColors.primaryLight)
                            .frame(width: 6, height: 6)
                            .padding(.top, 5)
                        Text(step.text)
                            .font(CawnexTypography.footnote)
                            .foregroundStyle(CawnexColors.cardForeground)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(CawnexSpacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - Acceptance Criteria

    private func acceptanceCriteriaSection(criteria: [AcceptanceCriterion]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("ACCEPTANCE CRITERIA")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.5)

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                ForEach(criteria) { criterion in
                    HStack(alignment: .top, spacing: CawnexSpacing.sm) {
                        Image(systemName: criterion.passed ? "checkmark.circle.fill" : "circle")
                            .font(.system(size: 14))
                            .foregroundStyle(criterion.passed ? CawnexColors.success : CawnexColors.mutedForeground)
                        Text(criterion.text)
                            .font(CawnexTypography.footnote)
                            .foregroundStyle(CawnexColors.cardForeground)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(CawnexSpacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - PR Card

    private func prSection(pr: TaskPR) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("PULL REQUEST")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.5)

            Button {
                onPRTap(pr.number)
            } label: {
                HStack(spacing: CawnexSpacing.md) {
                    Image(systemName: "arrow.triangle.pull")
                        .font(.system(size: 18))
                        .foregroundStyle(CawnexColors.success)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(pr.number) — \(pr.title)")
                            .font(CawnexTypography.captionBold)
                            .foregroundStyle(CawnexColors.cardForeground)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                        Text("\(pr.status) · +\(pr.linesAdded) −\(pr.linesRemoved) · \(pr.filesChanged) files · \(pr.coverage)% coverage")
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
            .buttonStyle(.plain)
        }
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        TaskDetailScreen(
            projectId: "1",
            taskId: "t1",
            viewModel: TaskDetailViewModel(
                taskService: InMemoryTaskService(store: store)
            )
        )
    }
    .environment(store)
}
