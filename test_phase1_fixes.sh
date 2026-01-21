#!/bin/bash

# Phase 1 Critical Fixes - Test Suite
# Tests: Timeout protection, Data fields, Mixed language support

BACKEND="https://brigade-chatbot-production.up.railway.app"

echo "================================================"
echo "Phase 1 Critical Fixes - Test Suite"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name=$1
    local query=$2
    local expected=$3

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${YELLOW}Test $TOTAL_TESTS: $test_name${NC}"
    echo "Query: $query"

    # Run query with 20s timeout
    start_time=$(date +%s)
    response=$(curl -s -X POST "$BACKEND/api/assist/" \
        -H "Content-Type: application/json" \
        -d "{\"call_id\":\"test-$TOTAL_TESTS\",\"query\":\"$query\"}" \
        --max-time 20 2>&1)
    end_time=$(date +%s)
    duration=$((end_time - start_time))

    # Check if request completed
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Request completed in ${duration}s${NC}"

        # Check for expected content
        if echo "$response" | grep -q "$expected"; then
            echo -e "${GREEN}✓ PASS: Found expected content${NC}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo -e "${RED}✗ FAIL: Expected content not found${NC}"
            echo "Response preview: $(echo "$response" | head -c 200)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "${RED}✗ FAIL: Request timed out or failed${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

# Wait for Railway deployment (give it 3 minutes)
echo "Waiting for Railway deployment to complete (3 minutes)..."
sleep 180

echo "================================================"
echo "1. PERFORMANCE TIMEOUT TESTS"
echo "================================================"
echo ""

# Test 1: Typo query that previously timed out
run_test "Typo query with timeout protection" \
    "2bhk in whtefield" \
    "projects"

# Test 2: Project name typo
run_test "Project name typo" \
    "brigade avlon" \
    "Avalon"

# Test 3: Fact type typo
run_test "Fact type typo" \
    "rera numbr" \
    "rera"

echo "================================================"
echo "2. MIXED LANGUAGE (HINDI) TESTS"
echo "================================================"
echo ""

# Test 4: Hindi need/want
run_test "Hindi 'chahiye' (need)" \
    "2 bhk chahiye" \
    "2"

# Test 5: Hindi possessive
run_test "Hindi 'ka' (of)" \
    "avalon ka price" \
    "Avalon"

# Test 6: Hindi location
run_test "Hindi 'mein' (in)" \
    "whitefield mein projects" \
    "Whitefield"

# Test 7: Complex Hindi query
run_test "Complex Hinglish query" \
    "3 bhk budget 2 crore mein chahiye" \
    "3"

echo "================================================"
echo "3. DATA FIELD POPULATION TEST"
echo "================================================"
echo ""

# First, run admin refresh
echo "Running admin refresh..."
refresh_response=$(curl -s -X POST "$BACKEND/admin/refresh-projects" \
    -H "x-admin-key: secret")

if echo "$refresh_response" | grep -q "success"; then
    echo -e "${GREEN}✓ Admin refresh successful${NC}"
    echo "Response: $refresh_response"
else
    echo -e "${RED}✗ Admin refresh failed${NC}"
    echo "Response: $refresh_response"
fi
echo ""

# Test 8: Check if new fields are populated
echo -e "${YELLOW}Test 8: Data fields populated after refresh${NC}"
echo "Query: Tell me about Mana Skanda"

fields_response=$(curl -s -X POST "$BACKEND/api/assist/" \
    -H "Content-Type: application/json" \
    -d '{"call_id":"test-fields","query":"Tell me about Mana Skanda"}')

TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Check for brochure_url
if echo "$fields_response" | jq -e '.projects[0].brochure_url' | grep -q "http"; then
    echo -e "${GREEN}✓ brochure_url populated${NC}"
else
    echo -e "${RED}✗ brochure_url still null${NC}"
fi

# Check for rm_details
if echo "$fields_response" | jq -e '.projects[0].rm_details.name' | grep -q -v "null"; then
    echo -e "${GREEN}✓ rm_details populated${NC}"
else
    echo -e "${RED}✗ rm_details still null${NC}"
fi

# Check for rera_number
if echo "$fields_response" | jq -e '.projects[0].rera_number' | grep -q -v "null"; then
    echo -e "${GREEN}✓ rera_number populated${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗ rera_number still null${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
echo ""

echo "================================================"
echo "4. CACHE PERFORMANCE TEST"
echo "================================================"
echo ""

# Test 9: First query (cold cache)
echo -e "${YELLOW}Test 9: Cache performance${NC}"
echo "Query 1 (cold cache): Show me projects in Sarjapur"

start_time=$(date +%s)
curl -s -X POST "$BACKEND/api/assist/" \
    -H "Content-Type: application/json" \
    -d '{"call_id":"test-cache-1","query":"Show me projects in Sarjapur"}' > /dev/null
end_time=$(date +%s)
duration1=$((end_time - start_time))

echo "Cold cache time: ${duration1}s"

# Test 9b: Second query (warm cache)
echo "Query 2 (warm cache): Show me projects in Whitefield"

start_time=$(date +%s)
curl -s -X POST "$BACKEND/api/assist/" \
    -H "Content-Type: application/json" \
    -d '{"call_id":"test-cache-2","query":"Show me projects in Whitefield"}' > /dev/null
end_time=$(date +%s)
duration2=$((end_time - start_time))

echo "Warm cache time: ${duration2}s"

TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ $duration2 -lt $duration1 ]; then
    echo -e "${GREEN}✓ Cache is working (warm cache faster)${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${YELLOW}⚠ Cache may not be working optimally${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
echo ""

echo "================================================"
echo "TEST SUMMARY"
echo "================================================"
echo ""
echo "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo "Phase 1 fixes are working correctly!"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo "Please review the failures above."
    exit 1
fi
