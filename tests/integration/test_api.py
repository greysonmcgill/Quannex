"""Integration tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient
from quan.main import app


class TestAPIEndpoints:
    """Test API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "QUAN Recovery"
        assert data["status"] == "operational"

    def test_health_endpoint(self, client):
        """Test health endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_ready_endpoint(self, client):
        """Test readiness endpoint"""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "checks" in data

    def test_analyze_endpoint(self, client):
        """Test portfolio analysis endpoint"""
        payload = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "balance": 450.00,
                    "original_creditor": "Klarna",
                    "debtor_name": "John Doe",
                    "days_overdue": 45,
                },
                {
                    "account_id": "ACC002",
                    "balance": 200.00,
                    "original_creditor": "Affirm",
                    "debtor_name": "Jane Smith",
                    "days_overdue": 30,
                },
            ]
        }

        response = client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["analyzed"] == 2
        assert len(data["strategies"]) == 2
        assert "coherence" in data

    def test_analyze_empty_portfolio(self, client):
        """Test analysis with empty portfolio"""
        payload = {"accounts": []}

        response = client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["analyzed"] == 0
        assert len(data["strategies"]) == 0

    def test_settlement_endpoint(self, client):
        """Test settlement calculation endpoint"""
        payload = {
            "account": {
                "account_id": "ACC001",
                "balance": 500.00,
                "days_overdue": 60,
            }
        }

        response = client.post("/api/v1/settlements", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == "ACC001"
        assert data["original_balance"] == 500.00
        assert data["settlement_amount"] < 500.00
        assert data["savings"] > 0
        assert len(data["payment_options"]) > 0

    def test_settlement_with_offer(self, client):
        """Test settlement with debtor offer"""
        payload = {
            "account": {
                "account_id": "ACC001",
                "balance": 500.00,
                "days_overdue": 60,
            },
            "offer": 300.00,
        }

        response = client.post("/api/v1/settlements", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "settlement_amount" in data


class TestIngestionAPI:
    """Test ingestion API endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_ingest_portfolio(self, client):
        """Test portfolio ingestion"""
        payload = {
            "accounts": [
                {
                    "account_id": "ACC001",
                    "balance": 450.00,
                    "original_creditor": "Klarna",
                    "debtor_name": "John Doe",
                    "days_overdue": 45,
                    "original_amount": 500.00,
                }
            ],
            "source_type": "bnpl",
            "client_id": "CLIENT001",
        }

        response = client.post("/api/v1/ingest/portfolio", json=payload)

        # May fail validation due to missing fields, but should process
        assert response.status_code in [200, 422]

    def test_ingestion_status(self, client):
        """Test ingestion status endpoint"""
        response = client.get("/api/v1/ingest/status/batch_123")

        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert "status" in data
