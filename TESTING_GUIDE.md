# Testing Guide - Frontend Integration Verification

**Date**: 2026-01-21
**Deployment**: e2ed061
**Status**: Ready for testing

---

## 🎯 What to Test

The following features were just deployed and need verification:

1. **CoachingPointCard** - Blue card with sales coaching guidance
2. **MatchingUnitsCard** - Green card showing matching BHK configurations
3. **Answer-first rendering** - Answer displays before projects
4. **Branding** - "Pin Click Sales Assist" throughout

---

## 🧪 Quick Manual Tests

### Test 1: Coaching Point Display

**Query**: "3BHK under 2Cr in East Bangalore"

**Expected Result**:
- ✅ Answer displays first (3-5 bullet points)
- ✅ Blue **Coaching Point** card appears after answer
- ✅ Coaching text is relevant to the query (e.g., "Highlight payment flexibility...")
- ✅ Projects display after coaching point

**What to Look For**:
```
Answer:
• Based on your requirement...
• Here's what's available...

[BLUE CARD]
💡 Coaching Point for Sales Rep
"Highlight payment flexibility and value appreciation to address budget concerns"
[/BLUE CARD]

Matching Projects:
[Project cards...]
```

---

### Test 2: Matching Units Display

**Query**: "2BHK under 1.5Cr in Sarjapur"

**Expected Result**:
- ✅ Projects display with ProjectCard
- ✅ Green **Matching Units** card appears below each project
- ✅ Shows which BHK configurations match the search
- ✅ Displays Config | Size | Price in table format

**What to Look For**:
```
[Project Card: Brigade Citrine]

[GREEN CARD]
✓ Matching Units in Brigade Citrine
Config    Size           Price
2BHK      1150 sq.ft     ₹1.45 Cr
[/GREEN CARD]
```

---

### Test 3: Generic Question with Coaching

**Query**: "How far is Sarjapur from the airport?"

**Expected Result**:
- ✅ Answer with 3-5 bullet points (NOT project cards)
- ✅ Coaching point specific to location questions
- ✅ Example coaching: "Acknowledge commute concern, then pivot to connectivity improvements..."

---

### Test 4: Hindi Query with Coaching

**Query**: "2 bhk chahiye"

**Expected Result**:
- ✅ Query understood correctly (property search, not project facts)
- ✅ Returns 2BHK projects
- ✅ Coaching point displays
- ✅ Matching units show which projects have 2BHK

---

### Test 5: Budget + BHK Query

**Query**: "Show me 3BHK options under 2 crore"

**Expected Result**:
- ✅ Answer summarizes available options first
- ✅ Coaching point about budget handling
- ✅ Projects display with matching 3BHK units only
- ✅ Matching units card shows configurations under 2Cr

---

### Test 6: Branding Verification

**What to Check**:
- ✅ Header shows "Pin Click Sales Assist"
- ✅ Input placeholder: "Message Pin Click Sales Assist..."
- ✅ Footer: "Pin Click Sales Assist can make mistakes..."
- ✅ No references to "Pin Click GPT"

---

## 🖥️ UI/UX Checklist

### Coaching Point Card
- [ ] Blue gradient background
- [ ] Lightbulb icon visible
- [ ] Text is readable and actionable
- [ ] Card displays after answer, before projects
- [ ] Responsive on mobile

### Matching Units Card
- [ ] Green theme (positive confirmation)
- [ ] Checkmark icon visible
- [ ] Table format: Config | Size | Price
- [ ] Shows correct BHK configurations
- [ ] Displays after each relevant project

### Answer-First Rendering
- [ ] Answer bullets display first
- [ ] Coaching point displays second
- [ ] Projects display last
- [ ] Clear visual separation between sections

### General UI
- [ ] No console errors
- [ ] No layout shifts or flickering
- [ ] Cards render smoothly
- [ ] Text is readable
- [ ] Spacing looks good

---

## 🚨 Known Issues to Watch For

### Issue 1: Missing Coaching Point
**Symptom**: No blue coaching card displays
**Cause**: Backend not returning coaching_point field
**Fix**: Verify GPT prompt includes coaching point rules

### Issue 2: Missing Matching Units
**Symptom**: No green matching units card
**Cause**: Backend not returning matching_units array
**Fix**: Verify budget + BHK filters are working

### Issue 3: Component Import Errors
**Symptom**: Console error about missing components
**Cause**: Build/deployment issue
**Fix**: Clear Next.js cache, rebuild:
```bash
cd frontend
rm -rf .next
npm run build
```

---

## 🔍 Debugging Commands

### Check Backend Response
```bash
curl -X POST https://brigade-chatbot-production.up.railway.app/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"debug-test","query":"3BHK under 2Cr"}' | jq '.'
```

**Look for**:
```json
{
  "coaching_point": "...",  // Should be present
  "answer": [...],
  "projects": [
    {
      "matching_units": [...]  // Should be present if BHK+budget query
    }
  ]
}
```

### Check Console for Errors
1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for:
   - ✅ No red errors
   - ✅ No "Cannot find module" errors
   - ⚠️ Warnings are OK

### Verify Component Files Deployed
```bash
ls -la frontend/src/components/CoachingPointCard.tsx
ls -la frontend/src/components/MatchingUnitsCard.tsx
ls -la frontend/src/components/ChatInterface.tsx
```

All should exist and show recent modification time.

---

## 📊 Test Scenarios Table

| Query | Expected Coaching | Expected Matching Units |
|-------|------------------|------------------------|
| "3BHK under 2Cr" | Budget/payment flexibility | 3BHK units under 2Cr |
| "2 bhk chahiye" | General search guidance | 2BHK units |
| "How far from airport?" | Location/commute handling | N/A (no projects) |
| "Tell me about Brigade Citrine" | Project-specific guidance | All available units |
| "Show ready to move" | Urgency/timeline guidance | Ready-to-move units |

---

## ✅ Success Criteria

### Minimum Viable Test Results
- [ ] Coaching point displays on **at least 5/5 test queries**
- [ ] Matching units display when BHK + budget specified (2/5 queries)
- [ ] Answer displays before projects in all cases
- [ ] No console errors
- [ ] Branding shows "Pin Click Sales Assist"

### Ideal Test Results
- [ ] All 6 manual tests pass completely
- [ ] UI/UX checklist 100% complete
- [ ] Mobile responsive verified
- [ ] Coaching points are contextually relevant
- [ ] Matching units show correct configurations

---

## 🎯 Performance Benchmarks

### Response Time
- ✅ Query response < 15 seconds
- ✅ Component render < 100ms
- ✅ No layout shift

### Functionality
- ✅ 100% queries include coaching_point
- ✅ BHK+budget queries include matching_units
- ✅ Answer-first rendering 100% of time

---

## 📞 If Issues Arise

1. **Check Railway Logs**: Look for deployment success/errors
2. **Verify Backend**: Test API endpoint directly with curl
3. **Clear Cache**: Browser cache and Next.js build cache
4. **Rebuild Frontend**: `cd frontend && npm run build`
5. **Check Git Status**: Verify e2ed061 is deployed

---

## 🚀 Next Steps After Testing

### If All Tests Pass ✅
1. Mark deployment as complete
2. Run automated test suite: `./test_phase1_fixes.sh`
3. Run admin refresh to populate data fields
4. User acceptance testing
5. Production monitoring

### If Issues Found ❌
1. Document specific issue
2. Check which component is failing
3. Review backend response format
4. Check frontend console errors
5. Create fix and redeploy

---

## 📝 Test Report Template

```
Test Date: _____________________
Tested By: _____________________

Test 1 - Coaching Point Display: [ ] PASS [ ] FAIL
Notes: _____________________

Test 2 - Matching Units Display: [ ] PASS [ ] FAIL
Notes: _____________________

Test 3 - Generic Question: [ ] PASS [ ] FAIL
Notes: _____________________

Test 4 - Hindi Query: [ ] PASS [ ] FAIL
Notes: _____________________

Test 5 - Budget + BHK: [ ] PASS [ ] FAIL
Notes: _____________________

Test 6 - Branding: [ ] PASS [ ] FAIL
Notes: _____________________

UI/UX Checklist: _____ / 13 items complete

Overall Status: [ ] PASS [ ] FAIL
Issues Found: _____________________
```

---

**Ready to Test**: Open chatbot UI and run the 6 manual tests above!

**Test URL**: https://brigade-chatbot-production.up.railway.app
