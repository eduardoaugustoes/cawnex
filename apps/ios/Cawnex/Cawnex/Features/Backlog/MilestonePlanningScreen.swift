import SwiftUI

struct MilestonePlanningScreen: View {
    let projectId: String
    let planningService: APIMilestonePlanningService
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
            milestonesPreviewSheet
        }
    }

    // MARK: - Scroll Content

    private var scrollContent: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                    navRow
                    chatArea
                    if planningService.hasMilestones && !isSaved {
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
                    Text("Plan Milestones")
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

    // MARK: - Action Buttons (shown after milestones are proposed)

    private var actionButtons: some View {
        VStack(spacing: CawnexSpacing.sm) {
            // Save Plan — primary action
            Button {
                Task { await savePlan() }
            } label: {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 16))
                    Text("Save Plan")
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
                // Preview
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

                // Refine
                Button {
                    messageText = "Let me refine these milestones."
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

    private var milestonesPreviewSheet: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                    Text("Milestone Plan")
                        .font(CawnexTypography.heading1)
                        .foregroundStyle(CawnexColors.cardForeground)

                    Text("\(planningService.plannedMilestones.count) milestones")
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)

                    Divider().overlay(accentColor)

                    ForEach(Array(planningService.plannedMilestones.enumerated()), id: \.offset) { index, milestone in
                        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                            Text("M\(index + 1): \(milestone.name)")
                                .font(CawnexTypography.bodyBold)
                                .foregroundStyle(CawnexColors.cardForeground)

                            Text(milestone.description)
                                .font(CawnexTypography.caption)
                                .foregroundStyle(CawnexColors.mutedForeground)

                            if !milestone.goals.isEmpty {
                                VStack(alignment: .leading, spacing: 6) {
                                    ForEach(milestone.goals) { goal in
                                        HStack(alignment: .top, spacing: 8) {
                                            Circle()
                                                .fill(accentColor)
                                                .frame(width: 6, height: 6)
                                                .padding(.top, 6)
                                            VStack(alignment: .leading, spacing: 2) {
                                                Text(goal.name)
                                                    .font(CawnexTypography.label)
                                                    .foregroundStyle(CawnexColors.cardForeground)
                                                Text(goal.description)
                                                    .font(CawnexTypography.footnote)
                                                    .foregroundStyle(CawnexColors.mutedForeground)
                                            }
                                        }
                                    }
                                }
                                .padding(.leading, CawnexSpacing.sm)
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
                id: UUID().uuidString,
                role: .ai,
                content: "Failed to load project context: \(error.localizedDescription)",
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
                id: UUID().uuidString,
                role: .ai,
                content: "Something went wrong: \(error.localizedDescription)",
                synthesizedSection: nil
            ))
        }

        isSending = false
    }

    private func savePlan() async {
        do {
            try await planningService.saveMilestones()
            isSaved = true
            // Auto-close after brief delay
            try? await Task.sleep(for: .seconds(1.5))
            onComplete()
        } catch {
            messages.append(ChatMessage(
                id: UUID().uuidString,
                role: .ai,
                content: "Failed to save: \(error.localizedDescription). Try again.",
                synthesizedSection: nil
            ))
        }
    }
}
