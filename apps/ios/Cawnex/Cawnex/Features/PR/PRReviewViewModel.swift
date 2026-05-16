import Foundation

enum PRActionResult: Equatable {
    case merged(sha: String)
    case rejected
}

@Observable
final class PRReviewViewModel {
    private let prService: any PRService
    private let actionsService: (any PRActionsService)?

    var state: ViewState<PRReviewDetail> = .idle
    var messageText: String = ""

    // PR-action UI state
    var isMerging: Bool = false
    var isRejecting: Bool = false
    var actionError: String?
    var showRejectSheet: Bool = false
    var showMergeConfirmSheet: Bool = false
    var rejectReason: String = ""
    var lastActionResult: PRActionResult?

    // Parsed at load time from the composite prId `wave_id:mvi_id:pr_number`
    private var waveId: String = ""
    private var mviId: String = ""
    private var prNumber: Int = 0
    private var projectId: String = ""

    var detail: PRReviewDetail? {
        if case .loaded(let d) = state { return d }
        return nil
    }

    /// True when the PR is in a state where Approve & Merge / Reject make sense.
    /// Once a PR is `merged` (terminal), both actions are hidden.
    var canMutate: Bool {
        detail?.status == .ready
    }

    init(prService: any PRService, actionsService: (any PRActionsService)? = nil) {
        self.prService = prService
        self.actionsService = actionsService
    }

    func load(projectId: String, prId: String) async {
        state = .loading
        self.projectId = projectId
        // Parse composite ID up-front so the action methods don't need the
        // raw prId on every call.
        let parts = prId.split(separator: ":")
        if parts.count == 3 {
            self.waveId = String(parts[0])
            self.mviId = String(parts[1])
            self.prNumber = Int(parts[2]) ?? 0
        }
        do {
            let loaded = try await prService.getPRReview(projectId: projectId, prId: prId)
            state = .loaded(loaded)
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    // MARK: - Actions

    @MainActor
    func approveAndMerge() async {
        guard let actionsService else {
            actionError = "Actions disabled in this build (no APIClient)."
            return
        }
        actionError = nil
        isMerging = true
        defer { isMerging = false }
        do {
            let result = try await actionsService.mergePR(
                projectId: projectId, waveId: waveId, mviId: mviId, prNumber: prNumber
            )
            lastActionResult = .merged(sha: result.sha)
            showMergeConfirmSheet = false
        } catch {
            actionError = "Merge failed: \(error.localizedDescription)"
        }
    }

    @MainActor
    func rejectPR() async {
        let trimmed = rejectReason.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else {
            actionError = "Please provide a reason for rejecting."
            return
        }
        guard let actionsService else {
            actionError = "Actions disabled in this build (no APIClient)."
            return
        }
        actionError = nil
        isRejecting = true
        defer { isRejecting = false }
        do {
            _ = try await actionsService.rejectPR(
                projectId: projectId, waveId: waveId, mviId: mviId, prNumber: prNumber,
                reason: trimmed
            )
            lastActionResult = .rejected
            showRejectSheet = false
            rejectReason = ""
        } catch {
            actionError = "Reject failed: \(error.localizedDescription)"
        }
    }
}
