import XCTest

@testable import Cawnex

final class CouncilSessionDecodingTests: XCTestCase {
    private static func loadFixture(_ name: String) throws -> Data {
        let bundle = Bundle(for: CouncilSessionDecodingTests.self)
        let url = bundle.url(forResource: name, withExtension: "json")!
        return try Data(contentsOf: url)
    }

    private static func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        let formatter = ISO8601DateFormatter()
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let str = try container.decode(String.self)
            guard let date = formatter.date(from: str) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Bad ISO8601 date: \(str)"
                )
            }
            return date
        }
        return d
    }

    func test_decodes_completed_session_with_all_advisors() throws {
        let data = try Self.loadFixture("council_session_completed")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        XCTAssertEqual(session.status, .completed)
        XCTAssertEqual(session.decision?.action, .approve)
        XCTAssertEqual(session.rounds.count, 1)
        XCTAssertEqual(session.rounds[0].votes.count, 6)
        XCTAssertEqual(session.pipelineHealth, .ok)
        let advisors = Set(session.rounds[0].votes.map(\.advisor))
        XCTAssertEqual(advisors, Set(AdvisorType.allCases))
    }

    func test_decodes_pending_session_with_null_decision() throws {
        let data = try Self.loadFixture("council_session_pending")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        XCTAssertEqual(session.status, .pending)
        XCTAssertNil(session.decision)
        XCTAssertTrue(session.rounds.isEmpty)
    }

    func test_decodes_errored_session_with_degraded_health() throws {
        let data = try Self.loadFixture("council_session_errored")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        XCTAssertEqual(session.status, .errored)
        XCTAssertEqual(session.pipelineHealth, .degraded)
        XCTAssertNil(session.decision)
    }

    func test_decodes_approve_with_condition_vote() throws {
        let data = try Self.loadFixture("council_session_completed")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        let perf = session.rounds[0].votes.first(where: { $0.advisor == .performance })!
        XCTAssertEqual(perf.vote, .approveWithCondition)
        XCTAssertNotNil(perf.condition)
    }

    func test_decodes_cited_evidence_and_investigation_trace() throws {
        let data = try Self.loadFixture("council_session_completed")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        let security = session.rounds[0].votes.first(where: { $0.advisor == .security })!
        XCTAssertEqual(security.citedEvidence.first?.filePath, "apps/api/foo.py")
        XCTAssertEqual(security.citedEvidence.first?.lineRange, [42, 58])
        XCTAssertEqual(security.investigationTrace.first?.toolName, "read_file")
        XCTAssertEqual(
            security.investigationTrace.first?.args["path"]?.value as? String,
            "apps/api/foo.py"
        )
    }
}
