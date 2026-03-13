import Foundation

// MARK: - ROI Summary

struct ROISummary: Equatable {
    let roiMultiplier: Int
    let humanEquivSaved: Decimal
    let creditsSpent: Decimal
    let aiMinutes: Int
    let humanHours: Int
}

// MARK: - Credit Balance

struct CreditBalance: Equatable {
    let remaining: Decimal
    let total: Decimal

    var spent: Decimal { total - remaining }

    var spentRatio: Double {
        let totalDouble = NSDecimalNumber(decimal: total).doubleValue
        guard totalDouble > 0 else { return 0 }
        return NSDecimalNumber(decimal: spent).doubleValue / totalDouble
    }
}

// MARK: - Project Budget

struct ProjectBudget: Identifiable, Equatable {
    let id: String
    let projectName: String
    let spent: Decimal
    let total: Decimal

    var spentRatio: Double {
        let totalDouble = NSDecimalNumber(decimal: total).doubleValue
        guard totalDouble > 0 else { return 0 }
        return NSDecimalNumber(decimal: spent).doubleValue / totalDouble
    }
}

// MARK: - Cost Breakdown Entry

struct CostBreakdownEntry: Identifiable, Equatable {
    let id: String
    let projectName: String
    let amount: Decimal
    let taskCount: Int
}

// MARK: - Crow Cost

struct CrowCost: Identifiable, Equatable {
    let id: String
    let crowName: String
    let role: String
    let amount: Decimal
}

// MARK: - Aggregate

struct CreditsData: Equatable {
    let roi: ROISummary
    let balance: CreditBalance
    let projectBudgets: [ProjectBudget]
    let costBreakdown: [CostBreakdownEntry]
    let crowCosts: [CrowCost]
    let breakdownPeriod: String
}
