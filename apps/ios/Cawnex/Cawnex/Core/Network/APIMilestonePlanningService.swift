import Foundation

/// AI-driven milestone planning service — plans ONE milestone at a time.
/// Loads existing milestones as context so the AI builds on what's already planned.
final class APIMilestonePlanningService {
    private let client: APIClient
    private let projectId: String

    private var context: PlanningContext?
    private var existingMilestones: [PlannedMilestone] = []
    private var proposedMilestone: PlannedMilestone?
    private var messages: [ChatMessage] = []

    init(client: APIClient, projectId: String) {
        self.client = client
        self.projectId = projectId
    }

    // MARK: - Load Context

    func loadContext() async throws -> ChatMessage {
        let response: PlanningContextDTO = try await client.get("/projects/\(projectId)/milestones/context")
        var docs: [String: DocContext] = [:]
        for (key, dto) in response.documents {
            docs[key] = DocContext(content: dto.content)
        }
        context = PlanningContext(documents: docs)

        // Load existing milestones as context
        if let existing: ExistingMilestonesDTO = try? await client.get("/projects/\(projectId)/milestones") {
            existingMilestones = existing.milestones.map { m in
                PlannedMilestone(
                    id: m.id, name: m.name, description: m.description,
                    goals: m.goals.map { g in PlannedGoal(id: g.id, name: g.name, description: g.description) }
                )
            }
        }

        let firstMessage = ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: buildOpeningMessage(),
            synthesizedSection: nil
        )
        messages.append(firstMessage)
        return firstMessage
    }

    // MARK: - Send Message

    func sendMessage(_ content: String) async throws -> ChatMessage {
        let userMsg = ChatMessage(id: UUID().uuidString, role: .user, content: content, synthesizedSection: nil)
        messages.append(userMsg)

        var claudeMessages: [AIChatMsg] = []
        for msg in messages {
            claudeMessages.append(AIChatMsg(
                role: msg.role == .ai ? "assistant" : "user",
                content: msg.content
            ))
        }

        let request = AIChatReq(system: buildSystemPrompt(), messages: claudeMessages, project_id: projectId)
        let response: AIChatResp = try await client.post("/ai/chat", body: request)
        let parsed = parseResponse(response.content)

        var synthesized: DocumentSection? = nil
        if let proposed = parsed.milestone {
            proposedMilestone = proposed
            var summary = "\(proposed.name)\n\(proposed.description)"
            if !proposed.goals.isEmpty {
                summary += "\n\n" + proposed.goals.map { "• \($0.name): \($0.description)" }.joined(separator: "\n")
            }
            synthesized = DocumentSection(
                id: "milestone",
                title: "M\(existingMilestones.count + 1): \(proposed.name)",
                content: summary,
                status: .complete
            )
        }

        let aiMsg = ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: parsed.message,
            synthesizedSection: synthesized
        )
        messages.append(aiMsg)
        return aiMsg
    }

    // MARK: - Save (append ONE milestone)

    func saveMilestone() async throws {
        guard let milestone = proposedMilestone else { return }
        let body = MilestoneDTO(
            id: milestone.id,
            name: milestone.name,
            description: milestone.description,
            status: "planned",
            goals: milestone.goals.map { g in
                GoalDTO(id: g.id, name: g.name, description: g.description, status: "planned")
            }
        )
        let _: SaveMilestonesRespDTO = try await client.post("/projects/\(projectId)/milestones", body: body)
    }

    var hasMilestone: Bool { proposedMilestone != nil }
    var allMessages: [ChatMessage] { messages }
    var existingCount: Int { existingMilestones.count }

    // MARK: - System Prompt

    private func buildSystemPrompt() -> String {
        var prompt = """
        You are Cawnex Milestone Planner — a product strategist who helps founders \
        define their next milestone.

        You have access to the founder's project documents and existing milestones. \
        Your job is to propose ONE milestone — the next major deliverable that \
        unlocks real value.

        ## Principles
        - Propose exactly ONE milestone, not a full roadmap.
        - Each milestone has 2-5 goals. Each goal becomes work the AI agents execute.
        - The milestone should build on what's already been delivered.
        - M1 should be the minimum viable loop — the smallest thing that proves the product works.
        - Be specific. "Build MVP" is not a milestone. "First user completes X via Y" is.
        - Respect the founder's priorities — if they want to adjust, do it.

        ## Output Format
        When proposing or updating a milestone, respond with JSON:
        {
          "ai_message": "Your conversational response",
          "milestone": {
            "id": "m1",
            "name": "Milestone Name",
            "description": "What this milestone delivers",
            "goals": [
              {"id": "g1", "name": "Goal Name", "description": "What this goal achieves"}
            ]
          }
        }

        When having a conversational exchange (no milestone changes), respond with plain text only.
        """

        if let ctx = context {
            prompt += "\n\n## Project Documents\n"
            for (docType, doc) in ctx.documents {
                if !doc.content.isEmpty {
                    prompt += "\n### \(docType.capitalized)\n\(doc.content)\n"
                }
            }
        }

        if !existingMilestones.isEmpty {
            prompt += "\n\n## Existing Milestones (already planned)\n"
            for (i, m) in existingMilestones.enumerated() {
                prompt += "\nM\(i+1): \(m.name) — \(m.description)"
                for g in m.goals {
                    prompt += "\n  - \(g.name): \(g.description)"
                }
            }
            prompt += "\n\nPropose the NEXT milestone (M\(existingMilestones.count + 1))."
        }

        return prompt
    }

    private func buildOpeningMessage() -> String {
        guard let ctx = context else {
            return "Let's plan your next milestone. What's the most important thing to deliver?"
        }

        let completedDocs = ctx.documents.filter { !$0.value.content.isEmpty }.map { $0.key.capitalized }

        if completedDocs.isEmpty {
            return "Complete your Vision document first — it's the foundation for milestone planning."
        }

        let milestoneNum = existingMilestones.count + 1

        if existingMilestones.isEmpty {
            return "I've read your \(completedDocs.joined(separator: ", ")) documents. Let's define your first milestone — the minimum viable deliverable that proves your product works.\n\nWhat's the single most important thing to ship first?"
        }

        let existing = existingMilestones.map { "• \($0.name)" }.joined(separator: "\n")
        return "You have \(existingMilestones.count) milestone(s) planned:\n\n\(existing)\n\nLet's define M\(milestoneNum). Based on what you've planned, what should come next?"
    }

    // MARK: - Parse Response

    private func parseResponse(_ content: String) -> ParsedPlanningResponse {
        let jsonString = extractJSON(from: content)

        guard let data = jsonString.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return ParsedPlanningResponse(message: content, milestone: nil)
        }

        let message = json["ai_message"] as? String ?? content

        if let m = json["milestone"] as? [String: Any] {
            let goals = (m["goals"] as? [[String: Any]])?.enumerated().map { (j, g) in
                PlannedGoal(
                    id: g["id"] as? String ?? "g\(j+1)",
                    name: g["name"] as? String ?? "",
                    description: g["description"] as? String ?? ""
                )
            } ?? []
            let milestone = PlannedMilestone(
                id: m["id"] as? String ?? "m\(existingMilestones.count + 1)",
                name: m["name"] as? String ?? "",
                description: m["description"] as? String ?? "",
                goals: goals
            )
            return ParsedPlanningResponse(message: message, milestone: milestone)
        }

        return ParsedPlanningResponse(message: message, milestone: nil)
    }

    private func extractJSON(from content: String) -> String {
        let trimmed = content.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.hasPrefix("{") { return trimmed }

        if let startRange = content.range(of: "```json") ?? content.range(of: "```\n{"),
           let endRange = content.range(of: "```", range: startRange.upperBound..<content.endIndex) {
            var json = String(content[startRange.upperBound..<endRange.lowerBound])
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if json.hasPrefix("json") {
                json = String(json.dropFirst(4)).trimmingCharacters(in: .whitespacesAndNewlines)
            }
            return json
        }

        if let firstBrace = content.firstIndex(of: "{"),
           let lastBrace = content.lastIndex(of: "}") {
            return String(content[firstBrace...lastBrace])
        }

        return content
    }
}

// MARK: - Models

struct PlannedMilestone: Identifiable, Equatable {
    let id: String
    let name: String
    let description: String
    var goals: [PlannedGoal]
}

struct PlannedGoal: Identifiable, Equatable {
    let id: String
    let name: String
    let description: String
}

private struct PlanningContext {
    let documents: [String: DocContext]
}

private struct DocContext {
    let content: String
}

private struct ParsedPlanningResponse {
    let message: String
    let milestone: PlannedMilestone?
}

// MARK: - DTOs

private struct AIChatMsg: Encodable {
    let role: String
    let content: String
}

private struct AIChatReq: Encodable {
    let system: String
    let messages: [AIChatMsg]
    let project_id: String?
}

private struct AIChatResp: Decodable {
    let content: String
    let tokens_in: Int
    let tokens_out: Int
    let cost_usd: String
}

private struct PlanningContextDocDTO: Decodable {
    let status: String
    let content: String
}

private struct PlanningContextDTO: Decodable {
    let documents: [String: PlanningContextDocDTO]
}

private struct ExistingGoalDTO: Decodable {
    let id: String
    let name: String
    let description: String
}

private struct ExistingMilestoneDTO: Decodable {
    let id: String
    let name: String
    let description: String
    let goals: [ExistingGoalDTO]
}

private struct ExistingMilestonesDTO: Decodable {
    let milestones: [ExistingMilestoneDTO]
}

private struct GoalDTO: Encodable {
    let id: String
    let name: String
    let description: String
    let status: String
}

private struct MilestoneDTO: Encodable {
    let id: String
    let name: String
    let description: String
    let status: String
    let goals: [GoalDTO]
}

private struct SaveMilestonesRespDTO: Decodable {
    let count: Int
    let status: String
}
