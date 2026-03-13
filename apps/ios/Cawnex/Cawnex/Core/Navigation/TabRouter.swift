import SwiftUI

@Observable
final class TabRouter {
    var projectPath = NavigationPath()
    var murderPath = NavigationPath()
    var skillPath = NavigationPath()
    var settingsPath = NavigationPath()

    // MARK: - Projects Tab

    func pushProject(_ projectId: String) {
        projectPath.append(ProjectRoute.projectHub(projectId: projectId))
    }

    func pushDocument(_ projectId: String, type: DocumentType) {
        projectPath.append(ProjectRoute.document(projectId: projectId, type: type))
    }

    func pushBacklog(_ projectId: String) {
        projectPath.append(ProjectRoute.backlog(projectId: projectId))
    }

    func pushMilestone(_ projectId: String, milestoneId: String) {
        projectPath.append(ProjectRoute.milestone(projectId: projectId, milestoneId: milestoneId))
    }

    func pushGoal(_ projectId: String, goalId: String) {
        projectPath.append(ProjectRoute.goal(projectId: projectId, goalId: goalId))
    }

    func pushMVI(_ projectId: String, mviId: String) {
        projectPath.append(ProjectRoute.mvi(projectId: projectId, mviId: mviId))
    }

    func pushTask(_ projectId: String, taskId: String) {
        projectPath.append(ProjectRoute.task(projectId: projectId, taskId: taskId))
    }

    func pushPR(_ projectId: String, prId: String) {
        projectPath.append(ProjectRoute.pr(projectId: projectId, prId: prId))
    }

    func isNavigatedDeep(tab: CawnexTab) -> Bool {
        switch tab {
        case .projects: !projectPath.isEmpty
        case .murders: !murderPath.isEmpty
        case .skills: !skillPath.isEmpty
        case .settings: !settingsPath.isEmpty
        }
    }

    func popToRoot(tab: CawnexTab) {
        switch tab {
        case .projects: projectPath = NavigationPath()
        case .murders: murderPath = NavigationPath()
        case .skills: skillPath = NavigationPath()
        case .settings: settingsPath = NavigationPath()
        }
    }
}
