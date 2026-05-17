import Foundation
import SwiftUI

@Observable
final class HumanTaskViewModel {
    let humanTaskService: any HumanTaskService
    let projectId: String

    var listState: ViewState<HumanTaskListResponse> = .idle
    var detailState: ViewState<HumanTaskDetail> = .idle
    var fieldValues: [String: String] = [:]
    var steerText: String = ""
    var isSubmitting = false
    var submitError: String?

    var pendingCount: Int {
        if case .loaded(let response) = listState {
            return response.pendingCount
        }
        return 0
    }

    var taskGroups: [String: [HumanTask]] {
        if case .loaded(let response) = listState {
            return response.tasks
        }
        return [:]
    }

    var detail: HumanTaskDetail? {
        if case .loaded(let d) = detailState {
            return d
        }
        return nil
    }

    init(humanTaskService: any HumanTaskService, projectId: String) {
        self.humanTaskService = humanTaskService
        self.projectId = projectId
    }

    func loadList() async {
        listState = .loading
        do {
            let response = try await humanTaskService.listHumanTasks(projectId: projectId)
            listState = .loaded(response)
        } catch {
            listState = .error(error.localizedDescription)
        }
    }

    func loadDetail(humanTaskId: String) async {
        detailState = .loading
        do {
            let detail = try await humanTaskService.getDetail(
                projectId: projectId, humanTaskId: humanTaskId
            )
            detailState = .loaded(detail)
            // Pre-populate field values if there's an existing response
            if let existingResponse = detail.response {
                fieldValues = existingResponse
            }
        } catch {
            detailState = .error(error.localizedDescription)
        }
    }

    func submit(humanTaskId: String) async {
        isSubmitting = true
        submitError = nil

        let hasResponse = !fieldValues.values.allSatisfy { $0.isEmpty }
        let hasSteer = !steerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty

        guard hasResponse || hasSteer else {
            submitError = "Please provide input or guidance"
            isSubmitting = false
            return
        }

        do {
            // Coerce each field's String-form value into the type the backend expects.
            // Without this, boolean toggles arrive as "true"/"false" strings and fail
            // the API's type validation with `type_mismatch`.
            let typedResponse: [String: Any]? = hasResponse
                ? coerceFieldValues() : nil
            let response: [String: Any]? = typedResponse
            let steer: String? = hasSteer ? steerText : nil
            let status = try await humanTaskService.respond(
                projectId: projectId,
                humanTaskId: humanTaskId,
                response: response,
                steer: steer
            )
            // Reload list after successful submit
            await loadList()
            isSubmitting = false
        } catch {
            submitError = error.localizedDescription
            isSubmitting = false
        }
    }

    /// Convert each fieldValues string to the JSON type the backend expects,
    /// based on the field's declared InputFieldType. Toggles arrive as
    /// "true"/"false" strings from the UI; the backend wants real booleans.
    /// Number fields likewise need to land as Int/Double.
    private func coerceFieldValues() -> [String: Any] {
        guard case .loaded(let d) = detailState else {
            return fieldValues  // fall back to raw strings
        }
        var typed: [String: Any] = [:]
        let typeByFieldId = Dictionary(
            uniqueKeysWithValues: d.inputSchema.map { ($0.id, $0.type) }
        )
        for (id, raw) in fieldValues {
            let fieldType = typeByFieldId[id] ?? .string
            switch fieldType {
            case .boolean:
                typed[id] = (raw == "true")
            case .number:
                if let intVal = Int(raw) {
                    typed[id] = intVal
                } else if let dblVal = Double(raw) {
                    typed[id] = dblVal
                } else {
                    typed[id] = raw
                }
            default:
                typed[id] = raw
            }
        }
        return typed
    }
}
