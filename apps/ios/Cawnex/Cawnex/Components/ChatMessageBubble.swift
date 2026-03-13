import SwiftUI

struct ChatMessageBubble: View {
    let message: ChatMessage
    let accentColor: Color

    var body: some View {
        if message.role == .ai {
            aiBubble
        } else {
            userBubble
        }
    }

    private var aiBubble: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
                HStack(spacing: 4) {
                    Image(systemName: "sparkles")
                        .font(.system(size: 11))
                        .foregroundStyle(accentColor)
                    Text("Cawnex AI")
                        .font(CawnexTypography.label)
                        .foregroundStyle(accentColor)
                }

                VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                    if let section = message.synthesizedSection {
                        synthCard(section: section)
                    }

                    Text(message.content)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(CawnexColors.cardForeground)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(CawnexColors.card)
                .clipShape(
                    UnevenRoundedRectangle(
                        topLeadingRadius: 0,
                        bottomLeadingRadius: 14,
                        bottomTrailingRadius: 14,
                        topTrailingRadius: 14
                    )
                )
            }
            Spacer(minLength: CawnexSpacing.xxxl)
        }
    }

    private var userBubble: some View {
        HStack(alignment: .top) {
            Spacer(minLength: CawnexSpacing.xxxl)
            VStack(alignment: .trailing, spacing: CawnexSpacing.xs) {
                Text("You")
                    .font(CawnexTypography.label)
                    .foregroundStyle(CawnexColors.mutedForeground)

                Text(message.content)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(accentColor)
                    .clipShape(
                        UnevenRoundedRectangle(
                            topLeadingRadius: 14,
                            bottomLeadingRadius: 14,
                            bottomTrailingRadius: 14,
                            topTrailingRadius: 0
                        )
                    )
            }
        }
    }

    private func synthCard(section: DocumentSection) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
            HStack(spacing: 4) {
                Image(systemName: "checkmark.circle")
                    .font(.system(size: 12))
                    .foregroundStyle(CawnexColors.success)
                Text(section.title)
                    .font(CawnexTypography.footnoteMedium)
                    .fontWeight(.bold)
                    .foregroundStyle(accentColor)
            }
            Text(section.content)
                .font(CawnexTypography.footnote)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.horizontal, CawnexSpacing.sm + 2)
        .padding(.vertical, CawnexSpacing.sm)
        .background(accentColor.opacity(0.067))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(accentColor.opacity(0.2), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        VStack(spacing: CawnexSpacing.md) {
            ChatMessageBubble(
                message: ChatMessage(
                    id: "1",
                    role: .ai,
                    content: "Who is the primary user of your product?",
                    synthesizedSection: nil
                ),
                accentColor: CawnexColors.primary
            )

            ChatMessageBubble(
                message: ChatMessage(
                    id: "2",
                    role: .user,
                    content: "Technical founders building AI-powered products.",
                    synthesizedSection: nil
                ),
                accentColor: CawnexColors.primary
            )

            ChatMessageBubble(
                message: ChatMessage(
                    id: "3",
                    role: .ai,
                    content: "Now let's define your core value proposition.",
                    synthesizedSection: DocumentSection(
                        id: "s2",
                        title: "Target User",
                        content: "Technical founders, pre-seed to seed stage.",
                        status: .complete
                    )
                ),
                accentColor: CawnexColors.primary
            )
        }
        .padding(CawnexSpacing.xl)
    }
}
