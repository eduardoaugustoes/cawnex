import SwiftUI

struct WaveReviewScreen: View {
    let projectId: String
    let waveId: String
    let sessionId: String
    @State var viewModel: WaveReviewViewModel
    @State private var showApproveConfirm = false
    @State private var showRejectSheet = false
    @State private var rejectReason = ""
    @State private var selectedAdvisor: AdvisorVote?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            content
        }
        .navigationTitle("Wave Review")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(false)
        .task {
            await viewModel.load(projectId: projectId, sessionId: sessionId)
        }
        .sheet(isPresented: $showApproveConfirm) {
            approveConfirmSheet
        }
        .sheet(isPresented: $showRejectSheet) {
            rejectSheet
        }
        .sheet(item: $selectedAdvisor) { vote in
            NavigationStack {
                InvestigationTraceScreen(vote: vote)
            }
        }
        .onChange(of: viewModel.state) { _, newState in
            if case .actionSucceeded = newState {
                dismiss()
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch viewModel.state {
        case .idle, .loading:
            ProgressView().padding(.top, 60)
        case .error(let message):
            errorView(message: message)
        case .loaded(let session):
            loadedView(session: session)
        case .actionPending(let action):
            ProgressView(
                "Submitting \(action == .approved ? "approve" : "reject")…"
            )
        case .actionSucceeded:
            ProgressView()
        case .actionFailed(_, let message):
            errorView(message: message)
                .overlay(alignment: .top) {
                    Text("Action failed: \(message)")
                        .padding()
                        .background(CawnexColors.destructive.opacity(0.13))
                }
        }
    }

    private func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(CawnexColors.warning)
            Text(message)
                .multilineTextAlignment(.center)
                .foregroundStyle(CawnexColors.cardForeground)
            Button("Retry") {
                Task {
                    await viewModel.load(projectId: projectId, sessionId: sessionId)
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    private func loadedView(session: CouncilSession) -> some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 16) {
                    if session.status == .pending || session.status == .running {
                        pollingBanner(session: session)
                    }
                    CouncilHeaderCard(session: session)
                    Text("ADVISORS")
                        .font(.system(size: 11, weight: .semibold))
                        .tracking(0.8)
                        .foregroundStyle(CawnexColors.mutedForeground)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(session.rounds.flatMap(\.votes)) { vote in
                        AdvisorCard(vote: vote) {
                            selectedAdvisor = vote
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 20)
            }
            actionBar(session: session)
        }
    }

    private func pollingBanner(session: CouncilSession) -> some View {
        let voted = session.rounds.first?.votes.count ?? 0
        return HStack(spacing: 8) {
            ProgressView().scaleEffect(0.8)
            Text("Council is still investigating — \(voted) of 6 advisors voted")
                .font(.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func actionBar(session: CouncilSession) -> some View {
        VStack(spacing: 10) {
            Button {
                showApproveConfirm = true
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark")
                    Text("Approve & merge wave")
                }
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(CawnexColors.success)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .accessibilityIdentifier("wave-review.approve")

            HStack(spacing: 10) {
                Button {
                    showRejectSheet = true
                } label: {
                    Label("Reject", systemImage: "xmark")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(CawnexColors.destructive)
                        .frame(maxWidth: .infinity)
                        .frame(height: 40)
                        .background(CawnexColors.card)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(CawnexColors.border, lineWidth: 1)
                        )
                }
                .accessibilityIdentifier("wave-review.reject")

                Button {
                    // Open in GitHub — out of scope for Layer B
                } label: {
                    Label("Open in GitHub", systemImage: "arrow.up.right.square")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                        .frame(maxWidth: .infinity)
                        .frame(height: 40)
                        .background(CawnexColors.card)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(CawnexColors.border, lineWidth: 1)
                        )
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 16)
        .padding(.bottom, 34)
        .background(CawnexColors.background)
    }

    private var approveConfirmSheet: some View {
        let session: CouncilSession? = {
            if case .loaded(let s) = viewModel.state { return s }
            return nil
        }()
        let advisorCount = session.map { $0.rounds.flatMap(\.votes).count } ?? 0
        return VStack(spacing: 20) {
            Text("Approve & merge wave")
                .font(.headline)
            Text(
                "Council voted \(session?.decision?.action.displayLabel ?? "—") with \(advisorCount) advisors."
            )
            .multilineTextAlignment(.center)
            .foregroundStyle(CawnexColors.cardForeground)
            Button("Approve & Merge") {
                Task {
                    await viewModel.approve(projectId: projectId, waveId: waveId)
                    showApproveConfirm = false
                }
            }
            .accessibilityIdentifier("wave-review.confirm-approve")
            .buttonStyle(.borderedProminent)
            Button("Cancel") { showApproveConfirm = false }
        }
        .padding(24)
        .presentationDetents([.medium])
    }

    private var rejectSheet: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Reject Wave")
                .font(.headline)
            Text("Reason (required — feeds back into the next planning pass)")
                .font(.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
            TextField(
                "Why is this wave not shippable?",
                text: $rejectReason,
                axis: .vertical
            )
            .lineLimit(3...6)
            .textFieldStyle(.roundedBorder)
            .accessibilityIdentifier("wave-review.reject-reason-field")
            HStack {
                Button("Cancel") {
                    showRejectSheet = false
                    rejectReason = ""
                }
                Spacer()
                Button("Reject Wave") {
                    Task {
                        await viewModel.reject(
                            projectId: projectId, waveId: waveId, reason: rejectReason
                        )
                        showRejectSheet = false
                    }
                }
                .accessibilityIdentifier("wave-review.confirm-reject")
                .disabled(
                    rejectReason.trimmingCharacters(in: .whitespaces).isEmpty
                )
                .buttonStyle(.borderedProminent)
                .tint(CawnexColors.destructive)
            }
        }
        .padding(24)
        .presentationDetents([.medium])
    }
}
