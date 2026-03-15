import Foundation

/// Fetches client configuration from the API at launch.
/// Falls back to AppConfiguration hardcoded values if fetch fails.
@Observable
final class RemoteConfig {

    private(set) var userPoolId: String = AppConfiguration.userPoolId
    private(set) var clientId: String = AppConfiguration.clientId
    private(set) var region: String = AppConfiguration.region
    private(set) var cognitoDomain: String = AppConfiguration.cognitoDomain
    private(set) var isLoaded: Bool = false

    /// Fetch configuration from the API. Safe to call multiple times.
    func load() async {
        let baseURL = AppConfiguration.apiBaseURL
        guard let url = URL(string: "\(baseURL)/config") else { return }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else { return }

            let config = try JSONDecoder().decode(ConfigResponse.self, from: data)
            await MainActor.run {
                if !config.userPoolId.isEmpty { self.userPoolId = config.userPoolId }
                if !config.iosClientId.isEmpty { self.clientId = config.iosClientId }
                if !config.region.isEmpty { self.region = config.region }
                if !config.cognitoDomain.isEmpty { self.cognitoDomain = config.cognitoDomain }
                self.isLoaded = true
            }
        } catch {
            // Silently fall back to hardcoded values
            #if DEBUG
            print("[RemoteConfig] Failed to load: \(error.localizedDescription). Using fallback.")
            #endif
        }
    }

    var cognitoEndpoint: String {
        "https://cognito-idp.\(region).amazonaws.com/"
    }
}

private struct ConfigResponse: Decodable {
    let userPoolId: String
    let iosClientId: String
    let webClientId: String
    let region: String
    let cognitoDomain: String
    let stage: String
}
