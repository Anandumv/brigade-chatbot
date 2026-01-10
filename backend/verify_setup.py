"""
Setup verification script to test all components.
Run this after initial setup to ensure everything works.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from database.supabase_client import supabase_client
from services.intent_classifier import intent_classifier
from services.retrieval import retrieval_service
from services.confidence_scorer import confidence_scorer
from services.answer_generator import answer_generator
from openai import OpenAI


class Colors:
    """Terminal colors for output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_warning(message):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


def print_info(message):
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")


async def verify_environment():
    """Verify environment variables are set."""
    print_info("Checking environment variables...")

    required_vars = [
        "openai_api_key",
        "supabase_url",
        "supabase_key"
    ]

    missing = []
    for var in required_vars:
        value = getattr(settings, var, None)
        if not value or value == f"your_{var}_here":
            missing.append(var.upper())

    if missing:
        print_error(f"Missing environment variables: {', '.join(missing)}")
        print_info("Please set these in your .env file")
        return False

    print_success("All required environment variables are set")
    return True


async def verify_openai():
    """Verify OpenAI API connection."""
    print_info("Testing OpenAI API connection...")

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input="test"
        )
        print_success(f"OpenAI API connected (model: {settings.embedding_model})")
        return True
    except Exception as e:
        print_error(f"OpenAI API error: {e}")
        return False


async def verify_supabase():
    """Verify Supabase connection and schema."""
    print_info("Testing Supabase connection...")

    try:
        # Test connection
        response = supabase_client.client.table("projects").select("count", count="exact").execute()

        print_success(f"Supabase connected ({response.count or 0} projects in database)")

        # Check for pgvector
        print_info("Checking pgvector extension...")
        # Try to query document_chunks table
        chunks_response = supabase_client.client.table("document_chunks").select("count", count="exact").execute()

        print_success(f"pgvector enabled ({chunks_response.count or 0} chunks in database)")

        if chunks_response.count == 0:
            print_warning("No document chunks found - run create_embeddings.py to process documents")

        return True
    except Exception as e:
        print_error(f"Supabase error: {e}")
        print_info("Make sure schema.sql has been executed")
        return False


async def verify_intent_classification():
    """Verify intent classification works."""
    print_info("Testing intent classification...")

    try:
        test_queries = {
            "What is the RERA number?": "project_fact",
            "Why should I buy here?": "sales_pitch",
            "Will property value increase?": "unsupported"
        }

        for query, expected_intent in test_queries.items():
            intent = intent_classifier.classify_intent(query)
            if intent == expected_intent:
                print_success(f"'{query}' → {intent}")
            else:
                print_warning(f"'{query}' → {intent} (expected {expected_intent})")

        return True
    except Exception as e:
        print_error(f"Intent classification error: {e}")
        return False


async def verify_retrieval():
    """Verify document retrieval works."""
    print_info("Testing document retrieval...")

    try:
        chunks = await retrieval_service.retrieve_similar_chunks(
            query="What is Brigade Citrine?",
            similarity_threshold=0.5  # Lower threshold for testing
        )

        if chunks:
            print_success(f"Retrieved {len(chunks)} chunks")
            print_info(f"Top chunk similarity: {chunks[0].get('similarity', 0):.3f}")
            print_info(f"Top chunk project: {chunks[0].get('project_name', 'Unknown')}")
            return True
        else:
            print_error("No chunks retrieved")
            print_warning("Make sure you've run create_embeddings.py")
            return False
    except Exception as e:
        print_error(f"Retrieval error: {e}")
        return False


async def verify_end_to_end():
    """Verify end-to-end query processing."""
    print_info("Testing end-to-end query processing...")

    try:
        test_query = "What is the RERA number for Brigade Citrine?"

        # Get intent
        intent = intent_classifier.classify_intent(test_query)

        # Retrieve chunks
        chunks = await retrieval_service.retrieve_similar_chunks(test_query)

        if not chunks:
            print_error("No chunks retrieved for test query")
            return False

        # Score confidence
        confidence = confidence_scorer.score_confidence(chunks)

        # Generate answer
        result = answer_generator.generate_answer(
            query=test_query,
            chunks=chunks,
            intent=intent,
            confidence=confidence
        )

        print_success("End-to-end processing works!")
        print_info(f"Answer: {result['answer'][:100]}...")
        print_info(f"Confidence: {result['confidence']}")
        print_info(f"Sources: {len(result['sources'])} documents cited")

        return True
    except Exception as e:
        print_error(f"End-to-end error: {e}")
        return False


async def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("  Real Estate Chatbot - Setup Verification")
    print("="*60 + "\n")

    checks = [
        ("Environment Variables", verify_environment()),
        ("OpenAI API", verify_openai()),
        ("Supabase Database", verify_supabase()),
        ("Intent Classification", verify_intent_classification()),
        ("Document Retrieval", verify_retrieval()),
        ("End-to-End Processing", verify_end_to_end()),
    ]

    results = []
    for name, check_coro in checks:
        print(f"\n--- {name} ---")
        result = await check_coro
        results.append((name, result))
        print()

    # Summary
    print("="*60)
    print("  Summary")
    print("="*60 + "\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.END} - {name}")

    print(f"\n{passed}/{total} checks passed")

    if passed == total:
        print_success("\n🎉 All checks passed! Your chatbot is ready to use.")
        print_info("\nNext steps:")
        print("  1. Start the API: uvicorn main:app --reload")
        print("  2. Visit http://localhost:8000/docs")
        print("  3. Try example queries from README.md")
    else:
        print_warning("\n⚠ Some checks failed. Please review errors above.")
        print_info("\nCommon fixes:")
        print("  - Missing environment variables: Edit .env file")
        print("  - Supabase errors: Run schema.sql in SQL Editor")
        print("  - No chunks: Run python scripts/create_embeddings.py")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
