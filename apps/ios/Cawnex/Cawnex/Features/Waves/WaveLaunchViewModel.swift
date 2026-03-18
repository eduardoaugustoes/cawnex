import Foundation

@Observable
final class WaveLaunchViewModel {
    let backlogService: any BacklogService
    let goalService: any GoalService
    let waveService: any WaveService
    let projectId: String

    var directive: String = ""
    var goals: [Goal] = []
    var selectedGoalId: String? = nil
    var mvIs: [MVI] = []
    var selectedMVIIds: Set<String> = []

    var isLoadingGoals: Bool = false
    var isLoadingMVIs: Bool = false
    var isSubmitting: Bool = false
    var error: String? = nil

    var canLaunch: Bool {
        !directive.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && selectedGoalId != nil
            && !selectedMVIIds.isEmpty
            && !isSubmitting
    }

    init(
        backlogService: any BacklogService,
        goalService: any GoalService,
        waveService: any WaveService,
        projectId: String
    ) {
        self.backlogService = backlogService
        self.goalService = goalService
        self.waveService = waveService
        self.projectId = projectId
    }

    func loadGoals() async {
        isLoadingGoals = true
        defer { isLoadingGoals = false }
        do {
            let milestones = try await backlogService.listMilestones(projectId: projectId)
            goals = milestones.flatMap { $0.goals }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func selectGoal(_ goalId: String) async {
        selectedGoalId = goalId
        selectedMVIIds = []
        mvIs = []
        isLoadingMVIs = true
        defer { isLoadingMVIs = false }
        do {
            let detail = try await goalService.getGoalDetail(projectId: projectId, goalId: goalId)
            mvIs = detail.mvis
        } catch {
            self.error = error.localizedDescription
        }
    }

    func toggleMVI(_ mviId: String) {
        if selectedMVIIds.contains(mviId) {
            selectedMVIIds.remove(mviId)
        } else {
            selectedMVIIds.insert(mviId)
        }
    }

    func launch() async -> WaveSummary? {
        guard let goalId = selectedGoalId, canLaunch else { return nil }
        isSubmitting = true
        error = nil
        defer { isSubmitting = false }
        do {
            let response = try await waveService.createWave(
                projectId: projectId,
                directive: directive.trimmingCharacters(in: .whitespacesAndNewlines),
                goalId: goalId,
                mviIds: Array(selectedMVIIds)
            )
            let summary = try await waveService.activateWave(
                projectId: projectId,
                waveId: response.waveId
            )
            return summary
        } catch {
            self.error = error.localizedDescription
            return nil
        }
    }
}
