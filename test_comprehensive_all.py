#!/usr/bin/env python3
"""
Comprehensive Test Suite - Tests Everything
Tests all corner cases, functionality, and performance
"""

import requests
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Configuration
BASE_URL = "https://brigade-chatbot-production.up.railway.app"
API_ENDPOINT = f"{BASE_URL}/api/assist/"

class ComprehensiveTester:
    def __init__(self):
        self.results = []
        self.session_id = f"test_all_{int(time.time())}"
        self.context_call_id = f"test_context_{int(time.time())}"
        
    def test_query(self, category: str, query: str, call_id: Optional[str] = None,
                   expected_fields: Optional[List[str]] = None,
                   max_time: float = 15.0,
                   live_call_mode: bool = False,
                   description: str = "") -> Dict:
        """Test a single query and record results."""
        if call_id is None:
            call_id = self.session_id
            
        print(f"\n{'='*80}")
        print(f"[{category}] {description or query}")
        print(f"Query: '{query}'")
        
        start_time = time.time()
        try:
            payload = {
                "call_id": call_id,
                "query": query,
                "live_call_mode": live_call_mode
            }
            
            response = requests.post(API_ENDPOINT, json=payload, timeout=max_time + 5)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # Check expected fields
                missing_fields = []
                if expected_fields:
                    for field in expected_fields:
                        if field not in data:
                            missing_fields.append(field)
                
                # Extract key info
                result = {
                    "category": category,
                    "query": query,
                    "status": "PASS" if not missing_fields and duration <= max_time else "PARTIAL",
                    "duration": round(duration, 2),
                    "has_answer": bool(data.get("answer")),
                    "answer_count": len(data.get("answer", [])) if isinstance(data.get("answer"), list) else 0,
                    "projects_count": len(data.get("projects", [])),
                    "has_coaching": bool(data.get("coaching_point")),
                    "has_live_call": bool(data.get("live_call_structure")) if live_call_mode else None,
                    "missing_fields": missing_fields,
                    "intent": data.get("intent", "unknown"),
                    "answer_preview": str(data.get("answer", []))[:200] if data.get("answer") else "No answer",
                    "error": None
                }
                
                status_icon = "✅" if result["status"] == "PASS" else "⚠️"
                print(f"{status_icon} Status: {result['status']} ({duration:.2f}s)")
                print(f"   Answer bullets: {result['answer_count']}")
                print(f"   Projects: {result['projects_count']}")
                print(f"   Coaching: {'Yes' if result['has_coaching'] else 'No'}")
                if live_call_mode:
                    print(f"   Live Call Structure: {'Yes' if result['has_live_call'] else 'No'}")
                if missing_fields:
                    print(f"   Missing fields: {missing_fields}")
                    
            else:
                duration = time.time() - start_time
                result = {
                    "category": category,
                    "query": query,
                    "status": "FAIL",
                    "duration": round(duration, 2),
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "has_answer": False,
                    "projects_count": 0
                }
                print(f"❌ Status: FAIL ({duration:.2f}s)")
                print(f"   Error: {result['error']}")
            
            self.results.append(result)
            time.sleep(1)  # Rate limiting
            return result
            
        except requests.Timeout:
            duration = time.time() - start_time
            result = {
                "category": category,
                "query": query,
                "status": "TIMEOUT",
                "duration": round(duration, 2),
                "error": f"Request timeout after {max_time}s",
                "has_answer": False
            }
            self.results.append(result)
            print(f"⏱️  Status: TIMEOUT ({duration:.2f}s)")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            result = {
                "category": category,
                "query": query,
                "status": "ERROR",
                "duration": round(duration, 2),
                "error": str(e),
                "has_answer": False
            }
            self.results.append(result)
            print(f"❌ Status: ERROR ({duration:.2f}s)")
            print(f"   Error: {str(e)}")
            return result
    
    def test_category(self, category_name: str, tests: List[Dict]):
        """Test a category of queries."""
        print(f"\n{'#'*80}")
        print(f"# TESTING CATEGORY: {category_name}")
        print(f"{'#'*80}")
        
        for test in tests:
            self.test_query(
                category=category_name,
                query=test["query"],
                call_id=test.get("call_id"),
                expected_fields=test.get("expected_fields"),
                max_time=test.get("max_time", 15.0),
                live_call_mode=test.get("live_call_mode", False),
                description=test.get("description", "")
            )
    
    def generate_report(self):
        """Generate comprehensive test report."""
        print(f"\n{'='*80}")
        print("COMPREHENSIVE TEST REPORT")
        print(f"{'='*80}\n")
        
        # Summary by category
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {
                    "total": 0, "pass": 0, "partial": 0, "fail": 0, 
                    "timeout": 0, "error": 0, "avg_duration": 0
                }
            categories[cat]["total"] += 1
            status_key = result["status"].lower()
            if status_key in categories[cat]:
                categories[cat][status_key] += 1
        
        # Calculate averages
        for cat in categories:
            durations = [r["duration"] for r in self.results if r["category"] == cat]
            if durations:
                categories[cat]["avg_duration"] = round(sum(durations) / len(durations), 2)
        
        print("SUMMARY BY CATEGORY:")
        print("-" * 100)
        print(f"{'Category':<30} | {'Total':<6} | {'Pass':<5} | {'Partial':<7} | {'Fail':<5} | {'Timeout':<7} | {'Error':<5} | {'Avg(s)':<7}")
        print("-" * 100)
        for cat, stats in categories.items():
            pass_rate = (stats["pass"] + stats["partial"]) / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"{cat:<30} | {stats['total']:<6} | {stats['pass']:<5} | {stats['partial']:<7} | "
                  f"{stats['fail']:<5} | {stats['timeout']:<7} | {stats['error']:<5} | {stats['avg_duration']:<7}")
        
        # Overall summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        partial = sum(1 for r in self.results if r["status"] == "PARTIAL")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        timeouts = sum(1 for r in self.results if r["status"] == "TIMEOUT")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        avg_duration = sum(r["duration"] for r in self.results) / total if total > 0 else 0
        
        print(f"\n{'='*80}")
        print("OVERALL SUMMARY:")
        print(f"  Total Tests: {total}")
        print(f"  ✅ Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"  ⚠️  Partial: {partial} ({partial/total*100:.1f}%)")
        print(f"  ❌ Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"  ⏱️  Timeouts: {timeouts} ({timeouts/total*100:.1f}%)")
        print(f"  🔴 Errors: {errors} ({errors/total*100:.1f}%)")
        print(f"  ⏱️  Average Duration: {avg_duration:.2f}s")
        print(f"{'='*80}\n")
        
        # Performance analysis
        slow_tests = [r for r in self.results if r["duration"] > 10]
        if slow_tests:
            print(f"⚠️  SLOW TESTS (>10s): {len(slow_tests)}")
            for test in sorted(slow_tests, key=lambda x: x["duration"], reverse=True)[:5]:
                print(f"   - {test['query'][:50]}... ({test['duration']:.2f}s)")
        
        # Failed tests details
        failed_tests = [r for r in self.results if r["status"] in ["FAIL", "TIMEOUT", "ERROR"]]
        if failed_tests:
            print(f"\n❌ FAILED TESTS: {len(failed_tests)}")
            print("-" * 80)
            for result in failed_tests[:10]:  # Show first 10
                print(f"Category: {result['category']}")
                print(f"Query: '{result['query']}'")
                print(f"Status: {result['status']}")
                print(f"Error: {result.get('error', 'Unknown error')}")
                print()
        
        # Save detailed report
        report_file = f"comprehensive_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "passed": passed,
                    "partial": partial,
                    "failed": failed,
                    "timeouts": timeouts,
                    "errors": errors,
                    "avg_duration": round(avg_duration, 2)
                },
                "categories": categories,
                "results": self.results
            }, f, indent=2)
        
        print(f"📄 Detailed report saved to: {report_file}")
        return report_file


def run_all_tests():
    """Run comprehensive test suite."""
    tester = ComprehensiveTester()
    
    # 1. Typo Handling (Critical)
    tester.test_category("Typo Handling", [
        {"query": "distnce of airport form brigade avalon", "description": "Distance and from typos"},
        {"query": "avalon prise", "description": "Price typo"},
        {"query": "citrine ammenities", "description": "Amenities typo"},
        {"query": "2bhk in whtefield", "description": "Whitefield typo"},
        {"query": "brigade avlon", "description": "Avalon typo"},
        {"query": "rera numbr", "description": "Number typo"},
    ])
    
    # 2. Property Search (Critical - should not return generic greeting)
    tester.test_category("Property Search", [
        {"query": "3BHK in Whitefield under 1.5 Cr", "expected_fields": ["answer", "projects"], 
         "description": "Should return projects, not greeting"},
        {"query": "2bhk under 80L", "expected_fields": ["answer"], 
         "description": "Budget search"},
        {"query": "show me 2bhk", "expected_fields": ["answer", "projects"], 
         "description": "Simple search"},
        {"query": "show me 3bhk", "expected_fields": ["answer", "projects"], 
         "description": "3BHK search"},
    ])
    
    # 3. Mixed Languages
    tester.test_category("Mixed Languages", [
        {"query": "2 bhk chahiye", "expected_fields": ["answer"], 
         "description": "Hindi + English"},
        {"query": "avalon ka price", "expected_fields": ["answer"], 
         "description": "Hindi + English"},
        {"query": "citrine ki location", "expected_fields": ["answer"], 
         "description": "Hindi + English"},
    ])
    
    # 4. Project Facts
    tester.test_category("Project Facts", [
        {"query": "avalon", "expected_fields": ["answer"], 
         "description": "Partial name"},
        {"query": "citrine", "expected_fields": ["answer"], 
         "description": "Partial name"},
        {"query": "brigade avalon", "expected_fields": ["answer"], 
         "description": "Full name"},
        {"query": "tell me about citrine", "expected_fields": ["answer"], 
         "description": "Project details"},
    ])
    
    # 5. Context Continuity (Critical)
    print(f"\n{'#'*80}")
    print("# TESTING CONTEXT CONTINUITY")
    print(f"{'#'*80}")
    
    ctx_id = tester.context_call_id
    tester.test_query("Context Continuity", "show 2bhk in whitefield", 
                     call_id=ctx_id, expected_fields=["answer", "projects"],
                     description="Start: Search query")
    
    tester.test_query("Context Continuity", "price", 
                     call_id=ctx_id, expected_fields=["answer"],
                     description="Follow-up: Should understand price of shown projects")
    
    tester.test_query("Context Continuity", "more", 
                     call_id=ctx_id, expected_fields=["answer"],
                     description="Follow-up: Should show more options")
    
    tester.test_query("Context Continuity", "nearby", 
                     call_id=ctx_id, expected_fields=["answer"],
                     description="Follow-up: Should show nearby to last location")
    
    # 6. Vague References (should ask for clarification)
    tester.test_category("Vague References", [
        {"query": "it", "call_id": f"test_vague_{int(time.time())}", 
         "description": "Pronoun, no context - should ask clarification"},
        {"query": "these", "call_id": f"test_vague_{int(time.time())}", 
         "description": "Pronoun, no context - should ask clarification"},
    ])
    
    # 7. Incomplete Queries (no context)
    tester.test_category("Incomplete Queries", [
        {"query": "price", "call_id": f"test_incomplete_{int(time.time())}", 
         "description": "Single word, no context"},
        {"query": "more", "call_id": f"test_incomplete_{int(time.time())}", 
         "description": "Vague, no context"},
        {"query": "details", "call_id": f"test_incomplete_{int(time.time())}", 
         "description": "Incomplete, no context"},
    ])
    
    # 8. Live Call Mode
    tester.test_category("Live Call Mode", [
        {"query": "On call with client who needs 3BHK under 2Cr in East Bangalore for Q2 2026 possession",
         "live_call_mode": True, "expected_fields": ["live_call_structure", "answer"],
         "description": "Live call response structure"},
    ])
    
    # 9. Distance/Connectivity
    tester.test_category("Distance/Connectivity", [
        {"query": "distance of airport from brigade avalon", 
         "expected_fields": ["answer"], "description": "Distance query"},
        {"query": "how far is metro from citrine", 
         "expected_fields": ["answer"], "description": "Metro distance"},
        {"query": "nearby schools to avalon", 
         "expected_fields": ["answer"], "description": "Nearby places"},
    ])
    
    # 10. Answer Structure (Answer FIRST, Projects SECOND)
    tester.test_category("Answer Structure", [
        {"query": "3BHK in Whitefield under 2 Cr", 
         "expected_fields": ["answer", "projects"],
         "description": "Should have answer bullets before projects"},
    ])
    
    # 11. Coaching Points
    tester.test_category("Coaching Points", [
        {"query": "show me 2bhk", "expected_fields": ["coaching_point"], 
         "description": "Should have coaching point"},
        {"query": "avalon price", "expected_fields": ["coaching_point"], 
         "description": "Should have coaching point"},
    ])
    
    # 12. Edge Cases
    tester.test_category("Edge Cases", [
        {"query": "2bhk @ whitefield", "description": "Special characters"},
        {"query": "2", "description": "Numbers only"},
        {"query": "yes", "description": "Confirmation"},
        {"query": "no", "description": "Negation"},
        {"query": "ok", "description": "Acknowledgment"},
        {"query": "thanks", "description": "Gratitude"},
    ])
    
    # Generate report
    report_file = tester.generate_report()
    return report_file


if __name__ == "__main__":
    print("="*80)
    print("COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"Testing against: {BASE_URL}")
    print(f"API Endpoint: {API_ENDPOINT}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        report_file = run_all_tests()
        print(f"\n✅ Testing completed! Report: {report_file}")
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
        print("Generating partial report...")
        tester.generate_report()
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
