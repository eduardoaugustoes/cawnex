import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: MilestoneService

struct MilestoneServiceContractTests {

    private func makeSUT() -> (any MilestoneService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryMilestoneService(store: store)
        return (service, store)
    }

    // MARK: - getMilestoneDetail

    @Test func getMilestoneDetail_returnsMilestoneWithMatchingId() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        #expect(detail.milestone.id == "ms1")
    }

    @Test func getMilestoneDetail_hasBreadcrumb() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        #expect(!detail.breadcrumb.isEmpty)
    }

    @Test func getMilestoneDetail_sectionsHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        let ids = detail.sections.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!detail.sections.isEmpty)
    }

    @Test func getMilestoneDetail_completedSectionsDoNotExceedTotal() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        #expect(detail.completedSections <= detail.totalSections)
        #expect(detail.totalSections == detail.sections.count)
    }

    @Test func getMilestoneDetail_sectionsHaveTitles() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        for section in detail.sections {
            #expect(!section.title.isEmpty)
        }
    }

    @Test func getMilestoneDetail_messagesHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        let ids = detail.messages.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getMilestoneDetail_messagesHaveContent() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        for message in detail.messages {
            #expect(!message.content.isEmpty)
        }
    }

    @Test func getMilestoneDetail_goalsHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        let ids = detail.goals.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getMilestoneDetail_goalsHaveNamesAndDescriptions() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getMilestoneDetail(projectId: projectId, milestoneId: "ms1")
        for goal in detail.goals {
            #expect(!goal.name.isEmpty)
            #expect(!goal.description.isEmpty)
        }
    }

    // MARK: - sendMessage

    @Test func sendMessage_returnsAIMessage() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let reply = try await service.sendMessage(
            projectId: projectId, milestoneId: "ms1", content: "Test message"
        )
        #expect(reply.role == .ai)
        #expect(!reply.content.isEmpty)
        #expect(!reply.id.isEmpty)
    }

    @Test func sendMessage_returnsUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let first = try await service.sendMessage(projectId: projectId, milestoneId: "ms1", content: "A")
        let second = try await service.sendMessage(projectId: projectId, milestoneId: "ms1", content: "B")
        #expect(first.id != second.id)
    }
}
