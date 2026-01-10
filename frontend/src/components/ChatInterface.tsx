'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Message, ProjectInfo, PersonaInfo, ChatQueryResponse } from '@/types';
import { apiService } from '@/services/api';
import { ResponseCard } from './ResponseCard';
import { Send, Loader2, Sparkles, User, AlertCircle, Zap } from 'lucide-react';

interface ChatInterfaceProps {
    projects: ProjectInfo[];
    personas: PersonaInfo[];
}

export function ChatInterface({ projects, personas }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
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
                project_id: undefined,
                persona: undefined,
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

    return (
        <div className="flex flex-col h-full bg-white relative font-sans">
            {/* Minimal Header */}
            <div className="flex justify-center items-center py-4 bg-white/90 backdrop-blur-md sticky top-0 z-20 border-b border-gray-50">
                <div className="flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-gray-50/50 border border-gray-100">
                    <span className="text-sm font-semibold text-gray-700 tracking-wide">Pinclick Genie</span>
                    <div className="bg-gradient-to-tr from-rose-500 to-orange-500 p-1 rounded-full shadow-sm">
                        <Sparkles className="w-3 h-3 text-white fill-white" />
                    </div>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto w-full max-w-3xl mx-auto px-4 pb-36">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-8 animate-fade-in px-4">
                        <div className="relative group cursor-default">
                            <div className="absolute -inset-1 bg-gradient-to-r from-rose-400 to-orange-500 rounded-full blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
                            <div className="relative w-24 h-24 rounded-full bg-white flex items-center justify-center shadow-2xl ring-1 ring-gray-100">
                                <Sparkles className="w-10 h-10 text-rose-500 fill-rose-50" />
                            </div>
                        </div>
                        <div className="space-y-2 max-w-md">
                            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600">
                                How can I help you today?
                            </h1>
                            <p className="text-gray-400 text-sm">
                                Ask about project details, pricing, or amenities.
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-8 py-8">
                        {messages.map((message) => (
                            <div
                                key={message.id}
                                className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : ''} animate-slide-up group`}
                            >
                                {/* Bot Icon */}
                                {message.role === 'assistant' && (
                                    <div className="w-8 h-8 flex-shrink-0 rounded-full bg-gradient-to-br from-rose-100 to-orange-50 border border-rose-100 flex items-center justify-center shadow-sm mt-0.5">
                                        <Sparkles className="w-4 h-4 text-rose-600" />
                                    </div>
                                )}

                                <div
                                    className={`max-w-[80%] ${message.role === 'user'
                                        ? 'bg-gray-100 text-gray-900 rounded-[20px] rounded-tr-sm px-6 py-3.5 shadow-sm'
                                        : 'w-full'
                                        }`}
                                >
                                    {message.role === 'user' ? (
                                        <p className="text-[15px] leading-relaxed font-medium text-gray-800">{message.content}</p>
                                    ) : message.isLoading ? (
                                        <div className="flex items-center gap-3 text-gray-500 bg-gray-50/50 rounded-2xl px-4 py-3 w-fit">
                                            <Loader2 className="w-4 h-4 animate-spin text-rose-500" />
                                            <span className="text-sm font-medium">Genie is thinking...</span>
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

                                {/* User Icon */}
                                {message.role === 'user' && (
                                    <div className="w-8 h-8 flex-shrink-0 rounded-full bg-gray-200 border border-gray-300 flex items-center justify-center shadow-sm mt-0.5 overflow-hidden">
                                        <User className="w-5 h-5 text-gray-500" />
                                    </div>
                                )}
                            </div>
                        ))}
                        <div ref={messagesEndRef} />
                    </div>
                )}
            </div>

            {/* Floating Input Area */}
            <div className="fixed bottom-0 left-0 w-full bg-gradient-to-t from-white via-white/95 to-transparent pb-8 pt-12 px-4 z-10 pointer-events-none">
                <div className="max-w-3xl mx-auto pointer-events-auto">
                    {error && (
                        <div className="mb-3 mx-auto w-fit flex items-center gap-2 bg-red-50 text-red-600 px-4 py-2 rounded-full text-xs font-medium border border-red-100 animate-slide-up">
                            <AlertCircle className="w-3 h-3" />
                            {error}
                        </div>
                    )}

                    <div className="relative group transition-all duration-300 focus-within:-translate-y-1">
                        <div className="absolute -inset-0.5 bg-gradient-to-r from-rose-200 via-orange-200 to-rose-200 rounded-[2rem] opacity-40 group-focus-within:opacity-100 blur transition duration-500"></div>
                        <div className="relative shadow-xl shadow-gray-200/50 rounded-[1.8rem] bg-white border border-gray-100">
                            <form onSubmit={handleSubmit} className="relative flex items-end p-2 pl-6">
                                <textarea
                                    ref={inputRef}
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder="Message Pinclick Genie..."
                                    className="w-full resize-none bg-transparent border-0 focus:ring-0 text-gray-800 placeholder-gray-400 py-4 max-h-48 text-[15px]"
                                    rows={1}
                                    style={{ minHeight: '56px' }}
                                />
                                <button
                                    type="submit"
                                    disabled={!input.trim() || isLoading}
                                    className={`mb-1.5 mr-1.5 p-2.5 rounded-full transition-all duration-300 ${input.trim()
                                        ? 'bg-gradient-to-tr from-rose-600 to-orange-500 text-white shadow-lg hover:shadow-orange-200 scale-100'
                                        : 'bg-gray-100 text-gray-300 scale-90'
                                        }`}
                                >
                                    {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5 ml-0.5" />}
                                </button>
                            </form>
                        </div>
                    </div>
                    <p className="text-center text-[10px] text-gray-400 mt-3 font-medium tracking-wide">
                        Pinclick Genie can make mistakes. Consider checking important information.
                    </p>
                </div>
            </div>
        </div>
    );
}

export default ChatInterface;
