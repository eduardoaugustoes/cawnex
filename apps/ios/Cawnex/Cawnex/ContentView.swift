import SwiftUI

struct ContentView: View {
    @State private var router = AppRouter()

    var body: some View {
        Group {
            switch router.currentRoute {
            case .splash:
                SplashScreen(onFinished: router.splashFinished)
                    .transition(.opacity)
            case .signIn:
                SignInScreen(onSignIn: router.signedIn)
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
