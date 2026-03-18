import Foundation

final class APIWaveService: WaveService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func listWaves(projectId: String) async throws -> [WaveSummary] {
        let dto: WaveListDTO = try await client.get("/projects/\(projectId)/waves")
        return dto.waves.map { $0.toDomain() }
    }

    func getWave(projectId: String, waveId: String) async throws -> WaveDetail {
        let dto: WaveDetailDTO = try await client.get("/projects/\(projectId)/waves/\(waveId)")
        return dto.toDomain()
    }

    func createWave(projectId: String, directive: String, goalId: String, mviIds: [String]) async throws -> CreateWaveResponse {
        struct Body: Encodable {
            let directive: String
            let goal_id: String
            let mvi_ids: [String]
        }
        let dto: CreateWaveDTO = try await client.post(
            "/projects/\(projectId)/waves",
            body: Body(directive: directive, goal_id: goalId, mvi_ids: mviIds)
        )
        return CreateWaveResponse(
            waveId: dto.wave_id,
            status: dto.status,
            mviIds: dto.mvis?.map { $0.id } ?? []
        )
    }

    func activateWave(projectId: String, waveId: String) async throws -> WaveSummary {
        struct Empty: Encodable {}
        let dto: ActivateDTO = try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/activate",
            body: Empty()
        )
        return WaveSummary(
            id: dto.wave_id, status: WaveStatus(rawValue: dto.status) ?? .executing,
            directive: "", progress: WaveProgress(mvisTotal: 0, mvisShipped: 0, tasksDone: 0, tasksTotal: 0),
            budget: WaveBudget(spent: 0, limit: 0), createdAt: ""
        )
    }

    func pauseWave(projectId: String, waveId: String) async throws -> WaveSummary {
        struct Empty: Encodable {}
        let dto: StatusDTO = try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/pause",
            body: Empty()
        )
        return WaveSummary(
            id: dto.wave_id, status: WaveStatus(rawValue: dto.status) ?? .paused,
            directive: "", progress: WaveProgress(mvisTotal: 0, mvisShipped: 0, tasksDone: 0, tasksTotal: 0),
            budget: WaveBudget(spent: 0, limit: 0), createdAt: ""
        )
    }

    func cancelWave(projectId: String, waveId: String) async throws -> WaveSummary {
        struct Empty: Encodable {}
        let dto: StatusDTO = try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/cancel",
            body: Empty()
        )
        return WaveSummary(
            id: dto.wave_id, status: WaveStatus(rawValue: dto.status) ?? .cancelled,
            directive: "", progress: WaveProgress(mvisTotal: 0, mvisShipped: 0, tasksDone: 0, tasksTotal: 0),
            budget: WaveBudget(spent: 0, limit: 0), createdAt: ""
        )
    }

    func getEvents(projectId: String, waveId: String, after: String?) async throws -> WaveEventsPage {
        var path = "/projects/\(projectId)/waves/\(waveId)/events?limit=50"
        if let after { path += "&after=\(after)" }
        let dto: EventsDTO = try await client.get(path)
        return WaveEventsPage(
            events: dto.events.enumerated().map { (i, e) in e.toDomain(index: i) },
            nextCursor: dto.next_cursor
        )
    }

    func shipMVI(projectId: String, waveId: String, mviId: String) async throws -> String {
        struct Empty: Encodable {}
        let dto: ShipDTO = try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/mvis/\(mviId)/ship",
            body: Empty()
        )
        return dto.status
    }
}

// MARK: - DTOs

private struct WaveListDTO: Decodable {
    let waves: [WaveSummaryDTO]
    let count: Int
}

private struct WaveSummaryDTO: Decodable {
    let wave_id: String
    let status: String
    let directive: String
    let progress: ProgressDTO?
    let budget: BudgetDTO?
    let created_at: String?

    func toDomain() -> WaveSummary {
        WaveSummary(
            id: wave_id,
            status: WaveStatus(rawValue: status) ?? .planning,
            directive: directive,
            progress: progress?.toDomain() ?? WaveProgress(mvisTotal: 0, mvisShipped: 0, tasksDone: 0, tasksTotal: 0),
            budget: budget?.toDomain() ?? WaveBudget(spent: 0, limit: 0),
            createdAt: created_at ?? ""
        )
    }
}

private struct ProgressDTO: Decodable {
    let mvis_total: FlexibleInt?
    let mvis_shipped: FlexibleInt?
    let tasks_done: FlexibleInt?
    let tasks_total: FlexibleInt?

    func toDomain() -> WaveProgress {
        WaveProgress(
            mvisTotal: mvis_total?.value ?? 0,
            mvisShipped: mvis_shipped?.value ?? 0,
            tasksDone: tasks_done?.value ?? 0,
            tasksTotal: tasks_total?.value ?? 0
        )
    }
}

private struct BudgetDTO: Decodable {
    let spent: FlexibleInt?
    let limit: FlexibleInt?

    func toDomain() -> WaveBudget {
        WaveBudget(spent: spent?.value ?? 0, limit: limit?.value ?? 0)
    }
}

private struct WaveDetailDTO: Decodable {
    let wave: WaveItemDTO?
    let mvis: [MVIItemDTO]?
    let human_tasks: [HumanTaskItemDTO]?

    func toDomain() -> WaveDetail {
        let waveSummary = wave?.toDomain() ?? WaveSummary(
            id: "", status: .planning, directive: "",
            progress: WaveProgress(mvisTotal: 0, mvisShipped: 0, tasksDone: 0, tasksTotal: 0),
            budget: WaveBudget(spent: 0, limit: 0), createdAt: ""
        )
        return WaveDetail(
            wave: waveSummary,
            mvis: (mvis ?? []).map { $0.toDomain() },
            humanTasks: (human_tasks ?? []).map { $0.toDomain() }
        )
    }
}

private struct WaveItemDTO: Decodable {
    let SK: String?
    let status: String?
    let human_directive: String?
    let progress: ProgressDTO?
    let budget: BudgetDTO?
    let created_at: String?

    func toDomain() -> WaveSummary {
        let sk = SK ?? ""
        let waveId = sk.hasPrefix("S#") ? String(sk.dropFirst(2)) : sk
        return WaveSummary(
            id: waveId,
            status: WaveStatus(rawValue: status ?? "") ?? .planning,
            directive: human_directive ?? "",
            progress: progress?.toDomain() ?? WaveProgress(mvisTotal: 0, mvisShipped: 0, tasksDone: 0, tasksTotal: 0),
            budget: budget?.toDomain() ?? WaveBudget(spent: 0, limit: 0),
            createdAt: created_at ?? ""
        )
    }
}

private struct MVIItemDTO: Decodable {
    let SK: String?
    let name: String?
    let status: String?
    let description: String?
    let tasks_done: FlexibleInt?
    let tasks_total: FlexibleInt?
    let can_ship: Bool?
    let cost: CostDTO?

    func toDomain() -> WaveMVI {
        let sk = SK ?? ""
        let parts = sk.split(separator: "#")
        let mviId = parts.count >= 3 ? String(parts[2].dropFirst()) : sk
        return WaveMVI(
            id: mviId,
            name: name ?? "",
            status: status ?? "draft",
            description: description ?? "",
            tasksDone: tasks_done?.value ?? 0,
            tasksTotal: tasks_total?.value ?? 0,
            canShip: can_ship ?? false,
            cost: cost?.credits?.value ?? 0
        )
    }
}

private struct CostDTO: Decodable {
    let credits: FlexibleInt?
}

private struct HumanTaskItemDTO: Decodable {
    let id: String?
    let ask: String?
    let human_task_subtype: String?
    let status: String?
    let deadline_hint: String?
    let created_at: String?

    func toDomain() -> HumanTask {
        HumanTask(
            id: id ?? "",
            ask: ask ?? "",
            subtype: human_task_subtype ?? "",
            status: HumanTaskStatus(rawValue: status ?? "") ?? .pending,
            deadlineHint: deadline_hint ?? "",
            createdAt: created_at ?? ""
        )
    }
}

private struct CreateWaveDTO: Decodable {
    let wave_id: String
    let status: String
    let mvis: [CreateMVIDTO]?
}

private struct CreateMVIDTO: Decodable {
    let id: String
}

private struct ActivateDTO: Decodable {
    let wave_id: String
    let status: String
    let mvis_queued: Int?
}

private struct StatusDTO: Decodable {
    let wave_id: String
    let status: String
}

private struct EventsDTO: Decodable {
    let events: [EventItemDTO]
    let next_cursor: String?
}

private struct EventItemDTO: Decodable {
    let event_type: String
    let message: String
    let color: String
    let timestamp: String
    let extra: [String: String]?

    func toDomain(index: Int) -> WaveEvent {
        WaveEvent(
            id: "\(timestamp)_\(index)",
            eventType: event_type,
            message: message,
            color: color,
            timestamp: timestamp,
            extra: extra ?? [:]
        )
    }
}

private struct ShipDTO: Decodable {
    let status: String
}
