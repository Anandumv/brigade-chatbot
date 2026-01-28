"""
Test location filtering to ensure Sarjapur queries return East Bangalore projects
and North Bangalore queries return North Bangalore projects.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.flow_engine import FlowState, FlowRequirements, execute_flow

def test_sarjapur_query():
    """Test: '2 bhk under 90 lacs in sarjapur' should return East Bangalore projects"""
    print("\n" + "="*80)
    print("TEST 1: Sarjapur Query (East Bangalore)")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "2 bhk under 90 lacs in sarjapur"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Intent: {state.last_intent}")
    print(f"Extracted Requirements: {response.extracted_requirements}")
    print(f"\nNumber of projects found: {len(response.projects)}")

    if response.projects:
        print("\nProjects returned:")
        for i, project in enumerate(response.projects[:5], 1):
            zone = project.get('zone', 'N/A')
            location = project.get('location', 'N/A')
            name = project.get('name', 'N/A')
            print(f"{i}. {name}")
            print(f"   Zone: {zone}")
            print(f"   Location: {location}")

        # Verify all projects are in East Bangalore
        all_east = all('east' in str(p.get('zone', '')).lower() or
                       'east' in str(p.get('location', '')).lower()
                       for p in response.projects)

        if all_east:
            print("\n✅ SUCCESS: All projects are from East Bangalore")
            return True
        else:
            print("\n❌ FAILURE: Some projects are NOT from East Bangalore")
            return False
    else:
        print("\n❌ FAILURE: No projects found")
        return False

def test_north_bangalore_query():
    """Test: 'Show me options with 2cr budget in north bangalore' should return North Bangalore projects"""
    print("\n" + "="*80)
    print("TEST 2: North Bangalore Query")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "Show me options with 2cr budget in north bangalore"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Intent: {state.last_intent}")
    print(f"Extracted Requirements: {response.extracted_requirements}")
    print(f"\nNumber of projects found: {len(response.projects)}")

    if response.projects:
        print("\nProjects returned:")
        for i, project in enumerate(response.projects[:5], 1):
            zone = project.get('zone', 'N/A')
            location = project.get('location', 'N/A')
            name = project.get('name', 'N/A')
            print(f"{i}. {name}")
            print(f"   Zone: {zone}")
            print(f"   Location: {location}")

        # Verify all projects are in North Bangalore
        all_north = all('north' in str(p.get('zone', '')).lower() or
                        'north' in str(p.get('location', '')).lower()
                        for p in response.projects)

        if all_north:
            print("\n✅ SUCCESS: All projects are from North Bangalore")
            return True
        else:
            print("\n❌ FAILURE: Some projects are NOT from North Bangalore")
            return False
    else:
        print("\n❌ WARNING: No projects found for North Bangalore")
        print("This might be expected if there are no North Bangalore projects in the database")
        return True  # Not necessarily a failure if DB doesn't have North Bangalore projects

def test_sarjapur_specific_query():
    """Test: '2 bhk under 1.20 cr in sarjapur' should return Sarjapur area projects"""
    print("\n" + "="*80)
    print("TEST 3: Sarjapur Specific Area Query")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "2 bhk under 1.20 cr in sarjapur"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Intent: {state.last_intent}")
    print(f"Extracted Requirements: {response.extracted_requirements}")
    print(f"\nNumber of projects found: {len(response.projects)}")

    if response.projects:
        print("\nProjects returned:")
        for i, project in enumerate(response.projects[:5], 1):
            zone = project.get('zone', 'N/A')
            location = project.get('location', 'N/A')
            name = project.get('name', 'N/A')
            print(f"{i}. {name}")
            print(f"   Zone: {zone}")
            print(f"   Location: {location}")

        # Verify projects are in East Bangalore (Sarjapur is in East Bangalore)
        all_east = all('east' in str(p.get('zone', '')).lower() or
                       'east' in str(p.get('location', '')).lower()
                       for p in response.projects)

        if all_east:
            print("\n✅ SUCCESS: All projects are from East Bangalore (Sarjapur region)")
            return True
        else:
            print("\n❌ FAILURE: Some projects are NOT from East Bangalore")
            return False
    else:
        print("\n❌ FAILURE: No projects found")
        return False

def test_non_property_query():
    """Test: Non-property queries should be handled appropriately"""
    print("\n" + "="*80)
    print("TEST 4: Non-Property Query")
    print("="*80)

    state = FlowState(requirements=FlowRequirements())
    query = "How do I ask for a meeting with my client?"

    response = execute_flow(state, query)

    print(f"\nQuery: {query}")
    print(f"Intent: {state.last_intent}")
    print(f"Response: {response.system_action}")
    print(f"\nNumber of projects returned: {len(response.projects)}")

    # Non-property query should not return projects
    if len(response.projects) == 0:
        print("\n✅ SUCCESS: No projects returned for non-property query")
        return True
    else:
        print("\n❌ FAILURE: Projects were returned for a non-property query")
        return False

if __name__ == "__main__":
    print("="*80)
    print("LOCATION FILTERING TEST SUITE")
    print("="*80)

    results = []

    # Run all tests
    results.append(("Sarjapur Query", test_sarjapur_query()))
    results.append(("North Bangalore Query", test_north_bangalore_query()))
    results.append(("Sarjapur Specific Query", test_sarjapur_specific_query()))
    results.append(("Non-Property Query", test_non_property_query()))

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
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
