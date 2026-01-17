// Example: Complete ChatInterface with Scheduling Integration
// Copy this example to integrate scheduling into your existing ChatInterface

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Message, ProjectInfo } from '@/types';
import { apiService } from '@/services/api';
import { ResponseCard } from './ResponseCard';
import { ProjectCard } from './ProjectCard';
import { Send, Calendar, Phone } from '@/components/icons';
import {
    ScheduleVisitModal,
    CallbackRequestButton,
} from '@/components/scheduling';

export function ChatInterfaceWithScheduling() {
    // Existing state
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // New state for scheduling
    const [showScheduleModal, setShowScheduleModal] = useState(false);
    const [selectedProjectForSchedule, setSelectedProjectForSchedule] = useState<ProjectInfo | null>(null);
    
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

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: `msg_${Date.now()}`,
            role: 'user',
            content: input.trim(),
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await apiService.sendQuery({
                query: input.trim(),
                user_id: userId,
            });

            const assistantMessage: Message = {
                id: `msg_${Date.now()}_bot`,
                role: 'assistant',
                content: response.answer,
                timestamp: new Date(),
                confidence: response.confidence,
                projects: response.projects,
                suggested_actions: response.suggested_actions,
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Error sending message:', error);
            const errorMessage: Message = {
                id: `msg_${Date.now()}_error`,
                role: 'assistant',
                content: 'Sorry, I encountered an error. Please try again.',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-screen bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
                <h1 className="text-xl font-semibold text-gray-900">
                    Real Estate Assistant
                </h1>
                <p className="text-sm text-gray-600">
                    Find your dream home in Bangalore
                </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${
                            message.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                    >
                        <div
                            className={`max-w-3xl rounded-lg px-4 py-3 ${
                                message.role === 'user'
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-white border border-gray-200'
                            }`}
                        >
                            {/* Message Content */}
                            <div className="prose prose-sm max-w-none">
                                {message.content}
                            </div>

                            {/* Projects */}
                            {message.projects && message.projects.length > 0 && (
                                <div className="mt-4 space-y-3">
                                    {message.projects.map((project, idx) => (
                                        <div
                                            key={idx}
                                            className="bg-gray-50 rounded-lg p-4 border border-gray-200"
                                        >
                                            <h3 className="font-semibold text-gray-900">
                                                {project.name}
                                            </h3>
                                            <p className="text-sm text-gray-600 mt-1">
                                                {project.location} • {project.developer}
                                            </p>
                                            {project.price_range && (
                                                <p className="text-sm font-medium text-gray-900 mt-2">
                                                    {typeof project.price_range === 'string'
                                                        ? project.price_range
                                                        : `₹${project.price_range.min_display} - ₹${project.price_range.max_display}`}
                                                </p>
                                            )}
                                        </div>
                                    ))}

                                    {/* 🆕 Schedule Visit Button */}
                                    <button
                                        onClick={() => {
                                            setSelectedProjectForSchedule(message.projects![0]);
                                            setShowScheduleModal(true);
                                        }}
                                        className="w-full mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 font-medium"
                                    >
                                        <Calendar className="w-4 h-4" />
                                        Schedule Site Visit
                                    </button>
                                </div>
                            )}

                            {/* Suggested Actions */}
                            {message.suggested_actions && message.suggested_actions.length > 0 && (
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {message.suggested_actions.map((action, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => setInput(action)}
                                            className="px-3 py-1 bg-white border border-gray-300 rounded-full text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                                        >
                                            {action}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {/* Loading */}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="bg-white border-t border-gray-200 px-4 py-4">
                <form onSubmit={handleSendMessage} className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask about properties..."
                        className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </form>
            </div>

            {/* 🆕 Floating Callback Button */}
            <CallbackRequestButton userId={userId} sessionId={sessionId} />

            {/* 🆕 Schedule Visit Modal */}
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
                            id: `msg_${Date.now()}_success`,
                            role: 'assistant',
                            content: `✅ Perfect! I've scheduled your site visit for ${selectedProjectForSchedule.name}. You'll receive a confirmation email and SMS shortly. Our Relationship Manager will contact you before the visit.`,
                            timestamp: new Date(),
                        };
                        setMessages(prev => [...prev, successMessage]);
                        
                        // Close modal
                        setShowScheduleModal(false);
                        setSelectedProjectForSchedule(null);
                    }}
                />
            )}
        </div>
    );
}
