import Foundation

protocol ProjectService {
    func listProjects() async throws -> [Project]
    func getProject(_ id: String) async throws -> Project?
    func createProject(name: String, description: String, murders: Set<MurderType>) async throws -> Project
}

final class InMemoryProjectService: ProjectService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func listProjects() async throws -> [Project] {
        store.projects
    }

    func getProject(_ id: String) async throws -> Project? {
        store.projects.first { $0.id == id }
    }

    func createProject(name: String, description: String, murders: Set<MurderType>) async throws -> Project {
        let project = Project(
            id: UUID().uuidString,
            name: name,
            description: description,
            status: .active,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0
        )
        store.projects.append(project)
        return project
    }
}
