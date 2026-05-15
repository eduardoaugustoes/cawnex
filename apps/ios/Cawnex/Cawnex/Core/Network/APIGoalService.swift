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
            let hours = m.estimated_hours?.value ?? 0
            // Backend enriches plan records with execution snapshot state
            // when an MVI has actually run (status, tasks_done, tasks_total
            // overlaid from S#{wave_id}#m{mvi_id}). When no wave has run
            // yet, these fields are absent and we fall back to "draft" /
            // 0 counts — the correct representation of an unstarted MVI.
            return MVI(
                id: m.id,
                name: m.name,
                status: Self.mapStatus(m.status),
                tasksDone: m.tasks_done ?? 0,
                tasksTotal: m.tasks_total ?? 0,
                aiMinutes: 0,
                humanDays: "~\(Int(hours))h",
                aiCost: 0,
                humanEquiv: Decimal(hours * 50), // Mid-level rate $50/hr
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

extension APIGoalService {
    /// Map backend MVI status strings onto the iOS enum. Unknown values
    /// (or absent — when no wave has run) fall back to .draft.
    fileprivate static func mapStatus(_ raw: String?) -> MVIStatus {
        switch (raw ?? "").lowercased() {
        case "draft", "planned", "": return .draft
        case "refining": return .refining
        case "ready", "ready_to_ship": return .ready
        case "executing", "running", "planning", "queued": return .executing
        case "shipped", "completed": return .shipped
        case "rejected", "failed", "cancelled": return .rejected
        default: return .draft
        }
    }
}

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
    let acceptance_criteria: String?
    let estimated_hours: FlexibleDouble?
    // Execution-state fields: present only when the backend's enrichment
    // found a matching execution snapshot for this MVI's wave_id. Absent
    // means "no wave has run yet for this MVI" — defaults to draft + 0
    // counts in the mapping above.
    let status: String?
    let tasks_done: Int?
    let tasks_total: Int?
}

private struct GoalContextResp: Decodable {
    let goal: GoalRefDTO
    let milestone: MilestoneRefDTO
    let sibling_goals: [GoalRefDTO]
    let documents: [String: String]
    let existing_mvis: [ExistingMVIRefDTO]
}
