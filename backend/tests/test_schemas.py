import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    SessionCreate,
    SessionResponse,
    SessionFullResponse,
    PaperWithDetails,
    AnalysisResponse,
    SummaryResponse,
    CitationResponse,
    NoteCreate,
    NoteResponse,
    ConflictResponse,
    ConflictResolve,
    ConflictDetectionResult,
    ScheduledDigestCreate,
    ScheduledDigestResponse,
    DigestRunResponse,
    RoadmapResponse,
    OrchestrateResponse,
    HealthResponse,
)


class TestUserSchemas:
    def test_user_create_valid(self):
        user = UserCreate(
            email="test@example.com",
            username="testuser",
            password="securepassword123",
            confirm_password="securepassword123",
        )
        assert user.email == "test@example.com"
        assert user.username == "testuser"

    def test_user_create_stores_passwords(self):
        user = UserCreate(
            email="test@example.com",
            username="testuser",
            password="password1",
            confirm_password="password2",
        )
        assert user.password == "password1"
        assert user.confirm_password == "password2"

    def test_user_login_valid(self):
        login = UserLogin(email="user@example.com", password="mypassword")
        assert login.email == "user@example.com"

    def test_user_response(self):
        now = datetime.now()
        response = UserResponse(
            id="user-123",
            email="user@example.com",
            username="testuser",
            is_active=True,
            is_admin=False,
            created_at=now,
        )
        assert response.id == "user-123"
        assert response.is_active == True

    def test_user_update_partial(self):
        update = UserUpdate(username="newusername")
        assert update.username == "newusername"
        assert update.email is None
        assert update.password is None

    def test_user_update_password_only(self):
        update = UserUpdate(password="newpassword")
        assert update.password == "newpassword"
        assert update.username is None


class TestSessionSchemas:
    def test_session_create(self):
        session = SessionCreate(name="My Research", query="machine learning")
        assert session.name == "My Research"
        assert session.query == "machine learning"

    def test_session_response(self):
        now = datetime.now()
        response = SessionResponse(
            id="session-123",
            name="Test Session",
            query="AI research",
            created_at=now,
            updated_at=now,
            paper_count=10,
        )
        assert response.paper_count == 10

    def test_session_full_response(self):
        now = datetime.now()
        response = SessionFullResponse(
            id="session-456",
            name="Full Session",
            query="deep learning",
            created_at=now,
            updated_at=now,
            papers=[],
            analyses=[],
            syntheses=[],
            conflicts=[],
        )
        assert len(response.papers) == 0
        assert len(response.conflicts) == 0


class TestPaperSchemas:
    def test_paper_with_details(self):
        now = datetime.now()
        paper = PaperWithDetails(
            id="paper-123",
            session_id="session-123",
            title="Research Paper",
            authors=["Author 1", "Author 2"],
            year=2024,
            source="arxiv",
            created_at=now,
            updated_at=now,
        )
        assert paper.title == "Research Paper"
        assert len(paper.authors) == 2
        assert paper.summary is None
        assert paper.notes == []

    def test_paper_optional_fields(self):
        now = datetime.now()
        paper = PaperWithDetails(
            id="paper-456",
            session_id="session-123",
            title="Minimal Paper",
            authors=[],
            source="arxiv",
            created_at=now,
            updated_at=now,
        )
        assert paper.year is None
        assert paper.abstract is None
        assert paper.citation_count is None


class TestAnalysisSchemas:
    def test_analysis_response(self):
        now = datetime.now()
        analysis = AnalysisResponse(
            id="analysis-123",
            session_id="session-123",
            analysis_type="publication_trend",
            data_json={"years": [2020, 2021, 2022]},
            created_at=now,
            updated_at=now,
        )
        assert analysis.analysis_type == "publication_trend"
        assert "years" in analysis.data_json


class TestSummarySchemas:
    def test_summary_response(self):
        now = datetime.now()
        summary = SummaryResponse(
            id="summary-123",
            paper_id="paper-123",
            abstract_compression="Compressed abstract",
            key_contributions="Key contributions",
            methodology="Methodology used",
            limitations="Limitations",
            created_at=now,
            updated_at=now,
        )
        assert summary.abstract_compression == "Compressed abstract"

    def test_summary_optional_fields(self):
        now = datetime.now()
        summary = SummaryResponse(
            id="summary-456", paper_id="paper-456", created_at=now, updated_at=now
        )
        assert summary.abstract_compression is None
        assert summary.key_contributions is None


class TestCitationSchemas:
    def test_citation_response(self):
        now = datetime.now()
        citation = CitationResponse(
            id="citation-123",
            paper_id="paper-123",
            apa="Author (2024). Title.",
            mla="Author. 'Title.'",
            ieee="A. Author, 'Title,' 2024.",
            chicago="Author. 'Title.' 2024.",
            created_at=now,
            updated_at=now,
        )
        assert citation.apa is not None
        assert citation.mla is not None


class TestNoteSchemas:
    def test_note_create(self):
        note = NoteCreate(content="My research notes")
        assert note.content == "My research notes"

    def test_note_response(self):
        now = datetime.now()
        note = NoteResponse(
            id="note-123",
            paper_id="paper-123",
            content="Note content",
            created_at=now,
            updated_at=now,
        )
        assert note.content == "Note content"


class TestConflictSchemas:
    def test_conflict_response(self):
        now = datetime.now()
        conflict = ConflictResponse(
            id="conflict-123",
            session_id="session-123",
            conflict_type="semantic_contradiction",
            severity="high",
            title="Test Conflict",
            description="Description",
            analysis_insight="Analysis insight",
            summarization_insight="Summary insight",
            resolved=False,
            resolution_notes=None,
            created_at=now,
            updated_at=now,
        )
        assert conflict.conflict_type == "semantic_contradiction"
        assert conflict.resolved == False

    def test_conflict_resolve(self):
        resolve = ConflictResolve(resolution_notes="Resolved by manual review")
        assert resolve.resolution_notes == "Resolved by manual review"

    def test_conflict_detection_result(self):
        result = ConflictDetectionResult(
            conflicts=[{"type": "contradiction", "severity": "medium"}],
            summary="2 conflicts detected",
        )
        assert len(result.conflicts) == 1


class TestDigestSchemas:
    def test_digest_create_valid_frequencies(self):
        for freq in ["daily", "weekly", "biweekly", "monthly"]:
            digest = ScheduledDigestCreate(
                name="Test Digest", query="AI", frequency=freq
            )
            assert digest.frequency == freq

    def test_digest_response(self):
        now = datetime.now()
        response = ScheduledDigestResponse(
            id="digest-123",
            name="Weekly AI",
            query="artificial intelligence",
            frequency="weekly",
            is_active=True,
            notify_email="user@example.com",
            created_at=now,
            updated_at=now,
        )
        assert response.frequency == "weekly"

    def test_digest_run_response(self):
        now = datetime.now()
        run = DigestRunResponse(
            id="run-123",
            scheduled_digest_id="digest-123",
            query="ML",
            new_papers_count=5,
            new_paper_ids=["p1", "p2", "p3"],
            status="completed",
            created_at=now,
            updated_at=now,
        )
        assert run.new_papers_count == 5
        assert run.status == "completed"


class TestRoadmapSchemas:
    def test_roadmap_response(self):
        response = RoadmapResponse(
            foundational_papers=[
                {
                    "paper_id": "1",
                    "title": "Paper 1",
                    "reason": "High citations",
                    "citation_count": 100,
                    "year": 2020,
                    "priority": 1,
                }
            ],
            gap_areas=[
                {
                    "question": "Gap question?",
                    "evidence": "Limited research",
                    "related_papers": [],
                    "severity": "high",
                }
            ],
            next_query_suggestions=[
                {
                    "query": "next step",
                    "rationale": "Follow up",
                    "trigger_action": "discovery",
                    "expected_insight": "New insights",
                }
            ],
        )
        assert len(response.foundational_papers) == 1
        assert len(response.gap_areas) == 1

    def test_orchestrate_response(self):
        now = datetime.now()
        response = OrchestrateResponse(
            papers=[],
            analysis={"publication_trend": []},
            citations=[],
            summaries=[],
            trace=[{"agent": "test", "status": "done"}],
            conflicts=[],
        )
        assert "publication_trend" in response.analysis
        assert len(response.trace) == 1


class TestHealthResponse:
    def test_health_ok(self):
        health = HealthResponse(status="ok")
        assert health.status == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
