import Foundation
import SwiftUI

// MARK: - MVI Status

enum MVIStatus: String, Equatable, Hashable {
    case draft = "Draft"
    case refining = "Refining"
    case ready = "Ready"
    case executing = "Executing"
    case shipped = "Shipped"
    // The engine gave up: reviewer-blocked + fixer cap hit, or a crow type
    // exhausted its retry budget. Distinct from `.rejected`, which means a
    // human or the council actively declined the MVI.
    case failed = "Failed"
    case rejected = "Rejected"

    var label: String { rawValue }

    var color: Color {
        switch self {
        case .draft: CawnexColors.mutedForeground
        case .refining: CawnexColors.primaryLight
        case .ready: CawnexColors.info
        case .executing: CawnexColors.warning
        case .shipped: CawnexColors.success
        case .failed, .rejected: CawnexColors.destructive
        }
    }

    var icon: String {
        switch self {
        case .draft: "doc"
        case .refining: "sparkles"
        case .ready: "checkmark.shield"
        case .executing: "bolt.fill"
        case .shipped: "shippingbox.fill"
        case .failed: "exclamationmark.triangle.fill"
        case .rejected: "xmark.circle.fill"
        }
    }

    var transitions: [StatusTransition<MVIStatus>] {
        switch self {
        case .draft: []
        case .refining: []
        case .ready:
            [
                StatusTransition(label: "Approve", icon: "checkmark", target: .executing, style: .primary),
                StatusTransition(label: "Reject", icon: "xmark", target: .rejected, style: .destructive),
            ]
        case .executing: []
        case .shipped: []
        case .failed, .rejected:
            [StatusTransition(label: "Reopen", icon: "arrow.counterclockwise", target: .draft, style: .secondary)]
        }
    }
}

// MARK: - MVI

struct MVI: Identifiable, Equatable {
    let id: String
    let name: String
    let status: MVIStatus
    let tasksDone: Int
    let tasksTotal: Int
    let aiMinutes: Int
    let humanDays: String
    let aiCost: Decimal
    let humanEquiv: Decimal
    let roi: Int
    let description: String
}

// MARK: - Goal Detail

struct GoalDetail: Equatable {
    let goal: Goal
    let projectName: String
    let milestoneName: String
    let creditsSpent: Decimal
    let humanEquivSaved: Decimal
    let roi: Int
    let murderName: String
    let crowCount: Int
    let mvis: [MVI]
}
