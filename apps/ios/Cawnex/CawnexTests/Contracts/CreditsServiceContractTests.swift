import Foundation
import Testing
@testable import Cawnex

// MARK: - Contract: CreditsService

struct CreditsServiceContractTests {

    private func makeSUT() -> any CreditsService {
        let store = AppStore()
        store.seedData()
        return InMemoryCreditsService(store: store)
    }

    // MARK: - ROI

    @Test func getCreditsData_roiMultiplierIsPositive() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        #expect(data.roi.roiMultiplier > 0)
    }

    @Test func getCreditsData_roiMetricsAreNonNegative() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        #expect(data.roi.humanEquivSaved >= 0)
        #expect(data.roi.creditsSpent >= 0)
        #expect(data.roi.aiMinutes >= 0)
        #expect(data.roi.humanHours >= 0)
    }

    @Test func getCreditsData_humanHoursExceedAIMinutes() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        let aiHours = data.roi.aiMinutes / 60
        #expect(data.roi.humanHours > aiHours)
    }

    // MARK: - Balance

    @Test func getCreditsData_balanceRemainingDoesNotExceedTotal() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        #expect(data.balance.remaining <= data.balance.total)
        #expect(data.balance.remaining >= 0)
        #expect(data.balance.total > 0)
    }

    @Test func getCreditsData_balanceSpentPlusRemainingEqualsTotal() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        #expect(data.balance.spent + data.balance.remaining == data.balance.total)
    }

    @Test func getCreditsData_spentRatioIsBetween0And1() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        #expect(data.balance.spentRatio >= 0)
        #expect(data.balance.spentRatio <= 1)
    }

    // MARK: - Project Budgets

    @Test func getCreditsData_projectBudgetsHaveUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        let ids = data.projectBudgets.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!data.projectBudgets.isEmpty)
    }

    @Test func getCreditsData_budgetSpentDoesNotExceedTotal() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        for budget in data.projectBudgets {
            #expect(budget.spent <= budget.total)
            #expect(budget.spent >= 0)
            #expect(!budget.projectName.isEmpty)
        }
    }

    @Test func getCreditsData_budgetSpentRatioIsBetween0And1() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        for budget in data.projectBudgets {
            #expect(budget.spentRatio >= 0)
            #expect(budget.spentRatio <= 1)
        }
    }

    // MARK: - Cost Breakdown

    @Test func getCreditsData_costBreakdownHasUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        let ids = data.costBreakdown.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    @Test func getCreditsData_costBreakdownEntriesHaveRequiredFields() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        for entry in data.costBreakdown {
            #expect(!entry.projectName.isEmpty)
            #expect(entry.amount >= 0)
            #expect(entry.taskCount >= 0)
        }
    }

    @Test func getCreditsData_hasBreakdownPeriod() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        #expect(!data.breakdownPeriod.isEmpty)
    }

    // MARK: - Crow Costs

    @Test func getCreditsData_crowCostsHaveUniqueIds() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        let ids = data.crowCosts.map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(!data.crowCosts.isEmpty)
    }

    @Test func getCreditsData_crowCostsHaveRequiredFields() async throws {
        let service = makeSUT()
        let data = try await service.getCreditsData()
        for crow in data.crowCosts {
            #expect(!crow.crowName.isEmpty)
            #expect(!crow.role.isEmpty)
            #expect(crow.amount >= 0)
        }
    }
}
