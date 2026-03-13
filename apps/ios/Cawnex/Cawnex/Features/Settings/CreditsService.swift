import Foundation

protocol CreditsService {
    func getCreditsData() async throws -> CreditsData
}

final class InMemoryCreditsService: CreditsService {
    private let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getCreditsData() async throws -> CreditsData {
        CreditsData(
            roi: ROISummary(
                roiMultiplier: 78,
                humanEquivSaved: 14000,
                creditsSpent: 182,
                aiMinutes: 47,
                humanHours: 186
            ),
            balance: CreditBalance(
                remaining: 247.50,
                total: 500.00
            ),
            projectBudgets: [
                ProjectBudget(
                    id: "pb1",
                    projectName: "Cawnex",
                    spent: 142,
                    total: 350
                ),
                ProjectBudget(
                    id: "pb2",
                    projectName: "Calhou",
                    spent: 65,
                    total: 150
                ),
            ],
            costBreakdown: [
                CostBreakdownEntry(
                    id: "cb1",
                    projectName: "Cawnex",
                    amount: 142,
                    taskCount: 24
                ),
                CostBreakdownEntry(
                    id: "cb2",
                    projectName: "Calhou",
                    amount: 65,
                    taskCount: 11
                ),
            ],
            crowCosts: [
                CrowCost(id: "cc1", crowName: "Planner", role: "Planning & Scoping", amount: 23.40),
                CrowCost(id: "cc2", crowName: "Implementer", role: "Code Generation", amount: 98.70),
                CrowCost(id: "cc3", crowName: "Reviewer", role: "Review & QA", amount: 12.30),
            ],
            breakdownPeriod: "This month"
        )
    }
}
