import SwiftUI

struct MVIPlanningScreen: View {
    let projectId: String
    let goalId: String
    let goalName: String
    let planningService: APIMVIPlanningService
    var onCancel: () -> Void = {}
    var onComplete: () -> Void = {}

    @State private var messages: [ChatMessage] = []
    @State private var messageText: String = ""
    @State private var isSending: Bool = false
    @State private var isLoading: Bool = true
    @State private var isShowingPreview: Bool = false
    @State private var isSaved: Bool = false

    private let accentColor = CawnexColors.primary

    var body: some View {
        VStack(spacing: 0) {
            scrollContent
            inputBar
        }
        .background(CawnexColors.background)
        .task { await loadContext() }
        .sheet(isPresented: $isShowingPreview) {
            mvisPreviewSheet
        }
    }

    // MARK: - Scroll Content

    private var scrollContent: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                    navRow
                    chatArea
                    if planningService.hasMVIs && !isSaved {
                        actionButtons
                    }
                }
                .padding(.top, CawnexSpacing.sm)
                .padding(.horizontal, CawnexSpacing.xl)
                .padding(.bottom, CawnexSpacing.xl)
                .id("bottom-anchor")
            }
            .onChange(of: messages.count) {
                withAnimation {
                    proxy.scrollTo("bottom-anchor", anchor: .bottom)
                }
            }
        }
    }

    // MARK: - Nav Row

    private var navRow: some View {
        HStack {
            Button(action: onCancel) {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text("Plan MVIs")
                        .font(CawnexTypography.heading3)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
            }
            .buttonStyle(.plain)

            Spacer()

            if isSaved {
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 14))
                    Text("Saved")
                        .font(CawnexTypography.label)
                }
                .foregroundStyle(CawnexColors.success)
            }
        }
    }

    // MARK: - Chat Area

    @ViewBuilder
    private var chatArea: some View {
        if isLoading {
            HStack {
                Spacer()
                ProgressView()
                    .tint(accentColor)
                Spacer()
            }
            .padding(.vertical, CawnexSpacing.xxl)
        } else {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                ForEach(messages) { message in
                    ChatMessageBubble(message: message, accentColor: accentColor)
                }

                if isSending {
                    TypingIndicator(accentColor: accentColor)
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                }
            }
            .animation(.easeInOut(duration: 0.2), value: isSending)
        }
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        VStack(spacing: CawnexSpacing.sm) {
            Button {
                Task { await saveMVIs() }
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 16))
                    Text("Save MVIs")
                        .font(CawnexTypography.bodyBold)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(CawnexColors.success)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .buttonStyle(.plain)

            HStack(spacing: CawnexSpacing.sm) {
                Button(action: { isShowingPreview = true }) {
                    HStack(spacing: 6) {
                        Image(systemName: "list.bullet.clipboard")
                            .font(.system(size: 14))
                        Text("Preview")
                            .font(CawnexTypography.label)
                    }
                    .foregroundStyle(accentColor)
                    .frame(maxWidth: .infinity)
                    .frame(height: 40)
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.sm)
                            .stroke(accentColor, lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)

                Button {
                    messageText = "Let me refine these MVIs."
                    Task { await sendMessage() }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "pencil")
                            .font(.system(size: 14))
                        Text("Refine")
                            .font(CawnexTypography.label)
                    }
                    .foregroundStyle(CawnexColors.warning)
                    .frame(maxWidth: .infinity)
                    .frame(height: 40)
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.sm)
                            .stroke(CawnexColors.warning, lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)
            }

            Text("Or type specific changes below")
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        ChatInputBar(
            accentColor: accentColor,
            text: $messageText,
            onSend: {
                Task { await sendMessage() }
            },
            isSending: isSending
        )
    }

    // MARK: - Preview Sheet

    private var mvisPreviewSheet: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                    Text("MVIs for \(goalName)")
                        .font(CawnexTypography.heading2)
                        .foregroundStyle(CawnexColors.cardForeground)

                    let totalHours = planningService.proposedMVIs.reduce(0.0) { $0 + $1.estimated_hours }
                    Text("\(planningService.proposedMVIs.count) MVIs · ~\(Int(totalHours))h estimated")
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)

                    Divider().overlay(accentColor)

                    ForEach(Array(planningService.proposedMVIs.enumerated()), id: \.offset) { index, mvi in
                        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                            HStack {
                                Text("MVI \(index + 1): \(mvi.name)")
                                    .font(CawnexTypography.bodyBold)
                                    .foregroundStyle(CawnexColors.cardForeground)
                                Spacer()
                                Text("~\(Int(mvi.estimated_hours))h")
                                    .font(CawnexTypography.label)
                                    .foregroundStyle(CawnexColors.warning)
                            }

                            Text(mvi.description)
                                .font(CawnexTypography.caption)
                                .foregroundStyle(CawnexColors.mutedForeground)

                            if !mvi.acceptance_criteria.isEmpty {
                                Text("Acceptance: \(mvi.acceptance_criteria)")
                                    .font(CawnexTypography.footnote)
                                    .foregroundStyle(CawnexColors.success)
                            }
                        }
                        .padding(CawnexSpacing.md)
                        .background(CawnexColors.card)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    }
                }
                .padding(CawnexSpacing.xl)
            }
            .background(CawnexColors.background)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { isShowingPreview = false }
                }
            }
        }
    }

    // MARK: - Actions

    private func loadContext() async {
        isLoading = true
        do {
            let firstMessage = try await planningService.loadContext()
            messages = [firstMessage]
        } catch {
            messages = [ChatMessage(
                id: UUID().uuidString, role: .ai,
                content: "Failed to load goal context: \(error.localizedDescription)",
                synthesizedSection: nil
            )]
        }
        isLoading = false
    }

    private func sendMessage() async {
        let trimmed = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isSending else { return }

        let userMsg = ChatMessage(id: UUID().uuidString, role: .user, content: trimmed, synthesizedSection: nil)
        messages.append(userMsg)
        messageText = ""
        isSending = true

        do {
            let response = try await planningService.sendMessage(trimmed)
            messages.append(response)
        } catch {
            messages.append(ChatMessage(
                id: UUID().uuidString, role: .ai,
                content: "Something went wrong: \(error.localizedDescription)",
                synthesizedSection: nil
            ))
        }

        isSending = false
    }

    private func saveMVIs() async {
        do {
            try await planningService.saveMVIs()
            isSaved = true
            try? await Task.sleep(for: .seconds(1.5))
            onComplete()
        } catch {
            messages.append(ChatMessage(
                id: UUID().uuidString, role: .ai,
                content: "Failed to save: \(error.localizedDescription)",
                synthesizedSection: nil
            ))
        }
    }
}
