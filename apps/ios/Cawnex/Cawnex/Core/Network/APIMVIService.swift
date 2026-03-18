import Foundation

final class APIMVIService: MVIService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func getBlackboardDetail(projectId: String, waveId: String?, mviId: String) async throws -> MVIBlackboardDetail {
        guard let waveId else {
            throw APIMVIError.missingWaveId
        }

        async let waveDetailDTO: MVIWaveDetailDTO = client.get("/projects/\(projectId)/waves/\(waveId)")
        async let eventsDTO: MVIEventsDTO = client.get("/projects/\(projectId)/waves/\(waveId)/events?limit=50")

        let (detail, events) = try await (waveDetailDTO, eventsDTO)

        return try mapToBlackboardDetail(
            projectId: projectId,
            waveId: waveId,
            mviId: mviId,
            detail: detail,
            events: events
        )
    }

    // MARK: - Mapping

    private func mapToBlackboardDetail(
        projectId: String,
        waveId: String,
        mviId: String,
        detail: MVIWaveDetailDTO,
        events: MVIEventsDTO
    ) throws -> MVIBlackboardDetail {
        let mviDTO = detail.mvis?.first { dto in
            let sk = dto.SK ?? ""
            return sk.contains(mviId)
        }

        let mviName = mviDTO?.name ?? "MVI"
        let mviStatusRaw = mviDTO?.status ?? "draft"
        let mviStatus = mapMVIStatus(mviStatusRaw)
        let tasksDone = mviDTO?.tasks_done?.value ?? 0
        let tasksTotal = mviDTO?.tasks_total?.value ?? 0
        let credits = mviDTO?.cost?.credits?.value ?? 0
        let canShip = mviDTO?.can_ship ?? false

        let aiCost = Decimal(credits) / Decimal(1_000_000)
        let humanEquiv = Decimal(tasksTotal) * 50
        let roi: Int = aiCost > 0 ? Int(NSDecimalNumber(decimal: humanEquiv / aiCost).intValue) : 0

        let mvi = MVI(
            id: mviId,
            name: mviName,
            status: mviStatus,
            tasksDone: tasksDone,
            tasksTotal: tasksTotal,
            aiMinutes: 0,
            humanDays: "",
            aiCost: aiCost,
            humanEquiv: humanEquiv,
            roi: roi,
            description: mviDTO?.description ?? ""
        )

        let activeCrows = mapCrows(detail.crows)
        let tasks = mapTasks(from: detail.crows, tasksDone: tasksDone, tasksTotal: tasksTotal)
        let liveFeed = mapEvents(events.events ?? [])
        let mergeChecklist = buildMergeChecklist(tasksDone: tasksDone, tasksTotal: tasksTotal, canShip: canShip)

        let waveName = "Wave \(waveId)"
        let breadcrumb = "\(waveName) › \(mviName)"

        return MVIBlackboardDetail(
            mvi: mvi,
            breadcrumb: breadcrumb,
            activeCrows: activeCrows,
            tasks: tasks,
            liveFeed: liveFeed,
            mergeChecklist: mergeChecklist
        )
    }

    private func mapMVIStatus(_ raw: String) -> MVIStatus {
        switch raw {
        case "draft": .draft
        case "refining": .refining
        case "ready", "ready_to_ship": .ready
        case "executing": .executing
        case "shipped": .shipped
        case "rejected", "failed", "cancelled": .rejected
        default: .draft
        }
    }

    private func mapCrows(_ crows: [MVICrowDTO]?) -> [ActiveCrow] {
        guard let crows else { return [] }
        return crows.enumerated().map { index, crow in
            let crowId = crow.crow_id ?? "crow_\(index)"
            let crowType = crow.crow_type ?? "worker"
            let name = crowTypeName(crowType)
            let behaviorState = mapBehaviorState(crow.behavior_state ?? crow.status ?? "assigned")
            return ActiveCrow(id: crowId, name: name, behaviorState: behaviorState, model: "Sonnet 4")
        }
    }

    private func crowTypeName(_ crowType: String) -> String {
        switch crowType {
        case "planner": "Planner"
        case "implementer": "Implementer"
        case "reviewer": "Reviewer"
        case "fixer": "Fixer"
        case "documenter": "Documenter"
        default: crowType.capitalized
        }
    }

    private func mapBehaviorState(_ raw: String) -> CrowBehaviorState {
        switch raw {
        case "scouting": .scouting
        case "planning": .planning
        case "building": .building
        case "hunting": .hunting
        case "reviewing": .reviewing
        case "documenting": .documenting
        case "landed", "completed", "assigned": .landed
        default: .landed
        }
    }

    private func mapTasks(from crows: [MVICrowDTO]?, tasksDone: Int, tasksTotal: Int) -> [MVITask] {
        guard let crows else { return [] }

        let plannerWithTasks = crows
            .filter { $0.crow_type == "planner" && $0.status == "completed" }
            .last ?? crows.first { $0.crow_type == "planner" }

        guard let tasks = plannerWithTasks?.outcome?.tasks, !tasks.isEmpty else {
            return buildPlaceholderTasks(tasksDone: tasksDone, tasksTotal: tasksTotal)
        }

        return tasks.enumerated().map { index, task in
            let isCompleted = index < tasksDone
            let isBuilding = index == tasksDone && tasksDone < tasksTotal
            let status: TaskStatus = isCompleted ? .completed : isBuilding ? .building : .queued
            return MVITask(
                id: "task_\(index)",
                name: task.name ?? "Task \(index + 1)",
                status: status,
                prNumber: nil,
                crowName: isBuilding ? "Implementer" : nil
            )
        }
    }

    private func buildPlaceholderTasks(tasksDone: Int, tasksTotal: Int) -> [MVITask] {
        guard tasksTotal > 0 else { return [] }
        return (0..<tasksTotal).map { index in
            let isCompleted = index < tasksDone
            let isBuilding = index == tasksDone && tasksDone < tasksTotal
            let status: TaskStatus = isCompleted ? .completed : isBuilding ? .building : .queued
            return MVITask(
                id: "task_\(index)",
                name: "Task \(index + 1)",
                status: status,
                prNumber: nil,
                crowName: nil
            )
        }
    }

    private func mapEvents(_ events: [MVIEventDTO]) -> [LiveFeedEvent] {
        events.prefix(20).enumerated().map { index, event in
            let timestamp = formatTimestamp(event.timestamp ?? "")
            let feedType = mapFeedEventType(event.color ?? "default")
            return LiveFeedEvent(
                id: "\(event.timestamp ?? "")_\(index)",
                timestamp: timestamp,
                message: event.message ?? "",
                type: feedType
            )
        }
    }

    private func formatTimestamp(_ iso: String) -> String {
        guard iso.count >= 16 else { return iso }
        let timePart = iso.dropFirst(11).prefix(5)
        return String(timePart)
    }

    private func mapFeedEventType(_ color: String) -> FeedEventType {
        switch color {
        case "green": .success
        case "yellow", "orange": .warning
        case "gray", "grey": .muted
        default: .standard
        }
    }

    private func buildMergeChecklist(tasksDone: Int, tasksTotal: Int, canShip: Bool) -> [MergeChecklistItem] {
        let allTasksDone = tasksTotal > 0 && tasksDone >= tasksTotal
        return [
            MergeChecklistItem(
                id: "mc_tasks",
                label: "\(tasksDone)/\(tasksTotal) tasks completed",
                passed: allTasksDone
            ),
            MergeChecklistItem(
                id: "mc_ready",
                label: "MVI approved for shipping",
                passed: canShip
            ),
        ]
    }
}

// MARK: - Error

private enum APIMVIError: LocalizedError {
    case missingWaveId

    var errorDescription: String? {
        switch self {
        case .missingWaveId: "Wave ID required to load MVI blackboard"
        }
    }
}

// MARK: - DTOs

private struct MVIWaveDetailDTO: Decodable {
    let wave: MVIWaveItemDTO?
    let mvis: [MVIMVIItemDTO]?
    let crows: [MVICrowDTO]?
    let human_tasks: [MVIHumanTaskDTO]?
}

private struct MVIWaveItemDTO: Decodable {
    let SK: String?
    let status: String?
    let human_directive: String?
}

private struct MVIMVIItemDTO: Decodable {
    let SK: String?
    let name: String?
    let status: String?
    let description: String?
    let tasks_done: FlexibleInt?
    let tasks_total: FlexibleInt?
    let can_ship: Bool?
    let cost: MVICostDTO?
}

private struct MVICostDTO: Decodable {
    let credits: FlexibleInt?
}

private struct MVICrowDTO: Decodable {
    let crow_id: String?
    let crow_type: String?
    let status: String?
    let behavior_state: String?
    let instructions: String?
    let outcome: MVICrowOutcomeDTO?
    let cost: MVICostDTO?
}

private struct MVICrowOutcomeDTO: Decodable {
    let tasks: [MVICrowTaskDTO]?
}

private struct MVICrowTaskDTO: Decodable {
    let name: String?
    let description: String?
}

private struct MVIHumanTaskDTO: Decodable {
    let id: String?
    let ask: String?
    let status: String?
}

private struct MVIEventsDTO: Decodable {
    let events: [MVIEventDTO]?
    let next_cursor: String?
}

private struct MVIEventDTO: Decodable {
    let event_type: String?
    let message: String?
    let color: String?
    let timestamp: String?
}
