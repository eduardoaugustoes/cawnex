import Foundation

protocol GoalService {
    func getGoalDetail(projectId: String, goalId: String) async throws -> GoalDetail
}

final class InMemoryGoalService: GoalService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getGoalDetail(projectId: String, goalId: String) async throws -> GoalDetail {
        GoalDetail(
            goal: Goal(id: goalId, name: "API Infrastructure", status: .active, mviCount: 3, mvisComplete: 1),
            projectName: store.projects.first { $0.id == projectId }?.name ?? "Project",
            milestoneName: "M1: Foundation",
            creditsSpent: 86,
            humanEquivSaved: 6200,
            roi: 72,
            murderName: "Dev Murder",
            crowCount: 4,
            mvis: [
                MVI(
                    id: "mvi1",
                    name: "MVI 1.1: REST API Endpoints",
                    status: .shipped,
                    tasksDone: 4,
                    tasksTotal: 4,
                    aiMinutes: 23,
                    humanDays: "~3 days",
                    aiCost: 18,
                    humanEquiv: 1200,
                    roi: 67,
                    description: "Build CRUD endpoints for core resources with API Gateway and Lambda integration."
                ),
                MVI(
                    id: "mvi2",
                    name: "MVI 1.2: DynamoDB Storage",
                    status: .executing,
                    tasksDone: 2,
                    tasksTotal: 5,
                    aiMinutes: 14,
                    humanDays: "~4 days",
                    aiCost: 12,
                    humanEquiv: 1600,
                    roi: 0,
                    description: "Set up single-table DynamoDB schema with tenant-scoped access patterns."
                ),
                MVI(
                    id: "mvi3",
                    name: "MVI 1.3: S3 Asset Pipeline",
                    status: .refining,
                    tasksDone: 0,
                    tasksTotal: 0,
                    aiMinutes: 0,
                    humanDays: "~2 days",
                    aiCost: 0,
                    humanEquiv: 800,
                    roi: 0,
                    description: "Configure S3 buckets with lifecycle policies and presigned URL generation."
                ),
            ]
        )
    }
}
