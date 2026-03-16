import Foundation

/// AI-driven MVI planning within a goal.
/// Same chat + steer pattern as documents and milestones.
/// Each MVI must be ≤ 8 hours. AI auto-splits if larger.
final class APIMVIPlanningService {
    private let client: APIClient
    private let projectId: String
    private let goalId: String

    private var goalContext: GoalContextDTO?
    private(set) var proposedMVIs: [PlannedMVI] = []
    private var messages: [ChatMessage] = []

    init(client: APIClient, projectId: String, goalId: String) {
        self.client = client
        self.projectId = projectId
        self.goalId = goalId
    }

    // MARK: - Load Context

    func loadContext() async throws -> ChatMessage {
        let response: GoalContextDTO = try await client.get(
            "/projects/\(projectId)/goals/\(goalId)/context"
        )
        goalContext = response

        // If MVIs already exist, show them
        if !response.existing_mvis.isEmpty {
            proposedMVIs = response.existing_mvis.map { m in
                PlannedMVI(
                    id: m.id, name: m.name, description: m.description,
                    acceptance_criteria: m.acceptance_criteria,
                    estimated_hours: m.estimated_hours
                )
            }
            let summary = proposedMVIs.map {
                "• \($0.name) (~\(Int($0.estimated_hours))h)"
            }.joined(separator: "\n")
            let msg = ChatMessage(
                id: UUID().uuidString, role: .ai,
                content: "This goal already has MVIs planned:\n\n\(summary)\n\nWould you like to refine them or plan different ones?",
                synthesizedSection: nil
            )
            messages.append(msg)
            return msg
        }

        let firstMessage = ChatMessage(
            id: UUID().uuidString, role: .ai,
            content: buildOpeningMessage(),
            synthesizedSection: nil
        )
        messages.append(firstMessage)
        return firstMessage
    }

    // MARK: - Send Message

    func sendMessage(_ content: String) async throws -> ChatMessage {
        let userMsg = ChatMessage(
            id: UUID().uuidString, role: .user, content: content, synthesizedSection: nil
        )
        messages.append(userMsg)

        var claudeMessages: [MVIChatMsg] = messages.map { msg in
            MVIChatMsg(role: msg.role == .ai ? "assistant" : "user", content: msg.content)
        }

        let request = MVIChatReq(
            system: buildSystemPrompt(),
            messages: claudeMessages,
            project_id: projectId
        )

        let response: MVIChatResp = try await client.post("/ai/chat", body: request)
        let parsed = parseResponse(response.content)

        var synthesized: DocumentSection? = nil
        if let proposed = parsed.mvis, !proposed.isEmpty {
            proposedMVIs = proposed
            let totalHours = proposed.reduce(0) { $0 + $1.estimated_hours }
            let summary = proposed.map {
                "• \($0.name) (~\(Int($0.estimated_hours))h)\n  \($0.description)"
            }.joined(separator: "\n\n")
            synthesized = DocumentSection(
                id: "mvis",
                title: "\(proposed.count) MVIs · ~\(Int(totalHours))h total",
                content: summary,
                status: .complete
            )
        }

        let aiMsg = ChatMessage(
            id: UUID().uuidString, role: .ai,
            content: parsed.message,
            synthesizedSection: synthesized
        )
        messages.append(aiMsg)
        return aiMsg
    }

    // MARK: - Save

    func saveMVIs() async throws {
        let body = SaveMVIsDTO(
            mvis: proposedMVIs.map { m in
                MVIInputDTO(
                    id: m.id, name: m.name, description: m.description,
                    acceptance_criteria: m.acceptance_criteria,
                    estimated_hours: m.estimated_hours
                )
            }
        )
        let _: SaveMVIsRespDTO = try await client.post(
            "/projects/\(projectId)/goals/\(goalId)/mvis", body: body
        )
    }

    var hasMVIs: Bool { !proposedMVIs.isEmpty }
    var allMessages: [ChatMessage] { messages }

    // MARK: - System Prompt

    private func buildSystemPrompt() -> String {
        var prompt = """
        You are Cawnex MVI Planner — a technical product strategist who breaks \
        goals into Minimum Valuable Increments (MVIs).

        An MVI is a 2-5 day deliverable — the smallest unit of work that \
        delivers measurable value. Each MVI will be executed by AI agents.

        ## CRITICAL RULES
        - Every MVI MUST be ≤ 8 hours of human equivalent work.
        - If a piece of work would take > 8h, SPLIT IT into multiple MVIs.
        - Each MVI must have: name, description, acceptance_criteria, estimated_hours.
        - estimated_hours is used for ROI calculation (AI cost vs human cost).
        - Propose 2-4 MVIs per goal. More specific = better execution.

        ## Principles
        - MVIs should be independently deliverable (can be merged separately).
        - Order matters: MVI 1 should unblock MVI 2 where dependencies exist.
        - Acceptance criteria must be concrete and testable.
        - estimated_hours should reflect what a mid-level developer would take.

        ## Output Format
        When proposing MVIs, respond with JSON:
        {
          "ai_message": "Your conversational response",
          "mvis": [
            {
              "id": "mvi1",
              "name": "MVI Name",
              "description": "What this MVI delivers",
              "acceptance_criteria": "Concrete, testable criteria",
              "estimated_hours": 6
            }
          ]
        }

        When having a conversational exchange, respond with plain text only.
        """

        if let ctx = goalContext {
            prompt += "\n\n## Goal Being Planned"
            prompt += "\nGoal: \(ctx.goal.name)"
            prompt += "\nDescription: \(ctx.goal.description)"
            prompt += "\n\nParent Milestone: \(ctx.milestone.name) — \(ctx.milestone.description)"

            if !ctx.sibling_goals.isEmpty {
                prompt += "\n\nSibling Goals (NOT this goal's responsibility):"
                for g in ctx.sibling_goals {
                    prompt += "\n- \(g.name): \(g.description)"
                }
            }

            prompt += "\n\n## Project Documents"
            for (docType, content) in ctx.documents {
                if !content.isEmpty {
                    prompt += "\n\n### \(docType.capitalized)\n\(content)"
                }
            }
        }

        if !proposedMVIs.isEmpty {
            prompt += "\n\n## Currently Proposed MVIs"
            for m in proposedMVIs {
                prompt += "\n- \(m.name) (~\(Int(m.estimated_hours))h): \(m.description)"
            }
        }

        return prompt
    }

    private func buildOpeningMessage() -> String {
        guard let ctx = goalContext else {
            return "Let's break this goal into MVIs. What are the key deliverables?"
        }

        return "I'm looking at the goal **\(ctx.goal.name)** within milestone **\(ctx.milestone.name)**.\n\n\"\(ctx.goal.description)\"\n\nLet me propose MVIs — each one a concrete, independently deliverable piece of work (≤ 8 hours). What's the most important thing to deliver first within this goal?"
    }

    // MARK: - Parse Response

    private func parseResponse(_ content: String) -> ParsedMVIResponse {
        let jsonString = extractJSON(from: content)

        guard let data = jsonString.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return ParsedMVIResponse(message: content, mvis: nil)
        }

        let message = json["ai_message"] as? String ?? content

        if let mvisJson = json["mvis"] as? [[String: Any]] {
            let parsed = mvisJson.enumerated().map { i, m in
                PlannedMVI(
                    id: m["id"] as? String ?? "mvi\(i + 1)",
                    name: m["name"] as? String ?? "",
                    description: m["description"] as? String ?? "",
                    acceptance_criteria: m["acceptance_criteria"] as? String ?? "",
                    estimated_hours: (m["estimated_hours"] as? Double) ?? (m["estimated_hours"] as? Int).map(Double.init) ?? 4.0
                )
            }
            return ParsedMVIResponse(message: message, mvis: parsed)
        }

        return ParsedMVIResponse(message: message, mvis: nil)
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

struct PlannedMVI: Identifiable, Equatable {
    let id: String
    let name: String
    let description: String
    let acceptance_criteria: String
    let estimated_hours: Double
}

private struct ParsedMVIResponse {
    let message: String
    let mvis: [PlannedMVI]?
}

// MARK: - Context DTOs

private struct GoalDTO: Decodable {
    let id: String
    let name: String
    let description: String
}

private struct MilestoneRefDTO: Decodable {
    let id: String
    let name: String
    let description: String
}

private struct ExistingMVIDTO: Decodable {
    let id: String
    let name: String
    let description: String
    let acceptance_criteria: String
    let estimated_hours: Double
}

private struct GoalContextDTO: Decodable {
    let goal: GoalDTO
    let milestone: MilestoneRefDTO
    let sibling_goals: [GoalDTO]
    let documents: [String: String]
    let existing_mvis: [ExistingMVIDTO]
}

// MARK: - Save DTOs

private struct MVIInputDTO: Encodable {
    let id: String
    let name: String
    let description: String
    let acceptance_criteria: String
    let estimated_hours: Double
}

private struct SaveMVIsDTO: Encodable {
    let mvis: [MVIInputDTO]
}

private struct SaveMVIsRespDTO: Decodable {
    let count: Int
    let status: String
}

// MARK: - Chat DTOs

private struct MVIChatMsg: Encodable {
    let role: String
    let content: String
}

private struct MVIChatReq: Encodable {
    let system: String
    let messages: [MVIChatMsg]
    let project_id: String?
}

private struct MVIChatResp: Decodable {
    let content: String
    let tokens_in: Int
    let tokens_out: Int
    let cost_usd: String
}
