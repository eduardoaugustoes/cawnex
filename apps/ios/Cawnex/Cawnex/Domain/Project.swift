import Foundation
import SwiftUI

// MARK: - Project Status

enum ProjectStatus: String, Equatable, CaseIterable, Hashable {
    case draft = "Draft"
    case active = "Active"
    case running = "Running"
    case idle = "Idle"
    case completed = "Completed"
    case paused = "Paused"
    case archived = "Archived"

    var label: String { rawValue }

    var color: Color {
        switch self {
        case .draft: CawnexColors.mutedForeground
        case .active: CawnexColors.primary
        case .running: CawnexColors.success
        case .idle: CawnexColors.warning
        case .completed: CawnexColors.success
        case .paused: CawnexColors.warning
        case .archived: CawnexColors.muted
        }
    }

    var icon: String {
        switch self {
        case .draft: "doc"
        case .active: "play.circle"
        case .running: "play.fill"
        case .idle: "pause.circle"
        case .completed: "checkmark.circle.fill"
        case .paused: "pause.fill"
        case .archived: "archivebox"
        }
    }

    var transitions: [StatusTransition<ProjectStatus>] { [] }
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
        status: .running,
        tasks: TaskCounts(done: 5, active: 3, refined: 4, draft: 6),
        creditsSpent: 182,
        humanEquivSaved: 14000
    )
}
