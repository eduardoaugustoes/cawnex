import Foundation

// MARK: - Implementation Step

struct ImplementationStep: Identifiable, Equatable {
    let id: String
    let text: String
    let completed: Bool
}

// MARK: - Acceptance Criterion

struct AcceptanceCriterion: Identifiable, Equatable {
    let id: String
    let text: String
    let passed: Bool
}

// MARK: - Task PR

struct TaskPR: Equatable {
    let number: String
    let title: String
    let branch: String
    let status: String
    let linesAdded: Int
    let linesRemoved: Int
    let filesChanged: Int
    let coverage: Int
}

// MARK: - Assigned Crow

struct AssignedCrow: Equatable {
    let name: String
    let role: String
    let model: String
    let behaviorState: CrowBehaviorState
    let executionMinutes: Int
    let filesChanged: Int
}

// MARK: - Task Detail

struct TaskDetail: Equatable {
    let id: String
    let name: String
    let status: TaskStatus
    let description: String
    let breadcrumb: String
    let humanEstimate: String
    let aiCost: Decimal
    let roi: Int
    let assignedCrow: AssignedCrow
    let implementationSteps: [ImplementationStep]
    let acceptanceCriteria: [AcceptanceCriterion]
    let pr: TaskPR?
}
