from fastapi.testclient import TestClient

from backend.main import app


def test_get_endpoints():
    with TestClient(app) as client:
        account_id = client.get("/api/accounts").json()[0]["account_id"]
        security_id = client.get("/api/securities").json()[0]["security_id"]
        paths = [
            "/api/health", "/api/summary", "/api/accounts", "/api/securities",
            f"/api/portfolio/{account_id}", "/api/transactions",
            "/api/analytics/top-customers", "/api/analytics/most-traded",
            "/api/analytics/daily-volume", "/api/analytics/performance",
            f"/api/analytics/returns/{security_id}", "/api/analytics/fees",
            "/api/analytics/dividends",
        ]
        for path in paths:
            assert client.get(path).status_code == 200, path


def test_transactions_pagination():
    with TestClient(app) as client:
        first = client.get("/api/transactions?offset=0&limit=25").json()
        second = client.get("/api/transactions?offset=25&limit=25").json()
    assert first["total"] == second["total"]
    assert set(row["transaction_id"] for row in first["rows"]).isdisjoint(
        row["transaction_id"] for row in second["rows"]
    )


def test_missing_portfolio_returns_404():
    with TestClient(app) as client:
        assert client.get("/api/portfolio/99999999").status_code == 404


def test_invalid_transaction_type_returns_422():
    with TestClient(app) as client:
        assert client.get("/api/transactions?transaction_type=INVALID").status_code == 422
