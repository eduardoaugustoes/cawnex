import Foundation

// MARK: - Milestone Definition Section

enum MilestoneDefinitionStatus: String, Equatable {
    case pending, complete
}

struct MilestoneDefinitionSection: Identifiable, Equatable {
    let id: String
    let title: String
    let status: MilestoneDefinitionStatus
}

// MARK: - Milestone Detail

struct MilestoneDetail: Equatable {
    let milestone: Milestone
    let breadcrumb: String
    let sections: [MilestoneDefinitionSection]
    let messages: [ChatMessage]
    let goals: [MilestoneGoalSummary]

    var completedSections: Int {
        sections.filter { $0.status == .complete }.count
    }

    var totalSections: Int {
        sections.count
    }
}

// MARK: - Goal Summary (for milestone detail)

struct MilestoneGoalSummary: Identifiable, Equatable {
    let id: String
    let name: String
    let status: GoalStatus
    let description: String
    let mviCount: Int
    let taskCount: Int
}
