# 🔌 Phase 2 Integration Guide - Enhanced UX Components

**Purpose**: How to integrate Welcome Back Banner, Proactive Nudges, Urgency Signals, and Sentiment Indicator

---

## ✅ Components Available

1. `WelcomeBackBanner` - Shows personalized welcome for returning users
2. `ProactiveNudgeCard` - Displays smart behavioral nudges
3. `UrgencySignals` - Shows urgency indicators (inventory, pricing, etc.)
4. `SentimentIndicator` - Displays sentiment with escalation button

---

## 📦 Import

```tsx
import {
    WelcomeBackBanner,
    ProactiveNudgeCard,
    UrgencySignals,
    SentimentIndicator,
} from '@/components/enhanced-ux';
```

---

## 🎯 Integration into ChatInterface

### Step 1: Add State for Enhanced UX Data

```tsx
// In ChatInterface.tsx
const [userProfile, setUserProfile] = useState<UserProfileData | undefined>();
const [currentSentiment, setCurrentSentiment] = useState<SentimentData | undefined>();
```

### Step 2: Parse Enhanced UX Data from Response

```tsx
// After receiving API response
const response = await apiService.sendQuery({...});

// Extract enhanced UX data (if backend returns it)
if (response.data) {
    if (response.data.user_profile) {
        setUserProfile(response.data.user_profile);
    }
    if (response.data.sentiment) {
        setCurrentSentiment(response.data.sentiment);
    }
}
```

### Step 3: Add Components to JSX

```tsx
return (
    <div className="flex flex-col h-screen">
        {/* Welcome Back Banner - Show once at top */}
        {userProfile && (
            <WelcomeBackBanner
                userProfile={userProfile}
                onDismiss={() => setUserProfile(undefined)}
            />
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
            {messages.map((message) => (
                <div key={message.id}>
                    {/* Message content */}
                    
                    {/* Proactive Nudge Card */}
                    {message.nudge && (
                        <ProactiveNudgeCard
                            nudge={message.nudge}
                            onAction={(action) => {
                                if (action === 'schedule_visit') {
                                    // Trigger schedule visit modal
                                } else if (action === 'show_alternatives') {
                                    // Show alternative properties
                                }
                            }}
                            onDismiss={() => {
                                // Remove nudge from message
                            }}
                        />
                    )}

                    {/* Urgency Signals */}
                    {message.urgency_signals && message.urgency_signals.length > 0 && (
                        <UrgencySignals
                            signals={message.urgency_signals}
                            projectName={message.projects?.[0]?.name}
                        />
                    )}

                    {/* Sentiment Indicator */}
                    {message.sentiment && (
                        <SentimentIndicator
                            sentiment={message.sentiment}
                            onEscalate={() => {
                                // Trigger human escalation
                                // Could open callback modal or show contact info
                            }}
                        />
                    )}
                </div>
            ))}
        </div>
    </div>
);
```

---

## 🔧 Backend Integration

### Option 1: Parse from Response Text (Current)

The backend currently adds nudges to the response text. You can parse them:

```tsx
// Parse nudge from response text
const nudgeMatch = response.answer.match(/🎯\s*(.+)/);
if (nudgeMatch) {
    // Extract nudge message and infer type
    const nudge: ProactiveNudge = {
        type: 'decision_ready', // Infer from message
        message: nudgeMatch[1],
        priority: 'high',
    };
}
```

### Option 2: Extend Backend Response (Recommended)

Update `ChatQueryResponse` in `backend/main.py`:

```python
class ChatQueryResponse(BaseModel):
    # ... existing fields ...
    nudge: Optional[Dict[str, Any]] = None
    urgency_signals: Optional[List[Dict[str, Any]]] = None
    sentiment: Optional[Dict[str, Any]] = None
    user_profile: Optional[Dict[str, Any]] = None
```

Then in the endpoint, return structured data:

```python
return ChatQueryResponse(
    answer=result["answer"],
    # ... other fields ...
    nudge=nudge_dict if nudge else None,
    urgency_signals=urgency_signals_list,
    sentiment=sentiment_dict,
    user_profile=user_profile_dict,
)
```

---

## 🎨 Component Usage Examples

### Welcome Back Banner

```tsx
<WelcomeBackBanner
    userProfile={{
        is_returning_user: true,
        last_visit_date: '2026-01-15',
        viewed_projects_count: 5,
        interests: ['3BHK', 'Whitefield'],
        lead_score: 'warm',
    }}
    onDismiss={() => console.log('Dismissed')}
/>
```

### Proactive Nudge Card

```tsx
<ProactiveNudgeCard
    nudge={{
        type: 'decision_ready',
        message: 'You\'ve viewed 5+ properties! Ready to schedule a site visit?',
        action: 'schedule_visit',
        priority: 'high',
    }}
    onAction={(action) => {
        if (action === 'schedule_visit') {
            setShowScheduleModal(true);
        }
    }}
    onDismiss={() => console.log('Nudge dismissed')}
/>
```

### Urgency Signals

```tsx
<UrgencySignals
    signals={[
        {
            type: 'low_inventory',
            message: 'Only 3 units left in this configuration!',
            priority_score: 9,
        },
        {
            type: 'price_increase',
            message: 'Prices increasing by 5% next month',
            priority_score: 7,
        },
    ]}
    projectName="Brigade Citrine"
/>
```

### Sentiment Indicator

```tsx
<SentimentIndicator
    sentiment={{
        sentiment: 'frustrated',
        frustration_score: 7.5,
        escalation_recommended: true,
        escalation_reason: 'Multiple unanswered questions',
        confidence: 0.85,
    }}
    onEscalate={() => {
        // Open callback modal or show contact info
        setShowCallbackModal(true);
    }}
/>
```

---

## 🎯 User Flows

### Flow 1: Returning User

1. User opens chat
2. Backend detects returning user
3. `WelcomeBackBanner` shows with saved preferences
4. User sees personalized message
5. User can dismiss banner

### Flow 2: Proactive Nudge

1. User views same project 3+ times
2. Backend detects pattern
3. `ProactiveNudgeCard` appears
4. User clicks "Schedule Visit"
5. Schedule modal opens

### Flow 3: Urgency Signal

1. User asks about a project
2. Backend checks inventory/urgency
3. `UrgencySignals` component shows
4. User sees "Only 3 units left!"
5. User is motivated to act

### Flow 4: Sentiment Escalation

1. User shows frustration (score > 7)
2. `SentimentIndicator` shows escalation button
3. User clicks "Talk to Human"
4. Callback modal opens with high urgency
5. Human agent contacts user

---

## 🎨 Styling Notes

### Color Schemes

- **High Priority**: Red theme (`bg-red-50`, `text-red-900`)
- **Medium Priority**: Orange theme (`bg-orange-50`, `text-orange-900`)
- **Low Priority**: Blue theme (`bg-blue-50`, `text-blue-900`)

### Responsive Design

- All components are mobile-responsive
- Cards stack vertically on mobile
- Buttons have adequate touch targets (44x44px minimum)

---

## 🧪 Testing

### Test Welcome Back Banner

```tsx
<WelcomeBackBanner
    userProfile={{
        is_returning_user: true,
        last_visit_date: new Date().toISOString(),
        viewed_projects_count: 3,
        lead_score: 'warm',
    }}
/>
```

### Test Proactive Nudge

```tsx
<ProactiveNudgeCard
    nudge={{
        type: 'repeat_views',
        message: 'You\'ve viewed this property 3 times! Interested?',
        action: 'schedule_visit',
        priority: 'high',
    }}
    onAction={(action) => console.log('Action:', action)}
/>
```

### Test Urgency Signals

```tsx
<UrgencySignals
    signals={[{
        type: 'low_inventory',
        message: 'Only 2 units remaining!',
        priority_score: 9,
    }]}
/>
```

### Test Sentiment Indicator

```tsx
<SentimentIndicator
    sentiment={{
        sentiment: 'frustrated',
        frustration_score: 8,
        escalation_recommended: true,
    }}
    onEscalate={() => console.log('Escalate!')}
/>
```

---

## ✅ Checklist

Before deploying:

- [ ] Backend returns structured nudge/sentiment/urgency data (or parse from text)
- [ ] Welcome Back Banner shows for returning users
- [ ] Proactive Nudge Cards appear when patterns detected
- [ ] Urgency Signals show for relevant projects
- [ ] Sentiment Indicator displays with escalation option
- [ ] All components are responsive
- [ ] Action buttons trigger correct modals/flows
- [ ] Dismiss functionality works
- [ ] Tested on mobile devices

---

## 📚 Related Files

- `frontend/src/types/enhanced-ux.ts` - Type definitions
- `frontend/src/components/enhanced-ux/` - All components
- `backend/services/proactive_nudger.py` - Nudge detection logic
- `backend/services/sentiment_analyzer.py` - Sentiment analysis
- `backend/services/urgency_engine.py` - Urgency signal generation

---

## 🚀 Quick Start

1. Import components
2. Add state for enhanced UX data
3. Parse data from API response (or use mock data for testing)
4. Render components in message flow
5. Handle actions (schedule visit, escalate, etc.)

**That's it!** The components are ready to use. 🎉
