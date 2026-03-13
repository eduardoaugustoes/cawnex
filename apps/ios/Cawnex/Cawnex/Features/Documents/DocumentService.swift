import Foundation

protocol DocumentService {
    func getDocument(projectId: String, type: DocumentType) async throws -> DocumentDetail
    func sendMessage(projectId: String, type: DocumentType, content: String) async throws -> ChatMessage
}

struct InMemoryDocumentService: DocumentService {

    func getDocument(projectId: String, type: DocumentType) async throws -> DocumentDetail {
        switch type {
        case .vision:
            return visionDocument(projectId: projectId)
        case .architecture:
            return architectureDocument(projectId: projectId)
        case .glossary:
            return glossaryDocument(projectId: projectId)
        case .design:
            return designDocument(projectId: projectId)
        }
    }

    func sendMessage(projectId: String, type: DocumentType, content: String) async throws -> ChatMessage {
        ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: "Thanks for sharing that. Let me synthesize this into the document.",
            synthesizedSection: nil
        )
    }

    // MARK: - Seed Data

    private func visionDocument(projectId: String) -> DocumentDetail {
        let sections: [DocumentSection] = [
            DocumentSection(
                id: "s1",
                title: "Problem Statement",
                content: "Founders waste months building the wrong thing because they lack structured guidance to validate assumptions early.",
                status: .complete
            ),
            DocumentSection(
                id: "s2",
                title: "Target User",
                content: "Technical founders with a validated idea, pre-seed to seed stage, building their first AI-powered product.",
                status: .complete
            ),
            DocumentSection(id: "s3", title: "Core Value Proposition", content: "", status: .pending),
            DocumentSection(id: "s4", title: "Key Features", content: "", status: .pending),
            DocumentSection(id: "s5", title: "Success Metrics", content: "", status: .pending),
            DocumentSection(id: "s6", title: "Non-Goals", content: "", status: .pending),
        ]

        let synthesized = DocumentSection(
            id: "s2",
            title: "Target User",
            content: "Technical founders with a validated idea, pre-seed to seed stage, building their first AI-powered product.",
            status: .complete
        )

        let messages: [ChatMessage] = [
            ChatMessage(
                id: "m1",
                role: .ai,
                content: "Who is the primary user of your product? Describe them in terms of their role, experience level, and the context in which they'll use it.",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "m2",
                role: .user,
                content: "Technical founders at the pre-seed to seed stage who are building AI-powered products and need structured help to avoid building the wrong thing.",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "m3",
                role: .ai,
                content: "Got it. Now let's define your core value proposition — what is the single most important outcome your product delivers for them?",
                synthesizedSection: synthesized
            ),
        ]

        return DocumentDetail(projectId: projectId, sections: sections, messages: messages)
    }

    private func architectureDocument(projectId: String) -> DocumentDetail {
        let sections: [DocumentSection] = [
            DocumentSection(
                id: "a1",
                title: "System Overview",
                content: "Multi-agent orchestration platform with iOS client, API gateway, and agent fleet running on AWS infrastructure.",
                status: .complete
            ),
            DocumentSection(
                id: "a2",
                title: "High-Level Components",
                content: "iOS app (SwiftUI), API Gateway (NestJS), Agent Orchestrator, Blackboard (DynamoDB), Git Service (CodeCommit), and Task Queue (SQS).",
                status: .complete
            ),
            DocumentSection(id: "a3", title: "Data Flow", content: "", status: .pending),
            DocumentSection(id: "a4", title: "Infrastructure", content: "", status: .pending),
            DocumentSection(id: "a5", title: "Security Model", content: "", status: .pending),
            DocumentSection(id: "a6", title: "Scalability Strategy", content: "", status: .pending),
            DocumentSection(id: "a7", title: "Technology Decisions", content: "", status: .pending),
        ]

        let synthesized = DocumentSection(
            id: "a2",
            title: "High-Level Components",
            content: "iOS app (SwiftUI), API Gateway (NestJS), Agent Orchestrator, Blackboard (DynamoDB), Git Service (CodeCommit), and Task Queue (SQS).",
            status: .complete
        )

        let messages: [ChatMessage] = [
            ChatMessage(
                id: "am1",
                role: .ai,
                content: "Let's define the architecture for your project. Can you describe the main components of your system and how they interact at a high level?",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "am2",
                role: .user,
                content: "We have an iOS app talking to an API gateway, which coordinates AI agents. Agents use a shared blackboard on DynamoDB and work in isolated git worktrees.",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "am3",
                role: .ai,
                content: "Great — I've captured the high-level components. Now let's map out the data flow. How does a user request flow from the app through to the agents and back?",
                synthesizedSection: synthesized
            ),
        ]

        return DocumentDetail(projectId: projectId, sections: sections, messages: messages)
    }

    private func glossaryDocument(projectId: String) -> DocumentDetail {
        let sections: [DocumentSection] = [
            DocumentSection(
                id: "g1",
                title: "Domain Terms",
                content: "Crow, Murder, Nest, Blackboard, MVI — core concepts of the multi-agent orchestration model.",
                status: .complete
            ),
            DocumentSection(
                id: "g2",
                title: "User-Facing Terms",
                content: "Project, Milestone, Goal, Task, Credit — terms visible to end users in the app interface.",
                status: .complete
            ),
            DocumentSection(id: "g3", title: "Technical Terms", content: "", status: .pending),
            DocumentSection(id: "g4", title: "Business Terms", content: "", status: .pending),
            DocumentSection(id: "g5", title: "Abbreviations", content: "", status: .pending),
        ]

        let synthesized = DocumentSection(
            id: "g2",
            title: "User-Facing Terms",
            content: "Project, Milestone, Goal, Task, Credit — terms visible to end users in the app interface.",
            status: .complete
        )

        let messages: [ChatMessage] = [
            ChatMessage(
                id: "gm1",
                role: .ai,
                content: "Let's build a shared vocabulary for your project. What are the core domain-specific terms your team uses that might be unfamiliar to new contributors?",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "gm2",
                role: .user,
                content: "We call our AI agents Crows, a group of them is a Murder, they work in isolated Nests (git worktrees), and coordinate via a Blackboard (shared state in DynamoDB).",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "gm3",
                role: .ai,
                content: "Love the naming convention. I've captured those domain terms. Now what terms do your end users see in the app — things like project, milestone, credit?",
                synthesizedSection: synthesized
            ),
        ]

        return DocumentDetail(projectId: projectId, sections: sections, messages: messages)
    }

    private func designDocument(projectId: String) -> DocumentDetail {
        let sections: [DocumentSection] = [
            DocumentSection(
                id: "d1",
                title: "Color Palette",
                content: "Dark-first palette: background #0A0A0A, card #1A1C1E, primary #7C3AED, success #22C55E, warning #F59E0B, destructive #EF4444.",
                status: .complete
            ),
            DocumentSection(
                id: "d2",
                title: "Typography Scale",
                content: "Inter font family. Headings: 28/22/18pt heavy. Body: 14pt regular. Caption: 12pt. Label: 13pt medium. Mono: SF Mono 12pt.",
                status: .complete
            ),
            DocumentSection(id: "d3", title: "Spacing & Layout", content: "", status: .pending),
            DocumentSection(id: "d4", title: "Component Library", content: "", status: .pending),
            DocumentSection(id: "d5", title: "Iconography", content: "", status: .pending),
            DocumentSection(id: "d6", title: "Motion & Animation", content: "", status: .pending),
        ]

        let synthesized = DocumentSection(
            id: "d2",
            title: "Typography Scale",
            content: "Inter font family. Headings: 28/22/18pt heavy. Body: 14pt regular. Caption: 12pt. Label: 13pt medium. Mono: SF Mono 12pt.",
            status: .complete
        )

        let messages: [ChatMessage] = [
            ChatMessage(
                id: "dm1",
                role: .ai,
                content: "Let's define your design system. What's the visual identity you're going for — colors, mood, and overall aesthetic?",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "dm2",
                role: .user,
                content: "Dark-first, minimal, professional. Purple as the primary brand color. Clean typography using Inter. Rounded corners, subtle glass effects on overlays.",
                synthesizedSection: nil
            ),
            ChatMessage(
                id: "dm3",
                role: .ai,
                content: "Great aesthetic direction. I've captured your color palette and typography scale. Now let's define your spacing system — do you use a fixed scale like 4/8/12/16/20/24?",
                synthesizedSection: synthesized
            ),
        ]

        return DocumentDetail(projectId: projectId, sections: sections, messages: messages)
    }
}
