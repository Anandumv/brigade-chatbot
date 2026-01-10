'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Message, ProjectInfo, PersonaInfo, ChatQueryResponse } from '@/types';
import { apiService } from '@/services/api';
import { ResponseCard } from './ResponseCard';
import { Send, Loader2, Sparkles, AlertCircle } from 'lucide-react';

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
        <div className="flex flex-col h-full bg-white relative">
            {/* Minimal Header */}
            <div className="flex justify-center items-center py-4 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
                <div className="flex items-center gap-2">
                    <span className="text-xl font-semibold text-gray-800 tracking-tight">Pinclick Genie</span>
                    <Sparkles className="w-5 h-5 text-pinclick-red" />
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto w-full max-w-3xl mx-auto px-4 pb-32">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-6 animate-fade-in">
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-red-500 to-pink-600 flex items-center justify-center shadow-xl shadow-red-200">
                            <Sparkles className="w-8 h-8 text-white" />
                        </div>
                        <h1 className="text-3xl font-bold text-gray-900">How can I help you today?</h1>
                    </div>
                ) : (
                    <div className="space-y-6 py-6">
                        {messages.map((message) => (
                            <div
                                key={message.id}
                                className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : ''} animate-slide-up`}
                            >
                                {/* Bot Icon */}
                                {message.role === 'assistant' && (
                                    <div className="w-8 h-8 flex-shrink-0 rounded-full bg-red-100 flex items-center justify-center mt-1">
                                        <Sparkles className="w-4 h-4 text-pinclick-red" />
                                    </div>
                                )}

                                <div
                                    className={`max-w-[85%] ${message.role === 'user'
                                        ? 'bg-gray-100 text-gray-900 rounded-2xl px-5 py-3'
                                        : 'w-full'
                                        }`}
                                >
                                    {message.role === 'user' ? (
                                        <p className="text-sm leading-relaxed">{message.content}</p>
                                    ) : message.isLoading ? (
                                        <div className="flex items-center gap-2 text-gray-400">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            <span className="text-sm">Thinking...</span>
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
                    </div>
                )}
            </div>

            {/* Floating Input Area */}
            <div className="fixed bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent pb-6 pt-10 px-4">
                <div className="max-w-3xl mx-auto relative shadow-2xl rounded-3xl bg-white border border-gray-100">
                    <form onSubmit={handleSubmit} className="relative flex items-end p-2">
                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Message Pinclick Genie..."
                            className="w-full resize-none bg-transparent border-0 focus:ring-0 text-gray-800 placeholder-gray-400 py-3 pl-4 pr-12 max-h-48"
                            rows={1}
                            style={{ minHeight: '52px' }}
                        />
                        <button
                            type="submit"
                            disabled={!input.trim() || isLoading}
                            className={`absolute right-3 bottom-3 p-2 rounded-xl transition-all ${input.trim()
                                ? 'bg-pinclick-red text-white hover:bg-red-600 shadow-md'
                                : 'bg-gray-100 text-gray-400'
                                }`}
                        >
                            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        </button>
                    </form>
                </div>
                {error && (
                    <div className="text-center mt-2 flex items-center justify-center gap-2 text-red-500 text-xs">
                        <AlertCircle className="w-3 h-3" />
                        {error}
                    </div>
                )}
                <p className="text-center text-[10px] text-gray-400 mt-2">
                    Pinclick Genie can make mistakes. Consider checking important information.
                </p>
            </div>
        </div>
    );
}

export default ChatInterface;
