import Foundation
import SwiftUI

protocol SkillsService {
    func getSkills() async throws -> SkillsData
}

final class InMemorySkillsService: SkillsService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getSkills() async throws -> SkillsData {
        SkillsData(
            skills: [
                Skill(
                    id: "sk1",
                    name: "TypeScript CRUD",
                    icon: "curlybraces",
                    category: .dev,
                    description: "Generate REST CRUD endpoints with validation, error handling, and OpenAPI docs for any entity.",
                    usedBy: "Dev Murder",
                    useCount: 142
                ),
                Skill(
                    id: "sk2",
                    name: "Jest Unit Tests",
                    icon: "flask.fill",
                    category: .dev,
                    description: "Write comprehensive Jest unit tests following TDD methodology with jest-mock-extended.",
                    usedBy: "Dev Murder",
                    useCount: 98
                ),
                Skill(
                    id: "sk3",
                    name: "Chapter Writer",
                    icon: "pencil.line",
                    category: .editorial,
                    description: "Draft book chapters from outline, maintaining voice consistency and narrative arc across the manuscript.",
                    usedBy: "Editorial Murder",
                    useCount: 56
                ),
                Skill(
                    id: "sk4",
                    name: "Social Post Creator",
                    icon: "square.and.arrow.up",
                    category: .social,
                    description: "Create platform-optimized social media posts with hooks, CTAs, and hashtag strategies for engagement.",
                    usedBy: "Social Murder",
                    useCount: 34
                ),
            ],
            marketplace: [
                MarketplaceSkill(
                    id: "msk1",
                    name: "Security Auditor",
                    icon: "checkmark.shield.fill",
                    iconColor: CawnexColors.destructive,
                    description: "OWASP top 10 scanning, dependency audit, secret detection. For Dev Murder reviewer crows.",
                    rating: 4.9,
                    installs: "3.2k",
                    author: "@secops"
                ),
                MarketplaceSkill(
                    id: "msk2",
                    name: "Image Generator",
                    icon: "photo.fill",
                    iconColor: CawnexColors.pink,
                    description: "AI-powered image creation for social posts, thumbnails, and marketing assets. For Social Murder.",
                    rating: 4.6,
                    installs: "890",
                    author: "@creativelabs"
                ),
            ]
        )
    }
}
