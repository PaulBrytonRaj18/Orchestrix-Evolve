import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    User,
    Session,
    Paper,
    Analysis,
    Summary,
    Synthesis,
    Citation,
    Note,
    Conflict,
    ScheduledDigest,
    DigestRun,
    Roadmap,
    generate_uuid,
    DigestFrequency,
)


class TestGenerateUuid:
    def test_returns_string(self):
        result = generate_uuid()
        assert isinstance(result, str)

    def test_returns_valid_uuid_format(self):
        result = generate_uuid()
        assert len(result) == 36
        assert result.count("-") == 4

    def test_returns_unique_values(self):
        values = [generate_uuid() for _ in range(100)]
        assert len(set(values)) == 100


class TestDigestFrequency:
    def test_has_daily(self):
        assert DigestFrequency.DAILY.value == "daily"

    def test_has_weekly(self):
        assert DigestFrequency.WEEKLY.value == "weekly"

    def test_has_biweekly(self):
        assert DigestFrequency.BIWEEKLY.value == "biweekly"

    def test_has_monthly(self):
        assert DigestFrequency.MONTHLY.value == "monthly"


class TestUserModel:
    def test_user_creation(self):
        user = User(
            email="test@example.com", username="testuser", hashed_password="hashed123"
        )
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.hashed_password == "hashed123"

    def test_user_defaults(self):
        user = User(
            email="test2@example.com", username="testuser2", hashed_password="hashed456"
        )
        assert user.id is None
        assert user.created_at is None

    def test_user_defaults(self):
        from models import User

        assert User.is_active.default.arg == True
        assert User.is_admin.default.arg == False


class TestSessionModel:
    def test_session_creation(self):
        session = Session(name="Test Session", query="machine learning")
        assert session.name == "Test Session"
        assert session.query == "machine learning"
        assert session.user_id is None

    def test_session_with_user(self):
        session = Session(
            name="User Session", query="deep learning", user_id="user-123"
        )
        assert session.user_id == "user-123"


class TestPaperModel:
    def test_paper_creation(self):
        paper = Paper(
            session_id="session-123",
            title="Test Paper",
            authors=["Author 1", "Author 2"],
            year=2024,
            abstract="This is a test abstract.",
            source="arxiv",
            citation_count=100,
        )
        assert paper.title == "Test Paper"
        assert paper.authors == ["Author 1", "Author 2"]
        assert paper.year == 2024
        assert paper.source == "arxiv"
        assert paper.citation_count == 100

    def test_paper_defaults(self):
        paper = Paper(session_id="session-123", title="Minimal Paper", source="unknown")
        assert paper.authors in [[], None]
        assert paper.year is None
        assert paper.abstract is None


class TestAnalysisModel:
    def test_analysis_creation(self):
        analysis = Analysis(
            session_id="session-123",
            analysis_type="publication_trend",
            data_json={"trend": "increasing"},
        )
        assert analysis.analysis_type == "publication_trend"
        assert analysis.data_json == {"trend": "increasing"}


class TestSummaryModel:
    def test_summary_creation(self):
        summary = Summary(
            paper_id="paper-123",
            abstract_compression="Compressed version",
            key_contributions="Key contributions here",
            methodology="Experimental",
            limitations="Limited scope",
        )
        assert summary.abstract_compression == "Compressed version"
        assert summary.key_contributions == "Key contributions here"


class TestCitationModel:
    def test_citation_creation(self):
        citation = Citation(
            paper_id="paper-123",
            apa="Author (2024). Title.",
            mla="Author. 'Title.'",
            ieee="A. Author, 'Title,' 2024.",
            chicago="Author. 'Title.' 2024.",
        )
        assert citation.apa == "Author (2024). Title."
        assert citation.mla == "Author. 'Title.'"
        assert citation.ieee == "A. Author, 'Title,' 2024."


class TestNoteModel:
    def test_note_creation(self):
        note = Note(paper_id="paper-123", content="My research notes")
        assert note.content == "My research notes"

    def test_note_default_content(self):
        note = Note(paper_id="paper-123", content="")
        assert note.content == ""


class TestConflictModel:
    def test_conflict_creation(self):
        conflict = Conflict(
            session_id="session-123",
            conflict_type="semantic_contradiction",
            severity="medium",
            title="Test Conflict",
            description="Description of conflict",
            analysis_insight="Analysis shows X",
            summarization_insight="Summary says Y",
        )
        assert conflict.conflict_type == "semantic_contradiction"
        assert conflict.severity == "medium"
        assert conflict.resolved in [False, None]
        assert conflict.resolution_notes is None


class TestScheduledDigestModel:
    def test_digest_creation(self):
        digest = ScheduledDigest(
            name="Weekly ML Papers",
            query="machine learning",
            frequency="weekly",
            notify_email="user@example.com",
        )
        assert digest.name == "Weekly ML Papers"
        assert digest.frequency == "weekly"
        assert digest.is_active in [True, None]

    def test_digest_defaults(self):
        digest = ScheduledDigest(name="Daily Update", query="AI", frequency="daily")
        assert digest.is_active in [True, None]
        assert digest.last_run_at is None
        assert digest.next_run_at is None


class TestDigestRunModel:
    def test_digest_run_creation(self):
        run = DigestRun(
            scheduled_digest_id="digest-123",
            query="machine learning",
            new_papers_count=5,
            new_paper_ids=["p1", "p2", "p3"],
            status="completed",
        )
        assert run.new_papers_count == 5
        assert len(run.new_paper_ids) == 3
        assert run.status == "completed"

    def test_digest_run_defaults(self):
        run = DigestRun(scheduled_digest_id="digest-123", query="test query")
        assert run.new_papers_count in [0, None]
        assert run.status in ["pending", None]


class TestRoadmapModel:
    def test_roadmap_creation(self):
        roadmap = Roadmap(
            session_id="session-123",
            foundational_papers_json=[{"paper_id": "1", "title": "Foundational Paper"}],
            gap_areas_json=[
                {
                    "question": "What about X?",
                    "severity": "high",
                    "evidence": "test",
                    "related_papers": [],
                }
            ],
            next_queries_json=[
                {
                    "query": "next research",
                    "rationale": "Fill gap",
                    "trigger_action": "discovery",
                    "expected_insight": "test",
                }
            ],
        )
        assert len(roadmap.foundational_papers_json) == 1
        assert len(roadmap.gap_areas_json) == 1
        assert len(roadmap.next_queries_json) == 1


class TestSynthesisModel:
    def test_synthesis_creation(self):
        synthesis = Synthesis(
            session_id="session-123",
            paper_ids=["p1", "p2"],
            content="Synthesized content of papers",
        )
        assert len(synthesis.paper_ids) == 2
        assert synthesis.content == "Synthesized content of papers"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
