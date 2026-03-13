import Foundation
import SwiftUI

// MARK: - Milestone Status

enum MilestoneStatus: String, Equatable, CaseIterable, Hashable {
    case planned = "Planned"
    case active = "Active"
    case paused = "Paused"
    case completed = "Completed"

    var label: String { rawValue }

    var color: Color {
        switch self {
        case .planned: CawnexColors.mutedForeground
        case .active: CawnexColors.primary
        case .paused: CawnexColors.warning
        case .completed: CawnexColors.success
        }
    }

    var icon: String {
        switch self {
        case .planned: "calendar"
        case .active: "play.fill"
        case .paused: "pause.fill"
        case .completed: "checkmark.circle.fill"
        }
    }

    var transitions: [StatusTransition<MilestoneStatus>] {
        switch self {
        case .planned:
            [StatusTransition(label: "Start", icon: "play.fill", target: .active, style: .primary)]
        case .active:
            [StatusTransition(label: "Pause", icon: "pause.fill", target: .paused, style: .secondary)]
        case .paused:
            [StatusTransition(label: "Resume", icon: "play.fill", target: .active, style: .primary)]
        case .completed:
            []
        }
    }
}

// MARK: - Milestone

struct Milestone: Identifiable, Equatable {
    let id: String
    let name: String
    let description: String
    var status: MilestoneStatus
    let tasks: TaskCounts
    let creditsSpent: Decimal
    let humanEquivSaved: Decimal
    let roi: Int
    let goals: [Goal]

    var progress: Int {
        guard tasks.total > 0 else { return 0 }
        return (tasks.done * 100) / tasks.total
    }
}

// MARK: - Goal Status

enum GoalStatus: String, Equatable, Hashable {
    case planned = "Planned"
    case active = "Active"
    case paused = "Paused"
    case completed = "Completed"
    case rejected = "Rejected"

    var label: String { rawValue }

    var color: Color {
        switch self {
        case .planned: CawnexColors.mutedForeground
        case .active: CawnexColors.primary
        case .paused: CawnexColors.warning
        case .completed: CawnexColors.success
        case .rejected: CawnexColors.destructive
        }
    }

    var icon: String {
        switch self {
        case .planned: "calendar"
        case .active: "play.fill"
        case .paused: "pause.fill"
        case .completed: "checkmark.circle.fill"
        case .rejected: "xmark.circle.fill"
        }
    }
}

// MARK: - Goal

struct Goal: Identifiable, Equatable {
    let id: String
    let name: String
    let status: GoalStatus
    let mviCount: Int
    let mvisComplete: Int
}
