import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: GoalService

struct GoalServiceContractTests {

    private func makeSUT() -> (any GoalService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryGoalService(store: store)
        return (service, store)
    }

    @Test func getGoalDetail_returnsGoalWithMatchingId() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        #expect(detail.goal.id == "g1")
    }

    @Test func getGoalDetail_projectNameMatchesStore() async throws {
        let (service, store) = makeSUT()
        let project = try #require(store.projects.first)
        let detail = try await service.getGoalDetail(projectId: project.id, goalId: "g1")
        #expect(detail.projectName == project.name)
    }

    @Test func getGoalDetail_hasNonEmptyMilestoneName() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        #expect(!detail.milestoneName.isEmpty)
    }

    @Test func getGoalDetail_creditsAreNonNegative() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        #expect(detail.creditsSpent >= 0)
        #expect(detail.humanEquivSaved >= 0)
        #expect(detail.roi >= 0)
    }

    @Test func getGoalDetail_mvisHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        let ids = detail.mvis.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getGoalDetail_mvisHaveNamesAndDescriptions() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        for mvi in detail.mvis {
            #expect(!mvi.name.isEmpty)
            #expect(!mvi.description.isEmpty)
        }
    }

    @Test func getGoalDetail_mviTasksDoneDoNotExceedTotal() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        for mvi in detail.mvis {
            #expect(mvi.tasksDone <= mvi.tasksTotal)
        }
    }

    @Test func getGoalDetail_mviCostsAreNonNegative() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        for mvi in detail.mvis {
            #expect(mvi.aiMinutes >= 0)
            #expect(mvi.aiCost >= 0)
            #expect(mvi.humanEquiv >= 0)
            #expect(mvi.roi >= 0)
        }
    }

    @Test func getGoalDetail_murderInfoPresent() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getGoalDetail(projectId: projectId, goalId: "g1")
        #expect(!detail.murderName.isEmpty)
        #expect(detail.crowCount > 0)
    }
}
