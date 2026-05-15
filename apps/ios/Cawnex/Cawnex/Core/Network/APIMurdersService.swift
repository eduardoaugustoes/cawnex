import Foundation
import SwiftUI

/// Real backend implementation of MurdersService, replacing the InMemory mock.
///
/// Endpoint: `GET /murders`
///
/// v1 returns a static catalog from the backend. Live state (which crows
/// are currently active, behavior lines like "2 crows building", per-murder
/// stats) is placeholder data until a real telemetry rollup is built.
/// iOS renders "idle" for every murder and an empty behaviorLines list —
/// which is the honest representation, not fabricated activity.
final class APIMurdersService: MurdersService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func getMurders() async throws -> MurdersData {
        let dto: MurdersDataDTO = try await client.get("/murders")
        return mapToMurdersData(dto)
    }

    // MARK: - Mapping

    private func mapToMurdersData(_ dto: MurdersDataDTO) -> MurdersData {
        MurdersData(
            murders: dto.murders.map(mapMurder),
            marketplace: dto.marketplace.map(mapMarketplace)
        )
    }

    private func mapMurder(_ dto: MurderDTO) -> Murder {
        Murder(
            id: dto.id,
            name: dto.name,
            type: mapMurderType(dto.type),
            description: dto.description,
            status: mapMurderStatus(dto.status),
            icon: dto.icon,
            behaviorLines: dto.behavior_lines.map {
                BehaviorLine(id: $0.id, text: $0.text, color: colorForTone($0.tone))
            },
            crows: dto.crows.map {
                CrowSummary(
                    id: $0.id,
                    name: $0.name,
                    isActive: $0.is_active,
                    activityColor: $0.is_active
                        ? CawnexColors.success : CawnexColors.mutedForeground
                )
            },
            tasksDone: dto.tasks_done,
            successRate: dto.success_rate,
            totalCost: Decimal(string: dto.total_cost) ?? Decimal(0)
        )
    }

    private func mapMarketplace(_ dto: MarketplaceMurderDTO) -> MarketplaceMurder {
        MarketplaceMurder(
            id: dto.id,
            name: dto.name,
            icon: dto.icon,
            iconColor: colorForTone(dto.icon_color),
            description: dto.description,
            rating: dto.rating,
            installs: dto.installs,
            author: dto.author
        )
    }

    private func mapMurderType(_ raw: String) -> MurderType {
        MurderType(rawValue: raw.lowercased()) ?? .dev
    }

    private func mapMurderStatus(_ raw: String) -> MurderStatus {
        switch raw.lowercased() {
        case "active": return .active
        case "error": return .error
        case "idle", "": return .idle
        default: return .idle
        }
    }

    private func colorForTone(_ tone: String) -> Color {
        switch tone.lowercased() {
        case "success": return CawnexColors.success
        case "info": return CawnexColors.info
        case "warning": return CawnexColors.warning
        case "primary": return CawnexColors.primary
        case "muted", "": return CawnexColors.mutedForeground
        default: return CawnexColors.mutedForeground
        }
    }
}

// MARK: - DTOs

private struct MurdersDataDTO: Decodable {
    let murders: [MurderDTO]
    let marketplace: [MarketplaceMurderDTO]
}

private struct MurderDTO: Decodable {
    let id: String
    let name: String
    let type: String
    let description: String
    let status: String
    let icon: String
    let behavior_lines: [BehaviorLineDTO]
    let crows: [CrowSummaryDTO]
    let tasks_done: Int
    let success_rate: Int
    let total_cost: String  // Pydantic Decimal -> string
}

private struct BehaviorLineDTO: Decodable {
    let id: String
    let text: String
    let tone: String
}

private struct CrowSummaryDTO: Decodable {
    let id: String
    let name: String
    let is_active: Bool
}

private struct MarketplaceMurderDTO: Decodable {
    let id: String
    let name: String
    let icon: String
    let icon_color: String
    let description: String
    let rating: Double
    let installs: String
    let author: String
}
