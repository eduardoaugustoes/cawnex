import Foundation
import SwiftUI

/// ProjectViewModel manages the project detail state and decodes the current_state field.
@Observable
final class ProjectViewModel {
    private let projectService: any ProjectService
    
    var projectId: String
    var project: Project?
    var projectState: ProjectStatus = .draft
    var state: ViewState<Project> = .idle
    
    init(projectId: String, projectService: any ProjectService) {
        self.projectId = projectId
        self.projectService = projectService
    }
    
    @MainActor
    func load() async {
        state = .loading
        do {
            guard let loaded = try await projectService.getProject(projectId) else {
                state = .error("Project not found")
                return
            }
            self.project = loaded
            self.projectState = loaded.status
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
