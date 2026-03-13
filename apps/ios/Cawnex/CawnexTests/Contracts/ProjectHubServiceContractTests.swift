import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: ProjectHubService

struct ProjectHubServiceContractTests {

    private func makeSUT() -> (any ProjectHubService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryProjectHubService(store: store)
        return (service, store)
    }

    // MARK: - getProjectHub

    @Test func getProjectHub_returnsDetailForKnownProject() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try await service.getProjectHub(projectId)
        #expect(detail != nil)
    }

    @Test func getProjectHub_returnsNilForUnknownProject() async throws {
        let (service, _) = makeSUT()
        let detail = try await service.getProjectHub("nonexistent-999")
        #expect(detail == nil)
    }

    @Test func getProjectHub_containsMatchingProject() async throws {
        let (service, store) = makeSUT()
        let project = try #require(store.projects.first)
        let detail = try #require(try await service.getProjectHub(project.id))
        #expect(detail.project.id == project.id)
        #expect(detail.project.name == project.name)
    }

    // MARK: - Stats

    @Test func getProjectHub_statsProgressIsBetween0And100() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        #expect(detail.stats.progress >= 0)
        #expect(detail.stats.progress <= 100)
    }

    @Test func getProjectHub_statsTasksDoneDoesNotExceedTotal() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        #expect(detail.stats.tasksDone <= detail.stats.tasksTotal)
    }

    @Test func getProjectHub_statsRoiIsNonNegative() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        #expect(detail.stats.roi >= 0)
    }

    // MARK: - Documents

    @Test func getProjectHub_containsAllFourDocumentTypes() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        let types = Set(detail.documents.map(\.type))
        #expect(types.contains(.vision))
        #expect(types.contains(.architecture))
        #expect(types.contains(.glossary))
        #expect(types.contains(.design))
    }

    @Test func getProjectHub_documentIdsAreUnique() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        let ids = detail.documents.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    // MARK: - Backlog

    @Test func getProjectHub_backlogPipelineMatchesProjectTasks() async throws {
        let (service, store) = makeSUT()
        let project = try #require(store.projects.first)
        let detail = try #require(try await service.getProjectHub(project.id))
        #expect(detail.backlog.pipeline == project.tasks)
    }

    @Test func getProjectHub_backlogMvisShippedDoesNotExceedTotal() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        #expect(detail.backlog.mvisShipped <= detail.backlog.mvisTotal)
    }

    // MARK: - Murders

    @Test func getProjectHub_murdersHaveIds() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        for murder in detail.murders {
            #expect(!murder.id.isEmpty)
            #expect(!murder.name.isEmpty)
        }
    }

    @Test func getProjectHub_murderIdsAreUnique() async throws {
        let (service, store) = makeSUT()
        let projectId = try #require(store.projects.first?.id)
        let detail = try #require(try await service.getProjectHub(projectId))
        let ids = detail.murders.map(\.id)
        #expect(Set(ids).count == ids.count)
    }
}
