import Foundation

protocol DocumentService {
    func getDocument(projectId: String, type: DocumentType) async throws -> VisionDocumentDetail
    func sendMessage(projectId: String, type: DocumentType, content: String) async throws -> ChatMessage
}

struct InMemoryDocumentService: DocumentService {

    func getDocument(projectId: String, type: DocumentType) async throws -> VisionDocumentDetail {
        let sections: [DocumentSection] = [
            DocumentSection(
                id: "s1",
                title: "Problem Statement",
                content: "Founders waste months building the wrong thing because they lack structured guidance to validate assumptions early.",
                status: .complete
            ),
            DocumentSection(
                id: "s2",
                title: "Target User",
                content: "Technical founders with a validated idea, pre-seed to seed stage, building their first AI-powered product.",
                status: .complete
            ),
            DocumentSection(id: "s3", title: "Core Value Proposition", content: "", status: .pending),
            DocumentSection(id: "s4", title: "Key Features", content: "", status: .pending),
            DocumentSection(id: "s5", title: "Success Metrics", content: "", status: .pending),
            DocumentSection(id: "s6", title: "Non-Goals", content: "", status: .pending),
        ]

        let synthesized = DocumentSection(
            id: "s2",
            title: "Target User",
            content: "Technical founders with a validated idea, pre-seed to seed stage, building their first AI-powered product.",
            status: .complete
        )

        let messages: [ChatMessage] = [
            ChatMessage(
                id: "m1",
                role: .ai,
                content: "Who is the primary user of your product? Describe them in terms of their role, experience level, and the context in which they'll use it.",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "m2",
                role: .user,
                content: "Technical founders at the pre-seed to seed stage who are building AI-powered products and need structured help to avoid building the wrong thing.",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "m3",
                role: .ai,
                content: "Got it. Now let's define your core value proposition — what is the single most important outcome your product delivers for them?",
                synthesizedSection: synthesized
            ),
        ]

        return VisionDocumentDetail(projectId: projectId, sections: sections, messages: messages)
    }

    func sendMessage(projectId: String, type: DocumentType, content: String) async throws -> ChatMessage {
        ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: "Thanks for sharing that. Let me synthesize this into the document.",
            synthesizedSection: nil
        )
    }
}
