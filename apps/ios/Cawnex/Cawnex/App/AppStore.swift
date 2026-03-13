import Foundation

@Observable
final class AppStore {
    var projects: [Project] = []
    var currentUser: User?

    func seedData() {
        currentUser = User(
            id: "u1",
            name: "Eduardo",
            email: "eduardo@cawnex.io"
        )

        projects = [
            Project(
                id: "1",
                name: "Cawnex",
                description: "Multi-agent AI orchestration platform",
                status: .active,
                tasks: TaskCounts(done: 5, active: 3, refined: 4, draft: 6),
                creditsSpent: 182,
                humanEquivSaved: 14000
            ),
            Project(
                id: "2",
                name: "Calhou",
                description: "Insurance quoting and policy management",
                status: .paused,
                tasks: TaskCounts(done: 4, active: 2, refined: 0, draft: 5),
                creditsSpent: 65,
                humanEquivSaved: 5200
            ),
        ]
    }
}
