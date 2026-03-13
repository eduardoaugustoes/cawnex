import Foundation
import SwiftUI

protocol MurdersService {
    func getMurders() async throws -> MurdersData
}

final class InMemoryMurdersService: MurdersService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getMurders() async throws -> MurdersData {
        MurdersData(
            murders: [
                Murder(
                    id: "m1",
                    name: "Dev Murder",
                    type: .dev,
                    description: "Software development orchestration",
                    status: .active,
                    icon: "bird.fill",
                    behaviorLines: [
                        BehaviorLine(id: "b1", text: "2 crows building", color: CawnexColors.success),
                        BehaviorLine(id: "b2", text: "1 crow reviewing", color: CawnexColors.info),
                    ],
                    crows: [
                        CrowSummary(id: "c1", name: "Planner", isActive: true, activityColor: CawnexColors.success),
                        CrowSummary(id: "c2", name: "Implementer", isActive: true, activityColor: CawnexColors.success),
                        CrowSummary(id: "c3", name: "Reviewer", isActive: true, activityColor: CawnexColors.info),
                        CrowSummary(id: "c4", name: "Fixer", isActive: false, activityColor: CawnexColors.mutedForeground),
                        CrowSummary(id: "c5", name: "Documenter", isActive: false, activityColor: CawnexColors.mutedForeground),
                    ],
                    tasksDone: 47,
                    successRate: 92,
                    totalCost: 12.40
                ),
                Murder(
                    id: "m2",
                    name: "Editorial Murder",
                    type: .editorial,
                    description: "Book & long-form content creation",
                    status: .idle,
                    icon: "book.fill",
                    behaviorLines: [],
                    crows: [
                        CrowSummary(id: "c6", name: "Researcher", isActive: false, activityColor: CawnexColors.mutedForeground),
                        CrowSummary(id: "c7", name: "Writer", isActive: false, activityColor: CawnexColors.mutedForeground),
                        CrowSummary(id: "c8", name: "Editor", isActive: false, activityColor: CawnexColors.mutedForeground),
                        CrowSummary(id: "c9", name: "Proofreader", isActive: false, activityColor: CawnexColors.mutedForeground),
                    ],
                    tasksDone: 0,
                    successRate: 0,
                    totalCost: 0
                ),
                Murder(
                    id: "m3",
                    name: "Social Murder",
                    type: .social,
                    description: "Social media content & publishing",
                    status: .idle,
                    icon: "megaphone.fill",
                    behaviorLines: [],
                    crows: [
                        CrowSummary(id: "c10", name: "Creator", isActive: false, activityColor: CawnexColors.mutedForeground),
                        CrowSummary(id: "c11", name: "Designer", isActive: false, activityColor: CawnexColors.mutedForeground),
                        CrowSummary(id: "c12", name: "Scheduler", isActive: false, activityColor: CawnexColors.mutedForeground),
                        CrowSummary(id: "c13", name: "Analyst", isActive: false, activityColor: CawnexColors.mutedForeground),
                    ],
                    tasksDone: 0,
                    successRate: 0,
                    totalCost: 0
                ),
            ],
            marketplace: [
                MarketplaceMurder(
                    id: "mp1",
                    name: "Infra Murder",
                    icon: "server.rack",
                    iconColor: Color(hex: 0x06B6D4),
                    description: "Terraform, Docker, CI/CD pipelines. Crows: Provisioner, Monitor, Deployer, Scaler.",
                    rating: 4.8,
                    installs: "2.4k",
                    author: "@cloudnative"
                ),
                MarketplaceMurder(
                    id: "mp2",
                    name: "Data Murder",
                    icon: "externaldrive.fill",
                    iconColor: Color(hex: 0x10B981),
                    description: "ETL pipelines, data quality checks, schema migrations. Crows: Extractor, Transformer, Validator.",
                    rating: 4.5,
                    installs: "1.1k",
                    author: "@dataops"
                ),
            ]
        )
    }
}
