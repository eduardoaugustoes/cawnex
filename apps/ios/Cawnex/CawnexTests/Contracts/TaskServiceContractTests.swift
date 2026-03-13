import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: TaskService

struct TaskServiceContractTests {

    private func makeSUT() -> (any TaskService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryTaskService(store: store)
        return (service, store)
    }

    @Test func getTaskDetail_returnsTaskWithMatchingId() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        #expect(detail.id == "t1")
    }

    @Test func getTaskDetail_hasNameAndDescription() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        #expect(!detail.name.isEmpty)
        #expect(!detail.description.isEmpty)
    }

    @Test func getTaskDetail_hasBreadcrumb() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        #expect(!detail.breadcrumb.isEmpty)
    }

    @Test func getTaskDetail_costsAreNonNegative() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        #expect(detail.aiCost >= 0)
        #expect(detail.roi >= 0)
        #expect(!detail.humanEstimate.isEmpty)
    }

    // MARK: - Assigned Crow

    @Test func getTaskDetail_assignedCrowHasRequiredFields() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        #expect(!detail.assignedCrow.name.isEmpty)
        #expect(!detail.assignedCrow.role.isEmpty)
        #expect(!detail.assignedCrow.model.isEmpty)
        #expect(detail.assignedCrow.executionMinutes >= 0)
        #expect(detail.assignedCrow.filesChanged >= 0)
    }

    // MARK: - Implementation Steps

    @Test func getTaskDetail_stepsHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        let ids = detail.implementationSteps.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!detail.implementationSteps.isEmpty)
    }

    @Test func getTaskDetail_stepsHaveText() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        for step in detail.implementationSteps {
            #expect(!step.text.isEmpty)
        }
    }

    // MARK: - Acceptance Criteria

    @Test func getTaskDetail_criteriaHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        let ids = detail.acceptanceCriteria.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!detail.acceptanceCriteria.isEmpty)
    }

    @Test func getTaskDetail_criteriaHaveText() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        for criterion in detail.acceptanceCriteria {
            #expect(!criterion.text.isEmpty)
        }
    }

    // MARK: - PR

    @Test func getTaskDetail_completedTaskHasPR() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getTaskDetail(projectId: projectId, taskId: "t1")
        if detail.status == .completed {
            let pr = try #require(detail.pr)
            #expect(!pr.number.isEmpty)
            #expect(!pr.title.isEmpty)
            #expect(!pr.branch.isEmpty)
            #expect(pr.linesAdded >= 0)
            #expect(pr.linesRemoved >= 0)
            #expect(pr.filesChanged >= 0)
            #expect(pr.coverage >= 0 && pr.coverage <= 100)
        }
    }
}
