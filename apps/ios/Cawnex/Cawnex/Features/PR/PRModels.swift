import Foundation
import SwiftUI

// MARK: - PR Status

enum PRStatus: String, Equatable {
    case ready = "Ready"
    case changesRequested = "Changes Requested"
    case merged = "Merged"

    var color: Color {
        switch self {
        case .ready: CawnexColors.warning
        case .changesRequested: CawnexColors.destructive
        case .merged: CawnexColors.success
        }
    }
}

// MARK: - Verdict

enum VerdictStatus: String, Equatable {
    case approved = "Approved"
    case changesNeeded = "Changes Needed"
    case rejected = "Rejected"

    var color: Color {
        switch self {
        case .approved: CawnexColors.success
        case .changesNeeded: CawnexColors.warning
        case .rejected: CawnexColors.destructive
        }
    }

    var icon: String {
        switch self {
        case .approved: "checkmark.shield.fill"
        case .changesNeeded: "exclamationmark.triangle.fill"
        case .rejected: "xmark.shield.fill"
        }
    }
}

enum VerdictConfidence: String, Equatable {
    case high = "High confidence"
    case medium = "Medium confidence"
    case low = "Low confidence"
}

// MARK: - Finding

enum FindingType: Equatable {
    case check
    case warning

    var color: Color {
        switch self {
        case .check: CawnexColors.success
        case .warning: CawnexColors.warning
        }
    }

    var icon: String {
        switch self {
        case .check: "checkmark.circle.fill"
        case .warning: "exclamationmark.triangle.fill"
        }
    }
}

struct PRFinding: Identifiable, Equatable {
    let id: String
    let text: String
    let type: FindingType
}

// MARK: - Verdict

struct PRVerdict: Equatable {
    let status: VerdictStatus
    let crowName: String
    let confidence: VerdictConfidence
    let filesAnalyzed: Int
    let summary: String
    let findings: [PRFinding]
}

// MARK: - Plan vs Execution

struct PlanStep: Identifiable, Equatable {
    let id: String
    let crowName: String
    let badgeColor: Color
    let plan: String
    let executed: String
    let hint: String?
}

// MARK: - Conversation

struct PRChatMessage: Identifiable, Equatable {
    let id: String
    let role: ChatRole
    let content: String
    let riskBadge: String?
}

// MARK: - PR Review Detail

struct PRReviewDetail: Equatable {
    let title: String
    let branch: String
    let status: PRStatus
    let breadcrumbMVI: String
    let breadcrumbTask: String
    let creditsCost: Int
    let aiMinutes: Int
    let filesChanged: Int
    let linesAdded: Int
    let linesRemoved: Int
    let verdict: PRVerdict
    let planSteps: [PlanStep]
    let suggestedQuestions: [String]
    let conversation: [PRChatMessage]
}
