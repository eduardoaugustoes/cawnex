import Foundation

/// Real backend implementation of CreditsService, replacing the InMemory mock.
///
/// Endpoint: `GET /billing/usage`
///
/// Some fields in the iOS `CreditsData` model are placeholders per Phase 2
/// spec — notably `balance` (no user-level balance modeled yet). The
/// backend returns nulls there; iOS surfaces "Setup required" rather than
/// fake numbers.
final class APICreditsService: CreditsService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func getCreditsData() async throws -> CreditsData {
        let dto: CreditsDataDTO = try await client.get("/billing/usage")
        return mapToCreditsData(dto)
    }

    // MARK: - Mapping

    private func mapToCreditsData(_ dto: CreditsDataDTO) -> CreditsData {
        CreditsData(
            roi: ROISummary(
                roiMultiplier: dto.roi.roi_multiplier,
                humanEquivSaved: parseDecimal(dto.roi.human_equiv_saved),
                creditsSpent: parseDecimal(dto.roi.credits_spent),
                aiMinutes: dto.roi.ai_minutes,
                humanHours: dto.roi.human_hours
            ),
            balance: CreditBalance(
                remaining: dto.balance.remaining.map(parseDecimal) ?? Decimal(0),
                total: dto.balance.total.map(parseDecimal) ?? Decimal(0)
            ),
            projectBudgets: dto.project_budgets.map {
                ProjectBudget(
                    id: $0.id,
                    projectName: $0.project_name,
                    spent: parseDecimal($0.spent),
                    total: parseDecimal($0.total)
                )
            },
            costBreakdown: dto.cost_breakdown.map {
                CostBreakdownEntry(
                    id: $0.id,
                    projectName: $0.project_name,
                    amount: parseDecimal($0.amount),
                    taskCount: $0.task_count
                )
            },
            crowCosts: dto.crow_costs.map {
                CrowCost(
                    id: $0.id,
                    crowName: $0.crow_name,
                    role: $0.role,
                    amount: parseDecimal($0.amount)
                )
            },
            breakdownPeriod: dto.breakdown_period
        )
    }

    /// Pydantic serializes Decimal as a JSON string ("1.50"); iOS expects
    /// a real Decimal. Round-trip via String to preserve precision.
    private func parseDecimal(_ raw: String) -> Decimal {
        Decimal(string: raw) ?? Decimal(0)
    }
}

// MARK: - DTOs

private struct CreditsDataDTO: Decodable {
    let roi: ROISummaryDTO
    let balance: CreditBalanceDTO
    let project_budgets: [ProjectBudgetDTO]
    let cost_breakdown: [CostBreakdownEntryDTO]
    let crow_costs: [CrowCostDTO]
    let breakdown_period: String
}

private struct ROISummaryDTO: Decodable {
    let roi_multiplier: Int
    let human_equiv_saved: String
    let credits_spent: String
    let ai_minutes: Int
    let human_hours: Int
}

private struct CreditBalanceDTO: Decodable {
    let remaining: String?
    let total: String?
}

private struct ProjectBudgetDTO: Decodable {
    let id: String
    let project_name: String
    let spent: String
    let total: String
}

private struct CostBreakdownEntryDTO: Decodable {
    let id: String
    let project_name: String
    let amount: String
    let task_count: Int
}

private struct CrowCostDTO: Decodable {
    let id: String
    let crow_name: String
    let role: String
    let amount: String
}
