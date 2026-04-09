"""Tests for project maturity stage inference."""

from monarch.maturity import assess_maturity


class TestAssessMaturity:
    def test_mvp_stays_mvp_with_no_waves(self) -> None:
        assert assess_maturity("mvp", waves_delivered=0, mvis_shipped=0) == "mvp"

    def test_mvp_stays_mvp_below_threshold(self) -> None:
        assert assess_maturity("mvp", waves_delivered=2, mvis_shipped=5) == "mvp"

    def test_mvp_advances_to_growth(self) -> None:
        assert assess_maturity("mvp", waves_delivered=3, mvis_shipped=8) == "growth"

    def test_mvp_needs_both_waves_and_mvis(self) -> None:
        # Enough waves but not enough MVIs
        assert assess_maturity("mvp", waves_delivered=5, mvis_shipped=3) == "mvp"
        # Enough MVIs but not enough waves
        assert assess_maturity("mvp", waves_delivered=1, mvis_shipped=20) == "mvp"

    def test_growth_advances_to_scale(self) -> None:
        assert (
            assess_maturity(
                "growth",
                waves_delivered=8,
                mvis_shipped=25,
                avg_coverage=75.0,
            )
            == "scale"
        )

    def test_growth_blocked_by_low_coverage(self) -> None:
        assert (
            assess_maturity(
                "growth",
                waves_delivered=10,
                mvis_shipped=30,
                avg_coverage=50.0,
            )
            == "growth"
        )

    def test_growth_advances_without_coverage_data(self) -> None:
        # If no coverage data, coverage threshold is not checked
        assert (
            assess_maturity(
                "growth",
                waves_delivered=8,
                mvis_shipped=25,
                avg_coverage=None,
            )
            == "scale"
        )

    def test_scale_advances_to_mature(self) -> None:
        assert (
            assess_maturity(
                "scale",
                waves_delivered=15,
                mvis_shipped=50,
                avg_coverage=85.0,
                council_rejection_rate=0.05,
            )
            == "mature"
        )

    def test_scale_blocked_by_high_rejection_rate(self) -> None:
        assert (
            assess_maturity(
                "scale",
                waves_delivered=20,
                mvis_shipped=60,
                avg_coverage=90.0,
                council_rejection_rate=0.2,
            )
            == "scale"
        )

    def test_mature_stays_mature(self) -> None:
        assert (
            assess_maturity(
                "mature",
                waves_delivered=100,
                mvis_shipped=500,
            )
            == "mature"
        )

    def test_only_advances_one_stage(self) -> None:
        # Even with enough signals for "scale", mvp only goes to growth
        result = assess_maturity(
            "mvp",
            waves_delivered=20,
            mvis_shipped=100,
            avg_coverage=90.0,
        )
        assert result == "growth"

    def test_never_regresses(self) -> None:
        # Growth with zero signals stays growth (doesn't go back to mvp)
        assert assess_maturity("growth", waves_delivered=0, mvis_shipped=0) == "growth"
