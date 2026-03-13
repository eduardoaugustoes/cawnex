import Foundation

protocol MVIService {
    func getBlackboardDetail(projectId: String, mviId: String) async throws -> MVIBlackboardDetail
}

final class InMemoryMVIService: MVIService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getBlackboardDetail(projectId: String, mviId: String) async throws -> MVIBlackboardDetail {
        MVIBlackboardDetail(
            mvi: MVI(
                id: mviId,
                name: "MVI 1.2: DynamoDB Storage",
                status: .executing,
                tasksDone: 2,
                tasksTotal: 3,
                aiMinutes: 14,
                humanDays: "~4 days",
                aiCost: 4.20,
                humanEquiv: 1200,
                roi: 286,
                description: "Set up single-table DynamoDB schema with tenant-scoped access patterns."
            ),
            breadcrumb: "M1: Foundation › API Infrastructure › MVI 1.2",
            activeCrows: [
                ActiveCrow(id: "c1", name: "Implementer", behaviorState: .building, model: "Opus 4"),
                ActiveCrow(id: "c2", name: "Reviewer", behaviorState: .reviewing, model: "Sonnet 4"),
                ActiveCrow(id: "c3", name: "Fixer", behaviorState: .landed, model: "Sonnet 4"),
            ],
            tasks: [
                MVITask(id: "t1", name: "Create DynamoDB table schema", status: .completed, prNumber: "PR #14", crowName: "Implementer"),
                MVITask(id: "t2", name: "Implement tenant-scoped access", status: .completed, prNumber: "PR #15", crowName: "Implementer"),
                MVITask(id: "t3", name: "Add session management", status: .building, prNumber: nil, crowName: "Implementer"),
            ],
            liveFeed: [
                LiveFeedEvent(id: "f1", timestamp: "14:32", message: "Implementer started building Session management", type: .standard),
                LiveFeedEvent(id: "f2", timestamp: "14:28", message: "Murder approved PR #15 → merge queue", type: .success),
                LiveFeedEvent(id: "f3", timestamp: "14:14", message: "Reviewer completed review on PR #15", type: .standard),
                LiveFeedEvent(id: "f4", timestamp: "13:50", message: "Murder sent PR #14 back → Fixer crow", type: .warning),
                LiveFeedEvent(id: "f5", timestamp: "13:32", message: "Kickoff: spawned 3 crows for MVI 1.2", type: .muted),
            ],
            mergeChecklist: [
                MergeChecklistItem(id: "mc1", label: "2/2 PRs reviewed and approved", passed: true),
                MergeChecklistItem(id: "mc2", label: "All CI checks passing", passed: true),
                MergeChecklistItem(id: "mc3", label: "1 task still building", passed: false),
            ]
        )
    }
}
