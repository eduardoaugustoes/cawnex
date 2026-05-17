import SwiftUI

/// WaveOverviewCard displays project state signals: crow completion, MVI queue, wave status, and council decision.
struct WaveOverviewCard: View {
    let state: ProjectState
    var onCouncilTap: () -> Void = {}

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            // Title
            Text("Wave Overview")
                .font(CawnexTypography.sectionTitle)
                .foregroundStyle(CawnexColors.cardForeground)

            // Crow completion badge
            crowBadge

            // MVI approval queue
            mviQueueRow

            // Wave status badge
            waveStatusBadge

            // Council decision callout (optional)
            if let summary = state.councilSummary {
                councilCallout(summary)
            }
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Crow Completion Badge

    private var crowBadge: some View {
        HStack(spacing: CawnexSpacing.sm) {
            Image(systemName: "bird.fill")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(CawnexColors.primaryLight)

            Text(state.crowCompletionLabel)
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()
        }
        .padding(CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    // MARK: - MVI Approval Queue

    private var mviQueueRow: some View {
        HStack(spacing: CawnexSpacing.sm) {
            Image(systemName: "checkmark.square")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(state.mvi_queue_count > 0 ? CawnexColors.warning : CawnexColors.success)

            Text(state.mviQueueLabel)
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            if state.mvi_queue_count > 0 {
                Text("\(state.mvi_queue_count)")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(.white)
                    .frame(width: 20, height: 20)
                    .background(CawnexColors.warning)
                    .clipShape(Circle())
            }
        }
        .padding(CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    // MARK: - Wave Status Badge

    private var waveStatusBadge: some View {
        HStack(spacing: CawnexSpacing.sm) {
            Image(systemName: waveStatusIcon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(waveStatusColor)

            Text(state.waveStatusLabel)
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()
        }
        .padding(CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    private var waveStatusIcon: String {
        switch state.wave_status.status {
        case "running":
            "play.fill"
        case "paused":
            "pause.fill"
        default:
            "circle"
        }
    }

    private var waveStatusColor: Color {
        switch state.wave_status.status {
        case "running":
            CawnexColors.success
        case "paused":
            CawnexColors.warning
        default:
            CawnexColors.mutedForeground
        }
    }

    // MARK: - Council Decision Callout

    private func councilCallout(_ summary: String) -> some View {
        Button(action: onCouncilTap) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "person.2.fill")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(CawnexColors.primary)

                Text(summary)
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .lineLimit(1)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(CawnexSpacing.sm)
            .background(CawnexColors.primary.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Preview

#Preview {
    let state = ProjectState(
        crow_count: 12,
        mvi_queue_count: 2,
        wave_status: WaveStatus(
            status: "running",
            elapsed_seconds: 9000,
            started_at: "2026-05-13T10:00:00Z"
        ),
        council_decision: CouncilDecision(
            approved_count: 4,
            security_flag_count: 1,
            other_count: 0
        )
    )

    return ZStack {
        CawnexColors.background.ignoresSafeArea()
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                WaveOverviewCard(state: state)
                    .padding(CawnexSpacing.lg)
                Spacer()
            }
        }
    }
}
