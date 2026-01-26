'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Message, ProjectInfo, PersonaInfo, ChatQueryResponse } from '@/types';
import { SelectedFilters } from '@/types/filters';
import { UserProfileData, ProactiveNudge, UrgencySignal, SentimentData } from '@/types/enhanced-ux';
import { apiService } from '@/services/api';
import { ResponseCard } from './ResponseCard';
import { ProjectCard } from './ProjectCard';
import { FilterPanel } from './FilterPanel';
import { QuickReplies, getQuickRepliesForIntent } from './QuickReplies';
import { Send, Loader2, User, AlertCircle, Zap } from '@/components/icons';
import { PinClickLogo, PinClickLogoIcon } from './PinClickLogo';
// Phase 1: Scheduling components
import { ScheduleVisitModal } from './scheduling';
// Phase 2: Enhanced UX components
import { WelcomeBackBanner, ProactiveNudgeCard, UrgencySignals, SentimentIndicator } from './enhanced-ux';
// Phase 3: Sales Coaching components
import { CoachingPanel } from './CoachingPanel';
// Phase 2/3: Response Enhancement components
import { CoachingPointCard } from './CoachingPointCard';
import { MatchingUnitsCard } from './MatchingUnitsCard';

interface ChatInterfaceProps {
    projects: ProjectInfo[];
    personas: PersonaInfo[];
}

export function ChatInterface({ projects, personas }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>({});
    const [isFilterCollapsed, setIsFilterCollapsed] = useState(true);

    // Phase 1: Scheduling state
    const [showScheduleModal, setShowScheduleModal] = useState(false);
    const [selectedProjectForSchedule, setSelectedProjectForSchedule] = useState<ProjectInfo | null>(null);

    // Phase 2: Enhanced UX state
    const [userProfile, setUserProfile] = useState<UserProfileData | undefined>();
    const [showWelcomeBanner, setShowWelcomeBanner] = useState(true);

    // User identification (persist across sessions)
    const [userId] = useState(() => {
        if (typeof window !== 'undefined') {
            let id = localStorage.getItem('chatbot_user_id');
            if (!id) {
                id = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                localStorage.setItem('chatbot_user_id', id);
            }
            return id;
        }
        return `user_${Date.now()}`;
    });

    // Session ID (new for each page load)
    const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const generateId = () => Math.random().toString(36).substring(2, 15);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: generateId(),
            role: 'user',
            content: input.trim(),
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);
        setError(null);

        // Add loading message
        const loadingMessage: Message = {
            id: generateId(),
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            isLoading: true,
        };
        setMessages((prev) => [...prev, loadingMessage]);

        try {
            // Use filter-aware query if filters are selected
            const hasFilters = Object.keys(selectedFilters).some(
                (key) => !key.includes('Min') && !key.includes('Max') && selectedFilters[key as keyof SelectedFilters]
            );

            let response: ChatQueryResponse;
            if (hasFilters) {
                response = await apiService.sendQueryWithFilters(
                    userMessage.content,
                    selectedFilters,
                    userId
                );
            } else {
                response = await apiService.sendQuery({
                    query: userMessage.content,
                    user_id: userId,
                    project_id: undefined,
                    persona: undefined,
                });
            }

            // Extract enhanced UX data from response
            let nudge: ProactiveNudge | undefined = response.nudge;
            let urgencySignals: UrgencySignal[] | undefined = response.urgency_signals;
            let sentiment: SentimentData | undefined = response.sentiment;
            let userProfileData: UserProfileData | undefined = response.user_profile;

            if (userProfileData) {
                setUserProfile(userProfileData);
            }

            // Parse nudge from response text if not in structured data
            // Backend currently adds nudges to response text with 🎯 prefix
            if (!nudge && response.answer.includes('🎯')) {
                const nudgeMatch = response.answer.match(/🎯\s*(.+?)(?:\n\n|$)/);
                if (nudgeMatch) {
                    const nudgeText = nudgeMatch[1];
                    // Infer nudge type from message
                    let nudgeType: ProactiveNudge['type'] = 'decision_ready';
                    if (nudgeText.toLowerCase().includes('viewed') && nudgeText.toLowerCase().includes('times')) {
                        nudgeType = 'repeat_views';
                    } else if (nudgeText.toLowerCase().includes('location')) {
                        nudgeType = 'location_focus';
                    } else if (nudgeText.toLowerCase().includes('budget')) {
                        nudgeType = 'budget_concern';
                    } else if (nudgeText.toLowerCase().includes('ready') || nudgeText.toLowerCase().includes('decide')) {
                        nudgeType = 'decision_ready';
                    }

                    nudge = {
                        type: nudgeType,
                        message: nudgeText,
                        action: nudgeText.toLowerCase().includes('schedule') ? 'schedule_visit' : undefined,
                        priority: nudgeText.toLowerCase().includes('ready') ? 'high' : 'medium',
                    };
                }
            }

            const assistantMessage: Message = {
                id: generateId(),
                role: 'assistant',
                content: typeof response.answer === 'string' ? response.answer : response.answer?.join('\n') || '',
                timestamp: new Date(),
                confidence: response.confidence,
                sources: response.sources,
                intent: response.intent,
                isRefusal: response.is_refusal,
                refusalReason: response.refusal_reason,
                suggested_actions: response.suggested_actions,
                projects: response.projects,
                // NEW: Handle answer as array (CopilotResponse format)
                answer_bullets: Array.isArray(response.answer) ? response.answer : undefined,
                // Phase 2: Enhanced UX data
                nudge: nudge || response.nudge,
                urgency_signals: urgencySignals || response.urgency_signals,
                sentiment: sentiment || response.sentiment,
                user_profile: userProfileData || response.user_profile,
                // Phase 3: Sales Coaching
                coaching_prompt: response.coaching_prompt,
                coaching_point: (response as any).coaching_point, // CopilotResponse format
                // NEW: Live call structure
                live_call_structure: (response as any).live_call_structure, // CopilotResponse format
            };

            setMessages((prev) =>
                prev.filter((m) => !m.isLoading).concat(assistantMessage)
            );
        } catch (err) {
            console.error('Chat error:', err);
            setError('Failed to get response. Please try again.');
            setMessages((prev) => prev.filter((m) => !m.isLoading));
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    // Build a natural language query from filters and trigger search
    const handleApplyFilters = async () => {
        if (isLoading) return;

        const parts: string[] = [];

        if (selectedFilters.configuration) {
            // Ensure configuration includes 'BHK' for proper query parsing
            const config = selectedFilters.configuration;
            const configDisplay = config.toLowerCase().includes('bhk') ? config : `${config} BHK`;
            parts.push(configDisplay);
        }
        if (selectedFilters.location) {
            parts.push(`in ${selectedFilters.location}`);
        }
        if (selectedFilters.budgetMax) {
            parts.push(`under ${selectedFilters.budgetMax / 100} Cr`);
        }
        if (selectedFilters.possessionYear === 'ready') {
            parts.push('ready to move');
        } else if (selectedFilters.possessionYear) {
            parts.push(`by ${selectedFilters.possessionYear}`);
        }

        if (parts.length === 0) return;

        const generatedQuery = `Show me ${parts.join(' ')}`;

        // Create user message
        const userMessage: Message = {
            id: generateId(),
            role: 'user',
            content: generatedQuery,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setIsLoading(true);
        setError(null);

        // Add loading message
        const loadingMessage: Message = {
            id: generateId(),
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            isLoading: true,
        };
        setMessages((prev) => [...prev, loadingMessage]);

        try {
            const response = await apiService.sendQueryWithFilters(
                generatedQuery,
                selectedFilters,
                userId
            );

            // Extract enhanced UX data (same as above)
            let nudge: ProactiveNudge | undefined = response.nudge;
            let urgencySignals: UrgencySignal[] | undefined = response.urgency_signals;
            let sentiment: SentimentData | undefined = response.sentiment;

            const assistantMessage: Message = {
                id: generateId(),
                role: 'assistant',
                content: response.answer,
                timestamp: new Date(),
                confidence: response.confidence,
                sources: response.sources,
                intent: response.intent,
                isRefusal: response.is_refusal,
                refusalReason: response.refusal_reason,
                suggested_actions: response.suggested_actions,
                projects: response.projects,
                // Phase 2: Enhanced UX data
                nudge: nudge || response.nudge,
                urgency_signals: urgencySignals || response.urgency_signals,
                sentiment: sentiment || response.sentiment,
                // Phase 3: Sales Coaching
                coaching_prompt: response.coaching_prompt,
            };

            setMessages((prev) =>
                prev.filter((m) => !m.isLoading).concat(assistantMessage)
            );
        } catch (err) {
            console.error('Filter search error:', err);
            setError('Failed to search with filters. Please try again.');
            setMessages((prev) => prev.filter((m) => !m.isLoading));
        } finally {
            setIsLoading(false);
        }
    };

    // Handle nudge actions
    const handleNudgeAction = (action: string) => {
        if (action === 'schedule_visit') {
            // Find the most recent project from messages
            const lastMessage = messages[messages.length - 1];
            if (lastMessage?.projects && lastMessage.projects.length > 0) {
                setSelectedProjectForSchedule(lastMessage.projects[0] as ProjectInfo);
                setShowScheduleModal(true);
            }
        } else if (action === 'contact_rm') {
            // Could open callback modal or show contact info
            // For now, just show a message
            setInput('I would like to speak with a relationship manager');
        }
    };

    return (
        <div className="flex flex-col h-full bg-gray-50 font-sans text-gray-800">
            {/* Minimal Header */}
            <div className="flex-shrink-0 py-4 bg-white/80 backdrop-blur-md border-b border-gray-200 flex justify-center items-center z-10 sticky top-0">
                <a href="/" className="font-semibold text-gray-800 tracking-tight flex items-center gap-2 hover:opacity-80 transition-opacity cursor-pointer">
                    <PinClickLogo size={24} showText={true} />
                </a>
            </div>

            {/* Chat Area - Mobile optimized with safe areas, full width for project cards */}
            <div className="flex-1 overflow-y-auto w-full max-w-4xl mx-auto px-4 sm:px-6 pb-32 sm:pb-36">
                {/* Phase 2: Welcome Back Banner */}
                {showWelcomeBanner && userProfile && userProfile.is_returning_user && (
                    <div className="pt-4">
                        <WelcomeBackBanner
                            userProfile={userProfile}
                            onDismiss={() => setShowWelcomeBanner(false)}
                        />
                    </div>
                )}
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center min-h-[50vh] sm:min-h-[60vh] text-center space-y-6 sm:space-y-8 animate-fade-in px-2 sm:px-4 pt-8">
                        <div className="space-y-3 sm:space-y-4">
                            <div className="flex flex-col items-center justify-center">
                                <PinClickLogo size={80} showText={true} className="mb-2" />
                            </div>
                            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 tracking-tight">
                                Pin Click Sales Assist
                            </h1>
                            <p className="text-gray-500 max-w-sm sm:max-w-md text-sm sm:text-base px-4 leading-relaxed">
                                Your AI Sales Copilot. Ask about projects, prices, or anything related to your client requirement
                            </p>
                        </div>

                        {/* Filter Panel - Collapsible */}
                        <div className="w-full max-w-2xl px-2">
                            <FilterPanel
                                selectedFilters={selectedFilters}
                                onFiltersChange={setSelectedFilters}
                                isCollapsed={isFilterCollapsed}
                                onToggleCollapse={() => setIsFilterCollapsed(!isFilterCollapsed)}
                                onApplyFilters={handleApplyFilters}
                            />
                        </div>

                        {/* Quick Suggestions - Mobile optimized */}
                        <div className="w-full max-w-2xl px-2">
                            <p className="text-[10px] text-gray-400 mb-3 uppercase tracking-widest font-semibold ml-1">Suggested Queries</p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                {[
                                    { icon: '🏠', text: '3BHK in Whitefield under 1.5 Cr' },
                                    { icon: '💰', text: 'How to stretch my budget?' },
                                    { icon: '🏗️', text: 'Why buy Under Construction?' },
                                ].map((suggestion, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => {
                                            setInput(suggestion.text);
                                            inputRef.current?.focus();
                                        }}
                                        className="flex items-center gap-3 p-4 bg-white border border-gray-100/50 hover:border-gray-200 hover:shadow-md active:scale-[0.98] rounded-2xl text-left transition-all group duration-200"
                                    >
                                        <span className="text-xl group-hover:scale-110 transition-transform duration-200">{suggestion.icon}</span>
                                        <span className="text-gray-600 group-hover:text-gray-900 text-sm font-medium">{suggestion.text}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-8 py-8">
                        {messages.map((message) => (
                            <div
                                key={message.id}
                                className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : ''} group`}
                            >
                                {/* Bot Icon */}
                                {message.role === 'assistant' && (
                                    <div className="w-8 h-8 flex-shrink-0 rounded-full bg-white flex items-center justify-center mt-1 shadow-sm ring-2 ring-gray-100">
                                        <PinClickLogoIcon size={20} />
                                    </div>
                                )}

                                <div
                                    className={`relative ${message.role === 'user'
                                        ? 'bg-gray-900 text-white rounded-2xl rounded-tr-sm px-6 py-4 shadow-sm max-w-[85%]'
                                        : 'w-full max-w-[90%]'
                                        }`}
                                >
                                    {message.role === 'user' ? (
                                        <p className="text-[15px] leading-relaxed">{message.content}</p>
                                    ) : message.isLoading ? (
                                        <div className="flex items-center gap-2 text-gray-500">
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                        </div>
                                    ) : (
                                        <>
                                            {/* 1. Show Answer Bullets FIRST (if available) */}
                                            {message.answer_bullets && message.answer_bullets.length > 0 && (
                                                <div className="answer-section mb-4">
                                                    <div className="answer-bullets space-y-2">
                                                        {message.answer_bullets.map((bullet, idx) => (
                                                            <div key={idx} className="flex items-start gap-2">
                                                                <span className="text-blue-500 mt-1 flex-shrink-0">•</span>
                                                                <span 
                                                                    className="flex-1 text-gray-700 leading-relaxed prose prose-sm max-w-none"
                                                                    dangerouslySetInnerHTML={{ 
                                                                        __html: bullet
                                                                            .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-900 bg-yellow-50 px-1 rounded">$1</strong>')
                                                                            .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
                                                                    }}
                                                                />
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Fallback to ResponseCard if no answer_bullets */}
                                            {!message.answer_bullets && (
                                                <ResponseCard
                                                    content={message.content}
                                                    confidence={message.confidence}
                                                    sources={message.sources}
                                                    isRefusal={message.isRefusal}
                                                    refusalReason={message.refusalReason}
                                                />
                                            )}

                                            {/* Phase 2: Proactive Nudge Card */}
                                            {message.nudge && (
                                                <div className="mt-4">
                                                    <ProactiveNudgeCard
                                                        nudge={message.nudge}
                                                        onAction={handleNudgeAction}
                                                        onDismiss={() => {
                                                            // Remove nudge from message
                                                            setMessages(prev => prev.map(m =>
                                                                m.id === message.id ? { ...m, nudge: undefined } : m
                                                            ));
                                                        }}
                                                    />
                                                </div>
                                            )}

                                            {/* Phase 2: Urgency Signals */}
                                            {message.urgency_signals && message.urgency_signals.length > 0 && (
                                                <div className="mt-4">
                                                    <UrgencySignals
                                                        signals={message.urgency_signals}
                                                        projectName={message.projects?.[0]?.name || message.projects?.[0]?.project_name}
                                                    />
                                                </div>
                                            )}

                                            {/* Phase 2: Sentiment Indicator */}
                                            {message.sentiment && (
                                                <div className="mt-4">
                                                    <SentimentIndicator
                                                        sentiment={message.sentiment}
                                                        onEscalate={() => {
                                                            // Open callback modal with high urgency
                                                            setInput('I need to speak with a human agent immediately');
                                                            inputRef.current?.focus();
                                                        }}
                                                    />
                                                </div>
                                            )}

                                            {/* Phase 3: Sales Coaching Prompt */}
                                            {message.coaching_prompt && (
                                                <div className="mt-4">
                                                    <CoachingPanel coaching_prompt={message.coaching_prompt} />
                                                </div>
                                            )}

                                            {/* Phase 2/3: Coaching Point Card (from copilot response) */}
                                            {message.coaching_point && (
                                                <div className="mt-4">
                                                    <CoachingPointCard coaching_point={message.coaching_point} />
                                                </div>
                                            )}

                                            {/* Live Call Structure (if available) */}
                                            {(message as any).live_call_structure && (
                                                <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                                                    <h4 className="font-semibold text-sm text-blue-900 mb-3">Live Call Guide</h4>
                                                    <div className="space-y-3 text-sm">
                                                        <div>
                                                            <p className="font-medium text-gray-700 mb-1">Situation Reframe:</p>
                                                            <p className="text-gray-600">{(message as any).live_call_structure.situation_reframe}</p>
                                                        </div>
                                                        <div>
                                                            <p className="font-medium text-gray-700 mb-1">Questions to Ask:</p>
                                                            <ul className="list-disc list-inside space-y-1 text-gray-600">
                                                                {(message as any).live_call_structure.consultant_questions.map((q: string, idx: number) => (
                                                                    <li key={idx}>{q}</li>
                                                                ))}
                                                            </ul>
                                                        </div>
                                                        {(message as any).live_call_structure.recommended_next_step && (
                                                            <div>
                                                                <p className="font-medium text-gray-700 mb-1">Recommended Next Step:</p>
                                                                <p className="text-gray-600">{(message as any).live_call_structure.recommended_next_step}</p>
                                                            </div>
                                                        )}
                                                        {(message as any).live_call_structure.pushback_handling && Object.keys((message as any).live_call_structure.pushback_handling).length > 0 && (
                                                            <div>
                                                                <p className="font-medium text-gray-700 mb-1">Pushback Handling:</p>
                                                                <div className="space-y-2">
                                                                    {Object.entries((message as any).live_call_structure.pushback_handling).map(([objection, response]: [string, string], idx: number) => (
                                                                        <div key={idx} className="bg-white p-2 rounded">
                                                                            <p className="font-medium text-gray-800 text-xs">"{objection}"</p>
                                                                            <p className="text-gray-600 text-xs mt-1">{response}</p>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                        <div>
                                                            <p className="font-medium text-gray-700 mb-1">Closing Summary:</p>
                                                            <p className="text-gray-600">{(message as any).live_call_structure.closing_summary}</p>
                                                        </div>
                                                        <div className="pt-2 border-t border-blue-200">
                                                            <p className="font-medium text-gray-700 mb-1">Post-Call Message:</p>
                                                            <p className="text-gray-600 whitespace-pre-wrap text-xs">{(message as any).live_call_structure.post_call_message}</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}

                                            {/* 2. THEN Show Projects (after answer) */}
                                            {message.projects && message.projects.length > 0 && (
                                                /* Carousel Container with negative margin on mobile to go edge-to-edge */
                                                <div className="mt-4 w-[calc(100%+32px)] -mx-4 px-4 sm:w-full sm:mx-0 sm:px-0">
                                                    <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory hide-scrollbar">
                                                        {message.projects.map((project, idx) => {
                                                            // Adapter to map backend fields to frontend ProjectCard props
                                                            const adaptProjectData = (apiProject: any) => {
                                                                // Handle price range - can be object or need to calculate
                                                                let priceInfo: any = apiProject.price_range;

                                                                if (!priceInfo || typeof priceInfo === 'string') {
                                                                    const minCr = (apiProject.budget_min || 0) / 100;
                                                                    const maxCr = (apiProject.budget_max || 0) / 100;

                                                                    let priceDisplay = 'Price on Request';
                                                                    if (minCr > 0) {
                                                                        if (maxCr > minCr) {
                                                                            priceDisplay = `₹${minCr.toFixed(2)} Cr - ₹${maxCr.toFixed(2)} Cr`;
                                                                        } else {
                                                                            priceDisplay = `Starting ₹${minCr.toFixed(2)} Cr`;
                                                                        }
                                                                    }
                                                                    priceInfo = priceDisplay;
                                                                }

                                                                return {
                                                                    id: apiProject.id || apiProject.project_id || '',
                                                                    name: apiProject.name || 'Unknown Project',
                                                                    project_id: apiProject.project_id || apiProject.id,
                                                                    project_name: apiProject.name || apiProject.project_name || 'Unknown Project',
                                                                    developer: apiProject.developer || apiProject.builder || 'Brigade Group',
                                                                    developer_name: apiProject.developer_name || apiProject.developer || apiProject.builder || 'Brigade Group',
                                                                    location: apiProject.location || 'Bangalore',
                                                                    zone: apiProject.zone,
                                                                    city: apiProject.city || apiProject.zone,
                                                                    locality: apiProject.locality || apiProject.location,
                                                                    price_range: priceInfo,
                                                                    configuration: apiProject.configuration || apiProject.config_summary || '2, 3 BHK',
                                                                    config_summary: apiProject.config_summary || apiProject.configuration,
                                                                    status: apiProject.status || 'Active',
                                                                    possession_year: apiProject.possession_year?.toString(),
                                                                    possession_quarter: apiProject.possession_quarter,
                                                                    rera_number: apiProject.rera_number,
                                                                    image_url: apiProject.image_url,
                                                                    usp: apiProject.usp || [],
                                                                    description: apiProject.description || apiProject.highlights,
                                                                    amenities: apiProject.amenities,
                                                                    highlights: apiProject.highlights,
                                                                    brochure_url: apiProject.brochure_url || apiProject.brochure_link,
                                                                    brochure_link: apiProject.brochure_link || apiProject.brochure_url,
                                                                    rm_details: apiProject.rm_details,
                                                                    rm_contact: apiProject.rm_contact,
                                                                    registration_process: apiProject.registration_process,
                                                                    total_land_area: apiProject.total_land_area,
                                                                    towers: apiProject.towers,
                                                                    floors: apiProject.floors,
                                                                    location_link: apiProject.location_link,
                                                                    can_expand: apiProject.can_expand
                                                                };
                                                            };

                                                            const adaptedProject = adaptProjectData(project);

                                                            return (
                                                                <div key={idx} className="relative min-w-[85%] sm:min-w-[320px] max-w-[85%] sm:max-w-[320px] snap-center space-y-3">
                                                                    <ProjectCard
                                                                        project={adaptedProject}
                                                                    />

                                                                    {/* Phase 2/3: Matching Units Card */}
                                                                    {project.matching_units && project.matching_units.length > 0 && (
                                                                        <MatchingUnitsCard
                                                                            matching_units={project.matching_units}
                                                                            projectName={project.name || project.project_name || 'this project'}
                                                                        />
                                                                    )}
                                                                </div>
                                                            );
                                                        })}

                                                        {/* Spacer for last item padding */}
                                                        <div className="w-2 flex-shrink-0" />
                                                    </div>
                                                </div>
                                                
                                                {/* Action Buttons After Projects */}
                                                {message.projects && message.projects.length > 0 && (
                                                    <div className="mt-4 flex flex-wrap gap-2 justify-center sm:justify-start">
                                                        <button
                                                            onClick={() => {
                                                                if (message.projects && message.projects.length > 0) {
                                                                    setSelectedProjectForSchedule(message.projects[0] as ProjectInfo);
                                                                    setShowScheduleModal(true);
                                                                }
                                                            }}
                                                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                        >
                                                            Schedule Site Visit
                                                        </button>
                                                        <button
                                                            onClick={() => {
                                                                // Download all brochures
                                                                message.projects?.forEach((proj: any) => {
                                                                    const brochureUrl = proj.brochure_url || proj.brochure_link;
                                                                    if (brochureUrl) {
                                                                        window.open(brochureUrl, '_blank');
                                                                    }
                                                                });
                                                            }}
                                                            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-gray-500"
                                                        >
                                                            Download All Brochures
                                                        </button>
                                                        {message.projects && message.projects.length > 1 && (
                                                            <button
                                                                onClick={() => {
                                                                    setInput(`Compare ${message.projects?.map((p: any) => p.name || p.project_name).join(' and ')}`);
                                                                    inputRef.current?.focus();
                                                                }}
                                                                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-gray-500"
                                                            >
                                                                Compare Projects
                                                            </button>
                                                        )}
                                                        {message.projects && message.projects.length > 0 && (
                                                            <button
                                                                onClick={() => {
                                                                    const firstProject = message.projects?.[0] as any;
                                                                    const rmContact = firstProject?.rm_details?.contact || firstProject?.rm_contact;
                                                                    if (rmContact) {
                                                                        window.open(`tel:${rmContact}`, '_self');
                                                                    }
                                                                }}
                                                                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-gray-500"
                                                            >
                                                                Contact RM
                                                            </button>
                                                        )}
                                                    </div>
                                                )}
                                            )}

                                            {messages.indexOf(message) === messages.length - 1 && (
                                                <QuickReplies
                                                    replies={
                                                        message.suggested_actions
                                                            ? message.suggested_actions.map(action => ({
                                                                label: action,
                                                                value: action,
                                                                variant: 'primary'
                                                            }))
                                                            : (message.intent ? getQuickRepliesForIntent(message.intent as string) : [])
                                                    }
                                                    onSelect={(value) => {
                                                        setInput(value);
                                                        inputRef.current?.focus();
                                                    }}
                                                    disabled={isLoading}
                                                />
                                            )}
                                        </>
                                    )}
                                </div>

                                {/* User Icon - Optional, ChatGPT often omits it, but user asked for icons */}
                                {/* {message.role === 'user' && (
                                    <div className="w-8 h-8 flex-shrink-0 rounded-full bg-gray-200 flex items-center justify-center mt-0.5">
                                        <User className="w-5 h-5 text-gray-500" />
                                    </div>
                                )} */}
                            </div>
                        ))}
                        <div ref={messagesEndRef} />
                    </div>
                )}
            </div>

            {/* Input Area - Mobile optimized with safe areas */}
            <div className="fixed bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent pb-4 sm:pb-6 pt-8 sm:pt-10 px-3 sm:px-4 z-20 safe-area-bottom">
                <div className="max-w-3xl mx-auto">
                    {error && (
                        <div className="mb-2 mx-auto w-fit flex items-center gap-2 text-red-600 text-xs font-medium">
                            <AlertCircle className="w-3 h-3" />
                            {error}
                        </div>
                    )}

                    <div className="relative shadow-lg ring-1 ring-gray-200 rounded-3xl bg-white overflow-hidden">
                        <form onSubmit={handleSubmit} className="relative flex items-end p-2 pl-4">
                            <textarea
                                ref={inputRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Message Pin Click Sales Assist..."
                                className="w-full resize-none bg-transparent border-0 focus:ring-0 text-gray-800 placeholder-gray-400 py-3 max-h-48 text-[15px]"
                                rows={1}
                                style={{ minHeight: '52px' }}
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || isLoading}
                                className={`mb-2 mr-2 p-2 rounded-full transition-colors ${input.trim()
                                    ? 'bg-black text-white hover:bg-gray-800'
                                    : 'bg-gray-100 text-gray-400'
                                    }`}
                            >
                                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            </button>
                        </form>
                    </div>
                    <p className="text-center text-[10px] text-gray-400 mt-2">
                        Pin Click Sales Assist can make mistakes. Check important info.
                    </p>
                </div>
            </div>

            {/* Phase 1: Schedule Visit Modal */}
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
                        // Add success message to chat
                        const successMessage: Message = {
                            id: generateId(),
                            role: 'assistant',
                            content: `✅ Perfect! I've scheduled your site visit for ${selectedProjectForSchedule.name || selectedProjectForSchedule.project_name}. You'll receive a confirmation email and SMS shortly. Our Relationship Manager will contact you before the visit.`,
                            timestamp: new Date(),
                        };
                        setMessages(prev => [...prev, successMessage]);
                        setShowScheduleModal(false);
                        setSelectedProjectForSchedule(null);
                    }}
                />
            )}
        </div>
    );
}

export default ChatInterface;
