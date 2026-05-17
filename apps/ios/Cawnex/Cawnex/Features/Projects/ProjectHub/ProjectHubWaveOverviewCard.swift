import SwiftUI

struct ProjectHubWaveOverviewCard: View {
    let waveOverview: WaveOverviewSummary

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            cardHeader
            crowCompletionRow
            mviApprovalRow
            waveStatusRow
            councilDecisionRow
        }
        .padding(CawnexSpacing.lg)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.primary.opacity(0.27), lineWidth: 1)
        )
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
            Text("Auto-refresh")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private var crowCompletionRow: some View {
        HStack {
            HStack(spacing: 8) {
                Image(systemName: "bird.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(CawnexColors.success)
                Text("Crow Completion")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
            Text("\(waveOverview.activeCrows) of \(waveOverview.totalCrows)")
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(CawnexColors.success)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    private var mviApprovalRow: some View {
        HStack {
            HStack(spacing: 8) {
                Image(systemName: "checkmark.circle")
                    .font(.system(size: 14))
                    .foregroundStyle(CawnexColors.warning)
                Text("MVI Approval Queue")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
            Text("\(waveOverview.pendingApprovals) awaiting")
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(CawnexColors.warning)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    private var waveStatusRow: some View {
        HStack {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(waveOverview.activeWaves > 0 ? CawnexColors.success : CawnexColors.info)
                    .frame(width: 8, height: 8)
                Text("Wave Status")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
            Text("\(waveOverview.activeWaves) active")
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(waveOverview.activeWaves > 0 ? CawnexColors.success : CawnexColors.info)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    private var councilDecisionRow: some View {
        HStack {
            HStack(spacing: 8) {
                Image(systemName: "person.2.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(CawnexColors.accent)
                Text("Council Tasks")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Spacer()
            Text("\(waveOverview.pendingHumanTasks) pending")
                .font(CawnexTypography.footnoteMedium)
                .foregroundStyle(CawnexColors.accent)
        }
        .padding(.horizontal, CawnexSpacing.md)
        .padding(.vertical, CawnexSpacing.sm)
        .background(CawnexColors.muted)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }
}

#Preview {
    ProjectHubWaveOverviewCard(
        waveOverview: WaveOverviewSummary(
            activeCrows: 5,
            totalCrows: 12,
            pendingApprovals: 3,
            pendingHumanTasks: 2,
            activeWaves: 1
        )
    )
    .padding()
    .background(CawnexColors.background)
}
