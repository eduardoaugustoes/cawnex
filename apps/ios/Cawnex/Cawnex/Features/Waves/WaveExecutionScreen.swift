import SwiftUI

struct WaveExecutionScreen: View {
    @State var viewModel: WaveExecutionViewModel
    var onBack: () -> Void = {}
    var onHumanTaskTap: (String) -> Void = { _ in }
    var onMVITap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                navRow

                switch viewModel.detailState {
                case .idle, .loading:
                    loadingView
                case .loaded(let detail):
                    executionContent(detail)
                case .error(let message):
                    errorView(message)
                }
            }
            .padding(.horizontal, CawnexSpacing.lg)
            .padding(.bottom, CawnexSpacing.xxxl)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load() }
        .onDisappear { viewModel.stopPolling() }
    }

    // MARK: - Navigation

    private var navRow: some View {
        HStack {
            Button(action: onBack) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(CawnexColors.cardForeground)
            }
            Text("Wave Execution")
                .font(CawnexTypography.heading2)
                .foregroundColor(CawnexColors.cardForeground)
            Spacer()
            if let wave = viewModel.wave {
                Text(wave.status.label)
                    .font(CawnexTypography.tiny)
                    .foregroundColor(wave.status.color)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(wave.status.color.opacity(0.15))
                    .clipShape(Capsule())
            }
        }
        .padding(.top, CawnexSpacing.md)
    }

    // MARK: - Content

    private func executionContent(_ detail: WaveDetail) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
            // Directive
            Text(detail.wave.directive)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.mutedForeground)

            // Budget bar
            budgetSection(detail.wave.budget)

            // Action buttons
            actionButtons(detail.wave)

            // Error
            if let error = viewModel.actionError {
                Text(error)
                    .font(CawnexTypography.caption)
                    .foregroundColor(CawnexColors.destructive)
            }

            // Human tasks (if any pending)
            if !detail.humanTasks.isEmpty {
                humanTasksSection(detail.humanTasks)
            }

            // MVIs
            mvisSection(detail.mvis)

            // Event feed
            eventFeedSection
        }
    }

    // MARK: - Budget

    private func budgetSection(_ budget: WaveBudget) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
            HStack {
                Text("Budget")
                    .font(CawnexTypography.captionBold)
                    .foregroundColor(CawnexColors.mutedForeground)
                Spacer()
                Text("$\(String(format: "%.2f", budget.spentDollars)) / $\(String(format: "%.2f", budget.limitDollars))")
                    .font(CawnexTypography.caption)
                    .foregroundColor(CawnexColors.mutedForeground)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(CawnexColors.cardElevated)
                        .frame(height: 8)
                    RoundedRectangle(cornerRadius: 4)
                        .fill(budget.percentage > 0.8 ? CawnexColors.warning : CawnexColors.primary)
                        .frame(width: geo.size.width * min(budget.percentage, 1.0), height: 8)
                }
            }
            .frame(height: 8)
        }
    }

    // MARK: - Actions

    private func actionButtons(_ wave: WaveSummary) -> some View {
        HStack(spacing: CawnexSpacing.md) {
            switch wave.status {
            case .planning:
                actionButton("Activate", icon: "play.fill", color: CawnexColors.primary) {
                    Task { await viewModel.activate() }
                }
            case .executing:
                actionButton("Pause", icon: "pause.fill", color: CawnexColors.warning) {
                    Task { await viewModel.pause() }
                }
                actionButton("Cancel", icon: "xmark", color: CawnexColors.destructive) {
                    Task { await viewModel.cancel() }
                }
            case .paused:
                actionButton("Resume", icon: "play.fill", color: CawnexColors.primary) {
                    Task { await viewModel.activate() }
                }
                actionButton("Cancel", icon: "xmark", color: CawnexColors.destructive) {
                    Task { await viewModel.cancel() }
                }
            default:
                EmptyView()
            }
        }
    }

    private func actionButton(_ label: String, icon: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: CawnexSpacing.xs) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                Text(label)
                    .font(CawnexTypography.captionBold)
            }
            .foregroundColor(.white)
            .padding(.horizontal, CawnexSpacing.lg)
            .padding(.vertical, CawnexSpacing.sm)
            .background(color)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - Human Tasks

    private func humanTasksSection(_ tasks: [HumanTask]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack {
                Image(systemName: "hand.raised.fill")
                    .foregroundColor(.orange)
                Text("Needs Your Input")
                    .font(CawnexTypography.captionBold)
                    .foregroundColor(CawnexColors.cardForeground)
                Spacer()
                Text("\(tasks.count)")
                    .font(CawnexTypography.tiny)
                    .foregroundColor(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(.orange)
                    .clipShape(Capsule())
            }

            ForEach(tasks) { task in
                Button { onHumanTaskTap(task.id) } label: {
                    HStack {
                        Text(task.ask)
                            .font(CawnexTypography.caption)
                            .foregroundColor(CawnexColors.cardForeground)
                            .lineLimit(1)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 10))
                            .foregroundColor(CawnexColors.mutedForeground)
                    }
                    .padding(CawnexSpacing.sm)
                    .background(CawnexColors.cardElevated)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(CawnexSpacing.md)
        .background(Color.orange.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - MVIs

    private func mvisSection(_ mvis: [WaveMVI]) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("MVIs")
                .font(CawnexTypography.captionBold)
                .foregroundColor(CawnexColors.mutedForeground)

            ForEach(mvis) { mvi in
                mviCard(mvi)
            }
        }
    }

    private func mviCard(_ mvi: WaveMVI) -> some View {
        Button { onMVITap(mvi.id) } label: {
            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                HStack {
                    Text(mvi.name)
                        .font(CawnexTypography.bodyBold)
                        .foregroundColor(CawnexColors.cardForeground)
                    Spacer()
                    mviStatusChip(mvi.status)
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundColor(CawnexColors.mutedForeground)
                }

                if mvi.tasksTotal > 0 {
                    HStack(spacing: CawnexSpacing.sm) {
                        ProgressView(value: Double(mvi.tasksDone), total: Double(mvi.tasksTotal))
                            .tint(CawnexColors.primary)
                        Text("\(mvi.tasksDone)/\(mvi.tasksTotal)")
                            .font(CawnexTypography.tiny)
                            .foregroundColor(CawnexColors.mutedForeground)
                    }
                }

                if mvi.canShip {
                    Button {
                        Task { await viewModel.shipMVI(mvi.id) }
                    } label: {
                        HStack {
                            if viewModel.isShipping.contains(mvi.id) {
                                ProgressView().tint(.white)
                            } else {
                                Image(systemName: "shippingbox.fill")
                                Text("Ship")
                            }
                        }
                        .font(CawnexTypography.captionBold)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, CawnexSpacing.sm)
                        .background(CawnexColors.success)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
                    }
                    .disabled(viewModel.isShipping.contains(mvi.id))
                }
            }
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .buttonStyle(.plain)
    }

    private func mviStatusChip(_ status: String) -> some View {
        let (label, color): (String, Color) = switch status {
        case "draft": ("Draft", CawnexColors.mutedForeground)
        case "queued": ("Queued", CawnexColors.mutedForeground)
        case "executing": ("Executing", CawnexColors.primary)
        case "ready_to_ship": ("Ready to Ship", CawnexColors.success)
        case "shipped": ("Shipped", CawnexColors.success)
        case "failed": ("Failed", CawnexColors.destructive)
        case "cancelled": ("Cancelled", CawnexColors.mutedForeground)
        default: (status, CawnexColors.mutedForeground)
        }

        return Text(label)
            .font(CawnexTypography.tiny)
            .foregroundColor(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.15))
            .clipShape(Capsule())
    }

    // MARK: - Event Feed

    private var eventFeedSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Text("Live Feed")
                .font(CawnexTypography.captionBold)
                .foregroundColor(CawnexColors.mutedForeground)

            if viewModel.events.isEmpty {
                Text("Waiting for events...")
                    .font(CawnexTypography.caption)
                    .foregroundColor(CawnexColors.mutedForeground)
                    .padding(.vertical, CawnexSpacing.lg)
            } else {
                ForEach(viewModel.events.reversed()) { event in
                    eventRow(event)
                }
            }
        }
    }

    private func eventRow(_ event: WaveEvent) -> some View {
        HStack(alignment: .top, spacing: CawnexSpacing.md) {
            Image(systemName: event.icon)
                .font(.system(size: 14))
                .foregroundColor(event.dotColor)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(event.message)
                    .font(CawnexTypography.caption)
                    .foregroundColor(CawnexColors.cardForeground)
                Text(event.timestamp.prefix(19).replacingOccurrences(of: "T", with: " "))
                    .font(CawnexTypography.tiny)
                    .foregroundColor(CawnexColors.mutedForeground)
            }
        }
        .padding(.vertical, CawnexSpacing.xs)
    }

    // MARK: - States

    private var loadingView: some View {
        VStack(spacing: CawnexSpacing.lg) {
            ProgressView().tint(CawnexColors.primary)
            Text("Loading wave...")
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: CawnexSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 32))
                .foregroundColor(.red)
            Text(message)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }
}

#Preview {
    WaveExecutionScreen(
        viewModel: WaveExecutionViewModel(
            waveService: InMemoryWaveService(store: AppStore()),
            projectId: "proj-001",
            waveId: "w001"
        )
    )
    .preferredColorScheme(.dark)
}
