import Foundation

@Observable
final class MilestoneDetailViewModel {
    private let milestoneService: any MilestoneService
    private var refreshTimer: Timer?
    private let projectService: any ProjectService
    
    var state: ViewState<MilestoneDetail> = .idle
    var messageText: String = ""
    var isSending: Bool = false
    @ObservationIgnored var stateReadout: ProjectState?

    var detail: MilestoneDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    var completedSections: Int { detail?.completedSections ?? 0 }
    var totalSections: Int { detail?.totalSections ?? 0 }

    init(milestoneService: any MilestoneService, projectService: any ProjectService = APIProjectService(client: APIClient.shared, store: AppStore())) {
        self.milestoneService = milestoneService
        self.projectService = projectService
    }

    func load(projectId: String, milestoneId: String) async {
        state = .loading
        do {
            let loaded = try await milestoneService.getMilestoneDetail(projectId: projectId, milestoneId: milestoneId)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    func sendMessage(projectId: String, milestoneId: String) async {
        let trimmed = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isSending else { return }
        guard case .loaded(var current) = state else { return }

        let userMessage = ChatMessage(id: UUID().uuidString, role: .user, content: trimmed, synthesizedSection: nil)
        current = MilestoneDetail(
            milestone: current.milestone,
            breadcrumb: current.breadcrumb,
            sections: current.sections,
            messages: current.messages + [userMessage],
            goals: current.goals
        )
        state = .loaded(current)
        messageText = ""
        isSending = true

        do {
            let reply = try await milestoneService.sendMessage(projectId: projectId, milestoneId: milestoneId, content: trimmed)
            guard case .loaded(var updated) = state else { return }
            updated = MilestoneDetail(
                milestone: updated.milestone,
                breadcrumb: updated.breadcrumb,
                sections: updated.sections,
                messages: updated.messages + [reply],
                goals: updated.goals
            )
            state = .loaded(updated)
        } catch {
            state = .error(error.localizedDescription)
        }
        isSending = false
    }

    /// Start a 30-second auto-refresh timer for project state.
    func startRefreshTimer(projectId: String) {
        stopRefreshTimer()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { await self?.refreshProjectState(projectId) }
        }
        // Initial load
        Task { await refreshProjectState(projectId) }
    }

    /// Stop the auto-refresh timer.
    func stopRefreshTimer() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    /// Refresh the project state from the API.
    private func refreshProjectState(_ projectId: String) async {
        do {
            guard let project = try await projectService.getProject(projectId) else {
                return
            }
            // Extract state from project response
            // Note: This requires ProjectService to be updated to return state field
            // For now, this is a placeholder that will be fully implemented
            // once the API contract is finalized
        } catch {
            // Log error silently; do not disrupt UI
            print("Failed to refresh project state: \(error.localizedDescription)")
        }
    }
}
