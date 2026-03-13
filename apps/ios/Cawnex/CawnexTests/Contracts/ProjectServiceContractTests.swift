import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: ProjectService

/// These tests verify the behavioral contract of any ProjectService implementation.
/// They must pass for InMemoryProjectService today AND any future APIProjectService.

struct ProjectServiceContractTests {

    private func makeSUT() -> (any ProjectService, AppStore) {
        let store = AppStore()
        store.seedData()
        let service = InMemoryProjectService(store: store)
        return (service, store)
    }

    // MARK: - listProjects

    @Test func listProjects_returnsNonEmptyList() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        #expect(!projects.isEmpty)
    }

    @Test func listProjects_allProjectsHaveIds() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        for project in projects {
            #expect(!project.id.isEmpty)
        }
    }

    @Test func listProjects_allProjectsHaveNames() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        for project in projects {
            #expect(!project.name.isEmpty)
        }
    }

    @Test func listProjects_idsAreUnique() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        let ids = projects.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func listProjects_allProjectsHaveValidStatus() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        let validStatuses: Set<ProjectStatus> = [.draft, .active, .paused, .completed, .archived]
        for project in projects {
            #expect(validStatuses.contains(project.status))
        }
    }

    @Test func listProjects_taskCountsAreNonNegative() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        for project in projects {
            #expect(project.tasks.done >= 0)
            #expect(project.tasks.active >= 0)
            #expect(project.tasks.refined >= 0)
            #expect(project.tasks.draft >= 0)
        }
    }

    @Test func listProjects_creditsAreNonNegative() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        for project in projects {
            #expect(project.creditsSpent >= 0)
            #expect(project.humanEquivSaved >= 0)
        }
    }

    // MARK: - getProject

    @Test func getProject_returnsProjectForKnownId() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        let first = try #require(projects.first)
        let fetched = try await service.getProject(first.id)
        #expect(fetched != nil)
        #expect(fetched?.id == first.id)
        #expect(fetched?.name == first.name)
    }

    @Test func getProject_returnsNilForUnknownId() async throws {
        let (service, _) = makeSUT()
        let result = try await service.getProject("nonexistent-id-999")
        #expect(result == nil)
    }

    @Test func getProject_returnsConsistentDataWithList() async throws {
        let (service, _) = makeSUT()
        let projects = try await service.listProjects()
        for project in projects {
            let fetched = try await service.getProject(project.id)
            #expect(fetched == project)
        }
    }

    // MARK: - createProject

    @Test func createProject_returnsProjectWithGivenNameAndDescription() async throws {
        let (service, _) = makeSUT()
        let created = try await service.createProject(
            name: "Test Project",
            description: "A test project",
            murders: [.dev]
        )
        #expect(created.name == "Test Project")
        #expect(created.description == "A test project")
    }

    @Test func createProject_returnsProjectWithUniqueId() async throws {
        let (service, _) = makeSUT()
        let first = try await service.createProject(name: "A", description: "a", murders: [.dev])
        let second = try await service.createProject(name: "B", description: "b", murders: [.editorial])
        #expect(first.id != second.id)
        #expect(!first.id.isEmpty)
        #expect(!second.id.isEmpty)
    }

    @Test func createProject_newProjectHasZeroTaskCounts() async throws {
        let (service, _) = makeSUT()
        let created = try await service.createProject(name: "New", description: "new", murders: [.dev])
        #expect(created.tasks.done == 0)
        #expect(created.tasks.active == 0)
        #expect(created.tasks.refined == 0)
        #expect(created.tasks.draft == 0)
    }

    @Test func createProject_newProjectHasZeroCredits() async throws {
        let (service, _) = makeSUT()
        let created = try await service.createProject(name: "New", description: "new", murders: [.dev])
        #expect(created.creditsSpent == 0)
        #expect(created.humanEquivSaved == 0)
    }

    @Test func createProject_projectAppearsInListAfterCreation() async throws {
        let (service, _) = makeSUT()
        let countBefore = try await service.listProjects().count
        let created = try await service.createProject(name: "New", description: "new", murders: [.dev])
        let listAfter = try await service.listProjects()
        #expect(listAfter.count == countBefore + 1)
        #expect(listAfter.contains(where: { $0.id == created.id }))
    }

    @Test func createProject_projectRetrievableByIdAfterCreation() async throws {
        let (service, _) = makeSUT()
        let created = try await service.createProject(name: "New", description: "new", murders: [.dev])
        let fetched = try await service.getProject(created.id)
        #expect(fetched == created)
    }
}
