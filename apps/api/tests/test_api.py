from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_no_mock_itinerary() -> None:
    """mock 行程已删除。规划链路做好之前，查不到任何行程。"""
    assert client.get("/api/itinerary-versions/mock-wuhan-3-days").status_code == 404
    assert client.get("/api/share/wuhan-3-days-mock").status_code == 404


def test_planning_not_implemented_yet() -> None:
    conversation = client.post("/api/conversations", json={"city": "武汉"}).json()
    response = client.post(
        f"/api/conversations/{conversation['conversationId']}/messages",
        json={"content": "我想去武汉玩三天，喜欢历史文化和美食。"},
    )
    assert response.status_code == 501
