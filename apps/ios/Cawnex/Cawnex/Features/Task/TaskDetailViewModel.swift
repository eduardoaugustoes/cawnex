import Foundation

@Observable
final class TaskDetailViewModel {
    private let taskService: any TaskService
    var state: ViewState<TaskDetail> = .idle

    var detail: TaskDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    init(taskService: any TaskService) {
        self.taskService = taskService
    }

    func load(projectId: String, taskId: String) async {
        state = .loading
        do {
            let loaded = try await taskService.getTaskDetail(projectId: projectId, taskId: taskId)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
