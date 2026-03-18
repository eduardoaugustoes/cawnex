import Foundation

/// Decodes a value that may arrive as either a JSON number or a JSON string.
/// DynamoDB serializes numbers as strings in some contexts, so API responses
/// may contain `"42"` instead of `42`.
struct FlexibleInt: Decodable, Equatable {
    let value: Int

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let intVal = try? container.decode(Int.self) {
            value = intVal
        } else if let strVal = try? container.decode(String.self), let parsed = Int(strVal) {
            value = parsed
        } else {
            value = 0
        }
    }
}

struct FlexibleDouble: Decodable, Equatable {
    let value: Double

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let dblVal = try? container.decode(Double.self) {
            value = dblVal
        } else if let strVal = try? container.decode(String.self), let parsed = Double(strVal) {
            value = parsed
        } else {
            value = 0
        }
    }
}
