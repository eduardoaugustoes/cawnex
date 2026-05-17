import XCTest

/// UI tests for the WaveReview screen.
///
/// Requires the app to honor a `--ui-test-wave-review-ready` launch argument
/// that constructs `WaveReviewScreen` directly with a seeded
/// `InMemoryWaveReviewService`. Add the hook in `CawnexApp.swift` (or
/// `ContentView.swift`) before running:
///
///     if CommandLine.arguments.contains("--ui-test-wave-review-ready") {
///         // seed InMemoryWaveReviewService from the bundled fixture and
///         // present WaveReviewScreen as the root.
///     }
final class WaveReviewUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    func test_happy_path_shows_6_advisors_and_approves() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-test-wave-review-ready"]
        app.launch()

        // All 6 advisor cards present
        for advisor in [
            "security", "architecture", "clarity", "performance", "ux", "cost",
        ] {
            XCTAssertTrue(
                app.otherElements["wave-review.advisor.\(advisor)"].exists,
                "Advisor card missing: \(advisor)"
            )
        }

        // Drill into Security investigation
        app.otherElements["wave-review.advisor.security.view-trace"].tap()
        XCTAssertTrue(
            app.otherElements["investigation-trace.tool-call.1"].waitForExistence(
                timeout: 2
            )
        )
        app.navigationBars.buttons.element(boundBy: 0).tap()

        // Approve flow — confirm sheet → confirm-approve button
        app.buttons["wave-review.approve"].tap()
        XCTAssertTrue(
            app.buttons["wave-review.confirm-approve"].waitForExistence(
                timeout: 2
            )
        )
        app.buttons["wave-review.confirm-approve"].tap()
    }
}
