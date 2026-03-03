import pytest


async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "flagdrop"
    assert "version" in data


async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "FlagDrop"
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/docs"
