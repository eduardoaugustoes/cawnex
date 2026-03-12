import SwiftUI

enum AppRoute: Equatable {
    case splash
    case signIn
    case main
}

@Observable
final class AppRouter {
    var currentRoute: AppRoute = .splash

    func splashFinished() {
        withAnimation(.easeInOut(duration: 0.3)) {
            currentRoute = .signIn
        }
    }

    func signedIn() {
        currentRoute = .main
    }
}
