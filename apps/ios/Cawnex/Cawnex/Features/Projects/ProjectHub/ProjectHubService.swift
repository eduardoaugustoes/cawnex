import Foundation

protocol ProjectHubService {
    func getProjectHub(_ projectId: String) async throws -> ProjectHubDetail?
}

final class InMemoryProjectHubService: ProjectHubService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getProjectHub(_ projectId: String) async throws -> ProjectHubDetail? {
        guard let project = store.projects.first(where: { $0.id == projectId }) else {
            return nil
        }

        let total = project.tasks.total
        let progress = total > 0 ? (project.tasks.done * 100) / total : 0
        let roi = project.humanEquivSaved > 0 && project.creditsSpent > 0
            ? Int(NSDecimalNumber(decimal: project.humanEquivSaved / project.creditsSpent).intValue)
            : 0

        return ProjectHubDetail(
            project: project,
            stats: ProjectStats(
                progress: progress,
                tasksDone: project.tasks.done,
                tasksTotal: total,
                pendingApprovals: 3,
                roi: roi
            ),
            documents: [
                ProjectDocument(id: "d1", type: .vision, status: .draft),
                ProjectDocument(id: "d2", type: .architecture, status: .notStarted),
                ProjectDocument(id: "d3", type: .glossary, status: .notStarted),
                ProjectDocument(id: "d4", type: .design, status: .notStarted),
            ],
            backlog: BacklogSummary(
                pipeline: project.tasks,
                activeMilestones: 3,
                mvisShipped: 5,
                mvisTotal: 18
            ),
            murders: [
                MurderSummary(id: "m1", name: "Dev Murder", crowCount: 4, isActive: true),
                MurderSummary(id: "m2", name: "Editorial Murder", crowCount: 2, isActive: false),
            ]
        )
    }
}
