import Foundation

/// BacklogService that reads milestones from the real API.
final class APIBacklogService: BacklogService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func listMilestones(projectId: String) async throws -> [Milestone] {
        guard let response: MilestonesResponseDTO = try? await client.get("/projects/\(projectId)/milestones") else {
            return []
        }

        return response.milestones.enumerated().map { index, m in
            Milestone(
                id: m.id,
                name: m.name,
                description: m.description,
                status: mapStatus(m.status),
                tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
                creditsSpent: 0,
                humanEquivSaved: 0,
                roi: 0,
                goals: m.goals.map { g in
                    Goal(
                        id: g.id,
                        name: g.name,
                        status: mapGoalStatus(g.status),
                        mviCount: g.mvi_count ?? 0,
                        mvisComplete: g.mvis_complete ?? 0
                    )
                }
            )
        }
    }

    func createMilestone(projectId: String, name: String, description: String) async throws -> Milestone {
        // Creation is handled by the AI planning chat, not manual
        Milestone(
            id: UUID().uuidString,
            name: name,
            description: description,
            status: .planned,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0,
            roi: 0,
            goals: []
        )
    }

    func updateMilestone(projectId: String, milestoneId: String, name: String, description: String) async throws -> Milestone {
        Milestone(
            id: milestoneId,
            name: name,
            description: description,
            status: .planned,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0,
            roi: 0,
            goals: []
        )
    }

    private func mapStatus(_ status: String) -> MilestoneStatus {
        switch status {
        case "active": .active
        case "paused": .paused
        case "completed": .completed
        default: .planned
        }
    }

    private func mapGoalStatus(_ status: String) -> GoalStatus {
        switch status {
        case "active": .active
        case "completed": .completed
        case "rejected": .rejected
        default: .planned
        }
    }
}

// MARK: - DTOs

private struct GoalResponseDTO: Decodable {
    let id: String
    let name: String
    let description: String
    let status: String
    let mvi_count: Int?
    let mvis_complete: Int?
}

private struct MilestoneResponseDTO: Decodable {
    let id: String
    let name: String
    let description: String
    let status: String
    let goals: [GoalResponseDTO]
}

private struct MilestonesResponseDTO: Decodable {
    let milestones: [MilestoneResponseDTO]
}
