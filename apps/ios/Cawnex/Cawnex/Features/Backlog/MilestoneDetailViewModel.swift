import Foundation

@Observable
final class MilestoneDetailViewModel {
    private let milestoneService: any MilestoneService
    var state: ViewState<MilestoneDetail> = .idle
    var messageText: String = ""
    var isSending: Bool = false

    var detail: MilestoneDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    var completedSections: Int { detail?.completedSections ?? 0 }
    var totalSections: Int { detail?.totalSections ?? 0 }

    init(milestoneService: any MilestoneService) {
        self.milestoneService = milestoneService
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
}
