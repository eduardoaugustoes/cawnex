import Foundation

@Observable
final class BacklogViewModel {
    private let backlogService: any BacklogService
    var state: ViewState<[Milestone]> = .idle
    var expandedMilestones: Set<String> = []

    var milestones: [Milestone] {
        if case .loaded(let m) = state { return m }
        return []
    }

    init(backlogService: any BacklogService) {
        self.backlogService = backlogService
    }

    func load(projectId: String) async {
        state = .loading
        do {
            let loaded = try await backlogService.listMilestones(projectId: projectId)
            state = .loaded(loaded)
            for milestone in loaded where milestone.status == .inProgress {
                expandedMilestones.insert(milestone.id)
            }
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    func toggleExpanded(_ milestoneId: String) {
        if expandedMilestones.contains(milestoneId) {
            expandedMilestones.remove(milestoneId)
        } else {
            expandedMilestones.insert(milestoneId)
        }
    }

    func isExpanded(_ milestoneId: String) -> Bool {
        expandedMilestones.contains(milestoneId)
    }
}
