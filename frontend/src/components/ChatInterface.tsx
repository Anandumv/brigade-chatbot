'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Message, ProjectInfo, PersonaInfo, ChatQueryResponse } from '@/types';
import { apiService } from '@/services/api';
import { ResponseCard } from './ResponseCard';
import { ProjectSelector } from './ProjectSelector';
import { PersonaSelector } from './PersonaSelector';
import { Send, Loader2, Sparkles, MessageSquare, Bot } from 'lucide-react';

interface ChatInterfaceProps {
    projects: ProjectInfo[];
    personas: PersonaInfo[];
}

export function ChatInterface({ projects, personas }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [selectedProject, setSelectedProject] = useState<ProjectInfo | null>(null);
    const [selectedPersona, setSelectedPersona] = useState<PersonaInfo | null>(null);
    const [error, setError] = useState<string | null>(null);

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
            const response: ChatQueryResponse = await apiService.sendQuery({
                query: userMessage.content,
                project_id: selectedProject?.id,
                persona: selectedPersona?.id,
            });

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

    const suggestedQueries = [
        'What amenities does Brigade Citrine offer?',
        'Tell me about the unit configurations in Avalon',
        'Compare Brigade Citrine and Avalon',
        'What is the price range for 3BHK units?',
    ];

    return (
        <div className="flex flex-col h-full bg-gradient-to-b from-gray-50 to-white">
            {/* Header with Selectors */}
            <div className="flex-shrink-0 px-6 py-4 bg-white border-b border-gray-200 shadow-sm">
                <div className="flex items-center justify-between max-w-4xl mx-auto">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brigade-gold to-yellow-600 flex items-center justify-center shadow-lg">
                            <Sparkles className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="text-lg font-bold text-brigade-dark">Brigade Sales Assistant</h1>
                            <p className="text-xs text-gray-500">AI-powered property information</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <ProjectSelector
                            projects={projects}
                            selectedProject={selectedProject}
                            onSelectProject={setSelectedProject}
                            disabled={isLoading}
                        />
                        <PersonaSelector
                            personas={personas}
                            selectedPersona={selectedPersona}
                            onSelectPersona={setSelectedPersona}
                            disabled={isLoading}
                        />
                    </div>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-6 py-6">
                <div className="max-w-4xl mx-auto space-y-6">
                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center">
                            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brigade-gold/20 to-brigade-gold/5 flex items-center justify-center mb-6">
                                <Bot className="w-10 h-10 text-brigade-gold" />
                            </div>
                            <h2 className="text-2xl font-bold text-brigade-dark mb-2">
                                Welcome to Brigade Sales Assistant
                            </h2>
                            <p className="text-gray-500 mb-8 max-w-md">
                                Ask me anything about Brigade Citrine or Avalon properties.
                                I provide accurate, source-backed information.
                            </p>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
                                {suggestedQueries.map((query, index) => (
                                    <button
                                        key={index}
                                        onClick={() => setInput(query)}
                                        className="flex items-center gap-3 px-4 py-3 bg-white rounded-xl border border-gray-200 hover:border-brigade-gold hover:shadow-md transition-all text-left group"
                                    >
                                        <MessageSquare className="w-5 h-5 text-gray-400 group-hover:text-brigade-gold transition-colors" />
                                        <span className="text-sm text-gray-700">{query}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <>
                            {messages.map((message) => (
                                <div
                                    key={message.id}
                                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}
                                >
                                    <div
                                        className={`max-w-[85%] ${message.role === 'user'
                                                ? 'bg-gradient-to-r from-brigade-dark to-brigade-accent text-white rounded-2xl rounded-tr-md px-5 py-3'
                                                : 'w-full'
                                            }`}
                                    >
                                        {message.role === 'user' ? (
                                            <p className="text-sm">{message.content}</p>
                                        ) : message.isLoading ? (
                                            <div className="flex items-center gap-3 p-4">
                                                <Loader2 className="w-5 h-5 animate-spin text-brigade-gold" />
                                                <span className="text-gray-500">Analyzing your query...</span>
                                            </div>
                                        ) : (
                                            <ResponseCard
                                                content={message.content}
                                                confidence={message.confidence}
                                                sources={message.sources}
                                                isRefusal={message.isRefusal}
                                                refusalReason={message.refusalReason}
                                            />
                                        )}
                                    </div>
                                </div>
                            ))}
                            <div ref={messagesEndRef} />
                        </>
                    )}
                </div>
            </div>

            {/* Error Message */}
            {error && (
                <div className="px-6">
                    <div className="max-w-4xl mx-auto">
                        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                            {error}
                        </div>
                    </div>
                </div>
            )}

            {/* Input Area */}
            <div className="flex-shrink-0 px-6 py-4 bg-white border-t border-gray-200">
                <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
                    <div className="relative flex items-end gap-3">
                        <div className="flex-1 relative">
                            <textarea
                                ref={inputRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask about Brigade properties..."
                                disabled={isLoading}
                                rows={1}
                                className="w-full resize-none rounded-xl border border-gray-300 px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-brigade-gold focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400"
                                style={{ minHeight: '48px', maxHeight: '120px' }}
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={!input.trim() || isLoading}
                            className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-r from-brigade-gold to-yellow-600 text-white flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all"
                        >
                            {isLoading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <Send className="w-5 h-5" />
                            )}
                        </button>
                    </div>
                    <p className="text-xs text-gray-400 mt-2 text-center">
                        Responses are grounded in official Brigade documents only. No external information used.
                    </p>
                </form>
            </div>
        </div>
    );
}

export default ChatInterface;
