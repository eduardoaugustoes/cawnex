import SwiftUI

struct ContentView: View {
    @State private var router = AppRouter()
    @State private var store = AppStore()
    @State private var authService: any AuthService = {
        #if DEBUG
        if AppConfiguration.clientId.isEmpty {
            return InMemoryAuthService()
        }
        #endif
        return CognitoAuthService()
    }()

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            switch router.currentRoute {
            case .splash:
                SplashScreen(onFinished: { router.splashFinished(authService: authService) })
                    .transition(.opacity)

            case .checking:
                // Brief loading state while checking Keychain
                ProgressView()
                    .tint(CawnexColors.primaryLight)

            case .signIn:
                SignInScreen(
                    viewModel: SignInViewModel(
                        authService: authService,
                        onSignedIn: { session in
                            store.setUser(from: session)
                            store.seedData()
                            router.signedIn()
                        },
                        onNeedsConfirmation: { email in
                            router.needsConfirmation(email: email)
                        }
                    ),
                    onSignUp: router.showSignUp
                )
                .transition(.opacity)

            case .signUp:
                SignUpScreen(
                    viewModel: SignUpViewModel(
                        authService: authService,
                        onConfirmationRequired: { email in
                            router.needsConfirmation(email: email)
                        }
                    ),
                    onBackToSignIn: router.showSignIn
                )
                .transition(.opacity)

            case .confirmEmail(let email):
                ConfirmEmailScreen(
                    viewModel: ConfirmEmailViewModel(
                        email: email,
                        authService: authService,
                        onConfirmed: {
                            router.showSignIn()
                        }
                    ),
                    onBackToSignIn: router.showSignIn
                )
                .transition(.opacity)

            case .main:
                MainTabView()
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.3), value: router.currentRoute)
    }
}

#Preview {
    ContentView()
}
