import Foundation
import SwiftUI

// MARK: - Murder Status

enum MurderStatus: String, Equatable {
    case active = "Active"
    case idle = "Idle"
    case error = "Error"

    var color: Color {
        switch self {
        case .active: CawnexColors.success
        case .idle: CawnexColors.mutedForeground
        case .error: CawnexColors.destructive
        }
    }
}

// MARK: - Crow Summary

struct CrowSummary: Identifiable, Equatable {
    let id: String
    let name: String
    let isActive: Bool
    let activityColor: Color
}

// MARK: - Behavior Line

struct BehaviorLine: Identifiable, Equatable {
    let id: String
    let text: String
    let color: Color
}

// MARK: - Murder

struct Murder: Identifiable, Equatable {
    let id: String
    let name: String
    let type: MurderType
    let description: String
    let status: MurderStatus
    let icon: String
    let behaviorLines: [BehaviorLine]
    let crows: [CrowSummary]
    let tasksDone: Int
    let successRate: Int
    let totalCost: Decimal
}

// MARK: - Marketplace Murder

struct MarketplaceMurder: Identifiable, Equatable {
    let id: String
    let name: String
    let icon: String
    let iconColor: Color
    let description: String
    let rating: Double
    let installs: String
    let author: String
}

// MARK: - Murders Screen Data

struct MurdersData: Equatable {
    let murders: [Murder]
    let marketplace: [MarketplaceMurder]
}
