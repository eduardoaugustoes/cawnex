import Foundation

/// Environment-specific configuration for AWS services.
/// Values are set at build time — no secrets in code.
struct AppConfiguration {
    let cognitoRegion: String
    let cognitoUserPoolId: String
    let cognitoClientId: String
    let apiBaseUrl: String

    /// Cognito JSON API endpoint derived from region.
    var cognitoEndpoint: String {
        "https://cognito-idp.\(cognitoRegion).amazonaws.com"
    }

    // MARK: - Environments

    static let dev = AppConfiguration(
        cognitoRegion: "us-east-1",
        cognitoUserPoolId: "", // Set after first cdk deploy
        cognitoClientId: "",   // Set after first cdk deploy
        apiBaseUrl: ""         // Set after first cdk deploy (CloudFront URL)
    )

    static let staging = AppConfiguration(
        cognitoRegion: "us-east-1",
        cognitoUserPoolId: "",
        cognitoClientId: "",
        apiBaseUrl: ""
    )

    static let prod = AppConfiguration(
        cognitoRegion: "us-east-1",
        cognitoUserPoolId: "",
        cognitoClientId: "",
        apiBaseUrl: "https://api.cawnex.ai"
    )

    /// Active configuration based on build scheme.
    static var current: AppConfiguration {
        #if DEBUG
        return .dev
        #else
        return .prod
        #endif
    }
}
