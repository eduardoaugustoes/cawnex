import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: MVIService

struct MVIServiceContractTests {

    private func makeSUT() -> (any MVIService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryMVIService(store: store)
        return (service, store)
    }

    @Test func getBlackboardDetail_returnsMVIWithMatchingId() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        #expect(detail.mvi.id == "mvi1")
    }

    @Test func getBlackboardDetail_hasBreadcrumb() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        #expect(!detail.breadcrumb.isEmpty)
    }

    // MARK: - Active Crows

    @Test func getBlackboardDetail_crowsHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        let ids = detail.activeCrows.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getBlackboardDetail_crowsHaveNamesAndModels() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        for crow in detail.activeCrows {
            #expect(!crow.name.isEmpty)
            #expect(!crow.model.isEmpty)
        }
    }

    // MARK: - Tasks

    @Test func getBlackboardDetail_tasksHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        let ids = detail.tasks.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!detail.tasks.isEmpty)
    }

    @Test func getBlackboardDetail_tasksHaveNames() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        for task in detail.tasks {
            #expect(!task.name.isEmpty)
        }
    }

    @Test func getBlackboardDetail_completedTasksHavePRNumbers() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        for task in detail.tasks where task.status == .completed {
            #expect(task.prNumber != nil)
        }
    }

    // MARK: - Live Feed

    @Test func getBlackboardDetail_liveFeedHasUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        let ids = detail.liveFeed.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!detail.liveFeed.isEmpty)
    }

    @Test func getBlackboardDetail_liveFeedEventsHaveContent() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        for event in detail.liveFeed {
            #expect(!event.timestamp.isEmpty)
            #expect(!event.message.isEmpty)
        }
    }

    // MARK: - Merge Checklist

    @Test func getBlackboardDetail_mergeChecklistHasItems() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        #expect(!detail.mergeChecklist.isEmpty)
        for item in detail.mergeChecklist {
            #expect(!item.label.isEmpty)
        }
    }

    @Test func getBlackboardDetail_canShipReflectsChecklistAndTasks() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getBlackboardDetail(projectId: projectId, mviId: "mvi1")
        let allTasksComplete = detail.tasks.allSatisfy { $0.status == .completed }
        let allChecksPassed = detail.mergeChecklist.allSatisfy { $0.passed }
        #expect(detail.canShip == (allTasksComplete && allChecksPassed))
    }
}
