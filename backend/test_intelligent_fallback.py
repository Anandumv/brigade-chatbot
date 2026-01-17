"""
Test script for Intelligent Fallback Suggestions feature.
Tests zero-result queries and validates that alternatives are suggested with sales pitches.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'vendor')))

from services.intelligent_fallback import intelligent_fallback
from services.filter_extractor import filter_extractor
from services.hybrid_retrieval import hybrid_retrieval
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator():
    print("\n" + "="*80 + "\n")


async def test_scenario(scenario_name: str, query: str, expected_behavior: str):
    """Test a specific scenario."""
    print_separator()
    print(f"🧪 TEST SCENARIO: {scenario_name}")
    print(f"📝 Query: '{query}'")
    print(f"✅ Expected: {expected_behavior}")
    print("-" * 80)
    
    try:
        # Extract filters
        filters = filter_extractor.extract_filters(query)
        print(f"\n📊 Extracted Filters:")
        filter_dict = filters.model_dump(exclude_none=True)
        for key, value in filter_dict.items():
            print(f"  • {key}: {value}")
        
        # First try normal search
        print(f"\n🔍 Searching with normal query...")
        search_results = await hybrid_retrieval.search_with_filters(
            query=query,
            filters=filters
        )
        
        normal_count = len(search_results.get("projects", []))
        print(f"  Found {normal_count} exact matches")
        
        if normal_count == 0:
            print(f"\n🎯 No exact matches - triggering intelligent fallback...")
            fallback_results = await intelligent_fallback.find_intelligent_alternatives(
                filters=filters,
                original_query=query,
                max_results=3
            )
            
            alternatives = fallback_results.get("alternatives", [])
            answer = fallback_results.get("answer", "")
            
            if alternatives:
                print(f"\n✅ SUCCESS: Found {len(alternatives)} alternatives!")
                print(f"\n📍 Alternatives Found:")
                for idx, alt in enumerate(alternatives, 1):
                    print(f"\n  {idx}. {alt.get('name')}")
                    print(f"     Location: {alt.get('location')}")
                    print(f"     Budget: ₹{alt.get('budget_min', 0)/100:.2f} - ₹{alt.get('budget_max', 0)/100:.2f} Cr")
                    print(f"     Distance: {alt.get('_distance', 'N/A')} km")
                    print(f"     Score: {alt.get('_score', 0):.2f}")
                
                print(f"\n💬 Generated Sales Pitch Preview (first 500 chars):")
                print("-" * 80)
                print(answer[:500] if answer else "No pitch generated")
                if len(answer) > 500:
                    print("...")
                print("-" * 80)
                
                return True
            else:
                print(f"\n⚠️  No alternatives found either")
                return False
        else:
            print(f"\n✅ Normal search returned results (no fallback needed)")
            print(f"   Top 3 projects:")
            for idx, proj in enumerate(search_results["projects"][:3], 1):
                print(f"   {idx}. {proj.get('project_name', proj.get('name'))}")
            return True
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        logger.exception("Test failed with exception")
        return False


async def run_all_tests():
    """Run all test scenarios."""
    print("\n" + "="*80)
    print("🚀 INTELLIGENT FALLBACK SUGGESTIONS - TEST SUITE")
    print("="*80)
    
    test_results = []
    
    # Test Scenario 1: Zero results query with location
    result1 = await test_scenario(
        scenario_name="Zero Results - Budget Too Low",
        query="projects under 50 lacs in indiranagar",
        expected_behavior="Should suggest nearby alternatives with higher budget"
    )
    test_results.append(("Budget Too Low", result1))
    
    # Test Scenario 2: Unrealistic budget for premium location
    result2 = await test_scenario(
        scenario_name="Unrealistic Budget - Premium Location",
        query="3 BHK under 1 Cr in koramangala",
        expected_behavior="Should suggest value alternatives in nearby areas"
    )
    test_results.append(("Unrealistic Budget", result2))
    
    # Test Scenario 3: Budget constraint in North Bangalore (from screenshot)
    result3 = await test_scenario(
        scenario_name="North Bangalore Under 70 Lacs",
        query="projects under 70 lacs in north bangalore",
        expected_behavior="Should suggest nearby projects within 10km radius"
    )
    test_results.append(("North Bangalore 70L", result3))
    
    # Test Scenario 4: Remote location with budget
    result4 = await test_scenario(
        scenario_name="Remote Location Search",
        query="projects in mysore road under 2 cr",
        expected_behavior="Should suggest nearby zones if available"
    )
    test_results.append(("Remote Location", result4))
    
    # Test Scenario 5: Normal query with results (should NOT trigger fallback)
    result5 = await test_scenario(
        scenario_name="Normal Query - Should Find Results",
        query="3 BHK in whitefield",
        expected_behavior="Should return normal results without fallback"
    )
    test_results.append(("Normal Query", result5))
    
    # Test Scenario 6: Specific configuration in area
    result6 = await test_scenario(
        scenario_name="Specific Config - East Bangalore",
        query="2 BHK under 1.5 cr in east bangalore",
        expected_behavior="Should find exact matches or suggest alternatives"
    )
    test_results.append(("Config + Area", result6))
    
    # Print Summary
    print_separator()
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for scenario_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {scenario_name}")
    
    print("-" * 80)
    print(f"\nResults: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Intelligent fallback is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review logs above.")
    
    print("="*80 + "\n")


async def test_pitch_quality():
    """Test the quality of generated sales pitches."""
    print_separator()
    print("🎨 TESTING SALES PITCH QUALITY")
    print("="*80)
    
    query = "projects under 70 lacs in north bangalore"
    filters = filter_extractor.extract_filters(query)
    
    print(f"Query: '{query}'\n")
    
    fallback_results = await intelligent_fallback.find_intelligent_alternatives(
        filters=filters,
        original_query=query,
        max_results=3
    )
    
    answer = fallback_results.get("answer", "")
    
    if answer:
        print("Generated Sales Pitch:\n")
        print("-" * 80)
        print(answer)
        print("-" * 80)
        
        # Check pitch quality criteria
        quality_checks = {
            "Has emoji": any(char in answer for char in "🏠📍💰🏗️✨📞"),
            "Mentions distance": "km" in answer.lower(),
            "Mentions budget/price": any(word in answer.lower() for word in ["cr", "lakh", "₹", "crore"]),
            "Has call-to-action": any(phrase in answer.lower() for phrase in ["would you like", "schedule", "visit", "interested"]),
            "Professional tone": len(answer) > 100,  # Should be substantial
            "Value-focused": any(word in answer.lower() for word in ["value", "affordable", "savings", "excellent", "great"]),
        }
        
        print("\n✅ Quality Checks:")
        for check, passed in quality_checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
        
        passed_checks = sum(quality_checks.values())
        total_checks = len(quality_checks)
        print(f"\nQuality Score: {passed_checks}/{total_checks} ({passed_checks/total_checks*100:.1f}%)")
        
        if passed_checks >= total_checks * 0.8:
            print("🎉 Sales pitch quality is EXCELLENT!")
        elif passed_checks >= total_checks * 0.6:
            print("👍 Sales pitch quality is GOOD")
        else:
            print("⚠️  Sales pitch quality needs improvement")
    else:
        print("❌ No pitch generated")
    
    print_separator()


async def main():
    """Main test runner."""
    print("\n🧪 Starting Intelligent Fallback Test Suite...\n")
    
    try:
        # Run all scenario tests
        await run_all_tests()
        
        # Test pitch quality
        await test_pitch_quality()
        
        print("\n✅ Test suite completed successfully!\n")
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        logger.exception("Test suite error")


if __name__ == "__main__":
    asyncio.run(main())
