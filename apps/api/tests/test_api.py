from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mock_itinerary() -> None:
    response = client.get("/api/itinerary-versions/mock-wuhan-3-days")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "武汉"
    assert len(payload["days"]) == 3
    assert payload["plannerTrace"]["provider"] == "mock"


def test_send_message_returns_completed_job() -> None:
    conversation = client.post("/api/conversations", json={"city": "武汉"}).json()
    response = client.post(
        f"/api/conversations/{conversation['conversationId']}/messages",
        json={"content": "我想去武汉玩三天，喜欢历史文化和美食。"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["itineraryVersionId"] == "mock-wuhan-3-days"
