import SwiftUI

@Observable
fileprivate final class WaveOverviewTimerViewModel {
    var elapsedSeconds: Int = 0
    private var timer: Timer?

    func startTimer() {
        elapsedSeconds = 0
        stopTimer()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.elapsedSeconds += 1
        }
    }

    func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    deinit {
        stopTimer()
    }
}

struct WaveOverviewCard: View {
    let waveOverview: WaveOverview
    @State private var timerViewModel = WaveOverviewTimerViewModel()

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            cardHeader
            crowCompletionRow
            mviApprovalRow
            waveStatusBadgeRow
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .onAppear {
            timerViewModel.startTimer()
        }
        .onDisappear {
            timerViewModel.stopTimer()
        }
    }

    private var cardHeader: some View {
        HStack {
            HStack(spacing: 10) {
                Image(systemName: "waveform.path")
                    .font(.system(size: 18))
                    .foregroundStyle(CawnexColors.primary)
                Text("Wave Overview")
                    .font(CawnexTypography.sectionTitle)
                    .foregroundStyle(CawnexColors.cardForeground)
            }
            Spacer()
        }
    }

    private var crowCompletionRow: some View {
        HStack(spacing: CawnexSpacing.md) {
            Image(systemName: "crow.fill")
                .font(.system(size: 16))
                .foregroundStyle(CawnexColors.mutedForeground)
            Text("\(waveOverview.crowsCompleted) of \(waveOverview.crowsTotal) Crows completed")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.cardForeground)
            Spacer()
        }
    }

    private var mviApprovalRow: some View {
        HStack(spacing: CawnexSpacing.md) {
            Image(systemName: "checkmark.circle")
                .font(.system(size: 16))
                .foregroundStyle(CawnexColors.mutedForeground)
            Text("\(waveOverview.mvisAwaitingReview) awaiting founder review")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.cardForeground)
            Spacer()
        }
    }

    private var waveStatusBadgeRow: some View {
        HStack(spacing: CawnexSpacing.md) {
            HStack(spacing: 6) {
                Image(systemName: waveOverview.waveStatus.icon)
                    .font(.system(size: 12, weight: .semibold))
                Text(waveOverview.waveStatus.rawValue)
                    .font(CawnexTypography.label)
                if let elapsed = elapsedDisplayValue {
                    Text(elapsed)
                        .font(CawnexTypography.label)
                }
            }
            .foregroundStyle(waveOverview.waveStatus.color)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(waveOverview.waveStatus.color.opacity(0.15))
            .clipShape(Capsule())
            Spacer()
        }
    }

    private var elapsedDisplayValue: String? {
        guard waveOverview.waveStatus == .running else { return nil }
        let total = (waveOverview.elapsedMinutes ?? 0) * 60 + timerViewModel.elapsedSeconds
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let seconds = total % 60

        if hours > 0 {
            return String(format: "%dh %dm", hours, minutes)
        } else if minutes > 0 {
            return String(format: "%dm %ds", minutes, seconds)
        } else {
            return String(format: "%ds", seconds)
        }
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        VStack(spacing: CawnexSpacing.lg) {
            WaveOverviewCard(
                waveOverview: WaveOverview(
                    crowsCompleted: 12,
                    crowsTotal: 15,
                    mvisAwaitingReview: 2,
                    waveStatus: .running,
                    elapsedMinutes: 45
                )
            )
            WaveOverviewCard(
                waveOverview: WaveOverview(
                    crowsCompleted: 8,
                    crowsTotal: 10,
                    mvisAwaitingReview: 0,
                    waveStatus: .idle,
                    elapsedMinutes: nil
                )
            )
            Spacer()
        }
        .padding(CawnexSpacing.xl)
    }
}
