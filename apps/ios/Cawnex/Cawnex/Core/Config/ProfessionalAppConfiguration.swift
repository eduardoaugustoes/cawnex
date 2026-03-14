import Foundation

/// Professional-grade app configuration using build settings and Info.plist
/// This approach is used by companies like Uber, Spotify, Netflix
struct ProfessionalAppConfiguration {

    // MARK: - Environment Detection

    enum Environment: String, CaseIterable {
        case development = "Development"
        case staging = "Staging"
        case production = "Production"

        static var current: Environment {
            #if DEBUG
            return .development
            #elseif STAGING
            return .staging
            #else
            return .production
            #endif
        }

        var isDevelopment: Bool { self == .development }
        var isProduction: Bool { self == .production }
    }

    // MARK: - Configuration Loading

    /// Load configuration value from Info.plist (set via .xcconfig files)
    private static func configValue<T>(for key: String, type: T.Type = T.self) -> T {
        guard let value = Bundle.main.object(forInfoDictionaryKey: key) as? T else {
            fatalError("Configuration key '\(key)' not found in Info.plist. Check your .xcconfig files.")
        }
        return value
    }

    /// Load optional configuration value
    private static func optionalConfigValue<T>(for key: String, type: T.Type = T.self) -> T? {
        return Bundle.main.object(forInfoDictionaryKey: key) as? T
    }

    // MARK: - Core Configuration

    static let environment = Environment.current

    // API Configuration
    static let apiBaseURL: String = configValue(for: "APIBaseURL")
    static let apiTimeout: TimeInterval = optionalConfigValue(for: "APITimeout") ?? 30.0
    static let apiRetries: Int = optionalConfigValue(for: "APIRetries") ?? 3

    // AWS Cognito Configuration
    static let userPoolId: String = configValue(for: "UserPoolId")
    static let clientId: String = configValue(for: "ClientId")
    static let cognitoDomain: String = configValue(for: "CognitoDomain")
    static let region: String = configValue(for: "AWSRegion")

    // Computed Properties
    static var cognitoEndpoint: String {
        return "https://cognito-idp.\(region).amazonaws.com/"
    }

    // MARK: - App Information

    static let appName = Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String ?? "Cawnex"
    static let bundleId = Bundle.main.bundleIdentifier ?? "com.cawnex.app"
    static let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0.0"
    static let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "1"

    // MARK: - Feature Flags

    struct FeatureFlags {
        static let debugMenuEnabled: Bool = {
            guard let enabled = Bundle.main.object(forInfoDictionaryKey: "EnableDebugMenu") as? String else {
                return environment.isDevelopment
            }
            return enabled.lowercased() == "yes" || enabled == "1"
        }()

        static let analyticsEnabled: Bool = {
            guard let enabled = Bundle.main.object(forInfoDictionaryKey: "EnableAnalytics") as? String else {
                return environment.isProduction
            }
            return enabled.lowercased() == "yes" || enabled == "1"
        }()

        static let crashReportingEnabled: Bool = {
            guard let enabled = Bundle.main.object(forInfoDictionaryKey: "EnableCrashReporting") as? String else {
                return environment.isProduction
            }
            return enabled.lowercased() == "yes" || enabled == "1"
        }()

        static let biometricsEnabled = true
        static let pushNotificationsEnabled = true
        static let loggingEnabled = true
    }

    // MARK: - URLs

    static let privacyPolicyURL = "https://cawnex.ai/privacy"
    static let termsOfServiceURL = "https://cawnex.ai/terms"
    static let supportURL = "https://cawnex.ai/support"

    // MARK: - Debug Information

    static func debugDescription() -> String {
        return """
        🔧 Cawnex Configuration Debug Info:

        📱 Environment: \(environment.rawValue)
        🆔 Bundle ID: \(bundleId)
        📦 Version: \(version) (\(build))
        🌍 App Name: \(appName)

        🔗 API Base URL: \(apiBaseURL)
        ⏱️ API Timeout: \(apiTimeout)s
        🔄 API Retries: \(apiRetries)

        🔐 User Pool: \(userPoolId)
        🎫 Client ID: \(clientId)
        🏷️ Cognito Domain: \(cognitoDomain)
        🌎 AWS Region: \(region)

        🎛️ Feature Flags:
        • Debug Menu: \(FeatureFlags.debugMenuEnabled)
        • Analytics: \(FeatureFlags.analyticsEnabled)
        • Crash Reporting: \(FeatureFlags.crashReportingEnabled)
        • Biometrics: \(FeatureFlags.biometricsEnabled)
        """
    }

    // MARK: - Validation

    static func validate() throws {
        // Validate required configuration
        guard !apiBaseURL.isEmpty else {
            throw ConfigurationError.missingValue("APIBaseURL")
        }

        guard !userPoolId.isEmpty else {
            throw ConfigurationError.missingValue("UserPoolId")
        }

        guard !clientId.isEmpty else {
            throw ConfigurationError.missingValue("ClientId")
        }

        guard URL(string: apiBaseURL) != nil else {
            throw ConfigurationError.invalidValue("APIBaseURL", apiBaseURL)
        }
    }

    enum ConfigurationError: LocalizedError {
        case missingValue(String)
        case invalidValue(String, String)

        var errorDescription: String? {
            switch self {
            case .missingValue(let key):
                return "Missing required configuration value: \(key)"
            case .invalidValue(let key, let value):
                return "Invalid configuration value for \(key): \(value)"
            }
        }
    }
}

// MARK: - Backward Compatibility

/// Alias for backward compatibility with existing code
typealias AppConfiguration = ProfessionalAppConfiguration
