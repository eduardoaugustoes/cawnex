import Foundation

protocol HumanTaskService {
    func listHumanTasks(projectId: String) async throws -> HumanTaskListResponse
    func getDetail(projectId: String, humanTaskId: String) async throws -> HumanTaskDetail
    func respond(projectId: String, humanTaskId: String, response: [String: Any]?, steer: String?) async throws -> String
    func requestUploadURL(projectId: String, humanTaskId: String, field: String, filename: String, contentType: String) async throws -> UploadURLResponse
}

final class InMemoryHumanTaskService: HumanTaskService {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
    }

    func listHumanTasks(projectId: String) async throws -> HumanTaskListResponse {
        let tasks: [String: [HumanTask]] = [
            "notified": [
                HumanTask(
                    id: "ht_esim",
                    ask: "Purchase an e-SIM number for WhatsApp Business",
                    subtype: "physical_action",
                    status: .notified,
                    deadlineHint: "2026-03-21",
                    createdAt: "2026-03-16T10:00:00Z"
                ),
                HumanTask(
                    id: "ht_token",
                    ask: "Provide WhatsApp Business API token",
                    subtype: "provide_secret",
                    status: .notified,
                    deadlineHint: "",
                    createdAt: "2026-03-16T10:00:00Z"
                ),
            ],
            "completed": [
                HumanTask(
                    id: "ht_logo",
                    ask: "Upload company logo",
                    subtype: "upload_asset",
                    status: .completed,
                    deadlineHint: "",
                    createdAt: "2026-03-15T10:00:00Z"
                ),
            ],
        ]
        return HumanTaskListResponse(tasks: tasks, pendingCount: 2, totalCount: 3)
    }

    func getDetail(projectId: String, humanTaskId: String) async throws -> HumanTaskDetail {
        HumanTaskDetail(
            id: "ht_esim",
            ask: "Purchase an e-SIM number for WhatsApp Business",
            instructions: "Buy a dedicated phone number (e-SIM or physical SIM) that will be used exclusively for the WhatsApp Business Account. This number must be able to receive SMS for verification.",
            subtype: "physical_action",
            status: .notified,
            inputSchema: [
                InputField(
                    id: "phone_number",
                    type: .string,
                    label: "Phone number (with country code)",
                    placeholder: "+55 11 99999-9999",
                    description: "E.164 format phone number",
                    required: true,
                    pattern: "^\\+[1-9]\\d{1,14}$",
                    patternHint: "E.164 format: +55 11 99999-9999",
                    minLength: nil,
                    maxLength: nil,
                    accept: [],
                    maxSizeMB: nil,
                    options: [],
                    min: nil,
                    max: nil
                ),
                InputField(
                    id: "carrier",
                    type: .string,
                    label: "Carrier name",
                    placeholder: "Claro, Vivo, TIM...",
                    description: "",
                    required: false,
                    pattern: nil,
                    patternHint: nil,
                    minLength: nil,
                    maxLength: nil,
                    accept: [],
                    maxSizeMB: nil,
                    options: [],
                    min: nil,
                    max: nil
                ),
            ],
            hasVerification: false,
            blocks: ["cr_impl_01"],
            response: nil,
            steer: nil,
            deadlineHint: "2026-03-21",
            estimatedHumanHours: 1,
            createdAt: "2026-03-16T10:00:00Z",
            completedAt: ""
        )
    }

    func respond(projectId: String, humanTaskId: String, response: [String: Any]?, steer: String?) async throws -> String {
        "completed"
    }

    func requestUploadURL(projectId: String, humanTaskId: String, field: String, filename: String, contentType: String) async throws -> UploadURLResponse {
        UploadURLResponse(
            uploadUrl: "https://s3.example.com/presigned",
            assetKey: "T/t1/P/p1/assets/\(humanTaskId)/\(filename)",
            expiresIn: 300
        )
    }
}
