import Foundation

/// ProjectHubService that calls the real Cawnex API.
final class APIProjectHubService: ProjectHubService {
    private let client: APIClient
    private let store: AppStore

    init(client: APIClient, store: AppStore) {
        self.client = client
        self.store = store
    }

    func getProjectHub(_ projectId: String) async throws -> ProjectHubDetail? {
        let response: HubResponseDTO = try await client.get("/projects/\(projectId)/hub")

        let documents = response.documents.map { doc in
            ProjectDocument(
                id: doc.type,
                type: DocumentType(rawValue: doc.type) ?? .vision,
                status: mapDocStatus(doc.status)
            )
        }

        let murders = (response.project.murders ?? ["dev"]).map { murder in
            MurderSummary(id: murder, name: "\(murder.capitalized) Murder", crowCount: 0, isActive: false)
        }

        let waves = response.waves
        let budgetSpentMicros = Decimal(waves?.budget_spent ?? 0)
        let creditsSpent = budgetSpentMicros / 1_000_000
        let humanEquivSaved = Decimal(response.stats.tasks_done * 4 * 50)
        let roi = humanEquivSaved > 0 && creditsSpent > 0
            ? Int(truncating: (humanEquivSaved / creditsSpent) as NSDecimalNumber)
            : 0

        return ProjectHubDetail(
            project: Project(
                id: response.project.id,
                name: response.project.name,
                description: response.project.one_liner,
                status: ProjectStatus(rawValue: response.project.status.capitalized) ?? .draft,
                tasks: TaskCounts(done: response.stats.tasks_done, active: waves?.active_count ?? 0, refined: 0, draft: 0),
                creditsSpent: creditsSpent,
                humanEquivSaved: humanEquivSaved
            ),
            stats: ProjectStats(
                progress: response.stats.progress,
                tasksDone: response.stats.tasks_done,
                tasksTotal: response.stats.tasks_total,
                pendingApprovals: response.stats.pending_approvals,
                roi: roi
            ),
            documents: documents,
            backlog: BacklogSummary(
                pipeline: TaskCounts(done: response.stats.tasks_done, active: waves?.active_count ?? 0, refined: 0, draft: 0),
                activeMilestones: waves?.active_count ?? 0,
                mvisShipped: waves?.mvis_shipped ?? 0,
                mvisTotal: waves?.mvis_total ?? 0
            ),
            murders: murders
        )
    }

    private func mapDocStatus(_ status: String) -> DocumentStatus {
        switch status {
        case "complete": .complete
        case "in_progress": .inProgress
        case "draft": .draft
        default: .notStarted
        }
    }
}

// MARK: - DTOs

private struct HubProjectDTO: Decodable {
    let id: String
    let name: String
    let one_liner: String
    let status: String
    let murders: [String]?
}

private struct HubDocumentDTO: Decodable {
    let type: String
    let status: String
}

private struct HubStatsDTO: Decodable {
    let progress: Int
    let tasks_done: Int
    let tasks_total: Int
    let pending_approvals: Int
    let ai_cost_usd: Double
    let ai_call_count: Int
}

private struct HubWavesDTO: Decodable {
    let active_count: Int?
    let pending_ship: Int?
    let pending_human_tasks: Int?
    let budget_spent: Int?
    let budget_limit: Int?
    let mvis_total: Int?
    let mvis_shipped: Int?
}

private struct HubResponseDTO: Decodable {
    let project: HubProjectDTO
    let documents: [HubDocumentDTO]
    let stats: HubStatsDTO
    let waves: HubWavesDTO?
}
