import SwiftUI

@Observable
final class ConfirmEmailViewModel {
    var code = ""
    var isLoading = false
    var errorMessage: String?
    var codeSent = false

    let email: String
    private let authService: any AuthService
    private let onConfirmed: () -> Void

    init(email: String, authService: any AuthService, onConfirmed: @escaping () -> Void) {
        self.email = email
        self.authService = authService
        self.onConfirmed = onConfirmed
    }

    var canConfirm: Bool {
        code.count == 6 && !isLoading
    }

    func confirm() {
        guard canConfirm else { return }
        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await authService.confirmSignUp(email: email, code: code)
                await MainActor.run {
                    isLoading = false
                    onConfirmed()
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                }
            }
        }
    }

    func resendCode() {
        Task {
            do {
                try await authService.resendConfirmationCode(email: email)
                await MainActor.run {
                    codeSent = true
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                }
            }
        }
    }
}

struct ConfirmEmailScreen: View {
    @Bindable var viewModel: ConfirmEmailViewModel
    var onBackToSignIn: () -> Void

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            VStack(spacing: CawnexSpacing.xxxl) {
                header
                codeField

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(CawnexTypography.caption)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                }

                confirmButton
                resendButton
                Spacer()
                backButton
            }
            .padding(.horizontal, 32)
            .padding(.top, 80)
        }
    }

    private var header: some View {
        VStack(spacing: CawnexSpacing.sm) {
            Image(systemName: "envelope.badge")
                .font(.system(size: 48))
                .foregroundStyle(CawnexColors.primaryLight)

            Text("Check Your Email")
                .font(CawnexTypography.heading1)
                .foregroundStyle(CawnexColors.cardForeground)

            Text("We sent a 6-digit code to\n\(viewModel.email)")
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)
                .multilineTextAlignment(.center)
        }
    }

    private var codeField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Confirmation Code")
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            TextField("", text: $viewModel.code, prompt: Text("000000").foregroundStyle(Color(hex: 0x475569)))
                .font(.system(size: 24, weight: .semibold, design: .monospaced))
                .foregroundStyle(CawnexColors.cardForeground)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 16)
                .frame(height: 56)
                .background(CawnexColors.card)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CawnexRadius.md)
                        .stroke(CawnexColors.border, lineWidth: 1)
                )
                .onChange(of: viewModel.code) { _, newValue in
                    // Limit to 6 digits
                    let filtered = newValue.filter(\.isNumber)
                    if filtered.count > 6 {
                        viewModel.code = String(filtered.prefix(6))
                    } else if filtered != newValue {
                        viewModel.code = filtered
                    }
                }
        }
    }

    private var confirmButton: some View {
        Button(action: viewModel.confirm) {
            Group {
                if viewModel.isLoading {
                    ProgressView().tint(.white)
                } else {
                    Text("Confirm")
                        .font(CawnexTypography.sectionTitle)
                        .foregroundStyle(.white)
                }
            }
            .frame(maxWidth: .infinity)
            .frame(height: 50)
            .background(viewModel.canConfirm ? CawnexColors.primaryLight : CawnexColors.primaryLight.opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .disabled(!viewModel.canConfirm)
    }

    private var resendButton: some View {
        Button(action: viewModel.resendCode) {
            Text(viewModel.codeSent ? "Code sent!" : "Resend code")
                .font(CawnexTypography.captionBold)
                .foregroundStyle(CawnexColors.primaryLight)
        }
        .disabled(viewModel.codeSent)
    }

    private var backButton: some View {
        Button(action: onBackToSignIn) {
            Text("Back to Sign In")
                .font(CawnexTypography.captionBold)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .padding(.bottom, 24)
    }
}
