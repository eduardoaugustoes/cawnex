import Foundation

@Observable
final class SignInViewModel {
    var email = ""
    var password = ""
    var isLoading = false
    var errorMessage: String?

    private let authService: any AuthService
    private let onSignedIn: (AuthSession) -> Void
    private let onNeedsConfirmation: (String) -> Void

    init(
        authService: any AuthService,
        onSignedIn: @escaping (AuthSession) -> Void,
        onNeedsConfirmation: @escaping (String) -> Void
    ) {
        self.authService = authService
        self.onSignedIn = onSignedIn
        self.onNeedsConfirmation = onNeedsConfirmation
    }

    var canSignIn: Bool {
        !email.isEmpty && !password.isEmpty && !isLoading
    }

    func signIn() {
        guard canSignIn else { return }
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let session = try await authService.signIn(email: email, password: password)
                await MainActor.run {
                    isLoading = false
                    onSignedIn(session)
                }
            } catch let error as AuthError {
                await MainActor.run {
                    isLoading = false
                    if case .userNotConfirmed = error {
                        onNeedsConfirmation(email)
                    } else {
                        errorMessage = error.localizedDescription
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
