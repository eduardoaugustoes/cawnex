import SwiftUI

enum AppRoute: Equatable {
    case splash
    case checking
    case signIn
    case signUp
    case confirmEmail(email: String)
    case main
}

@Observable
final class AppRouter {
    var currentRoute: AppRoute = .splash

    func splashFinished(authService: any AuthService, onSessionRestored: ((AuthSession) -> Void)? = nil) {
        currentRoute = .checking
        Task {
            if let session = await authService.currentSession() {
                await MainActor.run {
                    onSessionRestored?(session)
                    currentRoute = .main
                }
            } else {
                await MainActor.run {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        currentRoute = .signIn
                    }
                }
            }
        }
    }

    func showSignUp() {
        withAnimation(.easeInOut(duration: 0.2)) {
            currentRoute = .signUp
        }
    }

    func showSignIn() {
        withAnimation(.easeInOut(duration: 0.2)) {
            currentRoute = .signIn
        }
    }

    func needsConfirmation(email: String) {
        withAnimation(.easeInOut(duration: 0.2)) {
            currentRoute = .confirmEmail(email: email)
        }
    }

    func signedIn() {
        withAnimation(.easeInOut(duration: 0.3)) {
            currentRoute = .main
        }
    }

    func signedOut() {
        withAnimation(.easeInOut(duration: 0.3)) {
            currentRoute = .signIn
        }
    }
}
