import Foundation

/// GoalService that reads goal data from the milestones backlog + MVIs from the API.
final class APIGoalService: GoalService {
    private let client: APIClient
    private let store: AppStore

    init(client: APIClient, store: AppStore) {
        self.client = client
        self.store = store
    }

    func getGoalDetail(projectId: String, goalId: String) async throws -> GoalDetail {
        // Load goal context (includes goal, milestone, existing MVIs)
        let context: GoalContextResp = try await client.get(
            "/projects/\(projectId)/goals/\(goalId)/context"
        )

        let projectName = store.projects.first { $0.id == projectId }?.name ?? "Project"

        let mvis = context.existing_mvis.map { m in
            MVI(
                id: m.id,
                name: m.name,
                status: .draft,
                tasksDone: 0,
                tasksTotal: 0,
                aiMinutes: 0,
                humanDays: "~\(Int(m.estimated_hours))h",
                aiCost: 0,
                humanEquiv: Decimal(m.estimated_hours * 50), // Mid-level rate $50/hr
                roi: 0,
                description: m.description
            )
        }

        let goal = Goal(
            id: context.goal.id,
            name: context.goal.name,
            status: .planned,
            mviCount: mvis.count,
            mvisComplete: 0
        )

        return GoalDetail(
            goal: goal,
            projectName: projectName,
            milestoneName: context.milestone.name,
            creditsSpent: 0,
            humanEquivSaved: 0,
            roi: 0,
            murderName: "Dev Murder",
            crowCount: 0,
            mvis: mvis
        )
    }
}

// MARK: - DTOs

private struct GoalRefDTO: Decodable {
    let id: String
    let name: String
    let description: String
}

private struct MilestoneRefDTO: Decodable {
    let id: String
    let name: String
    let description: String
}

private struct ExistingMVIRefDTO: Decodable {
    let id: String
    let name: String
    let description: String
    let acceptance_criteria: String
    let estimated_hours: Double
}

private struct GoalContextResp: Decodable {
    let goal: GoalRefDTO
    let milestone: MilestoneRefDTO
    let sibling_goals: [GoalRefDTO]
    let documents: [String: String]
    let existing_mvis: [ExistingMVIRefDTO]
}
