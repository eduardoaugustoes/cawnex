import SwiftUI

@Observable
final class SignUpViewModel {
    var name = ""
    var email = ""
    var password = ""
    var isLoading = false
    var errorMessage: String?

    private let authService: any AuthService
    private let onConfirmationRequired: (String) -> Void

    init(authService: any AuthService, onConfirmationRequired: @escaping (String) -> Void) {
        self.authService = authService
        self.onConfirmationRequired = onConfirmationRequired
    }

    var canSignUp: Bool {
        !name.isEmpty && !email.isEmpty && password.count >= 8 && !isLoading
    }

    func signUp() {
        guard canSignUp else { return }
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let result = try await authService.signUp(email: email, password: password, name: name)
                await MainActor.run {
                    isLoading = false
                    if case .confirmationRequired(let email) = result {
                        onConfirmationRequired(email)
                    }
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                }
            }
        }
    }
}

struct SignUpScreen: View {
    @Bindable var viewModel: SignUpViewModel
    var onBackToSignIn: () -> Void

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            VStack(spacing: CawnexSpacing.xxxl) {
                header
                form
                Spacer()
                footer
            }
            .padding(.horizontal, 32)
            .padding(.top, 60)
        }
    }

    private var header: some View {
        VStack(spacing: CawnexSpacing.sm) {
            Text("Create Account")
                .font(CawnexTypography.heading1)
                .foregroundStyle(CawnexColors.cardForeground)
            Text("Start orchestrating with AI")
                .font(CawnexTypography.body)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private var form: some View {
        VStack(spacing: CawnexSpacing.lg) {
            field(label: "Name", icon: "person", text: $viewModel.name, contentType: .name, keyboard: .default)
            field(label: "Email", icon: "envelope", text: $viewModel.email, contentType: .emailAddress, keyboard: .emailAddress)
            passwordField

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
            }

            Button(action: viewModel.signUp) {
                Group {
                    if viewModel.isLoading {
                        ProgressView().tint(.white)
                    } else {
                        Text("Create Account")
                            .font(CawnexTypography.sectionTitle)
                            .foregroundStyle(.white)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .background(viewModel.canSignUp ? CawnexColors.primaryLight : CawnexColors.primaryLight.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            }
            .disabled(!viewModel.canSignUp)
        }
    }

    private func field(label: String, icon: String, text: Binding<String>, contentType: UITextContentType, keyboard: UIKeyboardType) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 16))
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(width: 18, height: 18)

                TextField("", text: text)
                    .font(CawnexTypography.body)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .textContentType(contentType)
                    .keyboardType(keyboard)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(keyboard == .emailAddress ? .never : .words)
            }
            .padding(.horizontal, 16)
            .frame(height: 48)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
    }

    private var passwordField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Password")
                .font(CawnexTypography.captionMedium)
                .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: 10) {
                Image(systemName: "lock")
                    .font(.system(size: 16))
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(width: 18, height: 18)

                SecureField("", text: $viewModel.password, prompt: Text("Min. 8 characters").foregroundStyle(Color(hex: 0x475569)))
                    .font(CawnexTypography.body)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .textContentType(.newPassword)
            }
            .padding(.horizontal, 16)
            .frame(height: 48)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
    }

    private var footer: some View {
        HStack(spacing: 4) {
            Text("Already have an account?")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
            Button(action: onBackToSignIn) {
                Text("Sign In")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.primaryLight)
            }
        }
        .padding(.bottom, 24)
    }
}
