import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: DocumentService

struct DocumentServiceContractTests {

    private func makeSUT() -> any DocumentService {
        InMemoryDocumentService()
    }

    // MARK: - getDocument (all types)

    @Test(arguments: DocumentType.allCases)
    func getDocument_returnsDocumentForEachType(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        #expect(detail.projectId == "1")
        #expect(!detail.sections.isEmpty)
        #expect(!detail.messages.isEmpty)
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_sectionsHaveUniqueIds(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        let ids = detail.sections.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_sectionsHaveTitles(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        for section in detail.sections {
            #expect(!section.title.isEmpty)
        }
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_completeSectionsHaveContent(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        for section in detail.sections where section.status == .complete {
            #expect(!section.content.isEmpty)
        }
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_pendingSectionsHaveEmptyContent(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        for section in detail.sections where section.status == .pending {
            #expect(section.content.isEmpty)
        }
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_messagesHaveUniqueIds(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        let ids = detail.messages.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_messagesHaveContent(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        for message in detail.messages {
            #expect(!message.content.isEmpty)
        }
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_firstMessageIsFromAI(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        let firstMessage = try #require(detail.messages.first)
        #expect(firstMessage.role == .ai)
    }

    @Test(arguments: DocumentType.allCases)
    func getDocument_hasAtLeastOneSynthesizedSection(type: DocumentType) async throws {
        let service = makeSUT()
        let detail = try await service.getDocument(projectId: "1", type: type)
        let hasSynthesized = detail.messages.contains { $0.synthesizedSection != nil }
        #expect(hasSynthesized)
    }

    // MARK: - sendMessage

    @Test func sendMessage_returnsAIReply() async throws {
        let service = makeSUT()
        let reply = try await service.sendMessage(
            projectId: "1", type: .vision, content: "Some input"
        )
        #expect(reply.role == .ai)
        #expect(!reply.content.isEmpty)
        #expect(!reply.id.isEmpty)
    }

    @Test func sendMessage_returnsUniqueIds() async throws {
        let service = makeSUT()
        let first = try await service.sendMessage(projectId: "1", type: .vision, content: "A")
        let second = try await service.sendMessage(projectId: "1", type: .vision, content: "B")
        #expect(first.id != second.id)
    }
}
