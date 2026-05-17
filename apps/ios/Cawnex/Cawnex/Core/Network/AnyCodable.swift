import Foundation

/// Type-erased wrapper for decoding heterogeneous JSON values (used for
/// tool-call args whose shape varies per tool). Stores the raw value as
/// `Any?` and supports round-trip Codable for primitives, arrays, and
/// dictionaries.
struct AnyCodable: Codable, Equatable {
    let value: Any?

    init(_ value: Any?) { self.value = value }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self.value = nil
        } else if let b = try? container.decode(Bool.self) {
            self.value = b
        } else if let i = try? container.decode(Int.self) {
            self.value = i
        } else if let d = try? container.decode(Double.self) {
            self.value = d
        } else if let s = try? container.decode(String.self) {
            self.value = s
        } else if let arr = try? container.decode([AnyCodable].self) {
            self.value = arr.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            self.value = dict.mapValues { $0.value }
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "AnyCodable: unsupported JSON value"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case nil:
            try container.encodeNil()
        case let b as Bool:
            try container.encode(b)
        case let i as Int:
            try container.encode(i)
        case let d as Double:
            try container.encode(d)
        case let s as String:
            try container.encode(s)
        case let arr as [Any?]:
            try container.encode(arr.map(AnyCodable.init))
        case let dict as [String: Any?]:
            try container.encode(dict.mapValues(AnyCodable.init))
        default:
            throw EncodingError.invalidValue(
                value as Any,
                EncodingError.Context(
                    codingPath: container.codingPath,
                    debugDescription: "AnyCodable: cannot encode value"
                )
            )
        }
    }

    static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        switch (lhs.value, rhs.value) {
        case (nil, nil): return true
        case let (l as Bool, r as Bool): return l == r
        case let (l as Int, r as Int): return l == r
        case let (l as Double, r as Double): return l == r
        case let (l as String, r as String): return l == r
        case let (l as [Any?], r as [Any?]):
            return l.map(AnyCodable.init) == r.map(AnyCodable.init)
        case let (l as [String: Any?], r as [String: Any?]):
            return l.mapValues(AnyCodable.init) == r.mapValues(AnyCodable.init)
        default: return false
        }
    }
}
