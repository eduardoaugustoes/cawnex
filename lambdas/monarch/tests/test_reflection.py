"""Tests for wave reflection — learning extraction from delivered waves."""

from monarch.reflection import (
    _prune_reflections,
    _token_estimate,
    reflect_on_wave,
    save_wave_reflection,
)


class TestReflectOnWave:
    def test_all_shipped_generates_success_learning(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w01"

        # Seed MVI snapshots
        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01",
                "level": "murder",
                "status": "shipped",
                "name": "Auth MVI",
                "mvi_id": "01",
            }
        )
        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m02",
                "level": "murder",
                "status": "shipped",
                "name": "API MVI",
                "mvi_id": "02",
            }
        )

        learnings = reflect_on_wave(dynamodb_table, pk, wave_id, {})

        assert any("all 2 MVIs shipped" in l for l in learnings)

    def test_failed_mvi_generates_failure_learning(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w02"

        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01",
                "level": "murder",
                "status": "shipped",
                "name": "Auth MVI",
            }
        )
        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m02",
                "level": "murder",
                "status": "failed",
                "name": "Payment MVI",
            }
        )

        learnings = reflect_on_wave(dynamodb_table, pk, wave_id, {})

        assert any("failed" in l.lower() and "Payment" in l for l in learnings)

    def test_cost_analysis(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w03"

        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01",
                "level": "murder",
                "status": "shipped",
            }
        )
        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01#cr_impl_01",
                "level": "crow",
                "crow_type": "implementer",
                "cost": {"credits": 5000, "tokens_in": 1000, "tokens_out": 500},
            }
        )
        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01#cr_review_01",
                "level": "crow",
                "crow_type": "reviewer",
                "cost": {"credits": 3000, "tokens_in": 800, "tokens_out": 200},
            }
        )

        learnings = reflect_on_wave(dynamodb_table, pk, wave_id, {})

        assert any("8000 credits" in l for l in learnings)

    def test_check_failure_patterns(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w04"

        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01",
                "level": "murder",
                "status": "shipped",
                "deterministic_checks": {
                    "passed": ["tests_pass"],
                    "failed": [],
                    "warnings": ["coverage_no_drop"],
                },
            }
        )
        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m02",
                "level": "murder",
                "status": "shipped",
                "deterministic_checks": {
                    "passed": ["tests_pass"],
                    "failed": [],
                    "warnings": ["coverage_no_drop", "lint_passes"],
                },
            }
        )

        learnings = reflect_on_wave(dynamodb_table, pk, wave_id, {})

        assert any("coverage_no_drop" in l for l in learnings)

    def test_council_conditions_captured(self) -> None:
        # No DynamoDB needed — council_decision is passed directly
        import os

        import boto3

        endpoint_url = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        # Use the fixture table name pattern
        table_name = "cawnex-monarch-reflect-test"
        try:
            existing = dynamodb.Table(table_name)
            existing.delete()
            existing.wait_until_not_exists()
        except Exception:
            pass

        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        pk = "T#t1#P#p1"
        table.put_item(
            Item={
                "PK": pk,
                "SK": "S#w05#m01",
                "level": "murder",
                "status": "shipped",
            }
        )

        council_decision = {
            "conditions": ["Rate limiting must be added before next wave"],
            "dissent_record": {"security": "Wanted to block payment endpoint"},
        }

        learnings = reflect_on_wave(table, pk, "w05", council_decision)

        assert any("Rate limiting" in l for l in learnings)
        assert any("security" in l.lower() for l in learnings)

        table.delete()

    def test_fixer_cycle_warning(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w06"

        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01",
                "level": "murder",
                "status": "shipped",
            }
        )
        # 3 fixer crows = high fixer activity
        for i in range(3):
            dynamodb_table.put_item(
                Item={
                    "PK": pk,
                    "SK": f"S#{wave_id}#m01#cr_fix_0{i}",
                    "level": "crow",
                    "crow_type": "fixer",
                    "cost": {"credits": 1000},
                }
            )

        learnings = reflect_on_wave(dynamodb_table, pk, wave_id, {})

        assert any("fixer" in l.lower() for l in learnings)

    def test_empty_wave_returns_no_learnings(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        learnings = reflect_on_wave(dynamodb_table, "T#t1#P#p1", "w99", {})
        assert learnings == []

    def test_max_five_learnings(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w07"

        # Set up conditions that trigger many learnings
        dynamodb_table.put_item(
            Item={
                "PK": pk,
                "SK": f"S#{wave_id}#m01",
                "level": "murder",
                "status": "failed",
                "name": "Failed MVI",
                "deterministic_checks": {
                    "passed": [],
                    "failed": ["tests_pass"],
                    "warnings": ["coverage_no_drop", "lint_passes"],
                },
            }
        )
        for i in range(4):
            dynamodb_table.put_item(
                Item={
                    "PK": pk,
                    "SK": f"S#{wave_id}#m01#cr_fix_0{i}",
                    "level": "crow",
                    "crow_type": "fixer",
                    "cost": {"credits": 1000},
                }
            )

        council = {
            "conditions": ["Add rate limiting"],
            "dissent_record": {"security": "Blocked", "quality": "Low coverage"},
        }

        learnings = reflect_on_wave(dynamodb_table, pk, wave_id, council)

        assert len(learnings) <= 5


class TestSaveWaveReflection:
    def test_saves_to_dynamodb(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        save_wave_reflection(
            dynamodb_table, pk, ["Learning 1", "Learning 2"]
        )

        item = dynamodb_table.get_item(
            Key={"PK": pk, "SK": "MEM#project#wave_reflections"}
        ).get("Item")
        assert item is not None
        assert "Learning 1" in item["content"]
        assert "Learning 2" in item["content"]
        assert item["entityType"] == "Memory"

    def test_appends_to_existing(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        save_wave_reflection(dynamodb_table, pk, ["First wave learning"])
        save_wave_reflection(dynamodb_table, pk, ["Second wave learning"])

        item = dynamodb_table.get_item(
            Key={"PK": pk, "SK": "MEM#project#wave_reflections"}
        ).get("Item")
        assert "First wave learning" in item["content"]
        assert "Second wave learning" in item["content"]

    def test_empty_learnings_noop(
        self, dynamodb_table,  # type: ignore[no-untyped-def]
    ) -> None:
        pk = "T#t1#P#p1"
        save_wave_reflection(dynamodb_table, pk, [])

        item = dynamodb_table.get_item(
            Key={"PK": pk, "SK": "MEM#project#wave_reflections"}
        ).get("Item")
        assert item is None


class TestPruneReflections:
    def test_under_budget_unchanged(self) -> None:
        content = "# Wave Reflection Log\n\n- [2026-04-09] Learning 1"
        assert _prune_reflections(content) == content

    def test_over_budget_drops_oldest(self) -> None:
        header = "# Wave Reflection Log\n\n"
        entries = [
            f"- [2026-04-{i:02d}] " + "x" * 200 for i in range(1, 100)
        ]
        content = header + "\n".join(entries)

        assert _token_estimate(content) > 4000

        result = _prune_reflections(content)
        assert _token_estimate(result) <= 4000
        assert "Wave Reflection Log" in result
        # Most recent should survive
        assert "2026-04-99" in result
