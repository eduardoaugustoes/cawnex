import Foundation

struct AutopilotMessage: Identifiable {
    let id: String
    let role: String
    let content: String

    var isUser: Bool { role == "user" }
}

@Observable
final class AutopilotChatViewModel {
    let autopilotService: any AutopilotService

    var messages: [AutopilotMessage] = []
    var phase: String = "gathering"
    var plan: AutopilotPlan?
    var result: AutopilotResult?
    var isLoading: Bool = false
    var sessionId: String?
    var error: String?

    init(autopilotService: any AutopilotService) {
        self.autopilotService = autopilotService
    }

    func sendMessage(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        messages.append(AutopilotMessage(id: UUID().uuidString, role: "user", content: trimmed))
        isLoading = true
        error = nil

        do {
            let response = try await autopilotService.chat(
                sessionId: sessionId,
                message: trimmed,
                action: "message"
            )
            applyResponse(response)
        } catch {
            self.error = error.localizedDescription
        }

        isLoading = false
    }

    func launch() async -> AutopilotResult? {
        isLoading = true
        error = nil

        do {
            let response = try await autopilotService.chat(
                sessionId: sessionId,
                message: "",
                action: "launch"
            )
            applyResponse(response)
            isLoading = false
            return response.result
        } catch {
            self.error = error.localizedDescription
            isLoading = false
            return nil
        }
    }

    // MARK: - Private

    private func applyResponse(_ response: AutopilotResponse) {
        if let id = response.session_id { sessionId = id }
        if let p = response.phase { phase = p }
        if let plan = response.plan { self.plan = plan }
        if let result = response.result { self.result = result }
        if let reply = response.reply, !reply.isEmpty {
            messages.append(AutopilotMessage(id: UUID().uuidString, role: "assistant", content: reply))
        }
    }
}
