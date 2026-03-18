import SwiftUI

struct AutopilotChatScreen: View {
    @State var viewModel: AutopilotChatViewModel
    var speechService: SpeechService
    var onCancel: () -> Void = {}
    var onPlanReview: (AutopilotPlan, String) -> Void = { _, _ in }

    @State private var inputText: String = ""
    @State private var isRecording: Bool = false
    @FocusState private var inputFocused: Bool
    @State private var initialMessage: String?

    init(
        viewModel: AutopilotChatViewModel,
        speechService: SpeechService,
        initialMessage: String? = nil,
        onCancel: @escaping () -> Void = {},
        onPlanReview: @escaping (AutopilotPlan, String) -> Void = { _, _ in }
    ) {
        self.viewModel = viewModel
        self.speechService = speechService
        self._initialMessage = State(initialValue: initialMessage)
        self.onCancel = onCancel
        self.onPlanReview = onPlanReview
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            CawnexColors.background.ignoresSafeArea()

            VStack(spacing: 0) {
                navRow
                    .padding(.horizontal, CawnexSpacing.xl)
                    .padding(.top, CawnexSpacing.lg)
                    .padding(.bottom, CawnexSpacing.md)

                Divider()
                    .background(CawnexColors.border)

                messageList

                inputBar
            }

            if isRecording {
                voiceOverlay
            }
        }
        .task {
            if let msg = initialMessage {
                initialMessage = nil
                inputText = msg
                await send()
            } else {
                inputFocused = true
            }
        }
    }

    // MARK: - Nav Row

    private var navRow: some View {
        HStack {
            Button("Cancel", action: onCancel)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)

            Spacer()

            Text("Autopilot")
                .font(CawnexTypography.heading3)
                .foregroundStyle(CawnexColors.cardForeground)

            Spacer()

            Text("Cancel")
                .font(CawnexTypography.body)
                .foregroundStyle(.clear)
        }
    }

    // MARK: - Message List

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                    if viewModel.messages.isEmpty {
                        monarchWelcomeBubble
                    }

                    ForEach(viewModel.messages) { (message: AutopilotMessage) in
                        if message.isUser {
                            userBubble(message.content)
                        } else {
                            aiBubble(message.content)
                        }
                    }

                    if viewModel.isLoading {
                        loadingBubble
                    }

                    Color.clear
                        .frame(height: 1)
                        .id("bottom")
                }
                .padding(.horizontal, CawnexSpacing.xl)
                .padding(.top, CawnexSpacing.lg)
                .padding(.bottom, 100)
            }
            .onChange(of: viewModel.messages.count) {
                withAnimation { proxy.scrollTo("bottom") }
            }
            .onChange(of: viewModel.isLoading) {
                withAnimation { proxy.scrollTo("bottom") }
            }
        }
    }

    private var monarchWelcomeBubble: some View {
        aiBubble("Hi! I'm Monarch. Tell me what you want to build — one sentence is enough. I'll ask a few quick questions, then generate a full project plan ready to launch.")
    }

    private func aiBubble(_ content: String) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            HStack(spacing: CawnexSpacing.xs) {
                Image(systemName: "bird")
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(CawnexColors.primary)
                Text("Monarch")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.primary)
            }

            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text(content)
                    .font(CawnexTypography.body)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .lineSpacing(4)
                    .frame(maxWidth: 310, alignment: .leading)

                if viewModel.phase == "proposed", let plan = viewModel.plan {
                    reviewPlanButton(plan)
                }
            }
            .padding(CawnexSpacing.md)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func reviewPlanButton(_ plan: AutopilotPlan) -> some View {
        Button {
            onPlanReview(plan, viewModel.sessionId ?? "")
        } label: {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "rocket")
                    .font(.system(size: 14, weight: .semibold))
                Text("Review Plan")
                    .font(CawnexTypography.bodyBold)
            }
            .foregroundStyle(CawnexColors.primaryForeground)
            .frame(maxWidth: .infinity)
            .padding(.vertical, CawnexSpacing.sm)
            .background(CawnexColors.primary)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .buttonStyle(.plain)
        .padding(.top, CawnexSpacing.xs)
    }

    private func userBubble(_ content: String) -> some View {
        Text(content)
            .font(CawnexTypography.body)
            .foregroundStyle(CawnexColors.primaryForeground)
            .lineSpacing(4)
            .padding(CawnexSpacing.md)
            .frame(maxWidth: 280, alignment: .leading)
            .background(CawnexColors.primary)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .frame(maxWidth: .infinity, alignment: .trailing)
    }

    private var loadingBubble: some View {
        HStack(spacing: CawnexSpacing.xs) {
            Image(systemName: "bird")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(CawnexColors.primary)
            ProgressView()
                .tint(CawnexColors.primary)
                .scaleEffect(0.8)
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: CawnexSpacing.sm) {
            Image(systemName: "sparkles")
                .font(.system(size: 16))
                .foregroundStyle(CawnexColors.mutedForeground)

            TextField("Ask anything...", text: $inputText, axis: .vertical)
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.cardForeground)
                .tint(CawnexColors.primaryLight)
                .lineLimit(1...4)
                .focused($inputFocused)
                .submitLabel(.send)
                .onSubmit { Task { await send() } }

            Button {
                if isRecording {
                    let text = speechService.stopRecording()
                    isRecording = false
                    if !text.isEmpty { inputText = text }
                } else {
                    isRecording = true
                }
            } label: {
                Image(systemName: isRecording ? "mic.fill" : "mic")
                    .font(.system(size: 18))
                    .foregroundStyle(isRecording ? CawnexColors.primary : CawnexColors.mutedForeground)
            }
            .disabled(!speechService.isAvailable)

            Button {
                Task { await send() }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 28))
                    .foregroundStyle(inputText.isEmpty ? CawnexColors.mutedForeground : CawnexColors.primary)
            }
            .disabled(inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isLoading)
        }
        .padding(CawnexSpacing.md)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.lg)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
        .padding(.horizontal, CawnexSpacing.xl)
        .padding(.bottom, CawnexSpacing.lg)
    }

    // MARK: - Voice Overlay

    private var voiceOverlay: some View {
        ZStack(alignment: .bottom) {
            Color.black.opacity(0.9)
                .ignoresSafeArea()
                .onTapGesture {
                    speechService.stopRecording()
                    isRecording = false
                }

            VStack(spacing: CawnexSpacing.xl) {
                ZStack {
                    Circle()
                        .fill(CawnexColors.primary.opacity(0.3))
                        .frame(width: 80, height: 80)

                    Image(systemName: "mic.fill")
                        .font(.system(size: 32))
                        .foregroundStyle(CawnexColors.primary)
                }

                Text("Listening...")
                    .font(CawnexTypography.sectionTitle)
                    .foregroundStyle(.white)

                if !speechService.transcription.isEmpty {
                    Text(speechService.transcription)
                        .font(CawnexTypography.caption)
                        .italic()
                        .foregroundStyle(CawnexColors.mutedForeground)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, CawnexSpacing.xl)
                }

                Button {
                    let text = speechService.stopRecording()
                    isRecording = false
                    if !text.isEmpty {
                        inputText = text
                        Task { await send() }
                    }
                } label: {
                    Text("Done")
                        .font(CawnexTypography.bodyBold)
                        .foregroundStyle(CawnexColors.primaryForeground)
                        .padding(.horizontal, CawnexSpacing.xxxl)
                        .padding(.vertical, CawnexSpacing.sm)
                        .background(CawnexColors.primary)
                        .clipShape(Capsule())
                }
            }
            .padding(.bottom, 80)
        }
        .onChange(of: speechService.transcription) { _, new in
            inputText = new
        }
        .onAppear { speechService.startRecording() }
    }

    // MARK: - Actions

    private func send() async {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        await viewModel.sendMessage(text)
    }
}
