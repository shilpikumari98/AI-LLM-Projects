# test_backend.py
# Verifies database connectivity, correctness of CRUD ops, API responses including new LLM fallback logic.

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from .main import app

client = TestClient(app)

def test_get_settings():
    response = client.get("/settings")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_insight_found():
    # Adjust 'max_connections' to a known existing setting with insight in your DB
    response = client.get("/insight/autovacuum_analyze_threshold")
    assert response.status_code == 200
    json_resp = response.json()
    assert json_resp["settings_name"] == "autovacuum_analyze_threshold"
    assert "Increase autovacuum_analyze_threshold" in json_resp["ai_insights"]

def test_get_insight_not_found():
    response = client.get("/insight/non_existent_setting")
    assert response.status_code == 404

def test_get_recommendations_found():
    response = client.get("/recommendations/autovacuum_analyze_threshold")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_recommendations_not_found():
    response = client.get("/recommendations/non_existent_setting")
    assert response.status_code == 404


# Tests for the new LLM fallback logic in /search endpoint

@patch("backend.app.llm_api.query_llm")
def test_search_llm_success(mock_query_llm):
    # Mock LLM to return valid answer
    mock_query_llm.return_value = ("This is a test LLM answer about autovacuum_analyze_threshold.", True)
    response = client.post("/search", json={"query": "Tell me about autovacuum_analyze_threshold"})
    
    assert response.status_code == 200
    data = response.json()
    assert "test LLM answer" in data["answer"]

@patch("backend.app.llm_api.query_llm")
def test_search_llm_failure_fallback(mock_query_llm):
    # Mock LLM to fail and fallback to local vector logic
    mock_query_llm.return_value = (None, False)
    
    test_query = "Explain autovacuum_vacuum_cost_limit"
    response = client.post("/search", json={"query": test_query})
    
    assert response.status_code == 200
    data = response.json()
    # Since the fallback uses real DB data, just verify answer is non-empty and not LLM text
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 10  # expecting meaningful fallback answer or message

@patch("backend.app.llm_api.query_llm")
def test_search_empty_query(mock_query_llm):
    # Empty query should not call LLM and return prompt
    response = client.post("/search", json={"query": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Please enter a query."
    mock_query_llm.assert_not_called()

@patch("backend.app.llm_api.query_llm")
def test_search_llm_returns_empty_string(mock_query_llm):
    # If LLM returns empty string, fallback should trigger
    mock_query_llm.return_value = ("", True)
    response = client.post("/search", json={"query": "Meaning of shared_buffers"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 10  # fallback answer expected
