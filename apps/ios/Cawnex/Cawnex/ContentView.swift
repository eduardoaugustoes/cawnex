import SwiftUI

struct ContentView: View {
    @Environment(AppStore.self) private var store
    @State private var router = AppRouter()
    @State private var remoteConfig = RemoteConfig()
    @State private var authService: (any AuthService)?
    @State private var apiClient: APIClient?
    @State private var splashDone = false

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            switch router.currentRoute {
            case .splash:
                SplashScreen(onFinished: {
                    splashDone = true
                    transitionIfReady()
                })
                .transition(.opacity)
                .task {
                    // Fetch config in parallel with splash animation
                    await remoteConfig.load()
                    let service: any AuthService = {
                        #if DEBUG
                        if remoteConfig.clientId.isEmpty {
                            return InMemoryAuthService()
                        }
                        #endif
                        return CognitoAuthService(remoteConfig: remoteConfig)
                    }()
                    authService = service
                    transitionIfReady()
                }

            case .checking:
                ProgressView()
                    .tint(CawnexColors.primaryLight)

            case .signIn:
                SignInScreen(
                    viewModel: SignInViewModel(
                        authService: authService!,
                        onSignedIn: { session in
                            store.setUser(from: session)
                            apiClient = APIClient(authService: authService!)
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
                        authService: authService!,
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
                        authService: authService!,
                        onConfirmed: {
                            router.showSignIn()
                        }
                    ),
                    onBackToSignIn: router.showSignIn
                )
                .transition(.opacity)

            case .main:
                MainTabView(onSignOut: {
                    apiClient = nil
                    Task {
                        await authService?.signOut()
                        store.clearUser()
                        router.signedOut()
                    }
                }, apiClient: apiClient)
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.3), value: router.currentRoute)
    }

    /// Transition only when both splash animation AND config fetch are done.
    /// Whichever finishes last triggers the transition — user never sees a spinner.
    private func transitionIfReady() {
        guard splashDone, let service = authService else { return }
        apiClient = APIClient(authService: service)
        router.splashFinished(authService: service) { session in
            store.setUser(from: session)
        }
    }
}

#Preview {
    ContentView()
}
