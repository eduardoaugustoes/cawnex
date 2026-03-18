import Foundation

final class APIHumanTaskService: HumanTaskService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func listHumanTasks(projectId: String) async throws -> HumanTaskListResponse {
        let dto: HumanTaskListDTO = try await client.get(
            "/projects/\(projectId)/human-tasks"
        )
        return dto.toDomain()
    }

    func getDetail(projectId: String, humanTaskId: String) async throws -> HumanTaskDetail {
        let dto: HumanTaskDetailDTO = try await client.get(
            "/projects/\(projectId)/human-tasks/\(humanTaskId)"
        )
        return dto.toDomain()
    }

    func respond(projectId: String, humanTaskId: String, response: [String: Any]?, steer: String?) async throws -> String {
        struct RespondBody: Encodable {
            let response: [String: String]?
            let steer: String?
        }

        let responseDict = response as? [String: String]
        let body = RespondBody(response: responseDict, steer: steer)
        let result: RespondResponseDTO = try await client.post(
            "/projects/\(projectId)/human-tasks/\(humanTaskId)/respond",
            body: body
        )
        return result.status
    }

    func requestUploadURL(projectId: String, humanTaskId: String, field: String, filename: String, contentType: String) async throws -> UploadURLResponse {
        struct UploadBody: Encodable {
            let field: String
            let filename: String
            let content_type: String
        }

        let body = UploadBody(field: field, filename: filename, content_type: contentType)
        let dto: UploadURLDTO = try await client.post(
            "/projects/\(projectId)/human-tasks/\(humanTaskId)/upload-url",
            body: body
        )
        return UploadURLResponse(
            uploadUrl: dto.upload_url,
            assetKey: dto.asset_key,
            expiresIn: dto.expires_in
        )
    }
}

// MARK: - DTOs

private struct HumanTaskListDTO: Decodable {
    let tasks: [String: [HumanTaskDTO]]
    let pending_count: Int
    let total_count: Int

    func toDomain() -> HumanTaskListResponse {
        var domainTasks: [String: [HumanTask]] = [:]
        for (key, dtos) in tasks {
            domainTasks[key] = dtos.map { $0.toDomain() }
        }
        return HumanTaskListResponse(
            tasks: domainTasks,
            pendingCount: pending_count,
            totalCount: total_count
        )
    }
}

private struct HumanTaskDTO: Decodable {
    let id: String
    let ask: String
    let human_task_subtype: String
    let status: String
    let deadline_hint: String?
    let created_at: String?

    func toDomain() -> HumanTask {
        HumanTask(
            id: id,
            ask: ask,
            subtype: human_task_subtype,
            status: HumanTaskStatus(rawValue: status) ?? .pending,
            deadlineHint: deadline_hint ?? "",
            createdAt: created_at ?? ""
        )
    }
}

private struct HumanTaskDetailDTO: Decodable {
    let id: String
    let ask: String
    let instructions: String
    let human_task_subtype: String
    let status: String
    let input_schema: [String: InputFieldDTO]?
    let verification: VerificationDTO?
    let blocks: [String]?
    let response: [String: String]?
    let steer: String?
    let deadline_hint: String?
    let estimated_human_hours: FlexibleDouble?
    let created_at: String?
    let completed_at: String?

    func toDomain() -> HumanTaskDetail {
        let fields = (input_schema ?? [:]).map { (key, dto) in
            dto.toDomain(id: key)
        }.sorted { $0.id < $1.id }

        return HumanTaskDetail(
            id: id,
            ask: ask,
            instructions: instructions,
            subtype: human_task_subtype,
            status: HumanTaskStatus(rawValue: status) ?? .pending,
            inputSchema: fields,
            hasVerification: verification != nil,
            blocks: blocks ?? [],
            response: response,
            steer: steer,
            deadlineHint: deadline_hint ?? "",
            estimatedHumanHours: estimated_human_hours?.value ?? 0,
            createdAt: created_at ?? "",
            completedAt: completed_at ?? ""
        )
    }
}

private struct InputFieldDTO: Decodable {
    let type: String
    let label: String?
    let placeholder: String?
    let description: String?
    let required: Bool?
    let pattern: String?
    let pattern_hint: String?
    let minLength: Int?
    let maxLength: Int?
    let accept: [String]?
    let maxSizeMB: Int?
    let options: [OptionDTO]?
    let min: Double?
    let max: Double?

    func toDomain(id: String) -> InputField {
        InputField(
            id: id,
            type: InputFieldType(rawValue: type) ?? .string,
            label: label ?? id,
            placeholder: placeholder ?? "",
            description: description ?? "",
            required: self.required ?? false,
            pattern: pattern,
            patternHint: pattern_hint,
            minLength: minLength,
            maxLength: maxLength,
            accept: accept ?? [],
            maxSizeMB: maxSizeMB,
            options: (options ?? []).map { InputField.EnumOption(value: $0.value, label: $0.label ?? $0.value) },
            min: min,
            max: max
        )
    }
}

private struct OptionDTO: Decodable {
    let value: String
    let label: String?
}

private struct VerificationDTO: Decodable {
    let type: String?
    let instructions: String?
}

private struct RespondResponseDTO: Decodable {
    let status: String
    let human_task_id: String?
}

private struct UploadURLDTO: Decodable {
    let upload_url: String
    let asset_key: String
    let expires_in: Int
}
