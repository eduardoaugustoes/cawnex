import Foundation
import SwiftUI

// MARK: - Skill Category

enum SkillCategory: String, Equatable, CaseIterable, Hashable {
    case dev = "Dev"
    case editorial = "Editorial"
    case social = "Social"
    case custom = "Custom"

    var color: Color {
        switch self {
        case .dev: CawnexColors.primaryLight
        case .editorial: CawnexColors.warning
        case .social: CawnexColors.pink
        case .custom: CawnexColors.mutedForeground
        }
    }
}

// MARK: - Skill

struct Skill: Identifiable, Equatable {
    let id: String
    let name: String
    let displayName: String
    let icon: String
    let category: SkillCategory
    let description: String
    let usedBy: String
    let useCount: Int

    var effectiveDisplayName: String {
        displayName.isEmpty ? name : displayName
    }
}

// MARK: - Marketplace Skill

struct MarketplaceSkill: Identifiable, Equatable {
    let id: String
    let name: String
    let icon: String
    let iconColor: Color
    let description: String
    let rating: Double
    let installs: String
    let author: String
}

// MARK: - Skills Screen Data

struct SkillsData: Equatable {
    let skills: [Skill]
    let marketplace: [MarketplaceSkill]
}
