import Foundation

protocol TaskService {
    func getTaskDetail(projectId: String, taskId: String) async throws -> TaskDetail
}

final class InMemoryTaskService: TaskService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getTaskDetail(projectId: String, taskId: String) async throws -> TaskDetail {
        TaskDetail(
            id: taskId,
            name: "RBAC middleware",
            status: .completed,
            description: "Create NestJS guard with role decorators (@Roles), permission checks, and 403 error handling. Support hierarchical roles with inheritance.",
            breadcrumb: "MVI 1.2 › Auth & JWT › Task 2",
            humanEstimate: "~8 hrs",
            aiCost: 3.80,
            roi: 105,
            assignedCrow: AssignedCrow(
                name: "Implementer",
                role: "sonnet-4-6",
                model: "Sonnet 4",
                behaviorState: .landed,
                executionMinutes: 7,
                filesChanged: 3
            ),
            implementationSteps: [
                ImplementationStep(id: "s1", text: "Create @Roles() decorator with metadata", completed: true),
                ImplementationStep(id: "s2", text: "Implement RolesGuard with canActivate()", completed: true),
                ImplementationStep(id: "s3", text: "Add role hierarchy (admin > editor > viewer)", completed: true),
                ImplementationStep(id: "s4", text: "Return 403 ForbiddenException on access denied", completed: true),
                ImplementationStep(id: "s5", text: "Write unit tests for guard and decorator", completed: true),
            ],
            acceptanceCriteria: [
                AcceptanceCriterion(id: "ac1", text: "Guard blocks unauthenticated requests with 401", passed: true),
                AcceptanceCriterion(id: "ac2", text: "Role hierarchy correctly enforced (admin > editor > viewer)", passed: true),
                AcceptanceCriterion(id: "ac3", text: "403 returned with descriptive error message", passed: true),
                AcceptanceCriterion(id: "ac4", text: "Unit test coverage ≥ 90% for guard logic", passed: true),
            ],
            pr: TaskPR(
                number: "PR #15",
                title: "Add RBAC middleware with role hierarchy",
                branch: "feat/rbac-middleware",
                status: "Merged",
                linesAdded: 342,
                linesRemoved: 18,
                filesChanged: 3,
                coverage: 94
            )
        )
    }
}
