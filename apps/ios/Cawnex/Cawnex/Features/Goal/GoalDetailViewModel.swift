import Foundation

@Observable
final class GoalDetailViewModel {
    private let goalService: any GoalService
    var state: ViewState<GoalDetail> = .idle

    var detail: GoalDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    init(goalService: any GoalService) {
        self.goalService = goalService
    }

    func load(projectId: String, goalId: String) async {
        state = .loading
        do {
            let loaded = try await goalService.getGoalDetail(projectId: projectId, goalId: goalId)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
