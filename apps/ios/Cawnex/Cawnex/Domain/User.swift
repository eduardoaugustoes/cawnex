import Foundation

struct User: Identifiable, Equatable {
    let id: String
    let name: String
    let email: String
    let tenantId: String

    init(id: String, name: String, email: String, tenantId: String) {
        self.id = id
        self.name = name
        self.email = email
        self.tenantId = tenantId
    }

    /// Create a User from an authenticated session.
    init(session: AuthSession) {
        self.id = session.userSub
        self.name = session.email // Name comes from Cognito attributes later
        self.email = session.email
        self.tenantId = session.tenantId
    }
}
