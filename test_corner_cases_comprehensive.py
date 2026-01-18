"""
Comprehensive Corner Case Testing for Universal GPT Understanding
Tests the chatbot on Railway deployment with all edge cases.
"""

import requests
import json
import time
from typing import Dict, List, Optional

# Railway deployment URL
BASE_URL = "https://brigade-chatbot-production.up.railway.app"
API_ENDPOINT = f"{BASE_URL}/api/chat/query"

# Test session ID (will be created automatically)
SESSION_ID = f"test_session_{int(time.time())}"

class CornerCaseTester:
    def __init__(self):
        self.results = []
        self.session_id = SESSION_ID
        self.conversation_context = []  # Track conversation for context tests
        
    def test_query(self, category: str, query: str, expected_intent: Optional[str] = None, 
                   should_have_context: bool = False, description: str = ""):
        """Test a single query and record results."""
        print(f"\n{'='*80}")
        print(f"Testing: {category}")
        print(f"Query: '{query}'")
        if description:
            print(f"Description: {description}")
        
        try:
            payload = {
                "query": query,
                "session_id": self.session_id,
                "user_id": "test_user"
            }
            
            response = requests.post(API_ENDPOINT, json=payload, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                intent = data.get("intent", "unknown")
                answer = data.get("answer", "")
                confidence = data.get("confidence", "Unknown")
                
                # Check if context was used (for context-dependent queries)
                context_used = len(self.conversation_context) > 0 if should_have_context else None
                
                result = {
                    "category": category,
                    "query": query,
                    "status": "PASS" if (not expected_intent or intent == expected_intent) else "PARTIAL",
                    "intent": intent,
                    "expected_intent": expected_intent,
                    "confidence": confidence,
                    "answer_length": len(answer),
                    "answer_preview": answer[:200] if answer else "No answer",
                    "context_used": context_used,
                    "description": description
                }
                
                # Add to conversation context for follow-up tests
                self.conversation_context.append({"role": "user", "content": query})
                if answer:
                    self.conversation_context.append({"role": "assistant", "content": answer[:100]})
                
                print(f"✅ Status: {result['status']}")
                print(f"   Intent: {intent} (expected: {expected_intent or 'any'})")
                print(f"   Confidence: {confidence}")
                print(f"   Answer preview: {answer[:150]}...")
                
            else:
                result = {
                    "category": category,
                    "query": query,
                    "status": "FAIL",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "description": description
                }
                print(f"❌ Status: FAIL")
                print(f"   Error: {result['error']}")
            
            self.results.append(result)
            time.sleep(2)  # Rate limiting - increased delay for GPT processing
            
        except Exception as e:
            result = {
                "category": category,
                "query": query,
                "status": "ERROR",
                "error": str(e),
                "description": description
            }
            self.results.append(result)
            print(f"❌ Status: ERROR")
            print(f"   Error: {str(e)}")
    
    def test_category(self, category_name: str, tests: List[Dict]):
        """Test a category of queries."""
        print(f"\n{'#'*80}")
        print(f"# TESTING CATEGORY: {category_name}")
        print(f"{'#'*80}")
        
        for test in tests:
            self.test_query(
                category=category_name,
                query=test["query"],
                expected_intent=test.get("expected_intent"),
                should_have_context=test.get("should_have_context", False),
                description=test.get("description", "")
            )
    
    def generate_report(self):
        """Generate a test report."""
        print(f"\n{'='*80}")
        print("TEST REPORT")
        print(f"{'='*80}\n")
        
        # Summary by category
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "pass": 0, "partial": 0, "fail": 0, "error": 0}
            categories[cat]["total"] += 1
            categories[cat][result["status"].lower()] += 1
        
        print("SUMMARY BY CATEGORY:")
        print("-" * 80)
        for cat, stats in categories.items():
            pass_rate = (stats["pass"] + stats["partial"]) / stats["total"] * 100
            print(f"{cat:30s} | Total: {stats['total']:2d} | Pass: {stats['pass']:2d} | Partial: {stats['partial']:2d} | Fail: {stats['fail']:2d} | Error: {stats['error']:2d} | Rate: {pass_rate:5.1f}%")
        
        # Overall summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        partial = sum(1 for r in self.results if r["status"] == "PARTIAL")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        
        print(f"\n{'='*80}")
        print("OVERALL SUMMARY:")
        print(f"  Total Tests: {total}")
        print(f"  ✅ Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"  ⚠️  Partial: {partial} ({partial/total*100:.1f}%)")
        print(f"  ❌ Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"  🔴 Errors: {errors} ({errors/total*100:.1f}%)")
        print(f"{'='*80}\n")
        
        # Failed tests details
        failed_tests = [r for r in self.results if r["status"] in ["FAIL", "ERROR"]]
        if failed_tests:
            print("FAILED TESTS:")
            print("-" * 80)
            for result in failed_tests:
                print(f"Category: {result['category']}")
                print(f"Query: '{result['query']}'")
                print(f"Error: {result.get('error', 'Unknown error')}")
                print()
        
        # Save detailed report to file
        report_file = "corner_case_test_report.json"
        with open(report_file, "w") as f:
            json.dump({
                "summary": {
                    "total": total,
                    "passed": passed,
                    "partial": partial,
                    "failed": failed,
                    "errors": errors
                },
                "categories": categories,
                "results": self.results
            }, f, indent=2)
        
        print(f"Detailed report saved to: {report_file}")


def run_all_tests():
    """Run all corner case tests."""
    tester = CornerCaseTester()
    
    # 1. Typo Handling
    tester.test_category("Typo Handling", [
        {"query": "distnce of airport form brigade avalon", "expected_intent": "sales_conversation", 
         "description": "Distance and from typos"},
        {"query": "avalon prise", "expected_intent": "project_facts", 
         "description": "Price typo"},
        {"query": "citrine ammenities", "expected_intent": "project_facts", 
         "description": "Amenities typo"},
        {"query": "2bhk in whtefield", "expected_intent": "property_search", 
         "description": "Whitefield typo"},
        {"query": "brigade avlon", "expected_intent": "project_facts", 
         "description": "Avalon typo"},
        {"query": "rera numbr", "expected_intent": "project_facts", 
         "description": "Number typo"},
    ])
    
    # 2. Incomplete Queries (will test with context later)
    tester.test_category("Incomplete Queries - No Context", [
        {"query": "price", "description": "Single word, no context"},
        {"query": "more", "description": "Vague, no context"},
        {"query": "details", "description": "Incomplete, no context"},
    ])
    
    # 3. Vague References & Pronouns (will test with context later)
    tester.test_category("Vague References - No Context", [
        {"query": "it", "description": "Pronoun, no context"},
        {"query": "these", "description": "Pronoun, no context"},
    ])
    
    # 4. Single Word Queries
    tester.test_category("Single Word Queries", [
        {"query": "yes", "description": "Confirmation"},
        {"query": "no", "description": "Negation"},
        {"query": "ok", "description": "Acknowledgment"},
        {"query": "thanks", "description": "Gratitude"},
    ])
    
    # 5. Mixed Languages
    tester.test_category("Mixed Languages", [
        {"query": "2 bhk chahiye", "expected_intent": "property_search", 
         "description": "Hindi + English"},
        {"query": "avalon ka price", "expected_intent": "project_facts", 
         "description": "Hindi + English"},
        {"query": "citrine ki location", "expected_intent": "project_facts", 
         "description": "Hindi + English"},
    ])
    
    # 6. Slang & Abbreviations
    tester.test_category("Slang & Abbreviations", [
        {"query": "show me 2bhk", "expected_intent": "property_search", 
         "description": "No space in 2bhk"},
        {"query": "show me 3bhk", "expected_intent": "property_search", 
         "description": "No space in 3bhk"},
        {"query": "what is rtm", "expected_intent": "sales_conversation", 
         "description": "RTM abbreviation"},
        {"query": "what is rera", "expected_intent": "sales_conversation", 
         "description": "RERA abbreviation"},
        {"query": "what is emi", "expected_intent": "sales_conversation", 
         "description": "EMI abbreviation"},
    ])
    
    # 7. No Question Marks
    tester.test_category("No Question Marks", [
        {"query": "show me 2bhk", "expected_intent": "property_search", 
         "description": "Statement, not question"},
        {"query": "avalon price", "expected_intent": "project_facts", 
         "description": "Statement"},
        {"query": "tell me about citrine", "expected_intent": "project_facts", 
         "description": "Statement"},
        {"query": "distance airport avalon", "expected_intent": "sales_conversation", 
         "description": "Statement"},
    ])
    
    # 8. Multiple Intents in One Query
    tester.test_category("Multiple Intents", [
        {"query": "show 2bhk and compare with citrine", 
         "description": "Search + comparison"},
        {"query": "price and amenities of avalon", 
         "description": "Multiple facts"},
    ])
    
    # 9. Context Continuity Tests
    print(f"\n{'#'*80}")
    print("# TESTING CONTEXT CONTINUITY")
    print(f"{'#'*80}")
    
    # Start with a search
    tester.test_query("Context Continuity", "show 2bhk in whitefield", 
                     expected_intent="property_search", 
                     description="Start: Search query")
    
    # Follow-ups that should use context
    tester.test_query("Context Continuity", "price", 
                     should_have_context=True,
                     description="Follow-up: Should understand price of shown projects")
    
    tester.test_query("Context Continuity", "more", 
                     should_have_context=True,
                     description="Follow-up: Should show more options")
    
    tester.test_query("Context Continuity", "nearby", 
                     should_have_context=True,
                     description="Follow-up: Should show nearby to last location")
    
    # 10. Project Name Variations
    tester.test_category("Project Name Variations", [
        {"query": "avalon", "expected_intent": "project_facts", 
         "description": "Partial name - should match Brigade Avalon"},
        {"query": "citrine", "expected_intent": "project_facts", 
         "description": "Partial name - should match Brigade Citrine"},
        {"query": "brigade avalon", "expected_intent": "project_facts", 
         "description": "Full name"},
    ])
    
    # 11. Distance/Connectivity Queries
    tester.test_category("Distance/Connectivity", [
        {"query": "distance of airport from brigade avalon", 
         "expected_intent": "sales_conversation", 
         "description": "Distance query with project"},
        {"query": "how far is metro from citrine", 
         "expected_intent": "sales_conversation", 
         "description": "Metro distance"},
        {"query": "nearby schools to avalon", 
         "expected_intent": "sales_conversation", 
         "description": "Nearby places"},
    ])
    
    # 12. Edge Cases
    tester.test_category("Edge Cases", [
        {"query": "2bhk @ whitefield", 
         "description": "Special characters"},
        {"query": "2", 
         "description": "Numbers only"},
    ])
    
    # Generate report
    tester.generate_report()


if __name__ == "__main__":
    print("Starting Comprehensive Corner Case Testing")
    print(f"Testing against: {BASE_URL}")
    print(f"Session ID: {SESSION_ID}\n")
    
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTesting interrupted by user")
        print("Generating partial report...")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
