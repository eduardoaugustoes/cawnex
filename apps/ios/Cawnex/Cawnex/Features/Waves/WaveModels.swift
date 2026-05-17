import Foundation
import SwiftUI

// MARK: - Wave Status

enum WaveStatus: String, Equatable, CaseIterable, Hashable {
    case planning
    case approved
    case executing
    case paused
    case review
    // Layer A wave-state extension — Council pipeline phases between
    // `review` and `delivered`.
    case integrating
    case needsRework = "needs_rework"
    case underCouncilReview = "under_council_review"
    case underHumanReview = "under_human_review"
    case steered
    case delivered
    case cancelled

    var label: String {
        switch self {
        case .planning: "Planning"
        case .approved: "Approved"
        case .executing: "Executing"
        case .paused: "Paused"
        case .review: "Review"
        case .integrating: "Integrating"
        case .needsRework: "Needs Rework"
        case .underCouncilReview: "Council Review"
        case .underHumanReview: "Awaiting"
        case .steered: "Steered"
        case .delivered: "Delivered"
        case .cancelled: "Cancelled"
        }
    }

    var color: Color {
        switch self {
        case .planning: CawnexColors.mutedForeground
        case .approved: CawnexColors.primary
        case .executing: CawnexColors.primary
        case .paused: CawnexColors.warning
        case .review: Color.orange
        case .integrating: CawnexColors.primary
        case .needsRework: CawnexColors.warning
        case .underCouncilReview: CawnexColors.primary
        case .underHumanReview: CawnexColors.warning
        case .steered: Color.orange
        case .delivered: CawnexColors.success
        case .cancelled: CawnexColors.destructive
        }
    }

    var icon: String {
        switch self {
        case .planning: "pencil"
        case .approved: "checkmark.seal"
        case .executing: "play.fill"
        case .paused: "pause.fill"
        case .review: "eye"
        case .integrating: "arrow.triangle.merge"
        case .needsRework: "arrow.uturn.backward.circle"
        case .underCouncilReview: "person.3"
        case .underHumanReview: "hand.raised"
        case .steered: "arrow.triangle.turn.up.right.diamond"
        case .delivered: "checkmark.circle.fill"
        case .cancelled: "xmark.circle.fill"
        }
    }

    var isTerminal: Bool {
        self == .delivered || self == .cancelled
    }

    /// Any non-terminal wave is "active" for list-grouping purposes —
    /// includes planning, approved, executing, paused, review, steered,
    /// AND the Layer A pipeline phases (integrating, needs_rework,
    /// under_council_review, under_human_review). Without this, waves in
    /// intermediate states fall into a UI limbo (not active, not terminal)
    /// and are invisible on the Waves list screen.
    var isActive: Bool {
        !isTerminal
    }
}

// MARK: - Wave Budget

struct WaveBudget: Equatable {
    let spent: Int
    let limit: Int

    var remaining: Int { limit - spent }
    var percentage: Double { limit > 0 ? Double(spent) / Double(limit) : 0 }
    var spentDollars: Double { Double(spent) / 1_000_000.0 }
    var limitDollars: Double { Double(limit) / 1_000_000.0 }
}

// MARK: - Wave Progress

struct WaveProgress: Equatable {
    let mvisTotal: Int
    let mvisShipped: Int
    let tasksDone: Int
    let tasksTotal: Int
}

// MARK: - Wave Summary (list view)

struct WaveSummary: Identifiable, Equatable {
    let id: String
    let status: WaveStatus
    let directive: String
    let progress: WaveProgress
    let budget: WaveBudget
    let createdAt: String
}

// MARK: - Wave MVI (detail view)

struct WaveMVI: Identifiable, Equatable {
    let id: String
    let name: String
    let status: String
    let description: String
    let tasksDone: Int
    let tasksTotal: Int
    let canShip: Bool
    let cost: Int
}

// MARK: - Wave Event

struct WaveEvent: Identifiable, Equatable {
    let id: String
    let eventType: String
    let message: String
    let color: String
    let timestamp: String
    let extra: [String: String]

    var dotColor: Color {
        switch color {
        case "blue": .blue
        case "green": CawnexColors.success
        case "red": CawnexColors.destructive
        case "yellow": CawnexColors.warning
        case "purple": CawnexColors.primary
        case "orange": .orange
        default: CawnexColors.mutedForeground
        }
    }

    var icon: String {
        switch eventType {
        case "wave_activated": "bolt.fill"
        case "worker_warming": "flame.fill"
        case "worker_ready": "checkmark.seal.fill"
        case "crow_assigned": "bird.fill"
        case "crow_completed": "checkmark.circle.fill"
        case "crow_failed": "xmark.circle.fill"
        case "mvi_ready": "gift.fill"
        case "mvi_shipped": "shippingbox.fill"
        case "human_task_created": "hand.raised.fill"
        case "human_task_completed": "hand.thumbsup.fill"
        case "task_blocked": "lock.fill"
        case "task_unblocked": "lock.open.fill"
        case "wave_paused": "pause.fill"
        case "wave_cancelled": "xmark.circle.fill"
        case "budget_warning": "exclamationmark.triangle.fill"
        case "budget_exceeded": "exclamationmark.octagon.fill"
        default: "circle.fill"
        }
    }
}

// MARK: - Wave Detail (full view)

struct WaveDetail: Equatable {
    let wave: WaveSummary
    let mvis: [WaveMVI]
    let humanTasks: [HumanTask]
}

// MARK: - Wave Events Page

struct WaveEventsPage: Equatable {
    let events: [WaveEvent]
    let nextCursor: String?
}

// MARK: - Create Wave Response

struct CreateWaveResponse: Equatable {
    let waveId: String
    let status: String
    let mviIds: [String]
}
