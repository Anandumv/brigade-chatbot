# 🔌 Integration Guide - Scheduling Components

**Purpose**: How to add Schedule Visit and Callback Request to your existing UI

---

## ✅ Components Available

1. `ScheduleVisitModal` - Modal for scheduling site visits
2. `CallbackRequestModal` - Modal for requesting callbacks  
3. `CallbackRequestButton` - Floating button with built-in modal

---

## 📦 Import

```tsx
import {
    ScheduleVisitModal,
    CallbackRequestModal,
    CallbackRequestButton,
} from '@/components/scheduling';
```

---

## 🎯 Integration Points

### 1. **Add to ChatInterface.tsx** (Main Chat)

```tsx
// Add at the top of ChatInterface.tsx
import { useState } from 'react';
import { ScheduleVisitModal, CallbackRequestButton } from '@/components/scheduling';
import { Calendar } from '@/components/icons';

export function ChatInterface({ projects, personas }: ChatInterfaceProps) {
    // Existing state...
    
    // Add new state
    const [showScheduleModal, setShowScheduleModal] = useState(false);
    const [selectedProjectForSchedule, setSelectedProjectForSchedule] = useState<ProjectInfo | null>(null);
    const [userId] = useState(() => {
        // Generate or get user ID
        return localStorage.getItem('userId') || `user_${Date.now()}`;
    });
    const [sessionId] = useState(() => `session_${Date.now()}`);

    // ... rest of component

    return (
        <div className="relative flex flex-col h-screen">
            {/* Existing chat UI... */}
            
            {/* Add Floating Callback Button */}
            <CallbackRequestButton 
                userId={userId} 
                sessionId={sessionId}
            />
            
            {/* Add Schedule Visit Modal */}
            {selectedProjectForSchedule && (
                <ScheduleVisitModal
                    project={selectedProjectForSchedule}
                    userId={userId}
                    sessionId={sessionId}
                    isOpen={showScheduleModal}
                    onClose={() => {
                        setShowScheduleModal(false);
                        setSelectedProjectForSchedule(null);
                    }}
                    onSuccess={(visitId) => {
                        console.log('Visit scheduled:', visitId);
                        // Show success toast or add message to chat
                        setMessages(prev => [...prev, {
                            id: generateId(),
                            role: 'assistant',
                            content: '✅ Great! I've scheduled your site visit. You'll receive a confirmation shortly.',
                            timestamp: new Date(),
                        }]);
                    }}
                />
            )}
        </div>
    );
}
```

### 2. **Add Button to Message Response** (When showing projects)

```tsx
// Inside the message rendering, after displaying properties:

{message.projects && message.projects.length > 0 && (
    <div className="mt-4 flex gap-2">
        <button
            onClick={() => {
                setSelectedProjectForSchedule(message.projects[0]);
                setShowScheduleModal(true);
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 text-sm font-medium"
        >
            <Calendar className="w-4 h-4" />
            Schedule Visit
        </button>
    </div>
)}
```

### 3. **Add to ProjectCard.tsx** (Project Cards)

```tsx
// At the top of ProjectCard.tsx
import { useState } from 'react';
import { ScheduleVisitModal } from '@/components/scheduling';
import { Calendar } from '@/components/icons';

export function ProjectCard({ project, userId }: Props) {
    const [showScheduleModal, setShowScheduleModal] = useState(false);

    return (
        <div className="project-card">
            {/* Existing project card content... */}
            
            {/* Add Schedule Visit Button */}
            <button
                onClick={() => setShowScheduleModal(true)}
                className="w-full mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center justify-center gap-2 font-medium"
            >
                <Calendar className="w-4 h-4" />
                Schedule Site Visit
            </button>
            
            {/* Add Modal */}
            <ScheduleVisitModal
                project={project}
                userId={userId}
                isOpen={showScheduleModal}
                onClose={() => setShowScheduleModal(false)}
                onSuccess={(visitId) => {
                    console.log('Visit scheduled for project:', project.name);
                    // Could trigger analytics, show toast, etc.
                }}
            />
        </div>
    );
}
```

---

## 🎨 Styling Notes

### Floating Button Position

The `CallbackRequestButton` is positioned:
- **Bottom**: `bottom-24` (6rem from bottom) - avoids overlapping with chat input
- **Right**: `right-6` (1.5rem from right)
- **Z-index**: `z-40` - appears above most content
- **Mobile**: Shows icon only, desktop shows "Request Callback" text

### Modal Styling

Both modals use:
- **Backdrop**: Black with 50% opacity and blur
- **Width**: `max-w-lg` (32rem / 512px)
- **Height**: `max-h-[90vh]` with scroll
- **Colors**: Blue for schedule visit, Green for callback
- **Animation**: Smooth transitions on all interactions

---

## 🔧 Customization

### Change Button Position

```tsx
<CallbackRequestButton 
    userId={userId}
    sessionId={sessionId}
    className="bottom-32 right-4" // Custom position
/>
```

### Custom Success Handler

```tsx
<ScheduleVisitModal
    // ... props
    onSuccess={(visitId) => {
        // Send to analytics
        analytics.track('visit_scheduled', { visitId });
        
        // Show toast notification
        toast.success('Visit scheduled successfully!');
        
        // Update state
        setScheduledVisits(prev => [...prev, visitId]);
        
        // Add message to chat
        addMessageToChat('Visit confirmed! Check your email.');
    }}
/>
```

### Pre-fill Form Data

You can modify the components to accept initial form data:

```tsx
// In the modal component, add initialData prop:
interface ScheduleVisitModalProps {
    // ... existing props
    initialData?: {
        contactName?: string;
        contactPhone?: string;
        contactEmail?: string;
    };
}

// Then in your usage:
<ScheduleVisitModal
    project={project}
    userId={userId}
    initialData={{
        contactName: userProfile.name,
        contactPhone: userProfile.phone,
        contactEmail: userProfile.email,
    }}
    // ... other props
/>
```

---

## 📱 Mobile Considerations

### Floating Button

On mobile (`< 768px`):
- Text is hidden (icon only)
- Slightly larger touch target
- Positioned to avoid keyboard

### Modals

On mobile:
- Full width with margins (`mx-4`)
- Scrollable content
- Large touch targets (min 44x44px)
- Keyboard-aware positioning

---

## 🎯 User Flow Examples

### Flow 1: Schedule from Chat

1. User asks: "Show me 3BHK properties"
2. Bot shows properties
3. User clicks "Schedule Visit" button
4. Modal opens with project pre-filled
5. User fills contact details
6. User selects date/time
7. Submit → Success message
8. Confirmation email/SMS sent

### Flow 2: Request Callback

1. User clicks floating callback button
2. Modal opens
3. User fills name, phone, reason
4. User selects urgency (e.g., "High")
5. Submit → Success message
6. Expected callback time shown (e.g., "Within 1-2 hours")

---

## 🧪 Testing

### Test Schedule Visit Modal

```tsx
// In your test or preview page
<ScheduleVisitModal
    project={{
        id: 'test-project',
        name: 'Test Project',
        developer: 'Test Developer',
        location: 'Test Location',
    }}
    userId="test-user"
    sessionId="test-session"
    isOpen={true}
    onClose={() => console.log('Closed')}
    onSuccess={(visitId) => console.log('Scheduled:', visitId)}
/>
```

### Test Callback Button

```tsx
<CallbackRequestButton
    userId="test-user"
    sessionId="test-session"
/>
```

---

## ⚡ Performance Tips

1. **Lazy Load Modals**: Only render when `isOpen={true}`
2. **Memoize Callbacks**: Use `useCallback` for `onSuccess` handlers
3. **Optimize Re-renders**: Modal state is internal, doesn't trigger parent re-renders
4. **Form Validation**: Happens client-side before API call

---

## 🐛 Troubleshooting

### Modal doesn't open
- Check `isOpen` prop is `true`
- Check z-index conflicts
- Verify no errors in console

### Form submission fails
- Check API endpoint is correct (default: `http://localhost:8000`)
- Set `NEXT_PUBLIC_API_URL` in `.env.local`
- Check network tab for error response

### Button not visible
- Check z-index (should be 40+)
- Verify position classes
- Check if overlapped by other elements

---

## 🔗 API Endpoints Used

```
POST /schedule-visit
POST /request-callback
GET /user/{userId}/visits
GET /user/{userId}/callbacks
```

Make sure your backend is running and these endpoints are accessible!

---

## ✅ Quick Checklist

Before deploying:

- [ ] Added `CallbackRequestButton` to main chat UI
- [ ] Added schedule visit trigger to project responses
- [ ] Tested both modals with real data
- [ ] Verified API endpoints work
- [ ] Tested on mobile devices
- [ ] Added success notifications/toasts
- [ ] Set up analytics tracking (optional)
- [ ] Updated user onboarding to mention features

---

## 📚 Example Implementation

See `INTEGRATION_EXAMPLE.tsx` (next file) for a complete working example!
