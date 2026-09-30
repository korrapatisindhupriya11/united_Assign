def test_health_reports_the_loaded_handbook(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["documents"] == 8
    assert body["chunks"] > 8
    assert body["generative"] is False


def test_chat_contract_and_history(client):
    response = client.post("/api/chat", json={"message": "Find information about onboarding steps."})
    assert response.status_code == 200
    body = response.json()
    for field in (
        "session_id",
        "message_id",
        "answer",
        "sources",
        "confidence",
        "refused",
        "degraded",
        "disclaimer",
        "model",
        "tools",
        "explain",
        "latency_ms",
    ):
        assert field in body
    assert body["refused"] is False
    assert body["sources"][0]["document_id"] == "onboarding"
    assert "People Operations" in body["answer"] or body["sources"][0]["owner"] == "People Operations"

    history = client.get(f"/api/sessions/{body['session_id']}")
    assert history.status_code == 200
    assert [item["role"] for item in history.json()["messages"]] == ["user", "assistant"]

    missing = client.get("/api/sessions/missing-session-id")
    assert missing.status_code == 404

    cleared = client.delete(f"/api/sessions/{body['session_id']}")
    assert cleared.status_code == 204
    assert client.get(f"/api/sessions/{body['session_id']}").status_code == 404


def test_blank_question_is_rejected(client):
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 422


def test_feedback_is_stored_and_summarized(client):
    chat = client.post("/api/chat", json={"message": "What is the escalation process for incidents?"})
    body = chat.json()
    saved = client.post(
        "/api/feedback",
        json={
            "session_id": body["session_id"],
            "message_id": body["message_id"],
            "rating": "down",
            "reason": "incomplete",
            "comment": "Missed the review step.",
        },
    )
    assert saved.status_code == 200
    summary = client.get("/api/governance/summary")
    assert summary.json()["down"] == 1
    assert summary.json()["reasons"]["incomplete"] == 1

    unknown = client.post(
        "/api/feedback",
        json={
            "session_id": body["session_id"],
            "message_id": "not-a-real-message",
            "rating": "up",
        },
    )
    assert unknown.status_code == 404


def test_homepage_has_the_question_field(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Ask about a Harborline policy" in page.text
    assert 'id="question"' in page.text
