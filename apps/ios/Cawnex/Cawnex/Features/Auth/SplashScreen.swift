import SwiftUI

struct SplashScreen: View {
    @State private var logoOpacity: Double = 0
    @State private var logoScale: CGFloat = 0.8
    @State private var wordmarkOpacity: Double = 0
    @State private var wordmarkOffset: CGFloat = 10
    @State private var taglineOpacity: Double = 0

    var onFinished: () -> Void

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            VStack(spacing: CawnexSpacing.xxl) {
                crowIcon
                wordmark
                tagline
            }
        }
        .onAppear {
            runAnimation()
        }
    }

    // MARK: - Crow Icon

    private var crowIcon: some View {
        Image("AppIconImage")
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: 120, height: 120)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.lg))
            .opacity(logoOpacity)
            .scaleEffect(logoScale)
    }

    // MARK: - Wordmark

    private var wordmark: some View {
        Text("CAWNEX")
            .font(CawnexTypography.wordmark)
            .tracking(6)
            .foregroundStyle(CawnexColors.cardForeground)
            .opacity(wordmarkOpacity)
            .offset(y: wordmarkOffset)
    }

    // MARK: - Tagline

    private var tagline: some View {
        Text("Coordinated Intelligence")
            .font(CawnexTypography.tagline)
            .tracking(1.5)
            .foregroundStyle(CawnexColors.mutedForeground)
            .opacity(taglineOpacity)
    }

    // MARK: - Animation Sequence

    private func runAnimation() {
        // Phase 1: Logo fades in and scales up
        withAnimation(.easeOut(duration: 0.6)) {
            logoOpacity = 1
            logoScale = 1
        }

        // Phase 2: Wordmark slides up and fades in
        withAnimation(.easeOut(duration: 0.5).delay(0.4)) {
            wordmarkOpacity = 1
            wordmarkOffset = 0
        }

        // Phase 3: Tagline fades in
        withAnimation(.easeOut(duration: 0.4).delay(0.7)) {
            taglineOpacity = 1
        }

        // Phase 4: Transition out after hold
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            onFinished()
        }
    }
}

#Preview {
    SplashScreen(onFinished: {})
}
