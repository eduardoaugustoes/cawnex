import Foundation

struct TaskCounts: Equatable {
    let done: Int
    let active: Int
    let refined: Int
    let draft: Int

    var total: Int { done + active + refined + draft }

    var summary: String {
        "Tasks · \(done) done · \(active) active · \(refined) refined · \(draft) draft"
    }
}
