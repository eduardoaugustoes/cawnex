import Foundation

@Observable
class DashboardViewModel {
    private let projectService: any ProjectService
    var projects: [Project] = []

    init(projectService: any ProjectService) {
        self.projectService = projectService
    }

    func load() async {
        projects = await projectService.listProjects()
    }
}
