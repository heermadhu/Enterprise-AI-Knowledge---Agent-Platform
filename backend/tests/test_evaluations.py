from app.routers.evaluations import _case_result


def test_numeric_evaluation_keyword_matches_rounded_answer() -> None:
    case = {
        "id": "numeric",
        "category": "calculation",
        "question": "Calculate a percentage.",
        "keywords": ["25.57"],
        "tools": ["calculator"],
    }
    result = {
        "answer": "Calculation result: 25.5722582849",
        "citations": [],
        "selected_tools": ["calculator"],
        "sql": None,
        "total_latency_ms": 12.0,
        "token_usage": None,
    }

    scored = _case_result(case, result)

    assert scored["answer_correctness"] == 1.0


def test_retrieval_relevance_measures_expected_source_precision() -> None:
    case = {
        "id": "retrieval",
        "category": "rag",
        "question": "What is the remote work allowance?",
        "keywords": ["three days per week"],
        "sources": ["Remote_Work_Policy"],
        "tools": ["document_search"],
    }
    result = {
        "answer": "Three days per week.",
        "citations": [
            {"filename": "Remote_Work_Policy.txt", "snippet": "three days per week"},
            {"filename": "HR_Handbook.txt", "snippet": "employees coordinate leave"},
        ],
        "selected_tools": ["document_search"],
        "sql": None,
        "total_latency_ms": 12.0,
        "token_usage": None,
    }

    scored = _case_result(case, result)

    assert scored["retrieval_relevance"] == 0.5
    assert scored["citation_correctness"] == 1.0
