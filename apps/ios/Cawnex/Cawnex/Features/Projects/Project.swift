import Foundation

struct TaskCounts: Equatable {
    let done: Int
    let active: Int
    let refined: Int
    let draft: Int

    var total: Int { done + active + refined + draft }

    var summary: String {
        "Tasks · \(done) done · \(active) active · \(refined) refined · \(draft) draft"
    }
}

struct Project: Identifiable, Equatable {
    let id: String
    let name: String
    let description: String
    let isActive: Bool
    let tasks: TaskCounts
    let creditsSpent: Decimal
    let humanEquivSaved: Decimal
}

extension Project {
    static let preview = Project(
        id: "1",
        name: "Cawnex",
        description: "Multi-agent AI orchestration platform",
        isActive: true,
        tasks: TaskCounts(done: 5, active: 3, refined: 4, draft: 6),
        creditsSpent: 182,
        humanEquivSaved: 14000
    )
}
