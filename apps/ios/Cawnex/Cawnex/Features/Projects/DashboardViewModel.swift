import Foundation

@Observable
final class DashboardViewModel {
    private let projectService: any ProjectService
    var state: ViewState<[Project]> = .idle

    var projects: [Project] {
        if case .loaded(let p) = state { return p }
        return []
    }

    init(projectService: any ProjectService) {
        self.projectService = projectService
    }

    func load() async {
        state = .loading
        do {
            let loaded = try await projectService.listProjects()
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
