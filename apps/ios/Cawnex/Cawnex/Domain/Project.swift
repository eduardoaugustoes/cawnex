import Foundation
import SwiftUI

// MARK: - Project Status

enum ProjectStatus: String, Equatable, CaseIterable, Hashable {
    case draft = "Draft"
    case active = "Active"
    case paused = "Paused"
    case completed = "Completed"
    case archived = "Archived"

    var label: String { rawValue }

    var color: Color {
        switch self {
        case .draft: CawnexColors.mutedForeground
        case .active: CawnexColors.primary
        case .paused: CawnexColors.warning
        case .completed: CawnexColors.success
        case .archived: CawnexColors.muted
        }
    }

    var icon: String {
        switch self {
        case .draft: "doc"
        case .active: "play.fill"
        case .paused: "pause.fill"
        case .completed: "checkmark.circle.fill"
        case .archived: "archivebox"
        }
    }

    var transitions: [StatusTransition<ProjectStatus>] {
        switch self {
        case .draft:
            [StatusTransition(label: "Start", icon: "play.fill", target: .active, style: .primary)]
        case .active:
            [
                StatusTransition(label: "Pause", icon: "pause.fill", target: .paused, style: .secondary),
                StatusTransition(label: "Archive", icon: "archivebox", target: .archived, style: .destructive),
            ]
        case .paused:
            [
                StatusTransition(label: "Resume", icon: "play.fill", target: .active, style: .primary),
                StatusTransition(label: "Archive", icon: "archivebox", target: .archived, style: .destructive),
            ]
        case .completed:
            [StatusTransition(label: "Archive", icon: "archivebox", target: .archived, style: .secondary)]
        case .archived:
            []
        }
    }
}

// MARK: - Project

struct Project: Identifiable, Equatable {
    let id: String
    let name: String
    let description: String
    let status: ProjectStatus
    let tasks: TaskCounts
    let creditsSpent: Decimal
    let humanEquivSaved: Decimal
}

extension Project {
    static let preview = Project(
        id: "1",
        name: "Cawnex",
        description: "Multi-agent AI orchestration platform",
        status: .active,
        tasks: TaskCounts(done: 5, active: 3, refined: 4, draft: 6),
        creditsSpent: 182,
        humanEquivSaved: 14000
    )
}
