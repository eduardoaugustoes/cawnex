import XCTest

@testable import Cawnex

@MainActor
final class WaveReviewViewModelTests: XCTestCase {
    private func loadCompletedSession() throws -> CouncilSession {
        let bundle = Bundle(for: Self.self)
        let url = bundle.url(
            forResource: "council_session_completed", withExtension: "json"
        )!
        let data = try Data(contentsOf: url)
        let d = JSONDecoder()
        let formatter = ISO8601DateFormatter()
        d.dateDecodingStrategy = .custom { decoder in
            let c = try decoder.singleValueContainer()
            let s = try c.decode(String.self)
            return formatter.date(from: s) ?? Date()
        }
        return try d.decode(CouncilSession.self, from: data)
    }

    func test_load_happy_path_transitions_idle_loading_loaded() async throws {
        let session = try loadCompletedSession()
        let service = InMemoryWaveReviewService(seed: [session])
        let vm = WaveReviewViewModel(service: service)
        XCTAssertEqual(vm.state, .idle)
        await vm.load(projectId: "p1", sessionId: session.sessionId)
        guard case .loaded(let loaded) = vm.state else {
            return XCTFail("Expected .loaded, got \(vm.state)")
        }
        XCTAssertEqual(loaded.status, .completed)
    }

    func test_load_missing_session_transitions_to_error() async {
        let service = InMemoryWaveReviewService(seed: [])
        let vm = WaveReviewViewModel(service: service)
        await vm.load(projectId: "p1", sessionId: "does-not-exist")
        guard case .error = vm.state else {
            return XCTFail("Expected .error, got \(vm.state)")
        }
    }

    func test_approve_success_transitions_to_actionSucceeded() async throws {
        let session = try loadCompletedSession()
        let service = InMemoryWaveReviewService(seed: [session])
        let vm = WaveReviewViewModel(service: service)
        await vm.load(projectId: "p1", sessionId: session.sessionId)
        await vm.approve(projectId: "p1", waveId: "w1")
        guard case .actionSucceeded(let action) = vm.state else {
            return XCTFail("Expected .actionSucceeded, got \(vm.state)")
        }
        XCTAssertEqual(action, .approved)
        XCTAssertEqual(service.approvedWaves, ["w1"])
    }

    func test_reject_writes_reason() async throws {
        let session = try loadCompletedSession()
        let service = InMemoryWaveReviewService(seed: [session])
        let vm = WaveReviewViewModel(service: service)
        await vm.load(projectId: "p1", sessionId: session.sessionId)
        await vm.reject(projectId: "p1", waveId: "w1", reason: "scope creep")
        guard case .actionSucceeded(let action) = vm.state else {
            return XCTFail("Expected .actionSucceeded, got \(vm.state)")
        }
        XCTAssertEqual(action, .rejected)
        XCTAssertEqual(service.rejectedWaves.first?.reason, "scope creep")
    }
}
