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
            for milestone in loaded where milestone.status == .active {
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

    func milestoneCreated(_ milestone: Milestone) {
        guard case .loaded(var list) = state else { return }
        list.append(milestone)
        state = .loaded(list)
    }

    func milestoneUpdated(_ milestone: Milestone) {
        guard case .loaded(var list) = state else { return }
        if let index = list.firstIndex(where: { $0.id == milestone.id }) {
            list[index] = milestone
        }
        state = .loaded(list)
    }

    func milestoneStatusChanged(_ milestoneId: String, to newStatus: MilestoneStatus) {
        guard case .loaded(var list) = state else { return }
        if let index = list.firstIndex(where: { $0.id == milestoneId }) {
            var milestone = list[index]
            milestone.status = newStatus
            list[index] = milestone
        }
        state = .loaded(list)
    }
}
