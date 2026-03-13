import Foundation
import SwiftUI

// MARK: - Task Status

enum TaskStatus: String, Equatable, Hashable {
    case queued = "Queued"
    case building = "Building"
    case reviewing = "Reviewing"
    case completed = "Completed"
    case failed = "Failed"

    var color: Color {
        switch self {
        case .queued: CawnexColors.mutedForeground
        case .building: CawnexColors.primaryLight
        case .reviewing: CawnexColors.info
        case .completed: CawnexColors.success
        case .failed: CawnexColors.destructive
        }
    }

    var icon: String {
        switch self {
        case .queued: "clock"
        case .building: "hammer.fill"
        case .reviewing: "eye.fill"
        case .completed: "checkmark.circle.fill"
        case .failed: "xmark.circle.fill"
        }
    }
}

// MARK: - MVI Task

struct MVITask: Identifiable, Equatable {
    let id: String
    let name: String
    let status: TaskStatus
    let prNumber: String?
    let crowName: String?
}

// MARK: - Active Crow

enum CrowBehaviorState: String, Equatable {
    case scouting = "Scouting"
    case planning = "Planning"
    case building = "Building"
    case hunting = "Hunting"
    case reviewing = "Reviewing"
    case documenting = "Documenting"
    case landed = "Landed"

    var color: Color {
        switch self {
        case .building, .hunting: CawnexColors.success
        case .reviewing, .planning: CawnexColors.info
        case .scouting, .documenting: CawnexColors.primaryLight
        case .landed: CawnexColors.mutedForeground
        }
    }
}

struct ActiveCrow: Identifiable, Equatable {
    let id: String
    let name: String
    let behaviorState: CrowBehaviorState
    let model: String
}

// MARK: - Live Feed Event

enum FeedEventType: Equatable {
    case success
    case warning
    case muted
    case standard

    var color: Color {
        switch self {
        case .success: CawnexColors.success
        case .warning: CawnexColors.warning
        case .muted: CawnexColors.mutedForeground
        case .standard: CawnexColors.cardForeground
        }
    }
}

struct LiveFeedEvent: Identifiable, Equatable {
    let id: String
    let timestamp: String
    let message: String
    let type: FeedEventType
}

// MARK: - Merge Checklist

struct MergeChecklistItem: Identifiable, Equatable {
    let id: String
    let label: String
    let passed: Bool
}

// MARK: - MVI Blackboard Detail

struct MVIBlackboardDetail: Equatable {
    let mvi: MVI
    let breadcrumb: String
    let activeCrows: [ActiveCrow]
    let tasks: [MVITask]
    let liveFeed: [LiveFeedEvent]
    let mergeChecklist: [MergeChecklistItem]

    var canShip: Bool {
        tasks.allSatisfy { $0.status == .completed }
            && mergeChecklist.allSatisfy { $0.passed }
    }
}
