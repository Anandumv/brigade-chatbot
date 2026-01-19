#!/usr/bin/env python3
"""
Test script for Redis connection and /assist endpoint.
Run this after deploying Redis to verify everything works.
"""

import sys
import json
import requests
from config import settings

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")


def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")


def print_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")


def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")


def test_redis_connection():
    """Test Redis connection directly."""
    print_info("Testing Redis connection...")

    try:
        from services.redis_context import init_redis_context_manager

        redis_manager = init_redis_context_manager(
            redis_url=settings.redis_url,
            ttl_seconds=settings.redis_ttl_seconds
        )

        # Check health
        health = redis_manager.health_check()

        if health['status'] == 'healthy':
            print_success(f"Redis connected: {settings.redis_url}")
            return True
        else:
            print_warning(f"Redis unhealthy: {health}")
            return False

    except Exception as e:
        print_error(f"Redis connection failed: {e}")
        return False


def test_redis_operations():
    """Test Redis read/write operations."""
    print_info("Testing Redis operations...")

    try:
        from services.redis_context import get_redis_context_manager

        redis_manager = get_redis_context_manager()

        # Test write
        test_context = {
            "call_id": "test-12345",
            "active_project": "Brigade Citrine",
            "last_budget": 13000000,
            "last_location": "Sarjapur",
            "last_results": [],
            "last_filters": {"bhk": ["2BHK"]},
            "signals": {"price_sensitive": True}
        }

        redis_manager.save_context("test-12345", test_context)
        print_success("Context saved to Redis")

        # Test read
        loaded_context = redis_manager.load_context("test-12345")

        if loaded_context["last_budget"] == 13000000:
            print_success("Context loaded from Redis successfully")
            return True
        else:
            print_error("Context mismatch")
            return False

    except Exception as e:
        print_error(f"Redis operations failed: {e}")
        return False


def test_assist_endpoint_local():
    """Test /assist endpoint on local server."""
    print_info("Testing /assist endpoint (local server must be running)...")

    base_url = "http://localhost:8000"

    try:
        # Test health check
        response = requests.get(f"{base_url}/api/assist/health", timeout=5)

        if response.status_code == 200:
            health_data = response.json()
            print_success(f"Health check passed: {health_data['status']}")
            print_info(f"Redis status: {health_data['redis']['status']}")
        else:
            print_error(f"Health check failed: {response.status_code}")
            return False

        # Test /assist endpoint
        test_request = {
            "call_id": "test-67890",
            "query": "Show me 2BHK under 1.3Cr in Sarjapur",
            "filters": {
                "bhk": ["2BHK"],
                "status": ["Ready-to-move"]
            }
        }

        response = requests.post(
            f"{base_url}/api/assist",
            json=test_request,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print_success("/assist endpoint working!")
            print_info(f"Projects returned: {len(data.get('projects', []))}")
            print_info(f"Answer bullets: {len(data.get('answer', []))}")
            print_info(f"Pitch help: {data.get('pitch_help', 'N/A')[:50]}...")

            # Pretty print response
            print("\n" + BLUE + "Sample Response:" + RESET)
            print(json.dumps(data, indent=2)[:500] + "...\n")
            return True
        else:
            print_error(f"/assist endpoint failed: {response.status_code}")
            print_error(response.text)
            return False

    except requests.ConnectionError:
        print_warning("Local server not running. Start with: uvicorn main:app --reload")
        return False
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


def test_context_persistence():
    """Test that context persists across multiple requests."""
    print_info("Testing context persistence...")

    base_url = "http://localhost:8000"
    call_id = "test-persistence-99999"

    try:
        # First query
        response1 = requests.post(
            f"{base_url}/api/assist",
            json={
                "call_id": call_id,
                "query": "Show me 2BHK in Sarjapur under 1.5Cr"
            },
            timeout=30
        )

        if response1.status_code != 200:
            print_error("First query failed")
            return False

        print_success("First query successful")

        # Follow-up query (should use context)
        response2 = requests.post(
            f"{base_url}/api/assist",
            json={
                "call_id": call_id,
                "query": "What about 3BHK?"
            },
            timeout=30
        )

        if response2.status_code != 200:
            print_error("Follow-up query failed")
            return False

        data2 = response2.json()

        # Check if context was used (answer should reference previous query)
        answer_text = " ".join(data2.get('answer', []))

        if "3BHK" in answer_text or "3 BHK" in answer_text:
            print_success("Context persistence working! Follow-up query understood.")
            return True
        else:
            print_warning("Context may not be persisting correctly")
            return False

    except Exception as e:
        print_error(f"Persistence test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + BLUE + "="*60 + RESET)
    print(BLUE + "  Redis & /assist Endpoint Test Suite" + RESET)
    print(BLUE + "="*60 + RESET + "\n")

    print_info(f"Redis URL: {settings.redis_url}")
    print_info(f"Redis TTL: {settings.redis_ttl_seconds}s (90 min)\n")

    results = []

    # Test 1: Redis connection
    results.append(("Redis Connection", test_redis_connection()))

    # Test 2: Redis operations
    if results[0][1]:  # Only if connection successful
        results.append(("Redis Operations", test_redis_operations()))

    # Test 3: /assist endpoint
    results.append(("/assist Endpoint", test_assist_endpoint_local()))

    # Test 4: Context persistence
    if results[-1][1]:  # Only if endpoint working
        results.append(("Context Persistence", test_context_persistence()))

    # Print summary
    print("\n" + BLUE + "="*60 + RESET)
    print(BLUE + "  Test Summary" + RESET)
    print(BLUE + "="*60 + RESET + "\n")

    for test_name, passed in results:
        if passed:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print(f"\n{BLUE}Total: {total_passed}/{total_tests} tests passed{RESET}\n")

    if total_passed == total_tests:
        print_success("All tests passed! ✨")
        return 0
    else:
        print_error("Some tests failed. Check logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
