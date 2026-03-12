import SwiftUI

struct ProjectHubStatsRow: View {
    let stats: ProjectStats

    var body: some View {
        HStack(spacing: 10) {
            statCard(value: "\(stats.progress)%", label: "Progress", color: CawnexColors.primary)
            statCard(value: "\(stats.tasksDone)/\(stats.tasksTotal)", label: "Tasks", color: CawnexColors.success)
            statCard(value: "\(stats.pendingApprovals)", label: "Pending", color: CawnexColors.warning)
            statCard(value: "\(stats.roi)x", label: "ROI", color: CawnexColors.accent)
        }
    }

    private func statCard(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(CawnexTypography.heading2)
                .foregroundStyle(color)
            Text(label)
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }
}
