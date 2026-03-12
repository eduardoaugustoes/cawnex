import Foundation

protocol ProjectService {
    func listProjects() async -> [Project]
    func getProject(_ id: String) async -> Project?
    func createProject(name: String, description: String) async -> Project
}

struct InMemoryProjectService: ProjectService {
    let store: AppStore

    func listProjects() async -> [Project] {
        store.projects
    }

    func getProject(_ id: String) async -> Project? {
        store.projects.first { $0.id == id }
    }

    func createProject(name: String, description: String) async -> Project {
        let project = Project(
            id: UUID().uuidString,
            name: name,
            description: description,
            isActive: true,
            tasks: TaskCounts(done: 0, active: 0, refined: 0, draft: 0),
            creditsSpent: 0,
            humanEquivSaved: 0
        )
        store.projects.append(project)
        return project
    }
}
