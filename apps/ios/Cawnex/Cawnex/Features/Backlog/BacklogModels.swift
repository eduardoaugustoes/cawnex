import Foundation

enum MilestoneStatus: String, Equatable {
    case inProgress = "In Progress"
    case notStarted = "Not started"
    case completed = "Completed"
}

struct Milestone: Identifiable, Equatable {
    let id: String
    let name: String
    let description: String
    let status: MilestoneStatus
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

struct Goal: Identifiable, Equatable {
    let id: String
    let name: String
    let status: GoalStatus
    let mviCount: Int
    let mvisComplete: Int
}

enum GoalStatus: String, Equatable {
    case active = "Active"
    case planned = "Planned"
    case complete = "Complete"
}
