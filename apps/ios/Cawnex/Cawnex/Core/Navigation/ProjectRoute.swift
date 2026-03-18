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

    // S32 — MVI Detail (waveId is present when navigating from wave execution context)
    case mvi(projectId: String, mviId: String, waveId: String? = nil)

    // S33 — Task Detail
    case task(projectId: String, taskId: String)

    // S34 — PR Review
    case pr(projectId: String, prId: String)

    // Human Tasks
    case humanTasks(projectId: String)
    case humanTaskDetail(projectId: String, humanTaskId: String)

    // Waves
    case waves(projectId: String)
    case waveLaunch(projectId: String)
    case waveExecution(projectId: String, waveId: String)

    // Autopilot
    case autopilotPlanReview(plan: AutopilotPlan, sessionId: String)
}
