import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: PRService

struct PRServiceContractTests {

    private func makeSUT() -> (any PRService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryPRService(store: store)
        return (service, store)
    }

    @Test func getPRReview_hasTitle() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        #expect(!detail.title.isEmpty)
        #expect(!detail.branch.isEmpty)
    }

    @Test func getPRReview_hasBreadcrumbs() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        #expect(!detail.breadcrumbMVI.isEmpty)
        #expect(!detail.breadcrumbTask.isEmpty)
    }

    @Test func getPRReview_metricsAreNonNegative() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        #expect(detail.creditsCost >= 0)
        #expect(detail.aiMinutes >= 0)
        #expect(detail.filesChanged >= 0)
        #expect(detail.linesAdded >= 0)
        #expect(detail.linesRemoved >= 0)
    }

    // MARK: - Verdict

    @Test func getPRReview_verdictHasRequiredFields() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        #expect(!detail.verdict.crowName.isEmpty)
        #expect(!detail.verdict.summary.isEmpty)
        #expect(detail.verdict.filesAnalyzed >= 0)
    }

    @Test func getPRReview_findingsHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        let ids = detail.verdict.findings.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getPRReview_findingsHaveText() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        for finding in detail.verdict.findings {
            #expect(!finding.text.isEmpty)
        }
    }

    // MARK: - Plan Steps

    @Test func getPRReview_planStepsHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        let ids = detail.planSteps.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!detail.planSteps.isEmpty)
    }

    @Test func getPRReview_planStepsHaveContent() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        for step in detail.planSteps {
            #expect(!step.crowName.isEmpty)
            #expect(!step.plan.isEmpty)
            #expect(!step.executed.isEmpty)
        }
    }

    // MARK: - Conversation

    @Test func getPRReview_conversationMessagesHaveContent() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        for message in detail.conversation {
            #expect(!message.id.isEmpty)
            #expect(!message.content.isEmpty)
        }
    }

    @Test func getPRReview_suggestedQuestionsNotEmpty() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getPRReview(projectId: projectId, prId: "pr1")
        #expect(!detail.suggestedQuestions.isEmpty)
        for question in detail.suggestedQuestions {
            #expect(!question.isEmpty)
        }
    }
}
