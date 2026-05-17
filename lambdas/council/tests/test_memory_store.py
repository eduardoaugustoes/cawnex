"""Tests for advisor memory store."""

import pytest

from council._blackboard import Blackboard
from council.enums import AdvisorType
from council.memory_store import CouncilMemoryStore, _prune_memory, _token_estimate


@pytest.fixture
def blackboard(dynamodb_table, events_table):  # type: ignore[no-untyped-def]
    return Blackboard(dynamodb_table, events_table=events_table)


@pytest.fixture
def memory_store(blackboard: Blackboard) -> CouncilMemoryStore:
    return CouncilMemoryStore(blackboard)


class TestReadWriteMemory:
    def test_read_empty_returns_empty_string(
        self, memory_store: CouncilMemoryStore
    ) -> None:
        result = memory_store.read_advisor_memory("t1", "p1", AdvisorType.SECURITY)
        assert result == ""

    def test_write_and_read(self, memory_store: CouncilMemoryStore) -> None:
        memory_store.write_advisor_memory(
            "t1", "p1", AdvisorType.SECURITY, "Rate limiting is important"
        )
        result = memory_store.read_advisor_memory("t1", "p1", AdvisorType.SECURITY)
        assert result == "Rate limiting is important"

    def test_overwrite(self, memory_store: CouncilMemoryStore) -> None:
        memory_store.write_advisor_memory(
            "t1", "p1", AdvisorType.ARCHITECTURE, "First version"
        )
        memory_store.write_advisor_memory(
            "t1", "p1", AdvisorType.ARCHITECTURE, "Updated version"
        )
        result = memory_store.read_advisor_memory("t1", "p1", AdvisorType.ARCHITECTURE)
        assert result == "Updated version"


class TestAppendLearning:
    def test_append_to_empty(self, memory_store: CouncilMemoryStore) -> None:
        result = memory_store.append_advisor_learning(
            "t1", "p1", AdvisorType.SECURITY, "Auth endpoints need rate limiting"
        )
        assert "Auth endpoints need rate limiting" in result
        assert "Security" in result

    def test_append_to_existing(self, memory_store: CouncilMemoryStore) -> None:
        memory_store.append_advisor_learning(
            "t1", "p1", AdvisorType.SECURITY, "First learning"
        )
        result = memory_store.append_advisor_learning(
            "t1", "p1", AdvisorType.SECURITY, "Second learning"
        )
        assert "First learning" in result
        assert "Second learning" in result

    def test_persists_to_dynamodb(self, memory_store: CouncilMemoryStore) -> None:
        memory_store.append_advisor_learning(
            "t1", "p1", AdvisorType.PERFORMANCE, "Add DB indexes"
        )
        stored = memory_store.read_advisor_memory(
            "t1", "p1", AdvisorType.PERFORMANCE
        )
        assert "Add DB indexes" in stored


class TestReadAllAdvisorMemories:
    def test_returns_all(self, memory_store: CouncilMemoryStore) -> None:
        memory_store.write_advisor_memory(
            "t1", "p1", AdvisorType.SECURITY, "sec memory"
        )
        memory_store.write_advisor_memory(
            "t1", "p1", AdvisorType.ARCHITECTURE, "qual memory"
        )
        result = memory_store.read_all_advisor_memories("t1", "p1")
        assert result["security"] == "sec memory"
        assert result["architecture"] == "qual memory"
        assert "performance" not in result

    def test_empty_project_returns_empty_dict(
        self, memory_store: CouncilMemoryStore
    ) -> None:
        result = memory_store.read_all_advisor_memories("t1", "p1")
        assert result == {}


class TestReadOrgStandards:
    def test_reads_org_standards(self, memory_store: CouncilMemoryStore) -> None:
        # Write org standards to tenant-level PK
        memory_store._blackboard.write_item(
            {
                "PK": "T#t1",
                "SK": "MEM#org#standards",
                "content": "Use TypeScript strict mode. All APIs must have rate limiting.",
                "entityType": "Memory",
            }
        )
        result = memory_store.read_org_standards("t1")
        assert "TypeScript strict mode" in result
        assert "rate limiting" in result

    def test_empty_org_returns_empty_string(
        self, memory_store: CouncilMemoryStore
    ) -> None:
        result = memory_store.read_org_standards("t1")
        assert result == ""


class TestReadProjectContext:
    def test_reads_all_project_memories(
        self, memory_store: CouncilMemoryStore
    ) -> None:
        pk = "T#t1#P#p1"
        memory_store._blackboard.write_item(
            {
                "PK": pk,
                "SK": "MEM#project#conventions",
                "content": "FastAPI + DynamoDB single table",
                "entityType": "Memory",
            }
        )
        memory_store._blackboard.write_item(
            {
                "PK": pk,
                "SK": "MEM#project#wave_reflections",
                "content": "- Wave w01: all 3 MVIs shipped",
                "entityType": "Memory",
            }
        )
        result = memory_store.read_project_context("t1", "p1")
        assert "Conventions" in result
        assert "FastAPI" in result
        assert "Wave Reflections" in result
        assert "all 3 MVIs shipped" in result

    def test_empty_project_returns_empty(
        self, memory_store: CouncilMemoryStore
    ) -> None:
        result = memory_store.read_project_context("t1", "p1")
        assert result == ""


class TestPruneMemory:
    def test_under_budget_unchanged(self) -> None:
        content = "# Header\n\n- Learning 1\n- Learning 2"
        result = _prune_memory(content)
        assert result == content

    def test_over_budget_drops_oldest(self) -> None:
        # Create content that exceeds 2000 tokens (~8000 chars)
        header = "# Security Advisor Learnings\n\n"
        learnings = [f"- Learning number {i}: " + "x" * 200 for i in range(50)]
        content = header + "\n".join(learnings)

        assert _token_estimate(content) > 2000

        result = _prune_memory(content)
        assert _token_estimate(result) <= 2000
        # Should keep header and recent learnings
        assert "Security Advisor Learnings" in result
        # Latest learning should still be there
        assert "Learning number 49" in result
        # Oldest should be gone
        assert "Learning number 0" not in result


class TestTokenEstimate:
    def test_empty(self) -> None:
        assert _token_estimate("") == 0

    def test_short(self) -> None:
        assert _token_estimate("hello world") == 2  # 11 // 4

    def test_longer(self) -> None:
        assert _token_estimate("a" * 100) == 25
