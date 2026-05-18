import Foundation

/// ProjectService that calls the real Cawnex API.
final class APIProjectService: ProjectService {
    private let client: APIClient
    private let store: AppStore

    init(client: APIClient, store: AppStore) {
        self.client = client
        self.store = store
    }

    func listProjects() async throws -> [Project] {
        let response: [ProjectDTO] = try await client.get("/projects")
        let projects = response.map { $0.toProject() }
        await MainActor.run { store.projects = projects }
        return projects
    }

    func getProject(_ id: String) async throws -> Project? {
        store.projects.first { $0.id == id }
    }

    func createProject(name: String, description: String, murders: Set<MurderType>) async throws -> Project {
        let body = CreateProjectDTO(
            name: name,
            one_liner: description,
            murders: murders.map { $0.rawValue }
        )
        let response: CreateProjectResponseDTO = try await client.post("/projects", body: body)
        let project = Project(
            id: response.project_id,
            name: response.name,
            description: description,
            status: decodeProjectStatus(response.current_state),
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0
        )
        await MainActor.run { store.projects.append(project) }
        return project
    }
}

// MARK: - Helper Functions

/// Decode a current_state string to ProjectStatus enum.
/// Maps lowercase state strings (draft/active/running/idle/completed) to capitalized enum cases.
private func decodeProjectStatus(_ stateString: String) -> ProjectStatus {
    let capitalized = stateString.capitalized
    return ProjectStatus(rawValue: capitalized) ?? .draft
}

// MARK: - DTOs

private struct CreateProjectDTO: Encodable {
    let name: String
    let one_liner: String
    let murders: [String]
}

private struct CreateProjectResponseDTO: Decodable {
    let project_id: String
    let name: String
    let status: String
    let current_state: String
    let murders: [String]
    let created_at: String
}

private struct ProjectDTO: Decodable {
    let project_id: String
    let name: String
    let one_liner: String
    let status: String
    let current_state: String
    let murders: [String]
    let created_at: String

    func toProject() -> Project {
        let status = decodeProjectStatus(current_state)
        return Project(
            id: project_id,
            name: name,
            description: one_liner,
            status: status,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0
        )
    }
}
