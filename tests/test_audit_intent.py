import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.domain.rag_engine import query_mechanic_agent


async def run_tests():
    logging.basicConfig(level=logging.INFO)
    
    test_queries = [
        {
            "id": "A (SYSTEM_QUERY)",
            "query": "are you online and is Qdrant connected",
            "car": "Toyota Corolla 2020"
        },
        {
            "id": "B (KNOWLEDGE_AUDIT)",
            "query": "Professionally analyze your RAG pipeline and categorize your ingested data. Reply in English",
            "car": "Toyota Corolla 2020"
        },
        {
            "id": "C (KNOWLEDGE_AUDIT - Deep)",
            "query": "Role: Senior Data Analyst — deep analysis of knowledge base, score each domain 1 to 10",
            "car": "Toyota Corolla 2020"
        },
        {
            "id": "D (FAULT_DIAGNOSIS - Regression)",
            "query": "wheel speed sensor fault code C1241",
            "car": "Toyota Corolla 2020"
        }
    ]

    for test in test_queries:
        print(f"\n{'='*60}")
        print(f"RUNNING TEST {test['id']}: {test['query']}")
        print(f"{'='*60}")
        try:
            response = await query_mechanic_agent(test['query'], test['car'])
            print("\nRESPONSE:")
            print(response)
        except Exception as e:
            print(f"\nERROR: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
