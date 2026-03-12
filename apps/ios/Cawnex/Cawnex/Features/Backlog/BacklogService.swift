import Foundation

protocol BacklogService {
    func listMilestones(projectId: String) async -> [Milestone]
}

struct InMemoryBacklogService: BacklogService {
    let store: AppStore

    func listMilestones(projectId: String) async -> [Milestone] {
        guard let project = store.projects.first(where: { $0.id == projectId }) else {
            return []
        }

        return [
            Milestone(
                id: "ms1",
                name: "M1: Foundation",
                description: "Platform can accept, orchestrate, and deliver the first autonomous task end-to-end.",
                status: .inProgress,
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
                status: .notStarted,
                tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
                creditsSpent: 0,
                humanEquivSaved: 0,
                roi: 0,
                goals: []
            ),
        ]
    }
}
