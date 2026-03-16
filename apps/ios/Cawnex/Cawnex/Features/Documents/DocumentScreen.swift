import SwiftUI

// MARK: - DocumentType Display Properties

extension DocumentType {
    var displayTitle: String {
        switch self {
        case .vision: "Vision"
        case .architecture: "Architecture"
        case .glossary: "Glossary"
        case .design: "Design System"
        }
    }

    var accentColor: Color {
        switch self {
        case .vision: CawnexColors.primary
        case .architecture: CawnexColors.info
        case .glossary: CawnexColors.success
        case .design: CawnexColors.accent
        }
    }
}

// MARK: - DocumentScreen

struct DocumentScreen: View {
    let projectId: String
    let type: DocumentType
    @State var viewModel: DocumentViewModel
    var onBack: () -> Void = {}
    @State private var isShowingPreview = false

    private var accentColor: Color { type.accentColor }
    private var title: String { type.displayTitle }

    var body: some View {
        VStack(spacing: 0) {
            scrollContent
            inputBar
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.load(projectId: projectId) }
        .sheet(isPresented: $isShowingPreview) {
            if let detail = viewModel.detail {
                DocumentPreviewSheet(
                    title: title,
                    accentColor: accentColor,
                    sections: detail.sections,
                    onDismiss: { isShowingPreview = false }
                )
            }
        }
    }

    private var scrollContent: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
                    navRow
                    bannerRow
                    chatArea
                    previewButton
                }
                .padding(.top, CawnexSpacing.sm)
                .padding(.horizontal, CawnexSpacing.xl)
                .padding(.bottom, CawnexSpacing.xl)
                .id("bottom-anchor")
            }
            .onChange(of: viewModel.detail?.messages.count) {
                withAnimation {
                    proxy.scrollTo("bottom-anchor", anchor: .bottom)
                }
            }
        }
    }

    private var navRow: some View {
        HStack {
            Button(action: onBack) {
                HStack(spacing: CawnexSpacing.sm) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text(title)
                        .font(CawnexTypography.heading3)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
            }
            .buttonStyle(.plain)

            Spacer()

            Text("Draft")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.warning)
                .padding(.horizontal, 10)
                .padding(.vertical, 3)
                .background(CawnexColors.warning.opacity(0.13))
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
        }
    }

    @ViewBuilder
    private var bannerRow: some View {
        if viewModel.detail != nil {
            DocPreviewBanner(
                title: title,
                accentColor: accentColor,
                sectionsComplete: viewModel.completedSections,
                sectionsTotal: viewModel.totalSections
            )
        }
    }

    @ViewBuilder
    private var chatArea: some View {
        if let detail = viewModel.detail {
            VStack(alignment: .leading, spacing: CawnexSpacing.md) {
                ForEach(detail.messages) { message in
                    ChatMessageBubble(message: message, accentColor: accentColor)
                }

                // Typing indicator while waiting for Claude
                if viewModel.isSending {
                    TypingIndicator(accentColor: accentColor)
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                }
            }
            .animation(.easeInOut(duration: 0.2), value: viewModel.isSending)
        } else if case .loading = viewModel.state {
            HStack {
                Spacer()
                ProgressView()
                    .tint(accentColor)
                Spacer()
            }
            .padding(.vertical, CawnexSpacing.xl)
        } else if case .error(let message) = viewModel.state {
            Text(message)
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.destructive)
        }
    }

    private var previewButton: some View {
        Button(action: { isShowingPreview = true }) {
            HStack(spacing: CawnexSpacing.sm) {
                Image(systemName: "eye")
                    .font(.system(size: 15))
                Text("Preview Document")
                    .font(CawnexTypography.subheading)
            }
            .foregroundStyle(accentColor)
            .frame(maxWidth: .infinity)
            .frame(height: 44)
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(accentColor, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private var inputBar: some View {
        ChatInputBar(
            accentColor: accentColor,
            text: $viewModel.messageText,
            onSend: {
                Task { await viewModel.sendMessage(projectId: projectId) }
            },
            isSending: viewModel.isSending
        )
    }
}

// MARK: - Typing Indicator

struct TypingIndicator: View {
    let accentColor: Color
    @State private var phase: Int = 0

    var body: some View {
        HStack(alignment: .top, spacing: CawnexSpacing.sm) {
            Image(systemName: "sparkles")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(accentColor)
                .padding(.top, 4)

            HStack(spacing: 4) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(accentColor.opacity(phase == index ? 1.0 : 0.3))
                        .frame(width: 8, height: 8)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .padding(.leading, 4)
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { _ in
                withAnimation(.easeInOut(duration: 0.3)) {
                    phase = (phase + 1) % 3
                }
            }
        }
    }
}

#Preview("Vision") {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        DocumentScreen(
            projectId: "1",
            type: .vision,
            viewModel: DocumentViewModel(
                documentService: InMemoryDocumentService(),
                documentType: .vision
            )
        )
    }
    .environment(store)
}

#Preview("Architecture") {
    let store = AppStore()
    store.seedData()
    return NavigationStack {
        DocumentScreen(
            projectId: "1",
            type: .architecture,
            viewModel: DocumentViewModel(
                documentService: InMemoryDocumentService(),
                documentType: .architecture
            )
        )
    }
    .environment(store)
}
