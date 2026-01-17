# 🎨 Frontend UI Implementation Plan

**Date**: January 17, 2026  
**Status**: Backend complete, UI needed  
**Stack**: Next.js + TypeScript + Tailwind CSS

---

## 📋 What's Already Built (Backend)

### Phase 1: Conversation Coaching ✅
- Real-time sales coaching engine
- Market intelligence with Bangalore data
- Urgency signals generation
- Budget alternatives suggestions

### Phase 2A: Sentiment Analysis ✅
- User sentiment tracking (positive, negative, frustrated, excited)
- Frustration score (0-10)
- Human escalation triggers

### Phase 2B: User Profiles ✅
- Cross-session memory
- Preference tracking
- Lead scoring (hot/warm/cold)
- Welcome back messages

### Phase 2C: Proactive Nudging ✅
- Behavior pattern detection
- Smart suggestions (repeat views, decision readiness, etc.)
- Cooldown logic

### Phase 3A: Scheduling ✅
- Site visit scheduling (`POST /schedule-visit`)
- Callback requests (`POST /request-callback`)
- RM assignment
- Status tracking

### Phase 3B: Calendar & Reminders ✅
- Calendar event creation
- Automated reminders (24h, 1h before)
- Email/SMS scheduling

---

## 🎯 UI Components Needed

### 1. **Site Visit Scheduling Modal** 🆕

**Purpose**: Let users schedule site visits directly from chat

**Location**: Trigger from chat message or project card

**Design**:
```tsx
<ScheduleVisitModal>
  {/* Project info (auto-filled from context) */}
  <ProjectSummary project={selectedProject} />
  
  {/* Contact details */}
  <Input label="Your Name" />
  <Input label="Phone Number" />
  <Input label="Email (optional)" />
  
  {/* Preferred date/time */}
  <DatePicker label="Preferred Date" />
  <TimeSlotPicker options={['morning', 'afternoon', 'evening']} />
  
  {/* Additional notes */}
  <Textarea label="Any specific requirements?" />
  
  {/* Submit */}
  <Button>Schedule Visit</Button>
</ScheduleVisitModal>
```

**API Call**:
```typescript
POST /schedule-visit
{
  user_id, session_id, project_id, project_name,
  contact_name, contact_phone, contact_email,
  requested_date, requested_time_slot, user_notes
}
```

**Success Message**:
```
✅ Visit Scheduled!
📅 Date: Monday, January 20, 2026
⏰ Time: 9:00 AM - 12:00 PM
👤 RM: Rajesh Kumar
📞 +91 98765 43210
📧 Confirmation sent to your email
```

---

### 2. **Callback Request Button** 🆕

**Purpose**: Quick way to request a callback

**Location**: Chat interface (floating button or in message)

**Design**:
```tsx
<CallbackRequestButton>
  <Icon>📞</Icon>
  <Text>Request Callback</Text>
</CallbackRequestButton>

<CallbackModal>
  <Input label="Your Name" />
  <Input label="Phone Number" />
  <Select label="Urgency" options={['Low', 'Medium', 'High', 'Urgent']} />
  <Select label="Reason" options={[
    'General inquiry',
    'Pricing details',
    'Site visit',
    'Documentation',
    'Other'
  ]} />
  <Textarea label="What would you like to discuss?" />
  <Button>Request Callback</Button>
</CallbackModal>
```

**Success Message**:
```
✅ Callback Requested!
📞 Agent: Priya Sharma
⏱️ Expected call: Within 1-2 hours
📱 We'll call you at: +91 98765 43210
```

---

### 3. **Welcome Back Banner** 🆕

**Purpose**: Show personalized greeting for returning users

**Location**: Top of chat interface (first message)

**Design**:
```tsx
<WelcomeBackBanner>
  <Icon>👋</Icon>
  <Heading>Welcome back, Anand!</Heading>
  <Subtext>
    You were interested in Brigade Citrine.
    Would you like to schedule a site visit?
  </Subtext>
  <LeadBadge type="hot">🔥 Hot Lead</LeadBadge>
  <Stats>
    <Stat>🏠 5 properties viewed</Stat>
    <Stat>❤️ 2 favorites</Stat>
    <Stat>📅 Session #3</Stat>
  </Stats>
</WelcomeBackBanner>
```

---

### 4. **Sentiment Indicator** 🆕

**Purpose**: Visual feedback on conversation sentiment

**Location**: Chat interface header or footer

**Design**:
```tsx
<SentimentIndicator sentiment="positive">
  <Icon>😊</Icon>
  <Text>Great! I'm here to help</Text>
</SentimentIndicator>

{/* States */}
😊 Positive (green)
😐 Neutral (gray)
😟 Frustrated (yellow)
😠 Very Frustrated (red) + "Talk to human" button
```

**Frustrated State**:
```tsx
<FrustrationAlert>
  <Icon>⚠️</Icon>
  <Text>Having trouble? Let me connect you with our team</Text>
  <Button onClick={escalateToHuman}>Talk to a Human</Button>
</FrustrationAlert>
```

---

### 5. **Proactive Nudge Cards** 🆕

**Purpose**: Display smart suggestions based on behavior

**Location**: Inline in chat (after AI response)

**Design**:
```tsx
<NudgeCard type="repeat_views">
  <Icon>👀</Icon>
  <Heading>You've viewed Brigade Citrine 3 times</Heading>
  <Text>
    Looks like you're interested! Would you like to:
  </Text>
  <Actions>
    <Button>📅 Schedule Visit</Button>
    <Button>📊 Compare with Others</Button>
    <Button>💰 Check Pricing</Button>
  </Actions>
</NudgeCard>
```

**Nudge Types**:
- `repeat_views`: Viewed same property multiple times
- `decision_ready`: High engagement, ready to decide
- `location_focus`: Focused on specific location
- `budget_concern`: Worried about pricing
- `long_session`: Engaged for extended time
- `abandoned_interest`: Previously interested, came back

---

### 6. **Coaching Prompt Display** 🆕

**Purpose**: Show sales guidance to RM (admin view)

**Location**: Admin dashboard sidebar

**Design**:
```tsx
<CoachingPanel>
  <Heading>💡 Coaching Prompts</Heading>
  
  <CoachingCard priority="high">
    <Badge>Site Visit Opportunity</Badge>
    <Message>
      User has viewed 3 properties. Perfect time to suggest site visit!
    </Message>
    <Script>
      "I see you're interested in {project_name}. 
       Would you like to visit it in person? 
       We have slots available this weekend."
    </Script>
  </CoachingCard>
  
  <CoachingCard priority="medium">
    <Badge>Budget Objection</Badge>
    <Message>User concerned about budget</Message>
    <Script>
      "I understand budget is a concern. 
       Let me show you similar properties that offer better value..."
    </Script>
  </CoachingCard>
</CoachingPanel>
```

---

### 7. **Market Intelligence Cards** 🆕

**Purpose**: Display competitive analysis and ROI data

**Location**: Inline with project details

**Design**:
```tsx
<MarketIntelligenceCard>
  <Heading>📊 Market Insights</Heading>
  
  <PriceComparison>
    <Label>Price vs Market Average</Label>
    <Bar percentage={-5} color="green">
      5% below market 💰
    </Bar>
  </PriceComparison>
  
  <AppreciationForecast>
    <Label>Expected Appreciation (3 years)</Label>
    <Value color="green">+35%</Value>
    <Subtext>₹1.2 Cr → ₹1.62 Cr</Subtext>
  </AppreciationForecast>
  
  <ROICalculator>
    <Label>Estimated ROI</Label>
    <Value>12% per year</Value>
  </ROICalculator>
  
  <LocalityInsights>
    <Tag>🚇 Metro nearby (2025)</Tag>
    <Tag>🏫 Top schools</Tag>
    <Tag>🏢 IT corridor</Tag>
  </LocalityInsights>
</MarketIntelligenceCard>
```

---

### 8. **Urgency Signals** 🆕

**Purpose**: Create FOMO with authentic urgency

**Location**: Project cards and details

**Design**:
```tsx
<UrgencyBanner type="high">
  <Icon>⚡</Icon>
  <Message>Only 3 units left in your budget!</Message>
  <Countdown>Last price increase 2 weeks ago</Countdown>
</UrgencyBanner>

{/* Types */}
<UrgencyTag type="low_inventory">
  🏠 Only 5 units left
</UrgencyTag>

<UrgencyTag type="price_increase">
  📈 Price increased ₹5L last month
</UrgencyTag>

<UrgencyTag type="limited_time">
  ⏰ Launch offer ends in 7 days
</UrgencyTag>

<UrgencyTag type="high_demand">
  🔥 10 bookings this week
</UrgencyTag>
```

---

### 9. **Admin Dashboard Enhancements** 🆕

**Purpose**: Manage visits, callbacks, and user profiles

**Location**: `/admin` route

**Design**:

#### **9a. Visits Management**
```tsx
<VisitsTable>
  <Filters>
    <Select label="Status" options={['All', 'Pending', 'Confirmed', 'Completed']} />
    <DateRange label="Date Range" />
    <Search placeholder="Search by name, project..." />
  </Filters>
  
  <Table>
    <Row>
      <Cell><Badge>Pending</Badge></Cell>
      <Cell>Anand Kumar</Cell>
      <Cell>Brigade Citrine</Cell>
      <Cell>Jan 20, 2026 - Morning</Cell>
      <Cell>Rajesh Kumar</Cell>
      <Cell>
        <Button size="sm">Confirm</Button>
        <Button size="sm" variant="outline">Reschedule</Button>
        <Button size="sm" variant="ghost">Cancel</Button>
      </Cell>
    </Row>
  </Table>
</VisitsTable>
```

#### **9b. Callbacks Dashboard**
```tsx
<CallbacksTable>
  <Filters>
    <Select label="Urgency" options={['All', 'Urgent', 'High', 'Medium', 'Low']} />
    <Select label="Status" options={['All', 'Pending', 'Contacted', 'Completed']} />
  </Filters>
  
  <Table>
    <Row urgency="high">
      <Cell><Badge color="red">High</Badge></Cell>
      <Cell>Priya Sharma</Cell>
      <Cell>+91 98765 43210</Cell>
      <Cell>Pricing details</Cell>
      <Cell>2 hours ago</Cell>
      <Cell>
        <Button size="sm">Call Now</Button>
        <Button size="sm" variant="outline">Mark Contacted</Button>
      </Cell>
    </Row>
  </Table>
</CallbacksTable>
```

#### **9c. User Profiles Dashboard**
```tsx
<UserProfilesTable>
  <Filters>
    <Select label="Lead Temperature" options={['All', 'Hot', 'Warm', 'Cold']} />
    <Input placeholder="Search users..." />
  </Filters>
  
  <Table>
    <Row>
      <Cell><LeadBadge type="hot">🔥 Hot</LeadBadge></Cell>
      <Cell>
        <UserInfo>
          <Name>Anand Kumar</Name>
          <Email>anand@example.com</Email>
        </UserInfo>
      </Cell>
      <Cell>
        <Score>
          <Label>Engagement</Label>
          <Value>8.5/10</Value>
        </Score>
        <Score>
          <Label>Intent</Label>
          <Value>9.2/10</Value>
        </Score>
      </Cell>
      <Cell>
        <Stats>
          <Stat>5 properties viewed</Stat>
          <Stat>3 sessions</Stat>
          <Stat>1 site visit scheduled</Stat>
        </Stats>
      </Cell>
      <Cell>
        <Button size="sm">View Profile</Button>
      </Cell>
    </Row>
  </Table>
</UserProfilesTable>
```

---

## 🚀 Implementation Priority

### **Phase 1 (Essential - 1-2 days)**
1. ✅ Site Visit Scheduling Modal
2. ✅ Callback Request Button
3. ✅ Admin Visits Management
4. ✅ Admin Callbacks Dashboard

### **Phase 2 (Enhanced UX - 1 day)**
5. ✅ Welcome Back Banner
6. ✅ Proactive Nudge Cards
7. ✅ Urgency Signals

### **Phase 3 (Advanced - 1 day)**
8. ✅ Sentiment Indicator
9. ✅ Market Intelligence Cards
10. ✅ User Profiles Dashboard

---

## 📁 File Structure

```
frontend/src/
├── components/
│   ├── scheduling/
│   │   ├── ScheduleVisitModal.tsx      🆕
│   │   ├── CallbackRequestButton.tsx   🆕
│   │   └── CallbackModal.tsx           🆕
│   ├── user/
│   │   ├── WelcomeBackBanner.tsx       🆕
│   │   ├── LeadBadge.tsx               🆕
│   │   └── SentimentIndicator.tsx      🆕
│   ├── coaching/
│   │   ├── NudgeCard.tsx               🆕
│   │   ├── CoachingPanel.tsx           🆕
│   │   └── UrgencyBanner.tsx           🆕
│   ├── intelligence/
│   │   └── MarketIntelligenceCard.tsx  🆕
│   └── admin/
│       ├── VisitsTable.tsx             🆕
│       ├── CallbacksTable.tsx          🆕
│       └── UserProfilesTable.tsx       🆕
├── services/
│   ├── api.ts                          (update)
│   └── scheduling-api.ts               🆕
└── types/
    ├── scheduling.ts                   🆕
    └── user-profile.ts                 🆕
```

---

## 🔌 API Integration

### **New API Endpoints to Integrate**

```typescript
// services/scheduling-api.ts

export const scheduleVisit = async (data: VisitRequest) => {
  return api.post('/schedule-visit', data);
};

export const requestCallback = async (data: CallbackRequest) => {
  return api.post('/request-callback', data);
};

export const getScheduledVisits = async (userId: string) => {
  return api.get(`/user/${userId}/visits`);
};

export const getCallbacks = async (userId: string) => {
  return api.get(`/user/${userId}/callbacks`);
};

// Admin endpoints
export const getAllVisits = async () => {
  return api.get('/admin/visits');
};

export const getAllCallbacks = async () => {
  return api.get('/admin/callbacks');
};

export const updateVisitStatus = async (visitId: string, status: string) => {
  return api.patch(`/admin/visits/${visitId}`, { status });
};

export const updateCallbackStatus = async (callbackId: string, status: string) => {
  return api.patch(`/admin/callbacks/${callbackId}`, { status });
};
```

---

## 🎨 Design System

### **Colors**

```css
/* Lead temperatures */
--hot-lead: #EF4444;      /* Red */
--warm-lead: #F59E0B;     /* Amber */
--cold-lead: #3B82F6;     /* Blue */

/* Sentiment */
--positive: #10B981;      /* Green */
--neutral: #6B7280;       /* Gray */
--frustrated: #F59E0B;    /* Amber */
--very-frustrated: #EF4444; /* Red */

/* Urgency */
--urgency-high: #EF4444;  /* Red */
--urgency-medium: #F59E0B; /* Amber */
--urgency-low: #3B82F6;   /* Blue */
```

### **Icons**

```tsx
// Use these emoji or replace with icon library
📅 Schedule
📞 Callback
👋 Welcome
😊 Sentiment
💡 Coaching
📊 Intelligence
⚡ Urgency
🔥 Hot Lead
❤️ Favorite
👀 Viewed
```

---

## ✅ Testing Checklist

### **User Flow Testing**

- [ ] User can schedule a site visit from chat
- [ ] User can request a callback
- [ ] Returning user sees welcome message
- [ ] Nudges appear at appropriate times
- [ ] Sentiment indicator updates correctly
- [ ] Frustrated users can escalate to human
- [ ] Admin can view all visits
- [ ] Admin can view all callbacks
- [ ] Admin can update visit/callback status
- [ ] Admin can view user profiles and lead scores

### **Mobile Responsiveness**

- [ ] Schedule modal works on mobile
- [ ] Callback button accessible on mobile
- [ ] Admin tables scroll horizontally on mobile
- [ ] All cards stack properly on mobile

---

## 📚 Documentation Needed

1. **User Guide**: How to schedule visits and request callbacks
2. **Admin Guide**: How to manage visits, callbacks, and leads
3. **Developer Guide**: How to add new nudges and coaching rules
4. **Design System**: Component library and usage examples

---

## 🎯 Success Metrics

After UI implementation, track:

- 📈 **Conversion Rate**: % users who schedule visits
- 📞 **Callback Rate**: % users who request callbacks
- ❤️ **Engagement**: Avg session duration, pages per session
- 🔥 **Lead Quality**: Hot/warm/cold lead distribution
- 😊 **Sentiment**: Positive vs frustrated conversations
- 👥 **Human Escalation**: % conversations escalated

---

## 🚀 Quick Start (For Developer)

```bash
# 1. Install dependencies
cd frontend
npm install

# 2. Add new API endpoints to services/api.ts

# 3. Create scheduling components
mkdir -p src/components/scheduling
# Create ScheduleVisitModal.tsx
# Create CallbackRequestButton.tsx

# 4. Update ChatInterface to show new features

# 5. Test locally
npm run dev

# 6. Deploy
npm run build
```

---

## 💡 Future Enhancements

- 📱 WhatsApp integration for reminders
- 📧 Email templates for confirmations
- 📊 Analytics dashboard for sales team
- 🤖 Chatbot handoff to human agent
- 🎥 Virtual site visit scheduling
- 💬 Live chat with RM
- 📱 Mobile app (React Native)

---

**Total Estimated Time**: 3-4 days for all UI components

**Priority**: Start with Phase 1 (scheduling) - highest business value
