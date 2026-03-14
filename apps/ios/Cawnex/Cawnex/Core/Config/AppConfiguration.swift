import Foundation

struct AppConfiguration {

    // MARK: - Environment Configuration
    #if DEBUG
    static let environment: Environment = .development
    #else
    static let environment: Environment = .production
    #endif

    // MARK: - Environment Settings
    enum Environment {
        case development
        case staging
        case production

        var userPoolId: String {
            switch self {
            case .development:
                return "us-east-1_38Ay7DArT"  // Development User Pool
            case .staging:
                return "us-east-1_38Ay7DArT"  // Staging uses dev for now
            case .production:
                return "us-east-1_6LT5eHiBs"  // Production User Pool
            }
        }

        var clientId: String {
            switch self {
            case .development:
                return "3qp8f80mhfvcgk0k8v7f2qhhg"  // Development iOS Client
            case .staging:
                return "3qp8f80mhfvcgk0k8v7f2qhhg"  // Staging uses dev for now
            case .production:
                return "7tqajln8jr6iim3oraln4ate6e"  // Production iOS Client
            }
        }

        var region: String {
            return "us-east-1"  // All environments in us-east-1
        }

        var apiBaseURL: String {
            switch self {
            case .development:
                return "https://api-dev.cawnex.ai"  // Development API
            case .staging:
                return "https://api-staging.cawnex.ai"  // Staging API
            case .production:
                return "https://api.cawnex.ai"  // Production API
            }
        }

        var cognitoDomain: String {
            switch self {
            case .development:
                return "cawnex-dev"  // Development Cognito Domain
            case .staging:
                return "cawnex-staging"  // Staging Cognito Domain
            case .production:
                return "cawnex-prod"  // Production Cognito Domain
            }
        }

        var description: String {
            switch self {
            case .development:
                return "Development"
            case .staging:
                return "Staging"
            case .production:
                return "Production"
            }
        }
    }

    // MARK: - Current Configuration
    static var userPoolId: String { environment.userPoolId }
    static var clientId: String { environment.clientId }
    static var region: String { environment.region }
    static var apiBaseURL: String { environment.apiBaseURL }
    static var cognitoDomain: String { environment.cognitoDomain }
    static var environmentName: String { environment.description }

    // MARK: - Computed Properties
    static var cognitoEndpoint: String {
        return "https://cognito-idp.\(region).amazonaws.com/"
    }

    // MARK: - App Information
    static let appName = "Cawnex"
    static let bundleIdentifier = Bundle.main.bundleIdentifier ?? "com.cawnex.app"
    static let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0"
    static let buildNumber = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"

    // MARK: - URLs
    static let privacyPolicyURL = "https://cawnex.ai/privacy"
    static let termsOfServiceURL = "https://cawnex.ai/terms"
    static let supportURL = "https://cawnex.ai/support"

    // MARK: - Feature Flags
    struct FeatureFlags {
        static let enableBiometrics = true
        static let enablePushNotifications = true
        static let enableAnalytics = environment != .development
        static let enableLogging = true
        static let enableDebugMenu = environment == .development
    }

    // MARK: - Debug Information
    static func debugDescription() -> String {
        return """
        Cawnex iOS Configuration:

        Environment: \(environmentName)
        User Pool ID: \(userPoolId)
        Client ID: \(clientId)
        Region: \(region)
        API Base URL: \(apiBaseURL)
        Cognito Domain: \(cognitoDomain)

        App Info:
        Bundle ID: \(bundleIdentifier)
        Version: \(appVersion) (\(buildNumber))

        Feature Flags:
        Biometrics: \(FeatureFlags.enableBiometrics)
        Push Notifications: \(FeatureFlags.enablePushNotifications)
        Analytics: \(FeatureFlags.enableAnalytics)
        Debug Menu: \(FeatureFlags.enableDebugMenu)
        """
    }
}
