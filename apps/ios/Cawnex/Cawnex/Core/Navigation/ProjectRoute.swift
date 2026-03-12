import Foundation

enum ProjectRoute: Hashable {
    // S12 — Project Hub
    case projectHub(projectId: String)

    // S20-S23 — AI-Guided Documents
    case document(projectId: String, type: DocumentType)

    // S24 — Backlog
    case backlog(projectId: String)

    // S30 — Milestone Detail
    case milestone(projectId: String, milestoneId: String)

    // S31 — Goal Detail
    case goal(projectId: String, goalId: String)

    // S32 — MVI Detail
    case mvi(projectId: String, mviId: String)

    // S33 — Task Detail
    case task(projectId: String, taskId: String)

    // S34 — PR Review
    case pr(projectId: String, prId: String)
}
