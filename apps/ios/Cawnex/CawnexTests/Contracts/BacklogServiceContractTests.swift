import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: BacklogService

struct BacklogServiceContractTests {

    private func makeSUT() -> (any BacklogService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryBacklogService(store: store)
        return (service, store)
    }

    // MARK: - listMilestones

    @Test func listMilestones_returnsNonEmptyForKnownProject() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let milestones = try await service.listMilestones(projectId: projectId)
        #expect(!milestones.isEmpty)
    }

    @Test func listMilestones_returnsEmptyForUnknownProject() async throws {
        let (service, _) = makeSUT()
        let milestones = try await service.listMilestones(projectId: "nonexistent-999")
        #expect(milestones.isEmpty)
    }

    @Test func listMilestones_allMilestonesHaveIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let milestones = try await service.listMilestones(projectId: projectId)
        for milestone in milestones {
            #expect(!milestone.id.isEmpty)
            #expect(!milestone.name.isEmpty)
        }
    }

    @Test func listMilestones_idsAreUnique() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let milestones = try await service.listMilestones(projectId: projectId)
        let ids = milestones.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func listMilestones_taskCountsAreNonNegative() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let milestones = try await service.listMilestones(projectId: projectId)
        for milestone in milestones {
            #expect(milestone.tasks.done >= 0)
            #expect(milestone.tasks.active >= 0)
            #expect(milestone.tasks.refined >= 0)
            #expect(milestone.tasks.draft >= 0)
        }
    }

    @Test func listMilestones_creditsAreNonNegative() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let milestones = try await service.listMilestones(projectId: projectId)
        for milestone in milestones {
            #expect(milestone.creditsSpent >= 0)
            #expect(milestone.humanEquivSaved >= 0)
            #expect(milestone.roi >= 0)
        }
    }

    @Test func listMilestones_goalsHaveUniqueIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let milestones = try await service.listMilestones(projectId: projectId)
        for milestone in milestones {
            let goalIds = milestone.goals.map(\.id)
            #expect(Set(goalIds).count == goalIds.count)
        }
    }

    @Test func listMilestones_goalMvisCompleteDoesNotExceedCount() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let milestones = try await service.listMilestones(projectId: projectId)
        for milestone in milestones {
            for goal in milestone.goals {
                #expect(goal.mvisComplete <= goal.mviCount)
            }
        }
    }

    // MARK: - createMilestone

    @Test func createMilestone_returnsWithGivenNameAndDescription() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let created = try await service.createMilestone(
            projectId: projectId, name: "Test MS", description: "Test desc"
        )
        #expect(created.name == "Test MS")
        #expect(created.description == "Test desc")
        #expect(!created.id.isEmpty)
    }

    @Test func createMilestone_newMilestoneStartsWithPlannedStatus() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let created = try await service.createMilestone(
            projectId: projectId, name: "New", description: "new"
        )
        #expect(created.status == .planned)
    }

    @Test func createMilestone_newMilestoneHasZeroTasks() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let created = try await service.createMilestone(
            projectId: projectId, name: "New", description: "new"
        )
        #expect(created.tasks.total == 0)
        #expect(created.goals.isEmpty)
    }

    // MARK: - updateMilestone

    @Test func updateMilestone_returnsWithUpdatedFields() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let updated = try await service.updateMilestone(
            projectId: projectId, milestoneId: "ms1",
            name: "Updated Name", description: "Updated desc"
        )
        #expect(updated.id == "ms1")
        #expect(updated.name == "Updated Name")
        #expect(updated.description == "Updated desc")
    }
}
