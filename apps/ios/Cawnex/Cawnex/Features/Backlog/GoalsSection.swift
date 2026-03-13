import SwiftUI

struct GoalsSection: View {
    let goals: [Goal]
    let onGoalTap: (Goal) -> Void

    var body: some View {
        VStack(spacing: 6) {
            Rectangle()
                .fill(CawnexColors.border)
                .frame(height: 1)
                .padding(.vertical, 4)

            ForEach(goals) { goal in
                goalRow(goal)
            }
        }
    }

    private func goalRow(_ goal: Goal) -> some View {
        Button {
            onGoalTap(goal)
        } label: {
            HStack {
                HStack(spacing: 8) {
                    Circle()
                        .fill(goal.status.color)
                        .frame(width: 8, height: 8)
                    Text(goal.name)
                        .font(CawnexTypography.captionMedium)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                Spacer()
                Text("\(goal.mvisComplete)/\(goal.mviCount) MVIs")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)
                Image(systemName: "chevron.right")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            .padding(.vertical, 6)
        }
        .buttonStyle(.plain)
    }
}
