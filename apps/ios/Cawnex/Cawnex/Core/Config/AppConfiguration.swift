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
        cognitoUserPoolId: "us-east-1_38Ay7DArT",
        cognitoClientId: "53ne6uhf0hln8bc75pp61kbdpj",
        apiBaseUrl: "https://d1elid9twwevj2.cloudfront.net"
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
