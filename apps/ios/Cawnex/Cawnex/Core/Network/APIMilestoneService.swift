import Foundation

/// Real backend implementation of MilestoneService, replacing the InMemory mock.
///
/// Endpoint: `GET /projects/{project_id}/milestones/{milestone_id}`
///
/// `sendMessage` is not yet wired to a real backend endpoint — the milestone
/// chat conversation is a placeholder per Phase 2 spec. Calls still return
/// a stubbed AI response so the UI doesn't crash; a real chat backend is
/// a Phase 3 follow-up.
final class APIMilestoneService: MilestoneService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func getMilestoneDetail(
        projectId: String,
        milestoneId: String
    ) async throws -> MilestoneDetail {
        let dto: MilestoneDetailDTO = try await client.get(
            "/projects/\(projectId)/milestones/\(milestoneId)"
        )
        return mapToMilestoneDetail(dto)
    }

    func sendMessage(
        projectId: String,
        milestoneId: String,
        content: String
    ) async throws -> ChatMessage {
        // Placeholder: milestone chat history isn't backed by any DDB store
        // yet. iOS calls this on send; we return a synthetic ack so the
        // chat composer doesn't hang. Replace with a real /milestones/{id}/chat
        // endpoint when the design lands.
        return ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: "Got it. Chat history isn't persisted yet — this acknowledgment is a placeholder.",
            synthesizedSection: nil
        )
    }

    // MARK: - Mapping

    private func mapToMilestoneDetail(_ dto: MilestoneDetailDTO) -> MilestoneDetail {
        let milestone = Milestone(
            id: dto.id,
            name: dto.name,
            description: dto.description,
            status: mapMilestoneStatus(dto.status),
            // Backend `mvi_counts` buckets MVIs by lifecycle stage. We
            // pack them into the iOS `TaskCounts` struct because the
            // domain model is shared with Backlog/ProjectHub views, but
            // the milestone-detail UI labels them "MVIs" — see
            // MilestoneDetailScreen.
            tasks: TaskCounts(
                done: dto.mvi_counts.done,
                active: dto.mvi_counts.active,
                refined: dto.mvi_counts.refined,
                draft: dto.mvi_counts.draft
            ),
            creditsSpent: Decimal(dto.credits_spent),
            humanEquivSaved: Decimal(dto.human_equiv_saved),
            roi: dto.roi,
            goals: dto.goals.map {
                Goal(
                    id: $0.id,
                    name: $0.name,
                    status: mapGoalStatus($0.status),
                    mviCount: $0.mvi_count,
                    mvisComplete: 0  // detail endpoint doesn't break this out
                )
            }
        )

        return MilestoneDetail(
            milestone: milestone,
            breadcrumb: dto.breadcrumb,
            sections: dto.sections.map {
                MilestoneDefinitionSection(
                    id: $0.id,
                    title: $0.title,
                    status: mapSectionStatus($0.status)
                )
            },
            messages: dto.messages.map(mapMessage),
            goals: dto.goals.map {
                MilestoneGoalSummary(
                    id: $0.id,
                    name: $0.name,
                    status: mapGoalStatus($0.status),
                    description: $0.description,
                    mviCount: $0.mvi_count,
                    taskCount: $0.task_count
                )
            }
        )
    }

    private func mapMilestoneStatus(_ raw: String) -> MilestoneStatus {
        switch raw.lowercased() {
        case "active": return .active
        case "paused": return .paused
        case "completed", "shipped": return .completed
        case "planned", "": return .planned
        default: return .planned
        }
    }

    private func mapGoalStatus(_ raw: String) -> GoalStatus {
        switch raw.lowercased() {
        case "active": return .active
        case "paused": return .paused
        case "completed": return .completed
        case "rejected": return .rejected
        case "planned", "": return .planned
        default: return .planned
        }
    }

    private func mapSectionStatus(_ raw: String) -> MilestoneDefinitionStatus {
        raw.lowercased() == "complete" ? .complete : .pending
    }

    private func mapMessage(_ dto: [String: AnyCodable]) -> ChatMessage {
        // The backend currently returns [] for messages, but the shape we
        // expect when this lands is {id, role, content}.
        let id = dto["id"]?.value as? String ?? UUID().uuidString
        let roleRaw = (dto["role"]?.value as? String ?? "ai").lowercased()
        let content = dto["content"]?.value as? String ?? ""
        return ChatMessage(
            id: id,
            role: roleRaw == "user" ? .user : .ai,
            content: content,
            synthesizedSection: nil
        )
    }
}

// MARK: - DTOs

private struct MilestoneDetailDTO: Decodable {
    let id: String
    let name: String
    let description: String
    let status: String
    let breadcrumb: String
    let mvi_counts: MVICountsDTO
    let credits_spent: Int
    let human_equiv_saved: Int
    let roi: Int
    let goals: [MilestoneGoalSummaryDTO]
    let sections: [MilestoneDefinitionSectionDTO]
    let messages: [[String: AnyCodable]]
}

private struct MVICountsDTO: Decodable {
    let done: Int
    let active: Int
    let refined: Int
    let draft: Int
}

private struct MilestoneGoalSummaryDTO: Decodable {
    let id: String
    let name: String
    let status: String
    let description: String
    let mvi_count: Int
    let task_count: Int
}

private struct MilestoneDefinitionSectionDTO: Decodable {
    let id: String
    let title: String
    let status: String
}

// Type-erased decoder for free-form message dicts.
private struct AnyCodable: Decodable {
    let value: Any

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let s = try? container.decode(String.self) {
            value = s
        } else if let i = try? container.decode(Int.self) {
            value = i
        } else if let b = try? container.decode(Bool.self) {
            value = b
        } else if let d = try? container.decode(Double.self) {
            value = d
        } else {
            value = NSNull()
        }
    }
}
