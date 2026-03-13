import Foundation

@Observable
final class VisionDocumentViewModel {
    private let documentService: any DocumentService
    var state: ViewState<VisionDocumentDetail> = .idle
    var messageText: String = ""
    var isSending: Bool = false

    var detail: VisionDocumentDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    var completedSections: Int {
        detail?.sections.filter { $0.status == .complete }.count ?? 0
    }

    var totalSections: Int {
        detail?.sections.count ?? 0
    }

    init(documentService: any DocumentService) {
        self.documentService = documentService
    }

    func load(projectId: String) async {
        state = .loading
        do {
            let loaded = try await documentService.getDocument(projectId: projectId, type: .vision)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    func sendMessage(projectId: String) async {
        let trimmed = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isSending else { return }

        guard case .loaded(var current) = state else { return }

        let userMessage = ChatMessage(id: UUID().uuidString, role: .user, content: trimmed)
        current = VisionDocumentDetail(
            projectId: current.projectId,
            sections: current.sections,
            messages: current.messages + [userMessage]
        )
        state = .loaded(current)
        messageText = ""
        isSending = true

        do {
            let response = try await documentService.sendMessage(projectId: projectId, type: .vision, content: trimmed)
            current = VisionDocumentDetail(
                projectId: current.projectId,
                sections: current.sections,
                messages: current.messages + [response]
            )
            state = .loaded(current)
        } catch {
            state = .error(error.localizedDescription)
        }

        isSending = false
    }
}
