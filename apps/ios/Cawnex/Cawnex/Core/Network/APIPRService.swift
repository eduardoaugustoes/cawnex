import Foundation
import SwiftUI

/// Real backend implementation of PRService, replacing the InMemory mock.
///
/// Endpoint: `GET /projects/{project_id}/waves/{wave_id}/mvis/{mvi_id}/prs/{pr_number}`
///
/// The iOS-side `prId` is the composite `wave_id:mvi_id:pr_number` produced
/// by APITaskService — that gives us all three URL params without needing
/// iOS to walk back up the navigation tree.
///
/// Empty arrays for `suggested_questions` and `conversation` are expected.
final class APIPRService: PRService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func getPRReview(projectId: String, prId: String) async throws -> PRReviewDetail {
        let (waveId, mviId, prNumber) = try parseCompositePRId(prId)
        let path = "/projects/\(projectId)/waves/\(waveId)/mvis/\(mviId)/prs/\(prNumber)"
        let dto: PRReviewDTO = try await client.get(path)
        return mapToPRReviewDetail(dto)
    }

    // MARK: - ID parsing

    private func parseCompositePRId(_ prId: String) throws -> (String, String, Int) {
        let parts = prId.split(separator: ":")
        guard parts.count == 3, let prNumber = Int(parts[2]) else {
            throw APIError.invalidURL(
                "prId must be 'wave_id:mvi_id:pr_number' (got '\(prId)')"
            )
        }
        return (String(parts[0]), String(parts[1]), prNumber)
    }

    // MARK: - Mapping

    private func mapToPRReviewDetail(_ dto: PRReviewDTO) -> PRReviewDetail {
        PRReviewDetail(
            title: dto.title,
            branch: dto.branch,
            status: mapPRStatus(dto.status),
            breadcrumbMVI: dto.breadcrumb_mvi,
            breadcrumbTask: dto.breadcrumb_task,
            creditsCost: dto.credits_cost,
            aiMinutes: dto.ai_minutes,
            filesChanged: dto.files_changed,
            linesAdded: dto.lines_added,
            linesRemoved: dto.lines_removed,
            verdict: mapVerdict(dto.verdict),
            planSteps: dto.plan_steps.map(mapPlanStep),
            suggestedQuestions: dto.suggested_questions,
            conversation: dto.conversation.map(mapChatMessage)
        )
    }

    private func mapPRStatus(_ raw: String) -> PRStatus {
        switch raw.lowercased() {
        case "merged": return .merged
        case "changes_requested": return .changesRequested
        case "ready", "open", "": return .ready
        default: return .ready
        }
    }

    private func mapVerdict(_ dto: PRVerdictDTO) -> PRVerdict {
        PRVerdict(
            status: mapVerdictStatus(dto.status),
            crowName: dto.crow_name,
            confidence: mapConfidence(dto.confidence),
            filesAnalyzed: dto.files_analyzed,
            summary: dto.summary,
            findings: dto.findings.map {
                PRFinding(id: $0.id, text: $0.text, type: mapFindingType($0.type))
            }
        )
    }

    private func mapVerdictStatus(_ raw: String) -> VerdictStatus {
        switch raw.lowercased() {
        case "approved": return .approved
        case "rejected": return .rejected
        case "changes_needed", "changes_requested", "": return .changesNeeded
        default: return .changesNeeded
        }
    }

    private func mapConfidence(_ raw: String) -> VerdictConfidence {
        switch raw.lowercased() {
        case "high": return .high
        case "low": return .low
        case "medium", "": return .medium
        default: return .medium
        }
    }

    private func mapFindingType(_ raw: String) -> FindingType {
        switch raw.lowercased() {
        case "warning": return .warning
        case "check", "": return .check
        default: return .check
        }
    }

    private func mapPlanStep(_ dto: PlanStepDTO) -> PlanStep {
        PlanStep(
            id: dto.id,
            crowName: dto.crow_name,
            // Color choice is iOS-side; backend doesn't dictate it.
            badgeColor: badgeColorForCrow(dto.crow_name),
            plan: dto.plan,
            executed: dto.executed,
            hint: dto.hint
        )
    }

    private func badgeColorForCrow(_ name: String) -> SwiftUI.Color {
        // Re-uses the existing palette conventions seen in the mock.
        switch name.lowercased() {
        case "planner": return CawnexColors.primaryLight
        case "implementer": return CawnexColors.success
        case "reviewer": return CawnexColors.info
        case "fixer": return CawnexColors.warning
        default: return CawnexColors.mutedForeground
        }
    }

    private func mapChatMessage(_ dto: PRChatMessageDTO) -> PRChatMessage {
        PRChatMessage(
            id: dto.id,
            role: dto.role.lowercased() == "user" ? .user : .ai,
            content: dto.content,
            riskBadge: dto.risk_badge
        )
    }
}

// MARK: - DTOs (mirror the backend response shape exactly)

private struct PRReviewDTO: Decodable {
    let title: String
    let branch: String
    let status: String
    let breadcrumb_mvi: String
    let breadcrumb_task: String
    let credits_cost: Int
    let ai_minutes: Int
    let files_changed: Int
    let lines_added: Int
    let lines_removed: Int
    let verdict: PRVerdictDTO
    let plan_steps: [PlanStepDTO]
    let suggested_questions: [String]
    let conversation: [PRChatMessageDTO]
}

private struct PRVerdictDTO: Decodable {
    let status: String
    let crow_name: String
    let confidence: String
    let files_analyzed: Int
    let summary: String
    let findings: [PRFindingDTO]
}

private struct PRFindingDTO: Decodable {
    let id: String
    let text: String
    let type: String
}

private struct PlanStepDTO: Decodable {
    let id: String
    let crow_name: String
    let plan: String
    let executed: String
    let hint: String?
}

private struct PRChatMessageDTO: Decodable {
    let id: String
    let role: String
    let content: String
    let risk_badge: String?
}

