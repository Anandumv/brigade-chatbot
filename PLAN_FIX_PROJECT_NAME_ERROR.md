# Plan: Fix UnboundLocalError for project_name

## Problem

```
ERROR: local variable 'project_name' referenced before assignment
at line 1085: if project_name and not filters.project_name:
```

## Root Cause

Line 1085 in `main.py` references `project_name` variable, but this variable is only defined inside the `more_info_request` intent block (line 766). When other intents like `property_search` execute, `project_name` is never defined, causing an `UnboundLocalError`.

### Current Code Flow

```python
# Line 766: project_name only defined in more_info_request block
if intent == "more_info_request":
    project_name = extraction.get("project_name")  # Defined here
    # ... more logic ...

# Line 1085: project_name referenced outside the block
if intent == "property_search":
    # ... 
    if project_name and not filters.project_name:  # ERROR: project_name not defined!
        filters.project_name = project_name
```

## Solution

Initialize `project_name = None` at the start of the request handler, before any intent-specific logic. This ensures the variable is always defined, even if it remains `None`.

## Implementation

**File**: [backend/main.py](backend/main.py)

**Location**: After extracting intent from GPT (around line 350-360), before any intent handlers

**Add**:
```python
# Initialize project_name to avoid UnboundLocalError
project_name = extraction.get("project_name") if extraction else None
```

This way:
- All intent handlers can access `project_name`
- If not extracted, it's `None` (safe to check)
- No breaking changes to existing logic

## Files to Modify

- [backend/main.py](backend/main.py) - Add `project_name` initialization

## Expected Result

✅ No more `UnboundLocalError`  
✅ All intents can safely reference `project_name`  
✅ Existing logic unchanged
