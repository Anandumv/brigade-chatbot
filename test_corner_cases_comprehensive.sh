#!/bin/bash
# Comprehensive Corner Case Test Suite
# Tests all 41 corner cases with fixes applied

BACKEND="${BACKEND_URL:-https://brigade-chatbot-production.up.railway.app}"

echo "=========================================="
echo "Comprehensive Corner Case Testing"
echo "Backend: $BACKEND"
echo "=========================================="
echo ""

# Test 1-6: Typo Handling
echo "=== Test 1-6: Typo Handling ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-1","query":"distnce of airport form brigade avalon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-2","query":"avalon prise"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-3","query":"citrine ammenities"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-4","query":"2bhk in whtefield"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-5","query":"brigade avlon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-6","query":"rera numbr"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 7-9: Incomplete Queries
echo ""
echo "=== Test 7-9: Incomplete Queries ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-7","query":"price"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-8","query":"more"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-9","query":"details"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 10-11: Vague References
echo ""
echo "=== Test 10-11: Vague References ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-10","query":"it"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-11","query":"these"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 12-15: Single Words
echo ""
echo "=== Test 12-15: Single Words ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-12","query":"yes"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-13","query":"no"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-14","query":"ok"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-15","query":"thanks"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 16-18: Mixed Languages
echo ""
echo "=== Test 16-18: Mixed Languages ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-16","query":"2 bhk chahiye"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-17","query":"avalon ka price"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-18","query":"citrine ki location"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 19-23: Slang & Abbreviations
echo ""
echo "=== Test 19-23: Slang & Abbreviations ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-19","query":"show me 2bhk"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-20","query":"show me 3bhk"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-21","query":"what is rtm"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-22","query":"what is rera"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-23","query":"what is emi"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 24-27: No Question Marks
echo ""
echo "=== Test 24-27: No Question Marks ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-24","query":"show me 2bhk"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-25","query":"avalon price"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-26","query":"tell me about citrine"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-27","query":"distance airport avalon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 28-29: Multiple Intents
echo ""
echo "=== Test 28-29: Multiple Intents ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-28","query":"show 2bhk and compare with citrine"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-29","query":"price and amenities of avalon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 30-33: Context Continuity
echo ""
echo "=== Test 30-33: Context Continuity ==="
CALL_ID="test-30"
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d "{\"call_id\":\"$CALL_ID\",\"query\":\"show 2bhk in whitefield\"}" \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d "{\"call_id\":\"$CALL_ID\",\"query\":\"price\"}" \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d "{\"call_id\":\"$CALL_ID\",\"query\":\"more\"}" \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d "{\"call_id\":\"$CALL_ID\",\"query\":\"nearby\"}" \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 34-36: Project Name Variations
echo ""
echo "=== Test 34-36: Project Name Variations ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-34","query":"avalon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-35","query":"citrine"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-36","query":"brigade avalon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 37-39: Distance/Connectivity
echo ""
echo "=== Test 37-39: Distance/Connectivity ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-37","query":"distance of airport from brigade avalon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-38","query":"how far is metro from citrine"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-39","query":"nearby schools to avalon"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

# Test 40-41: Edge Cases
echo ""
echo "=== Test 40-41: Edge Cases ==="
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-40","query":"2bhk @ whitefield"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-41","query":"2"}' \
  --max-time 15 | jq -r '.answer[0] // "ERROR"'

echo ""
echo "=========================================="
echo "All 41 corner case tests completed"
echo "=========================================="
