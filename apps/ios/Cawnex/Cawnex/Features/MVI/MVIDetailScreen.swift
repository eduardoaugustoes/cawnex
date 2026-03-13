import SwiftUI

struct MVIDetailScreen: View {
    let projectId: String
    let mviId: String
    @State var viewModel: MVIDetailViewModel
    var onBack: () -> Void = {}
    var onTaskTap: (String) -> Void = { _ in }
    var onPRTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                CawnexNavBar(title: viewModel.detail?.mvi.name ?? "MVI", onBack: onBack)

                if case .loading = viewModel.state {
                    loadingView
                }

                if case .error(let message) = viewModel.state {
                    Text(message)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.destructive)
                }

                if let detail = viewModel.detail {
                    breadcrumbRow(detail.breadcrumb)
                    statusRow(detail: detail)
                    progressBar(detail: detail)
                    crowsSection(crows: detail.activeCrows)
                    tasksSection(tasks: detail.tasks)
                    liveFeedSection(events: detail.liveFeed)
                    mergeReadinessSection(items: detail.mergeChecklist)
                    costRow(detail: detail)
                    shipButton(detail: detail)
                }
            }
            .padding(.top, CawnexSpacing.sm)
            .padding(.horizontal, CawnexSpacing.xl)
            .padding(.bottom, CawnexSpacing.xl)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId, mviId: mviId) }
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack(spacing: CawnexSpacing.sm) {
            ProgressView()
                .tint(CawnexColors.primaryLight)
            Text("Loading blackboard…")
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

    // MARK: - Status Row

    private func statusRow(detail: MVIBlackboardDetail) -> some View {
        HStack {
            StatusChip(
                label: detail.mvi.status.label,
                color: detail.mvi.status.color,
                icon: detail.mvi.status.icon,
                transitions: detail.mvi.status.transitions,
                onTransition: { _ in }
            )
            Spacer()
            Text("\(detail.mvi.tasksDone)/\(detail.mvi.tasksTotal) tasks")
                .font(CawnexTypography.captionBold)
                .foregroundStyle(CawnexColors.mutedForeground)
            Text("· $\(detail.mvi.aiCost as NSDecimalNumber)")
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.primary)
        }
    }

    // MARK: - Progress Bar

    private func progressBar(detail: MVIBlackboardDetail) -> some View {
        let progress: Double = detail.mvi.tasksTotal > 0
            ? Double(detail.mvi.tasksDone) / Double(detail.mvi.tasksTotal)
            : 0

        return GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(CawnexColors.muted)
                    .frame(height: 6)
                RoundedRectangle(cornerRadius: 3)
                    .fill(detail.mvi.status.color)
                    .frame(width: geo.size.width * progress, height: 6)
            }
        }
        .frame(height: 6)
    }

    // MARK: - Active Crows

    private func crowsSection(crows: [ActiveCrow]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("ACTIVE CROWS")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: CawnexSpacing.sm) {
                    ForEach(crows) { crow in
                        crowCard(crow)
                    }
                }
            }
        }
    }

    private func crowCard(_ crow: ActiveCrow) -> some View {
        HStack(spacing: CawnexSpacing.sm) {
            Circle()
                .fill(crow.behaviorState.color)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 1) {
                Text(crow.name)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                HStack(spacing: CawnexSpacing.xs) {
                    Text(crow.behaviorState.rawValue)
                        .font(CawnexTypography.tiny)
                        .foregroundStyle(crow.behaviorState.color)
                    Text("·")
                        .font(CawnexTypography.tiny)
                        .foregroundStyle(CawnexColors.mutedForeground)
                    Text(crow.model)
                        .font(CawnexTypography.tiny)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Tasks

    private func tasksSection(tasks: [MVITask]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("TASKS")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            VStack(spacing: 0) {
                ForEach(Array(tasks.enumerated()), id: \.element.id) { index, task in
                    if index > 0 {
                        Divider()
                            .background(CawnexColors.border)
                    }
                    taskRow(task)
                }
            }
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    private func taskRow(_ task: MVITask) -> some View {
        Button {
            onTaskTap(task.id)
        } label: {
            HStack(spacing: CawnexSpacing.md) {
                taskStatusIcon(task.status)

                VStack(alignment: .leading, spacing: 2) {
                    Text(task.name)
                        .font(CawnexTypography.captionBold)
                        .foregroundStyle(CawnexColors.cardForeground)
                        .lineLimit(1)

                    HStack(spacing: CawnexSpacing.xs) {
                        if let pr = task.prNumber {
                            Text(pr)
                                .font(CawnexTypography.mono)
                                .foregroundStyle(CawnexColors.info)
                        }
                        if task.status == .building, let crow = task.crowName {
                            Text(crow)
                                .font(CawnexTypography.tiny)
                                .foregroundStyle(CawnexColors.mutedForeground)
                        }
                    }
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(CawnexSpacing.md)
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func taskStatusIcon(_ status: TaskStatus) -> some View {
        switch status {
        case .completed:
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 16))
                .foregroundStyle(CawnexColors.success)
        case .building:
            ProgressView()
                .scaleEffect(0.7)
                .tint(CawnexColors.primaryLight)
        case .reviewing:
            Image(systemName: "eye.fill")
                .font(.system(size: 14))
                .foregroundStyle(CawnexColors.info)
        case .queued:
            Image(systemName: "clock")
                .font(.system(size: 14))
                .foregroundStyle(CawnexColors.mutedForeground)
        case .failed:
            Image(systemName: "xmark.circle.fill")
                .font(.system(size: 16))
                .foregroundStyle(CawnexColors.destructive)
        }
    }

    // MARK: - Live Feed

    private func liveFeedSection(events: [LiveFeedEvent]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack(spacing: CawnexSpacing.sm) {
                Text("LIVE FEED")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .tracking(1.2)

                Text("LIVE")
                    .font(CawnexTypography.microBold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(CawnexColors.destructive)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
            }

            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                ForEach(events) { event in
                    feedRow(event)
                }
            }
            .padding(CawnexSpacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    private func feedRow(_ event: LiveFeedEvent) -> some View {
        HStack(alignment: .top, spacing: CawnexSpacing.sm) {
            Text(event.timestamp)
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.mutedForeground)
                .frame(width: 40, alignment: .trailing)

            Text("—")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)

            Text(event.message)
                .font(CawnexTypography.footnote)
                .foregroundStyle(event.type.color)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: - Merge Readiness

    private func mergeReadinessSection(items: [MergeChecklistItem]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("MERGE READINESS")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
                .tracking(1.2)

            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                ForEach(items) { item in
                    HStack(spacing: CawnexSpacing.sm) {
                        Image(systemName: item.passed ? "checkmark.circle.fill" : "clock")
                            .font(.system(size: 14))
                            .foregroundStyle(item.passed ? CawnexColors.success : CawnexColors.primaryLight)
                        Text(item.label)
                            .font(CawnexTypography.caption)
                            .foregroundStyle(item.passed ? CawnexColors.cardForeground : CawnexColors.primaryLight)
                    }
                }
            }
            .padding(CawnexSpacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.success.opacity(0.3), lineWidth: 1)
            )
        }
    }

    // MARK: - Cost Row

    private func costRow(detail: MVIBlackboardDetail) -> some View {
        HStack {
            BudgetBar(spent: detail.mvi.aiCost, saved: detail.mvi.humanEquiv)

            if detail.mvi.roi > 0 {
                Text("\(detail.mvi.roi)x ROI")
                    .font(CawnexTypography.monoBold)
                    .foregroundStyle(CawnexColors.accent)
                    .fixedSize()
            }
        }
    }

    // MARK: - Ship Button

    private func shipButton(detail: MVIBlackboardDetail) -> some View {
        VStack(spacing: CawnexSpacing.sm) {
            Button {
                // Ship action
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: "arrow.triangle.merge")
                        .font(.system(size: 15, weight: .bold))
                    Text("Ship this MVI")
                        .font(CawnexTypography.sectionTitle)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(detail.canShip ? CawnexColors.success : CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)
            .disabled(!detail.canShip)

            if !detail.canShip {
                Text("Waiting for all tasks to complete")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
        }
    }
}

#Preview {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        MVIDetailScreen(
            projectId: "1",
            mviId: "mvi2",
            viewModel: MVIDetailViewModel(
                mviService: InMemoryMVIService(store: store)
            )
        )
    }
    .environment(store)
}
