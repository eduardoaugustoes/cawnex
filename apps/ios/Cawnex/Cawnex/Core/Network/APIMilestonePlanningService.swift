import Foundation

/// AI-driven milestone planning service.
/// Reads all 4 project documents from the backend, then uses the AI chat proxy
/// to guide the founder through breaking the vision into milestones and goals.
final class APIMilestonePlanningService {
    private let client: APIClient
    private let projectId: String

    private var context: PlanningContext?
    private var milestones: [PlannedMilestone] = []
    private var messages: [ChatMessage] = []
    private var currentPhase: PlanningPhase = .proposingMilestones

    init(client: APIClient, projectId: String) {
        self.client = client
        self.projectId = projectId
    }

    // MARK: - Load Context (call before first message)

    func loadContext() async throws -> ChatMessage {
        let response: PlanningContextDTO = try await client.get("/projects/\(projectId)/milestones/context")
        var docs: [String: DocContext] = [:]
        for (key, dto) in response.documents {
            docs[key] = DocContext(content: dto.content)
        }
        context = PlanningContext(documents: docs)

        // Check if milestones already exist
        if let existing: ExistingMilestonesDTO = try? await client.get("/projects/\(projectId)/milestones") {
            if !existing.milestones.isEmpty {
                milestones = existing.milestones.map { m in
                    PlannedMilestone(
                        id: m.id,
                        name: m.name,
                        description: m.description,
                        goals: m.goals.map { g in
                            PlannedGoal(id: g.id, name: g.name, description: g.description)
                        }
                    )
                }
                let summary = milestones.map { "• \($0.name): \($0.goals.count) goals" }.joined(separator: "\n")
                let msg = ChatMessage(
                    id: UUID().uuidString,
                    role: .ai,
                    content: "You already have milestones planned:\n\n\(summary)\n\nWould you like to revise them or start fresh?",
                    synthesizedSection: nil
                )
                messages.append(msg)
                return msg
            }
        }

        // No existing milestones — start the planning conversation
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
        // Add user message
        let userMsg = ChatMessage(id: UUID().uuidString, role: .user, content: content, synthesizedSection: nil)
        messages.append(userMsg)

        // Build Claude messages
        var claudeMessages: [AIChatMsg] = []
        for msg in messages {
            claudeMessages.append(AIChatMsg(
                role: msg.role == .ai ? "assistant" : "user",
                content: msg.content
            ))
        }

        let request = AIChatReq(
            system: buildSystemPrompt(),
            messages: claudeMessages,
            project_id: projectId
        )

        let response: AIChatResp = try await client.post("/ai/chat", body: request)

        // Parse response — try JSON first, fall back to plain text
        let parsed = parseResponse(response.content)

        // If milestones were proposed, store them
        if let proposed = parsed.milestones {
            milestones = proposed
        }

        let aiMsg = ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: parsed.message,
            synthesizedSection: nil
        )
        messages.append(aiMsg)
        return aiMsg
    }

    // MARK: - Save Milestones

    func saveMilestones() async throws {
        let body = SaveMilestonesDTO(
            milestones: milestones.map { m in
                MilestoneDTO(
                    id: m.id,
                    name: m.name,
                    description: m.description,
                    status: "planned",
                    goals: m.goals.map { g in
                        GoalDTO(id: g.id, name: g.name, description: g.description, status: "planned")
                    }
                )
            }
        )
        let _: SaveMilestonesRespDTO = try await client.put("/projects/\(projectId)/milestones", body: body)
    }

    var plannedMilestones: [PlannedMilestone] { milestones }
    var allMessages: [ChatMessage] { messages }
    var hasMilestones: Bool { !milestones.isEmpty }

    // MARK: - System Prompt

    private func buildSystemPrompt() -> String {
        var prompt = MilestonePlanningPrompt.system

        if let ctx = context {
            prompt += "\n\n## Project Documents\n"
            for (docType, doc) in ctx.documents {
                if !doc.content.isEmpty {
                    prompt += "\n### \(docType.capitalized)\n\(doc.content)\n"
                }
            }
        }

        if !milestones.isEmpty {
            prompt += "\n\n## Current Milestone Plan\n"
            for (i, m) in milestones.enumerated() {
                prompt += "\nM\(i+1): \(m.name) — \(m.description)"
                for g in m.goals {
                    prompt += "\n  - \(g.name): \(g.description)"
                }
            }
        }

        return prompt
    }

    private func buildOpeningMessage() -> String {
        guard let ctx = context else {
            return "Let's plan your milestones. What's the most important thing to deliver first?"
        }

        let completedDocs = ctx.documents.filter { !$0.value.content.isEmpty }.map { $0.key.capitalized }

        if completedDocs.isEmpty {
            return "I don't see any completed documents yet. Complete your Vision document first — it's the foundation for milestone planning."
        }

        return "I've read your \(completedDocs.joined(separator: ", ")) documents. Based on your vision, let me propose milestones.\n\nEach milestone should be a major deliverable that unlocks real value for your users. What's the single most important thing to ship first?"
    }

    // MARK: - Parse Response

    private func parseResponse(_ content: String) -> ParsedPlanningResponse {
        var cleaned = content.trimmingCharacters(in: .whitespacesAndNewlines)
        if cleaned.hasPrefix("```") {
            if let firstNewline = cleaned.firstIndex(of: "\n") {
                cleaned = String(cleaned[cleaned.index(after: firstNewline)...])
            }
            if cleaned.hasSuffix("```") {
                cleaned = String(cleaned.dropLast(3)).trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }

        guard let data = cleaned.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return ParsedPlanningResponse(message: content, milestones: nil)
        }

        let message = json["ai_message"] as? String ?? content

        if let milestonesJson = json["milestones"] as? [[String: Any]] {
            let parsed = milestonesJson.enumerated().map { (i, m) in
                let goals = (m["goals"] as? [[String: Any]])?.enumerated().map { (j, g) in
                    PlannedGoal(
                        id: g["id"] as? String ?? "g\(i+1)_\(j+1)",
                        name: g["name"] as? String ?? "",
                        description: g["description"] as? String ?? ""
                    )
                } ?? []
                return PlannedMilestone(
                    id: m["id"] as? String ?? "m\(i+1)",
                    name: m["name"] as? String ?? "",
                    description: m["description"] as? String ?? "",
                    goals: goals
                )
            }
            return ParsedPlanningResponse(message: message, milestones: parsed)
        }

        return ParsedPlanningResponse(message: message, milestones: nil)
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
    let milestones: [PlannedMilestone]?
}

private enum PlanningPhase {
    case proposingMilestones
    case refiningGoals
    case complete
}

// MARK: - System Prompt

enum MilestonePlanningPrompt {
    static let system = """
    You are Cawnex Milestone Planner — a product strategist who helps founders \
    break their vision into executable milestones.

    You have access to the founder's completed project documents (Vision, \
    Architecture, Glossary, Design System). Use them to propose milestones \
    that are grounded in the actual product strategy.

    ## Principles
    - Each milestone is a MAJOR DELIVERABLE that unlocks real user value.
    - Milestones are ordered: M1 ships first, M2 depends on M1, etc.
    - Each milestone has 2-5 goals. Each goal becomes a set of MVIs.
    - M1 should be the minimum viable loop — the smallest thing that proves \
      the product works end-to-end.
    - Be specific. "Build MVP" is not a milestone. "First user completes a \
      full collection flow via WhatsApp" is.
    - Respect the founder's priorities — if they want to reorder, do it.
    - After proposing milestones, break each into goals when the founder agrees.

    ## Conversation Flow
    1. Read the documents, propose 3-5 milestones with brief descriptions
    2. Founder steers (reorder, rename, split, merge, add, remove)
    3. Once milestones are agreed, break each into 2-5 goals
    4. Founder confirms, done

    ## Output Format
    When proposing or updating milestones, respond with JSON:
    ```
    {
      "ai_message": "Your conversational response explaining the proposal",
      "milestones": [
        {
          "id": "m1",
          "name": "WhatsApp Bot POC",
          "description": "First debtor receives automated collection message via WhatsApp",
          "goals": [
            {"id": "g1_1", "name": "WhatsApp API Integration", "description": "Connect to WhatsApp Business API"},
            {"id": "g1_2", "name": "Debt Data Import", "description": "Import overdue invoices from spreadsheet"}
          ]
        }
      ]
    }
    ```

    When having a conversational exchange (no milestone changes), respond with plain text only.

    When all milestones and goals are agreed upon, include `"status": "complete"` in the JSON.
    """
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

private struct SaveMilestonesDTO: Encodable {
    let milestones: [MilestoneDTO]
}

private struct SaveMilestonesRespDTO: Decodable {
    let count: Int
    let status: String
}
