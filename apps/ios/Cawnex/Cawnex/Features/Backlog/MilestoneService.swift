import Foundation

protocol MilestoneService {
    func getMilestoneDetail(projectId: String, milestoneId: String) async throws -> MilestoneDetail
    func sendMessage(projectId: String, milestoneId: String, content: String) async throws -> ChatMessage
}

final class InMemoryMilestoneService: MilestoneService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getMilestoneDetail(projectId: String, milestoneId: String) async throws -> MilestoneDetail {
        MilestoneDetail(
            milestone: Milestone(
                id: "ms1",
                name: "M1: Foundation",
                description: "Platform can accept, orchestrate, and deliver the first autonomous task end-to-end.",
                status: .active,
                tasks: TaskCounts(done: 8, active: 3, refined: 2, draft: 2),
                creditsSpent: 142,
                humanEquivSaved: 11000,
                roi: 78,
                goals: [
                    Goal(id: "g1", name: "API Infrastructure", status: .active, mviCount: 3, mvisComplete: 2),
                    Goal(id: "g2", name: "User Authentication", status: .planned, mviCount: 0, mvisComplete: 0),
                ]
            ),
            breadcrumb: "Cawnex › Backlog › M1: Foundation",
            sections: [
                MilestoneDefinitionSection(id: "ms1", title: "Business Achievement", status: .complete),
                MilestoneDefinitionSection(id: "ms2", title: "Success Criteria", status: .complete),
                MilestoneDefinitionSection(id: "ms3", title: "Target Impact", status: .complete),
                MilestoneDefinitionSection(id: "ms4", title: "Timeline", status: .complete),
                MilestoneDefinitionSection(id: "ms5", title: "Dependencies", status: .pending),
                MilestoneDefinitionSection(id: "ms6", title: "Risk Assessment", status: .pending),
            ],
            messages: [
                ChatMessage(
                    id: "mm1",
                    role: .ai,
                    content: "What are the key dependencies for this milestone? Think about:\n\n• External services or APIs you need\n• Infrastructure that must exist first\n• Team knowledge or access requirements\n• Other milestones this depends on",
                    synthesizedSection: nil
                ),
            ],
            goals: [
                MilestoneGoalSummary(
                    id: "g1",
                    name: "API Infrastructure",
                    status: .active,
                    description: "Build REST API, auth middleware, and database schema.",
                    mviCount: 3,
                    taskCount: 12
                ),
                MilestoneGoalSummary(
                    id: "g2",
                    name: "User Authentication",
                    status: .planned,
                    description: "OAuth 2.0, JWT tokens, RBAC, and session management.",
                    mviCount: 0,
                    taskCount: 0
                ),
            ]
        )
    }

    func sendMessage(projectId: String, milestoneId: String, content: String) async throws -> ChatMessage {
        ChatMessage(
            id: UUID().uuidString,
            role: .ai,
            content: "Good insight. Let me capture that in the Dependencies section.",
            synthesizedSection: nil
        )
    }
}
