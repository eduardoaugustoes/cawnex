import Foundation

@Observable
final class DocumentViewModel {
    private let documentService: any DocumentService
    private let documentType: DocumentType
    var state: ViewState<DocumentDetail> = .idle
    var messageText: String = ""
    var isSending: Bool = false

    var detail: DocumentDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    var completedSections: Int {
        detail?.sections.filter { $0.status == .complete }.count ?? 0
    }

    var totalSections: Int {
        detail?.sections.count ?? 0
    }

    init(documentService: any DocumentService, documentType: DocumentType) {
        self.documentService = documentService
        self.documentType = documentType
    }

    func load(projectId: String) async {
        state = .loading
        do {
            let loaded = try await documentService.getDocument(projectId: projectId, type: documentType)
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
        current = DocumentDetail(
            projectId: current.projectId,
            sections: current.sections,
            messages: current.messages + [userMessage]
        )
        state = .loaded(current)
        messageText = ""
        isSending = true

        do {
            let response = try await documentService.sendMessage(projectId: projectId, type: documentType, content: trimmed)
            current = DocumentDetail(
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
