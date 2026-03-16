import Foundation

/// DocumentService that uses the AI chat proxy for real Claude conversations.
/// Conversation state lives in-memory (client-side). Nothing persists until save.
final class APIDocumentService: DocumentService {
    private let client: APIClient
    private let projectId: String

    /// In-memory conversation state per document type
    private var conversations: [DocumentType: ConversationState] = [:]

    init(client: APIClient, projectId: String) {
        self.client = client
        self.projectId = projectId
    }

    func getDocument(projectId: String, type: DocumentType) async throws -> DocumentDetail {
        let state = getOrCreateConversation(type: type)
        return DocumentDetail(
            projectId: projectId,
            sections: state.sections,
            messages: state.messages
        )
    }

    func sendMessage(projectId: String, type: DocumentType, content: String) async throws -> ChatMessage {
        var state = getOrCreateConversation(type: type)
        let sectionDefs = SectionDefinitions.sections(for: type)

        // Find current pending section
        guard let currentIndex = state.sections.firstIndex(where: { $0.status == .pending }) else {
            return ChatMessage(
                id: UUID().uuidString,
                role: .ai,
                content: "All sections are complete! Tap 'Preview Document' to review.",
                synthesizedSection: nil
            )
        }

        let currentSection = sectionDefs[currentIndex]
        let nextSection = currentIndex + 1 < sectionDefs.count ? sectionDefs[currentIndex + 1] : nil

        // Build system prompt
        let systemPrompt = VisionGuidePrompt.system

        // Build message history for Claude
        var claudeMessages: [AIChatMessageDTO] = []
        for msg in state.messagesForCurrentSection {
            claudeMessages.append(AIChatMessageDTO(role: msg.role == .ai ? "assistant" : "user", content: msg.content))
        }
        claudeMessages.append(AIChatMessageDTO(role: "user", content: content))

        // Build user context
        let userContext = """
        Current section to complete: \(currentSection.title)
        Section guidance: \(currentSection.description)

        Next section: \(nextSection?.title ?? "none — this is the last section")

        User's answer: \(content)
        """

        // Prepend context as first user message if this is the first message for this section
        if state.messagesForCurrentSection.isEmpty {
            claudeMessages = [
                AIChatMessageDTO(role: "user", content: userContext)
            ]
        } else {
            claudeMessages.append(AIChatMessageDTO(role: "user", content: userContext))
        }

        // Call Claude via proxy
        let request = AIChatRequestDTO(
            system: systemPrompt,
            messages: claudeMessages,
            project_id: projectId
        )

        let response: AIChatResponseDTO = try await client.post("/ai/chat", body: request)

        // Parse Claude's JSON response
        let parsed = parseClaudeResponse(response.content)

        var synthesizedSection: DocumentSection? = nil

        if parsed.isSufficient, let synthesized = parsed.synthesizedContent {
            // Mark section as complete
            state.sections[currentIndex] = DocumentSection(
                id: currentSection.id,
                title: currentSection.title,
                content: synthesized,
                status: .complete
            )
            synthesizedSection = state.sections[currentIndex]
            state.currentSectionMessageStart = state.messages.count + 2 // +user +ai
        }

        // Add user message to history
        let userMsg = ChatMessage(id: UUID().uuidString, role: .user, content: content, synthesizedSection: nil)
        state.messages.append(userMsg)

        // Add AI message to history
        let aiMessage = ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: parsed.aiMessage,
            synthesizedSection: synthesizedSection
        )
        state.messages.append(aiMessage)

        conversations[type] = state

        return aiMessage
    }

    // MARK: - Conversation State

    private func getOrCreateConversation(type: DocumentType) -> ConversationState {
        if let existing = conversations[type] {
            return existing
        }

        let sectionDefs = SectionDefinitions.sections(for: type)
        let sections = sectionDefs.map { def in
            DocumentSection(id: def.id, title: def.title, content: "", status: .pending)
        }

        // First AI message: the first question
        let firstQuestion = sectionDefs[0].question
        let firstMessage = ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: firstQuestion,
            synthesizedSection: nil
        )

        let state = ConversationState(
            sections: sections,
            messages: [firstMessage],
            currentSectionMessageStart: 0
        )
        conversations[type] = state
        return state
    }

    // MARK: - Parse Claude Response

    private func parseClaudeResponse(_ content: String) -> ParsedResponse {
        // Strip markdown fences if present (```json ... ```)
        var cleaned = content.trimmingCharacters(in: .whitespacesAndNewlines)
        if cleaned.hasPrefix("```") {
            // Remove opening fence (```json or ```)
            if let firstNewline = cleaned.firstIndex(of: "\n") {
                cleaned = String(cleaned[cleaned.index(after: firstNewline)...])
            }
            // Remove closing fence
            if cleaned.hasSuffix("```") {
                cleaned = String(cleaned.dropLast(3)).trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }

        // Try to parse as JSON
        guard let data = cleaned.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            // Fallback: treat entire response as the AI message
            return ParsedResponse(isSufficient: false, synthesizedContent: nil, aiMessage: content)
        }

        let isSufficient = json["is_sufficient"] as? Bool ?? false
        let synthesized = json["synthesized_content"] as? String
        let aiMessage = json["ai_message"] as? String ?? content

        return ParsedResponse(
            isSufficient: isSufficient,
            synthesizedContent: isSufficient ? synthesized : nil,
            aiMessage: aiMessage
        )
    }
}

// MARK: - Internal Types

private struct ConversationState {
    var sections: [DocumentSection]
    var messages: [ChatMessage]
    var currentSectionMessageStart: Int

    var messagesForCurrentSection: [ChatMessage] {
        guard currentSectionMessageStart < messages.count else { return [] }
        return Array(messages[currentSectionMessageStart...])
    }
}

private struct ParsedResponse {
    let isSufficient: Bool
    let synthesizedContent: String?
    let aiMessage: String
}

// MARK: - DTOs

private struct AIChatMessageDTO: Encodable {
    let role: String
    let content: String
}

private struct AIChatRequestDTO: Encodable {
    let system: String
    let messages: [AIChatMessageDTO]
    let project_id: String?
}

private struct AIChatResponseDTO: Decodable {
    let content: String
    let tokens_in: Int
    let tokens_out: Int
    let cost_usd: String
    let model: String
    let duration_ms: Int
}

// MARK: - Vision Guide System Prompt

enum VisionGuidePrompt {
    static let system = """
    You are Cawnex Vision Guide — a startup advisor who helps founders \
    articulate their product vision with precision and clarity.

    Your role is to facilitate a structured conversation that builds a \
    document section by section. You ask one focused question at a time, \
    listen to the founder's answer, and synthesize it into a crisp, \
    professional section.

    ## Principles
    - Accept messy, conversational answers — your job is to extract the signal.
    - Synthesize answers into formal section voice: clear, specific, jargon-free.
    - If an answer is too vague (e.g., "better UX", "faster"), probe with one \
      follow-up. Mark is_sufficient: false.
    - If an answer has enough substance, mark is_sufficient: true even if it \
      could be more detailed. Founders need momentum, not perfection.
    - Keep synthesized sections under 60 words. Density over length.
    - After synthesizing, ask the next question with a brief bridge sentence.
    - Be specific, not generic. "Technical founders at pre-seed" beats "startups".

    ## Output Format
    Always respond with valid JSON only. No markdown fences.

    When the answer is sufficient:
    {
      "is_sufficient": true,
      "synthesized_content": "The synthesized section text, 1-3 sentences.",
      "ai_message": "Brief acknowledgment + next question."
    }

    When the answer needs clarification:
    {
      "is_sufficient": false,
      "synthesized_content": null,
      "ai_message": "The follow-up question to ask."
    }
    """
}

// MARK: - Section Definitions (client-side, matches server)

enum SectionDefinitions {
    struct Section {
        let id: String
        let title: String
        let question: String
        let description: String
    }

    static func sections(for type: DocumentType) -> [Section] {
        switch type {
        case .vision: return visionSections
        case .architecture: return architectureSections
        case .glossary: return glossarySections
        case .design: return designSections
        }
    }

    static let visionSections: [Section] = [
        Section(id: "s1", title: "Problem Statement",
                question: "What's the core problem you're solving? Describe the pain — who feels it, how often, and what they do today instead.",
                description: "A clear statement of the problem: who has it, how painful it is, and why existing solutions fail."),
        Section(id: "s2", title: "Target User",
                question: "Who is your primary user? Describe them in terms of their role, experience level, and the specific context where they'll use your product.",
                description: "A specific user profile: role, stage, context. Not a market segment — a person you can picture."),
        Section(id: "s3", title: "Core Value Proposition",
                question: "What's the single most important outcome your product delivers? Not features — the transformation.",
                description: "One sentence: For [user], [product] delivers [outcome] by eliminating [friction]."),
        Section(id: "s4", title: "Key Differentiators",
                question: "What makes your approach fundamentally different from existing solutions? What would a competitor need to copy to match you?",
                description: "3-4 concrete differentiators. Not adjectives — structural advantages."),
        Section(id: "s5", title: "Success Metrics",
                question: "How will you know if this is working in 6 months? Name 2-3 specific, measurable outcomes.",
                description: "Numbered list: metric + target value + timeframe."),
        Section(id: "s6", title: "Non-Goals",
                question: "What are you explicitly NOT building in the first version? What decisions keep the scope tight?",
                description: "Bulleted list of what's out of scope and why."),
    ]

    static let architectureSections: [Section] = [
        Section(id: "a1", title: "System Overview",
                question: "Describe your system in one paragraph. What does it do, who uses it, and what are the main moving parts?",
                description: "One paragraph: what the system does, who interacts, 3-5 major components."),
        Section(id: "a2", title: "High-Level Components",
                question: "What are the main components and how do they interact? Frontend, backend, database, external services, queues, workers.",
                description: "Component list with communication patterns."),
        Section(id: "a3", title: "Data Flow",
                question: "Walk me through a typical user request from button tap to final response. What systems does it touch?",
                description: "Step-by-step flow of a primary use case."),
        Section(id: "a4", title: "Data Model",
                question: "What are the core entities? What database(s) and why? Any key patterns like single-table, event sourcing?",
                description: "Core entities, storage choices, access patterns."),
        Section(id: "a5", title: "Security Model",
                question: "How do you handle auth, authorization, and data isolation? Approach to secrets and encryption?",
                description: "Auth mechanism, tenant isolation, encryption, secrets."),
        Section(id: "a6", title: "Infrastructure & Deployment",
                question: "Where does this run? Cloud provider, compute model, CI/CD approach, environment strategy?",
                description: "Cloud, compute, IaC, CI/CD, environments."),
        Section(id: "a7", title: "Technology Decisions",
                question: "What are the key tech choices and why? Language, framework, database — what was chosen or rejected?",
                description: "Key choices with rationale."),
    ]

    static let glossarySections: [Section] = [
        Section(id: "g1", title: "Domain Terms",
                question: "What are the core domain-specific terms your team uses that might be unfamiliar to new contributors?",
                description: "Domain vocabulary with special meaning in this project."),
        Section(id: "g2", title: "User-Facing Terms",
                question: "What terms do your end users see in the app? The vocabulary of the product interface.",
                description: "Terms visible to users in the UI."),
        Section(id: "g3", title: "Technical Terms",
                question: "What technical terms does your team use that aren't standard? Internal names for services or abstractions.",
                description: "Internal technical vocabulary."),
        Section(id: "g4", title: "Business Terms",
                question: "What business concepts matter? Pricing models, user segments, lifecycle stages, metrics you track.",
                description: "Business vocabulary: pricing, segments, KPIs."),
        Section(id: "g5", title: "Abbreviations",
                question: "What abbreviations or acronyms does your team use? List them with full form and context.",
                description: "Abbreviations with full form and context."),
    ]

    static let designSections: [Section] = [
        Section(id: "d1", title: "Visual Identity",
                question: "What's the visual identity you're going for? Mood, aesthetic, brand colors, inspirations?",
                description: "Brand aesthetic: mood, colors, references, light/dark."),
        Section(id: "d2", title: "Typography",
                question: "What fonts will you use? Type scale — heading sizes, body, captions? Specific font choices?",
                description: "Font families, type scale, weights."),
        Section(id: "d3", title: "Spacing & Layout",
                question: "What spacing system? Fixed scale like 4/8/12/16/24? Corner radius, card padding, screen margins?",
                description: "Spacing scale, radius tokens, margins."),
        Section(id: "d4", title: "Component Patterns",
                question: "What are the key reusable components? Cards, buttons, status chips, progress bars, inputs?",
                description: "Core UI components and patterns."),
        Section(id: "d5", title: "Iconography",
                question: "What icon set? SF Symbols, Lucide, custom? Filled vs outlined, sizes?",
                description: "Icon library, style, sizes."),
        Section(id: "d6", title: "Motion & Interaction",
                question: "How should things move? Transitions, animation durations, loading states, haptics?",
                description: "Animation principles: transitions, easing, haptics."),
    ]
}
