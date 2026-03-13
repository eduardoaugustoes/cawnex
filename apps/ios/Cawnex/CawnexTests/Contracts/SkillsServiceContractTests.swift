import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: SkillsService

struct SkillsServiceContractTests {

    private func makeSUT() -> any SkillsService {
        let store = AppStore()
        store.seedData()
        return InMemorySkillsService(store: store)
    }

    @Test func getSkills_returnsNonEmptyData() async throws {
        let service = makeSUT()
        let data = try await service.getSkills()
        #expect(!data.skills.isEmpty)
    }

    // MARK: - Skills

    @Test func getSkills_skillsHaveUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getSkills()
        let ids = data.skills.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getSkills_skillsHaveRequiredFields() async throws {
        let service = makeSUT()
        let data = try await service.getSkills()
        for skill in data.skills {
            #expect(!skill.id.isEmpty)
            #expect(!skill.name.isEmpty)
            #expect(!skill.icon.isEmpty)
            #expect(!skill.description.isEmpty)
            #expect(!skill.usedBy.isEmpty)
            #expect(skill.useCount >= 0)
        }
    }

    @Test func getSkills_categoriesAreValid() async throws {
        let service = makeSUT()
        let data = try await service.getSkills()
        let validCategories: Set<SkillCategory> = [.dev, .editorial, .social, .custom]
        for skill in data.skills {
            #expect(validCategories.contains(skill.category))
        }
    }

    // MARK: - Marketplace

    @Test func getSkills_marketplaceHasUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getSkills()
        let ids = data.marketplace.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getSkills_marketplaceItemsHaveRequiredFields() async throws {
        let service = makeSUT()
        let data = try await service.getSkills()
        for item in data.marketplace {
            #expect(!item.name.isEmpty)
            #expect(!item.description.isEmpty)
            #expect(!item.icon.isEmpty)
            #expect(!item.author.isEmpty)
            #expect(!item.installs.isEmpty)
            #expect(item.rating >= 0 && item.rating <= 5)
        }
    }
}
