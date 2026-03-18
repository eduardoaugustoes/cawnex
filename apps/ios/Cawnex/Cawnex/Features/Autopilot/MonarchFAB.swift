import SwiftUI

struct MonarchFAB: View {
    var onTap: () -> Void = {}
    var onVoiceResult: (String) -> Void = { _ in }

    @State private var speechService = SpeechService()
    @State private var isHolding: Bool = false

    var body: some View {
        VStack(spacing: CawnexSpacing.xs) {
            ZStack {
                Circle()
                    .fill(CawnexColors.primary)
                    .frame(width: 56, height: 56)
                    .shadow(color: CawnexColors.primary.opacity(0.4), radius: 12, y: 4)
                    .scaleEffect(isHolding ? 1.1 : 1.0)
                    .animation(.spring(response: 0.3), value: isHolding)

                Image(systemName: "bird")
                    .font(.system(size: 24, weight: .medium))
                    .foregroundStyle(CawnexColors.primaryForeground)
            }
            .gesture(
                LongPressGesture(minimumDuration: 0.4)
                    .onChanged { _ in
                        if !isHolding {
                            isHolding = true
                            speechService.startRecording()
                        }
                    }
                    .simultaneously(with:
                        DragGesture(minimumDistance: 0)
                            .onEnded { _ in
                                if isHolding {
                                    isHolding = false
                                    let text = speechService.stopRecording()
                                    if !text.isEmpty {
                                        onVoiceResult(text)
                                    }
                                }
                            }
                    )
            )
            .onTapGesture {
                onTap()
            }

            Text("Hold to speak")
                .font(CawnexTypography.label)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }
}

// MARK: - Voice Recording Overlay

struct VoiceRecordingOverlay: View {
    let transcription: String
    var onRelease: (String) -> Void = { _ in }

    @State private var pulseScale: CGFloat = 1.0
    @State private var speechService = SpeechService()

    var body: some View {
        ZStack(alignment: .bottom) {
            Color.black.opacity(0.9)
                .ignoresSafeArea()
                .onTapGesture {
                    let text = speechService.stopRecording()
                    onRelease(text)
                }

            VStack(spacing: CawnexSpacing.xl) {
                ZStack {
                    Circle()
                        .fill(CawnexColors.primary.opacity(0.3))
                        .frame(width: 80, height: 80)
                        .scaleEffect(pulseScale)
                        .animation(
                            .easeInOut(duration: 1.2).repeatForever(autoreverses: true),
                            value: pulseScale
                        )

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
            }
            .padding(.bottom, 80)
        }
        .onAppear {
            pulseScale = 1.2
            speechService.startRecording()
        }
    }
}
