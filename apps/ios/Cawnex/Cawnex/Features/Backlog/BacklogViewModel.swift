import Foundation

@Observable
class BacklogViewModel {
    private let backlogService: any BacklogService
    var milestones: [Milestone] = []
    var expandedMilestones: Set<String> = []

    init(backlogService: any BacklogService) {
        self.backlogService = backlogService
    }

    func load(projectId: String) async {
        milestones = await backlogService.listMilestones(projectId: projectId)
        // Auto-expand in-progress milestones
        for milestone in milestones where milestone.status == .inProgress {
            expandedMilestones.insert(milestone.id)
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
