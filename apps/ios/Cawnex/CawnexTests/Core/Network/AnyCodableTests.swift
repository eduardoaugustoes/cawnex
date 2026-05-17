import XCTest

@testable import Cawnex

final class AnyCodableTests: XCTestCase {
    func test_decodes_string() throws {
        let json = #"{"v":"hello"}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        XCTAssertEqual(decoded["v"]?.value as? String, "hello")
    }

    func test_decodes_int() throws {
        let json = #"{"v":42}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        XCTAssertEqual(decoded["v"]?.value as? Int, 42)
    }

    func test_decodes_nested_object() throws {
        let json = #"{"v":{"path":"foo.py","max":10}}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        let nested = decoded["v"]?.value as? [String: Any]
        XCTAssertEqual(nested?["path"] as? String, "foo.py")
        XCTAssertEqual(nested?["max"] as? Int, 10)
    }

    func test_decodes_null() throws {
        let json = #"{"v":null}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        XCTAssertNil(decoded["v"]?.value)
    }

    func test_encodes_round_trip() throws {
        let original: [String: AnyCodable] = [
            "a": AnyCodable("text"),
            "b": AnyCodable(7),
        ]
        let data = try JSONEncoder().encode(original)
        let roundtripped = try JSONDecoder().decode([String: AnyCodable].self, from: data)
        XCTAssertEqual(roundtripped["a"]?.value as? String, "text")
        XCTAssertEqual(roundtripped["b"]?.value as? Int, 7)
    }
}
