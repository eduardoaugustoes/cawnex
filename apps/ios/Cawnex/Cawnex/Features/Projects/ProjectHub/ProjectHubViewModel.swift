import Foundation

@Observable
class ProjectHubViewModel {
    private let projectHubService: any ProjectHubService
    var detail: ProjectHubDetail?

    init(projectHubService: any ProjectHubService) {
        self.projectHubService = projectHubService
    }

    func load(projectId: String) async {
        detail = await projectHubService.getProjectHub(projectId)
    }
}
