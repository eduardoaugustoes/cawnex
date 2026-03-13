import SwiftUI

struct MVICard: View {
    let mvi: MVI
    var onTap: () -> Void = {}
    var onStatusChange: (MVIStatus) -> Void = { _ in }

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.md) {
            headerRow
            if mvi.status == .refining {
                refiningContent
            } else {
                statsContent
            }
            if mvi.status == .executing || mvi.status == .ready {
                actionButtons
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }

    // MARK: - Header

    private var headerRow: some View {
        Button(action: onTap) {
            HStack {
                Text(mvi.name)
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .lineLimit(1)
                Spacer()
                StatusChip(
                    label: mvi.status.label,
                    color: mvi.status.color,
                    icon: mvi.status.icon,
                    transitions: mvi.status.transitions,
                    onTransition: onStatusChange
                )
                if mvi.status == .shipped || mvi.status == .executing {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }
        }
        .buttonStyle(.plain)
    }

    // MARK: - Refining Content

    private var refiningContent: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack(spacing: CawnexSpacing.sm) {
                ProgressView()
                    .scaleEffect(0.7)
                    .tint(CawnexColors.primaryLight)
                Text("Dev Murder generating tasks…")
                    .font(CawnexTypography.footnote)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            Text(mvi.description)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
                .lineLimit(2)
        }
    }

    // MARK: - Stats Content

    private var statsContent: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            taskRow
            costRow
            progressBar
            if mvi.roi > 0 {
                roiRow
            }
        }
    }

    private var taskRow: some View {
        Text("\(mvi.tasksDone)/\(mvi.tasksTotal) tasks · \(mvi.aiMinutes) min AI · \(mvi.humanDays) human")
            .font(CawnexTypography.tiny)
            .foregroundStyle(CawnexColors.mutedForeground)
    }

    private var costRow: some View {
        HStack(spacing: CawnexSpacing.xs) {
            Text("$\(mvi.aiCost as NSDecimalNumber)")
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.primary)
            Text("vs")
                .font(CawnexTypography.tiny)
                .foregroundStyle(CawnexColors.mutedForeground)
            Text("~$\(mvi.humanEquiv as NSDecimalNumber)")
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private var progressBar: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(CawnexColors.muted)
                    .frame(height: 6)
                RoundedRectangle(cornerRadius: 3)
                    .fill(mvi.status.color)
                    .frame(width: geo.size.width * progress, height: 6)
            }
        }
        .frame(height: 6)
    }

    private var roiRow: some View {
        HStack(spacing: CawnexSpacing.xs) {
            Image(systemName: "arrow.up.right")
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(CawnexColors.accent)
            Text("\(mvi.roi)x ROI · saved ~$\(mvi.humanEquiv as NSDecimalNumber)")
                .font(CawnexTypography.mono)
                .foregroundStyle(CawnexColors.accent)
        }
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        HStack(spacing: CawnexSpacing.sm) {
            if mvi.status == .ready {
                Button {
                    onStatusChange(.executing)
                } label: {
                    Text("Approve")
                        .font(CawnexTypography.captionBold)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 36)
                        .background(CawnexColors.success)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
                }
                .buttonStyle(.plain)
            }

            Button(action: onTap) {
                Text("Review Tasks")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(maxWidth: .infinity)
                    .frame(height: 36)
                    .background(CawnexColors.muted)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Helpers

    private var progress: Double {
        guard mvi.tasksTotal > 0 else { return 0 }
        return Double(mvi.tasksDone) / Double(mvi.tasksTotal)
    }
}
