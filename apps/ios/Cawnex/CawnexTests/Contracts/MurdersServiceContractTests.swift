import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: MurdersService

struct MurdersServiceContractTests {

    private func makeSUT() -> any MurdersService {
        let store = AppStore()
        store.seedData()
        return InMemoryMurdersService(store: store)
    }

    @Test func getMurders_returnsNonEmptyData() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        #expect(!data.murders.isEmpty)
    }

    // MARK: - Murders

    @Test func getMurders_murdersHaveUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        let ids = data.murders.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getMurders_murdersHaveRequiredFields() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        for murder in data.murders {
            #expect(!murder.id.isEmpty)
            #expect(!murder.name.isEmpty)
            #expect(!murder.description.isEmpty)
            #expect(!murder.icon.isEmpty)
        }
    }

    @Test func getMurders_activeMurdersHaveBehaviorLines() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        for murder in data.murders where murder.status == .active {
            #expect(!murder.behaviorLines.isEmpty)
        }
    }

    @Test func getMurders_idleMurdersHaveNoBehaviorLines() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        for murder in data.murders where murder.status == .idle {
            #expect(murder.behaviorLines.isEmpty)
        }
    }

    @Test func getMurders_crowsHaveUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        for murder in data.murders {
            let crowIds = murder.crows.map(\.id)
            #expect(Set(crowIds).count == crowIds.count)
        }
    }

    @Test func getMurders_crowsHaveNames() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        for murder in data.murders {
            for crow in murder.crows {
                #expect(!crow.name.isEmpty)
            }
        }
    }

    @Test func getMurders_metricsAreNonNegative() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        for murder in data.murders {
            #expect(murder.tasksDone >= 0)
            #expect(murder.successRate >= 0 && murder.successRate <= 100)
            #expect(murder.totalCost >= 0)
        }
    }

    // MARK: - Marketplace

    @Test func getMurders_marketplaceHasUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
        let ids = data.marketplace.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getMurders_marketplaceItemsHaveRequiredFields() async throws {
        let service = makeSUT()
        let data = try await service.getMurders()
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
