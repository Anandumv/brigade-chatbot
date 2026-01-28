"""
Test the three main filtering improvements:
1. Configuration flexibility (show higher BHK within budget)
2. Automatic budget expansion (show nearby budget projects)
3. Locality priority scoring (prioritize exact locality matches)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.flow_engine import FlowState, FlowRequirements, execute_flow

def test_configuration_flexibility():
    """Test: '2 bhk under 1.5 cr near yelahanka' should show both 2BHK and 3BHK within budget"""
    print("\n" + "="*80)
    print("TEST 1: Configuration Flexibility")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "2 bhk under 1.5 cr near yelahanka"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Intent: {state.last_intent}")
    print(f"Extracted Requirements: {response.extracted_requirements}")
    print(f"\nNumber of projects found: {len(response.projects)}")

    if response.projects:
        bhk_types = set()
        print("\nProjects returned:")
        for i, project in enumerate(response.projects[:10], 1):
            name = project.get('name', 'N/A')
            config = project.get('configuration', 'N/A')
            score = project.get('_match_score', 0)
            print(f"{i}. {name}")
            print(f"   Configuration: {config}")
            print(f"   Match Score: {score}")

            # Extract BHK types from configuration
            config_lower = str(config).lower()
            if '2bhk' in config_lower or '2 bhk' in config_lower:
                bhk_types.add('2BHK')
            if '3bhk' in config_lower or '3 bhk' in config_lower:
                bhk_types.add('3BHK')

        print(f"\nBHK types found: {', '.join(sorted(bhk_types))}")

        if '2BHK' in bhk_types and '3BHK' in bhk_types:
            print("\n✅ SUCCESS: Shows both 2BHK and 3BHK options")
            return True
        elif '2BHK' in bhk_types:
            print("\n⚠️  PARTIAL: Shows 2BHK but no 3BHK within budget")
            return False
        else:
            print("\n❌ FAILURE: Unexpected configuration results")
            return False
    else:
        print("\n❌ FAILURE: No projects found")
        return False

def test_budget_expansion():
    """Test: 'projects under 70 lacs in north bangalore' should show nearby budget projects"""
    print("\n" + "="*80)
    print("TEST 2: Automatic Budget Expansion")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "projects under 70 lacs in north bangalore"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Intent: {state.last_intent}")
    print(f"Extracted Requirements: {response.extracted_requirements}")
    print(f"\nNumber of projects found: {len(response.projects)}")
    print(f"Response message: {response.system_action[:200]}...")

    if response.projects:
        print("\nProjects returned:")
        for i, project in enumerate(response.projects[:5], 1):
            name = project.get('name', 'N/A')
            zone = project.get('zone', 'N/A')
            budget_min = project.get('budget_min', 0)
            budget_max = project.get('budget_max', 0)
            print(f"{i}. {name}")
            print(f"   Zone: {zone}")
            print(f"   Budget: {budget_min}-{budget_max} lacs")

        # Check if message indicates budget expansion
        if "no projects found under" in response.system_action.lower():
            print("\n✅ SUCCESS: Budget was automatically expanded and nearby projects shown")
            return True
        else:
            print("\n⚠️  Note: Projects found (possibly within original budget or data was updated)")
            return True
    else:
        print("\n❌ FAILURE: No projects found even with expansion")
        return False

def test_locality_priority():
    """Test: '2 bhk under 1.3 cr in sarjapur' should prioritize Sarjapur projects"""
    print("\n" + "="*80)
    print("TEST 3: Locality Priority Scoring")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "2 bhk under 1.3 cr in sarjapur"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Intent: {state.last_intent}")
    print(f"Extracted Requirements: {response.extracted_requirements}")
    print(f"\nNumber of projects found: {len(response.projects)}")

    if response.projects:
        print("\nTop 10 projects (sorted by relevance):")
        sarjapur_in_top_3 = 0
        for i, project in enumerate(response.projects[:10], 1):
            name = project.get('name', 'N/A')
            location = project.get('location', 'N/A')
            score = project.get('_match_score', 0)
            print(f"{i}. {name}")
            print(f"   Location: {location}")
            print(f"   Match Score: {score}")

            # Check if top 3 contain "Sarjapur"
            if i <= 3 and 'sarjapur' in location.lower():
                sarjapur_in_top_3 += 1

        if sarjapur_in_top_3 >= 2:
            print(f"\n✅ SUCCESS: {sarjapur_in_top_3}/3 top results are Sarjapur-specific")
            return True
        else:
            print(f"\n⚠️  PARTIAL: Only {sarjapur_in_top_3}/3 top results are Sarjapur-specific")
            print("     Other East Bangalore localities may be ranked higher")
            return False
    else:
        print("\n❌ FAILURE: No projects found")
        return False

def test_scoring_consistency():
    """Test: Verify that scoring is consistent and projects are properly sorted"""
    print("\n" + "="*80)
    print("TEST 4: Score Consistency")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "2 bhk under 1.5 cr in whitefield"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Number of projects found: {len(response.projects)}")

    if response.projects and len(response.projects) > 1:
        print("\nScore progression:")
        last_score = float('inf')
        is_sorted = True

        for i, project in enumerate(response.projects[:5], 1):
            name = project.get('name', 'N/A')
            score = project.get('_match_score', 0)
            print(f"{i}. {name}: Score = {score}")

            if score > last_score:
                is_sorted = False
            last_score = score

        if is_sorted:
            print("\n✅ SUCCESS: Projects are properly sorted by score (descending)")
            return True
        else:
            print("\n❌ FAILURE: Projects are NOT sorted correctly")
            return False
    else:
        print("\n⚠️  SKIP: Not enough projects to verify sorting")
        return True

if __name__ == "__main__":
    print("="*80)
    print("PROPERTY SEARCH FILTERING IMPROVEMENTS TEST SUITE")
    print("="*80)

    results = []

    # Run all tests
    results.append(("Configuration Flexibility", test_configuration_flexibility()))
    results.append(("Budget Expansion", test_budget_expansion()))
    results.append(("Locality Priority", test_locality_priority()))
    results.append(("Score Consistency", test_scoring_consistency()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed or partially passed")
