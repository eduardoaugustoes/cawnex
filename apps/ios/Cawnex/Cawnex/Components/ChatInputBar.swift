import SwiftUI

struct ChatInputBar: View {
    let accentColor: Color
    @Binding var text: String
    var onSend: () -> Void
    var isSending: Bool

    var body: some View {
        HStack(spacing: CawnexSpacing.sm) {
            TextField("", text: $text)
                .font(CawnexTypography.subheading)
                .foregroundStyle(CawnexColors.cardForeground)
                .placeholder(when: text.isEmpty) {
                    Text("Type your answer...")
                        .font(CawnexTypography.subheading)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                .padding(.horizontal, CawnexSpacing.lg)
                .frame(height: 44)
                .background(CawnexColors.card)
                .overlay(
                    Capsule()
                        .stroke(CawnexColors.border, lineWidth: 1)
                )
                .clipShape(Capsule())

            Button(action: onSend) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 40, height: 40)
                    .background(accentColor)
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
            .disabled(isSending || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .opacity(isSending || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.5 : 1)
        }
        .padding(.horizontal, CawnexSpacing.xl)
        .padding(.top, CawnexSpacing.md)
        .padding(.bottom, 28)
        .background(CawnexColors.background)
    }
}

private extension View {
    func placeholder<Content: View>(when condition: Bool, @ViewBuilder placeholder: () -> Content) -> some View {
        ZStack(alignment: .leading) {
            if condition { placeholder() }
            self
        }
    }
}

#Preview {
    ZStack {
        CawnexColors.background.ignoresSafeArea()
        VStack {
            Spacer()
            ChatInputBar(
                accentColor: CawnexColors.primary,
                text: .constant(""),
                onSend: {},
                isSending: false
            )
        }
    }
}
