import Foundation

@Observable
final class ProjectHubViewModel {
    private let projectHubService: any ProjectHubService
    var state: ViewState<ProjectHubDetail> = .idle
    @ObservationIgnored private var _projectState: ProjectStatus = .draft

    var detail: ProjectHubDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    var projectState: ProjectStatus {
        get { _projectState }
        set { _projectState = newValue }
    }

    init(projectHubService: any ProjectHubService) {
        self.projectHubService = projectHubService
    }

    func load(projectId: String) async {
        state = .loading
        do {
            if let detail = try await projectHubService.getProjectHub(projectId) {
                await MainActor.run {
                    self.projectState = detail.project.status
                }
                state = .loaded(detail)
            } else {
                state = .error("Project not found")
            }
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
