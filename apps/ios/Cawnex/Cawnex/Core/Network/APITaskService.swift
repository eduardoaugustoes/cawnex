import Foundation

/// Real backend implementation of TaskService, replacing the InMemory mock.
///
/// Endpoint: `GET /projects/{project_id}/tasks/{task_id}` where task_id is
/// the composite `wave_id:mvi_id:task_index`.
///
/// Response shape mirrors the iOS `TaskDetail` model. Empty arrays for
/// `implementation_steps` and `acceptance_criteria` are expected — iOS
/// renders placeholders rather than dropping the sections.
final class APITaskService: TaskService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func getTaskDetail(projectId: String, taskId: String) async throws -> TaskDetail {
        // Path encode: task IDs contain colons that need to be preserved
        // (the backend treats them as composite separators).
        let encodedTaskId = taskId.addingPercentEncoding(
            withAllowedCharacters: CharacterSet.urlPathAllowed
        ) ?? taskId
        let dto: TaskDetailDTO = try await client.get(
            "/projects/\(projectId)/tasks/\(encodedTaskId)"
        )
        return try mapToTaskDetail(dto)
    }

    // MARK: - Mapping

    private func mapToTaskDetail(_ dto: TaskDetailDTO) throws -> TaskDetail {
        TaskDetail(
            id: dto.id,
            name: dto.name,
            status: mapStatus(dto.status),
            description: dto.description,
            breadcrumb: dto.breadcrumb,
            humanEstimate: dto.human_estimate,
            aiCost: Decimal(string: dto.ai_cost) ?? Decimal(0),
            roi: dto.roi,
            assignedCrow: mapAssignedCrow(dto.assigned_crow),
            implementationSteps: dto.implementation_steps.map {
                ImplementationStep(id: $0.id, text: $0.text, completed: $0.completed)
            },
            acceptanceCriteria: dto.acceptance_criteria.map {
                AcceptanceCriterion(id: $0.id, text: $0.text, passed: $0.passed)
            },
            pr: dto.pr.map(mapPR)
        )
    }

    private func mapStatus(_ raw: String) -> TaskStatus {
        switch raw.lowercased() {
        case "completed": return .completed
        case "building", "in_progress", "running": return .building
        case "failed": return .failed
        case "pending", "queued", "": return .pending
        default: return .pending
        }
    }

    private func mapAssignedCrow(_ dto: AssignedCrowDTO) -> AssignedCrow {
        AssignedCrow(
            name: dto.name,
            role: dto.role,
            model: dto.model,
            behaviorState: mapBehaviorState(dto.behavior_state),
            executionMinutes: dto.execution_minutes,
            filesChanged: dto.files_changed
        )
    }

    private func mapBehaviorState(_ raw: String) -> CrowBehaviorState {
        switch raw.lowercased() {
        case "landed", "completed": return .landed
        case "building", "running": return .building
        case "idle", "pending", "queued", "": return .idle
        case "failed", "error": return .error
        default: return .idle
        }
    }

    private func mapPR(_ dto: TaskPRDTO) -> TaskPR {
        TaskPR(
            number: dto.number,
            title: dto.title,
            branch: dto.branch,
            status: dto.status,
            linesAdded: dto.lines_added,
            linesRemoved: dto.lines_removed,
            filesChanged: dto.files_changed,
            coverage: dto.coverage
        )
    }
}

// MARK: - DTOs (mirror the backend response shape exactly)

private struct TaskDetailDTO: Decodable {
    let id: String
    let name: String
    let status: String
    let description: String
    let breadcrumb: String
    let human_estimate: String
    let ai_cost: String  // Decimal serialized as string
    let roi: Int
    let assigned_crow: AssignedCrowDTO
    let implementation_steps: [ImplementationStepDTO]
    let acceptance_criteria: [AcceptanceCriterionDTO]
    let pr: TaskPRDTO?
}

private struct AssignedCrowDTO: Decodable {
    let name: String
    let role: String
    let model: String
    let behavior_state: String
    let execution_minutes: Int
    let files_changed: Int
}

private struct ImplementationStepDTO: Decodable {
    let id: String
    let text: String
    let completed: Bool
}

private struct AcceptanceCriterionDTO: Decodable {
    let id: String
    let text: String
    let passed: Bool
}

private struct TaskPRDTO: Decodable {
    let number: String
    let title: String
    let branch: String
    let status: String
    let lines_added: Int
    let lines_removed: Int
    let files_changed: Int
    let coverage: Int
}
