# Quick Start Guide - Production Deployment

**Last Updated**: 2026-01-21
**Status**: Backend deployed, Frontend ready

---

## ⚡ 3-Minute Quick Start

### Step 1: Verify Backend (30 seconds)

```bash
# Test backend is working
curl https://brigade-chatbot-production.up.railway.app/health

# Run admin refresh (load 76 projects)
curl -X POST https://brigade-chatbot-production.up.railway.app/admin/refresh-projects \
  -H 'x-admin-key: secret'

# Test a query
curl -X POST https://brigade-chatbot-production.up.railway.app/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test","query":"3BHK under 2Cr in East Bangalore"}' | jq
```

**Expected**: Should see projects with `matching_units` and `coaching_point` fields

---

### Step 2: Update Frontend (10 minutes)

**File to edit**: `frontend/src/components/ChatInterface.tsx`

**1. Add imports at top**:
```tsx
import { CoachingPointCard } from '@/components/CoachingPointCard';
import { MatchingUnitsCard } from '@/components/MatchingUnitsCard';
```

**2. Find where assistant messages render (around line 450)**

Add after answer bullets:
```tsx
{/* NEW: Display coaching point */}
{copilotResponse?.coaching_point && (
    <CoachingPointCard coaching_point={copilotResponse.coaching_point} />
)}
```

**3. Find where projects are mapped (around line 460-480)**

Wrap each project:
```tsx
{copilotResponse?.projects?.map((project, idx) => (
    <div key={idx} className="space-y-2">
        <ProjectCard project={project} />

        {/* NEW: Show matching units */}
        {project.matching_units && (
            <MatchingUnitsCard
                matching_units={project.matching_units}
                projectName={project.name}
            />
        )}
    </div>
))}
```

---

### Step 3: Test Locally (5 minutes)

```bash
cd frontend
npm run dev
```

**Test these 3 queries**:
1. "3BHK under 2Cr in East Bangalore" → Should see green MatchingUnitsCard
2. "Show me projects in Sarjapur" → Should see multiple projects
3. Any query → Should see blue CoachingPointCard

---

### Step 4: Deploy (2 minutes)

```bash
cd frontend
npm run build
# Deploy to your hosting
```

---

## ✅ What's Fixed

| Issue | Fixed | Test |
|-------|-------|------|
| Budget filtering | ✅ | "3BHK under 2Cr" shows only matching units |
| Missing fields | ✅ | Brochure, RM, RERA all present |
| Area searches | ✅ | "Projects in Sarjapur" returns list |
| Coaching | ✅ | Every response has coaching_point |

---

## 🔍 Quick Test Commands

```bash
# Production Backend
BACKEND="https://brigade-chatbot-production.up.railway.app"

# Test 1: Budget filtering
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-1","query":"3BHK under 2Cr"}' | jq '.projects[0].matching_units'

# Test 2: Coaching point
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-2","query":"How far is Sarjapur?"}' | jq '.coaching_point'

# Test 3: All fields
curl -X POST $BACKEND/api/assist/ \
  -H "Content-Type: application/json" \
  -d '{"call_id":"test-3","query":"Tell me about Mana Skanda"}' | \
  jq '.projects[0] | {brochure_url, rm_details, rera_number}'
```

---

## 📄 Documentation Files

- `BACKEND_FIXES_COMPLETED.md` - Detailed backend documentation
- `FRONTEND_UPDATES_GUIDE.md` - Step-by-step frontend guide
- `COMPLETE_IMPLEMENTATION_SUMMARY.md` - Complete overview
- `QUICK_START_GUIDE.md` - This file

---

## 🆘 Troubleshooting

**Backend returns 0 projects**:
```bash
# Run admin refresh
curl -X POST $BACKEND/admin/refresh-projects -H 'x-admin-key: secret'
```

**coaching_point missing**:
- Backend automatically adds default if missing
- Check backend logs for warnings

**matching_units not showing**:
- Only appears when BOTH BHK and budget filters are present
- Try: "3BHK under 2Cr" (has both filters)
- Not: "Show projects in Sarjapur" (no filters)

**Frontend components not found**:
```bash
# Verify files exist
ls frontend/src/components/CoachingPointCard.tsx
ls frontend/src/components/MatchingUnitsCard.tsx
```

---

## 🎯 Success Checklist

- [ ] Backend health check passes
- [ ] Admin refresh loads 76 projects
- [ ] Test query returns projects with new fields
- [ ] `matching_units` present when BHK + budget specified
- [ ] `coaching_point` present on every response
- [ ] Frontend shows blue CoachingPointCard
- [ ] Frontend shows green MatchingUnitsCard (when relevant)
- [ ] Brochure/RM buttons work in ProjectCard
- [ ] No console errors

**All checks passed?** You're production ready! 🚀

---

## 💡 Pro Tips

1. **Coaching points**: Appear on EVERY response - train sales reps to use them

2. **Matching units**: Only show when user specifies BHK + budget
   - Shows: "3BHK under 2Cr"
   - Doesn't show: "Projects in Sarjapur"

3. **Brochure download**: Already supported by existing ProjectCard component

4. **Admin key**: Default is "secret" - change in production for security

5. **Testing**: Use jq to prettify JSON: `| jq` at end of curl commands

---

**Total setup time**: ~15-20 minutes

**Ready to deploy!** 🎉
