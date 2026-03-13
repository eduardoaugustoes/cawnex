import Foundation

protocol BacklogService {
    func listMilestones(projectId: String) async throws -> [Milestone]
    func createMilestone(projectId: String, name: String, description: String) async throws -> Milestone
    func updateMilestone(projectId: String, milestoneId: String, name: String, description: String) async throws -> Milestone
}

final class InMemoryBacklogService: BacklogService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func listMilestones(projectId: String) async throws -> [Milestone] {
        guard let project = store.projects.first(where: { $0.id == projectId }) else {
            return []
        }

        return [
            Milestone(
                id: "ms1",
                name: "M1: Foundation",
                description: "Platform can accept, orchestrate, and deliver the first autonomous task end-to-end.",
                status: .active,
                tasks: project.tasks,
                creditsSpent: 142,
                humanEquivSaved: 11000,
                roi: 78,
                goals: [
                    Goal(id: "g1", name: "Core Orchestration", status: .active, mviCount: 4, mvisComplete: 2),
                    Goal(id: "g2", name: "Agent Runtime", status: .active, mviCount: 3, mvisComplete: 1),
                    Goal(id: "g3", name: "Git Integration", status: .planned, mviCount: 2, mvisComplete: 0),
                ]
            ),
            Milestone(
                id: "ms2",
                name: "M2: Growth",
                description: "First autonomous task execution completes end-to-end with real user approval.",
                status: .planned,
                tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
                creditsSpent: 0,
                humanEquivSaved: 0,
                roi: 0,
                goals: []
            ),
        ]
    }

    func createMilestone(projectId: String, name: String, description: String) async throws -> Milestone {
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
}
