import SwiftUI

struct WaveListScreen: View {
    @State var viewModel: WaveListViewModel
    var onBack: () -> Void = {}
    var onWaveTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                navRow

                switch viewModel.state {
                case .idle, .loading:
                    loadingView
                case .loaded:
                    waveSections
                case .error(let message):
                    errorView(message)
                }
            }
            .padding(.horizontal, CawnexSpacing.lg)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load() }
    }

    // MARK: - Navigation

    private var navRow: some View {
        HStack {
            Button(action: onBack) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(CawnexColors.textPrimary)
            }
            Text("Waves")
                .font(CawnexTypography.heading2)
                .foregroundColor(CawnexColors.textPrimary)
            Spacer()
        }
        .padding(.top, CawnexSpacing.md)
    }

    // MARK: - Sections

    private var waveSections: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
            if !viewModel.activeWaves.isEmpty {
                sectionHeader("Active", count: viewModel.activeWaves.count)
                ForEach(viewModel.activeWaves) { wave in
                    waveCard(wave)
                }
            }

            if !viewModel.completedWaves.isEmpty {
                sectionHeader("Completed", count: viewModel.completedWaves.count)
                ForEach(viewModel.completedWaves) { wave in
                    waveCard(wave)
                }
            }

            if viewModel.waves.isEmpty {
                emptyView
            }
        }
    }

    private func sectionHeader(_ title: String, count: Int) -> some View {
        HStack {
            Text(title)
                .font(CawnexTypography.heading3)
                .foregroundColor(CawnexColors.textPrimary)
            Text("\(count)")
                .font(CawnexTypography.caption)
                .foregroundColor(CawnexColors.textSecondary)
        }
    }

    private func waveCard(_ wave: WaveSummary) -> some View {
        Button { onWaveTap(wave.id) } label: {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                HStack {
                    Image(systemName: wave.status.icon)
                        .foregroundColor(wave.status.color)
                    Text(wave.directive)
                        .font(CawnexTypography.bodyBold)
                        .foregroundColor(CawnexColors.cardForeground)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    Spacer()
                    Text(wave.status.label)
                        .font(CawnexTypography.tiny)
                        .foregroundColor(wave.status.color)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(wave.status.color.opacity(0.15))
                        .clipShape(Capsule())
                }

                // Progress bar
                let total = wave.progress.mvisTotal
                let shipped = wave.progress.mvisShipped
                if total > 0 {
                    HStack(spacing: CawnexSpacing.sm) {
                        ProgressView(value: Double(shipped), total: Double(total))
                            .tint(CawnexColors.success)
                        Text("\(shipped)/\(total) MVIs")
                            .font(CawnexTypography.tiny)
                            .foregroundColor(CawnexColors.mutedForeground)
                    }
                }

                // Budget
                HStack {
                    Text("$\(String(format: "%.2f", wave.budget.spentDollars))")
                        .font(CawnexTypography.caption)
                        .foregroundColor(CawnexColors.cardForeground)
                    Text("of $\(String(format: "%.2f", wave.budget.limitDollars))")
                        .font(CawnexTypography.caption)
                        .foregroundColor(CawnexColors.mutedForeground)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 12))
                        .foregroundColor(CawnexColors.mutedForeground)
                }
            }
            .padding(CawnexSpacing.lg)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .buttonStyle(.plain)
    }

    // MARK: - States

    private var loadingView: some View {
        VStack(spacing: CawnexSpacing.lg) {
            ProgressView().tint(CawnexColors.primary)
            Text("Loading waves...")
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }

    private var emptyView: some View {
        VStack(spacing: CawnexSpacing.md) {
            Image(systemName: "waveform.path")
                .font(.system(size: 36))
                .foregroundColor(CawnexColors.mutedForeground)
            Text("No waves yet")
                .font(CawnexTypography.heading3)
                .foregroundColor(CawnexColors.cardForeground)
            Text("Create a wave from your goal MVIs to start execution")
                .font(CawnexTypography.caption)
                .foregroundColor(CawnexColors.mutedForeground)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 80)
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: CawnexSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 32))
                .foregroundColor(.red)
            Text(message)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }
}

#Preview {
    WaveListScreen(
        viewModel: WaveListViewModel(
            waveService: InMemoryWaveService(store: AppStore()),
            projectId: "proj-001"
        )
    )
    .preferredColorScheme(.dark)
}
