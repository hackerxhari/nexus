"""
Verification script for Nexus custom Q&A and cross‑document retrieval.
Run with: python scripts/verify_custom_qa.py
"""

import json
import uuid

from fastapi.testclient import TestClient

# Import the FastAPI app (main entry point)
from api.main import app

client = TestClient(app)

def create_custom_qa(question_patterns, answer, category="general", priority=10, is_active=True):
    payload = {
        "question_patterns": question_patterns,
        "answer": answer,
        "category": category,
        "priority": priority,
        "is_active": is_active,
    }
    response = client.post("/admin/custom_qa", json=payload)
    assert response.status_code == 200, f"Create failed: {response.text}"
    return response.json()

def query(question):
    payload = {"question": question, "conversation_history": []}
    response = client.post("/query", json=payload)
    return response.json()

def main():
    # 1. Insert custom Q&A entry
    print("Creating custom Q&A entry...")
    entry = create_custom_qa(
        question_patterns=["what is my name?", "who are you?"],
        answer="My name is Nexus, the assistant."
    )
    print("Created entry:", entry)

    # 2. Query with paraphrased question
    paraphrase = "how will people address you?"
    print(f"Querying with paraphrase: '{paraphrase}'")
    resp = query(paraphrase)
    print("Response:")
    print(json.dumps(resp, indent=2))

    # 3. Demonstrate multi‑hop (requires two uploaded Excel files in DB).
    # In a real test you would upload two Excel files via the ingestion API,
    # then ask a question that needs data from both.
    # Here we simply show the intended query format.
    print("\n--- Multi‑hop demonstration ---")
    multi_question = "What is the name of the student with roll no 101 and what are their marks?"
    resp2 = query(multi_question)
    print("Response (may be empty if no data uploaded):")
    print(json.dumps(resp2, indent=2))

if __name__ == "__main__":
    main()
