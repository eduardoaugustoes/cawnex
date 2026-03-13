import SwiftUI

struct StatusChip<S: Hashable>: View {
    let label: String
    let color: Color
    let icon: String
    let transitions: [StatusTransition<S>]
    var onTransition: (S) -> Void = { _ in }

    var body: some View {
        if transitions.isEmpty {
            chipLabel(showChevron: false)
        } else {
            Menu {
                ForEach(transitions) { transition in
                    Button {
                        onTransition(transition.target)
                    } label: {
                        Label(transition.label, systemImage: transition.icon)
                    }
                }
            } label: {
                chipLabel(showChevron: true)
            }
        }
    }

    private func chipLabel(showChevron: Bool) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 9, weight: .semibold))
            Text(label)
                .font(CawnexTypography.tinyMedium)
            if showChevron {
                Image(systemName: "chevron.down")
                    .font(.system(size: 7, weight: .bold))
            }
        }
        .foregroundStyle(color)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.15))
        .clipShape(Capsule())
    }
}

// MARK: - Convenience Initializers

extension StatusChip {
    init(milestoneStatus: MilestoneStatus, onTransition: @escaping (S) -> Void = { _ in }) where S == MilestoneStatus {
        self.label = milestoneStatus.label
        self.color = milestoneStatus.color
        self.icon = milestoneStatus.icon
        self.transitions = milestoneStatus.transitions
        self.onTransition = onTransition
    }

    init(projectStatus: ProjectStatus, onTransition: @escaping (S) -> Void = { _ in }) where S == ProjectStatus {
        self.label = projectStatus.label
        self.color = projectStatus.color
        self.icon = projectStatus.icon
        self.transitions = projectStatus.transitions
        self.onTransition = onTransition
    }

    init(goalStatus: GoalStatus) where S == GoalStatus {
        self.label = goalStatus.label
        self.color = goalStatus.color
        self.icon = goalStatus.icon
        self.transitions = []
        self.onTransition = { _ in }
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        VStack(spacing: 16) {
            StatusChip(milestoneStatus: .planned)
            StatusChip(milestoneStatus: .active)
            StatusChip(milestoneStatus: .paused)
            StatusChip(milestoneStatus: .completed)
            Divider()
            StatusChip(projectStatus: .draft)
            StatusChip(projectStatus: .active)
            StatusChip(projectStatus: .completed)
            StatusChip(projectStatus: .archived)
        }
    }
}
