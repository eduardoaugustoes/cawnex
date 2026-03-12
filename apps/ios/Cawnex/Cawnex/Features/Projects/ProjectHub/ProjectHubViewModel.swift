import Foundation

@Observable
final class ProjectHubViewModel {
    private let projectHubService: any ProjectHubService
    var state: ViewState<ProjectHubDetail> = .idle

    var detail: ProjectHubDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    init(projectHubService: any ProjectHubService) {
        self.projectHubService = projectHubService
    }

    func load(projectId: String) async {
        state = .loading
        do {
            if let detail = try await projectHubService.getProjectHub(projectId) {
                state = .loaded(detail)
            } else {
                state = .error("Project not found")
            }
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
