from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, request_buckets


def test_chat_returns_citations_persists_history_and_records_telemetry() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            headers={"X-Request-ID": "integration-chat-001"},
            json={"query": "What is NovaTech's remote work allowance?"},
        )
        assert response.status_code == 200
        result = response.json()
        assert "three days per week" in result["answer"]
        assert result["citations"][0]["filename"] == "Remote_Work_Policy.txt"
        assert "document_search" in result["selected_tools"]
        assert response.headers["X-Request-ID"] == "integration-chat-001"

        history = client.get(f"/api/conversations/{result['conversation_id']}")
        assert history.status_code == 200
        assert [message["role"] for message in history.json()["messages"]] == ["user", "assistant"]

        monitoring = client.get("/api/monitoring/summary")
        assert monitoring.status_code == 200
        assert monitoring.json()["requests"] >= 1
        recent = client.get("/api/monitoring/requests").json()
        assert any(row["request_id"] == "integration-chat-001" for row in recent)


def test_sql_api_executes_read_only_query_and_returns_generated_sql() -> None:
    with TestClient(app) as client:
        overview = client.get("/api/database/overview")
        assert overview.status_code == 200
        assert overview.json()["customers"] == 120
        assert overview.json()["products"] == 20
        assert overview.json()["orders"] == 1200
        assert overview.json()["recognized_revenue"] == "5854000.00"

        query = client.post("/api/database/query", json={"question": "What was revenue in Q3 2025?"})
        assert query.status_code == 200
        assert query.json()["rows"][0]["revenue"] == 1497000
        assert "SELECT" in query.json()["sql"]


def test_api_validation_does_not_reflect_untrusted_input() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"query": "x" * 5000})

    assert response.status_code == 422
    assert "x" * 100 not in response.text
    assert response.json()["detail"] == "Invalid request parameters."


def test_rate_limit_is_applied_to_api_requests(monkeypatch) -> None:
    from app.main import settings

    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    request_buckets.clear()
    with TestClient(app) as client:
        assert client.get("/api/conversations").status_code == 200
        response = client.get("/api/conversations")
    request_buckets.clear()

    assert response.status_code == 429
    assert response.json()["request_id"]


def test_evaluation_runs_real_cases_and_reports_measured_metrics() -> None:
    with TestClient(app) as client:
        cases = client.get("/api/evaluations/cases")
        assert cases.status_code == 200
        assert cases.json()["count"] >= 40

        run = client.post("/api/evaluations/runs", json={"limit": 2})

    assert run.status_code == 201
    result = run.json()
    assert result["status"] == "completed"
    assert result["total_cases"] == 2
    assert result["summary"]["answer_correctness"] is not None
    assert len(result["results"]) == 2


def test_document_upload_indexes_searchable_text_and_rejects_duplicates() -> None:
    content = f"Orion retention is 91 days for approved archives. Reference {uuid4()}."
    with TestClient(app) as client:
        upload = client.post(
            "/api/documents",
            files={"file": ("integration_policy.txt", content.encode(), "text/plain")},
        )
        assert upload.status_code == 201
        search = client.post(
            "/api/documents/search",
            json={"query": "How long is Orion retention for approved archives?", "limit": 3},
        )
        duplicate = client.post(
            "/api/documents",
            files={"file": ("another_name.txt", content.encode(), "text/plain")},
        )
        invalid = client.post(
            "/api/documents",
            files={"file": ("unsafe.exe", b"not an allowed document", "application/octet-stream")},
        )

    assert upload.json()["status"] == "indexed"
    assert search.status_code == 200
    assert search.json()["citations"][0]["filename"] == "integration_policy.txt"
    assert duplicate.status_code == 409
    assert invalid.status_code == 422
