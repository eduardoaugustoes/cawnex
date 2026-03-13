import Foundation
import SwiftUI

protocol PRService {
    func getPRReview(projectId: String, prId: String) async throws -> PRReviewDetail
}

final class InMemoryPRService: PRService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func getPRReview(projectId: String, prId: String) async throws -> PRReviewDetail {
        PRReviewDetail(
            title: "Add input validation for user registration endpoint",
            branch: "feat/user-registration-validation",
            status: .ready,
            breadcrumbMVI: "MVI 1.2",
            breadcrumbTask: "Input Validation",
            creditsCost: 12,
            aiMinutes: 8,
            filesChanged: 6,
            linesAdded: 142,
            linesRemoved: 23,
            verdict: PRVerdict(
                status: .approved,
                crowName: "Reviewer Crow",
                confidence: .high,
                filesAnalyzed: 6,
                summary: "Clean implementation. Validation logic follows the existing patterns in your codebase. Zod schemas are well-structured with proper error messages. Test coverage is comprehensive.",
                findings: [
                    PRFinding(id: "f1", text: "All 14 tests passing, coverage +3% to 87%", type: .check),
                    PRFinding(id: "f2", text: "No security vulnerabilities detected", type: .check),
                    PRFinding(id: "f3", text: "Minor: email regex could be stricter (RFC 5322)", type: .warning),
                ]
            ),
            planSteps: [
                PlanStep(
                    id: "ps1",
                    crowName: "Planner",
                    badgeColor: CawnexColors.primaryLight,
                    plan: "Add Zod validation schemas for email, password, and name fields on the registration endpoint",
                    executed: "Created Zod schemas with custom error messages, added email format + password strength validation",
                    hint: nil
                ),
                PlanStep(
                    id: "ps2",
                    crowName: "Implementer",
                    badgeColor: CawnexColors.success,
                    plan: "Implement validation middleware, write unit tests, update OpenAPI spec",
                    executed: "Created validation middleware + 14 unit tests. Also refactored existing error handler to support Zod errors",
                    hint: "Deviated from plan: refactored error handler. This was beyond the original scope but improves consistency."
                ),
                PlanStep(
                    id: "ps3",
                    crowName: "Reviewer",
                    badgeColor: CawnexColors.info,
                    plan: "Verify tests pass, check security, review code quality",
                    executed: "Approved. Clean code, good test coverage. One minor suggestion on email regex strictness.",
                    hint: nil
                ),
            ],
            suggestedQuestions: [
                "Why was error handler changed?",
                "Show me the Zod schemas",
                "Is this RFC 5322 issue a risk?",
                "What would break if I merge?",
            ],
            conversation: [
                PRChatMessage(
                    id: "m1",
                    role: .user,
                    content: "Why was the error handler refactored? That wasn't in the plan.",
                    riskBadge: nil
                ),
                PRChatMessage(
                    id: "m2",
                    role: .ai,
                    content: "The Implementer found that the existing error handler didn't support Zod's structured errors. Without the refactor, validation errors would have returned as generic 500s instead of helpful 422 responses.\n\nThe change is isolated to error-handler.ts and only adds a new case for ZodError — no existing behavior was modified.",
                    riskBadge: "Low risk — additive change only"
                ),
            ]
        )
    }
}
