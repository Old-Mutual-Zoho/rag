from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_general_information_fetch():
    from src.api.main import app
    client = TestClient(app)
    response = client.get("/api/v1/general-information", params={"session_id": "any", "product": "motor_private"})
    print("General Information Response:", response.json())
    assert response.status_code == 200
    info = response.json()
    assert info["definition"] == "Motor Private insurance covers privately owned vehicles against risks such as theft, accident, and fire."
    assert "Comprehensive coverage for accidents" in info["benefits"]
    assert info["eligibility"] == "Available to individuals with privately registered vehicles."
