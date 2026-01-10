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
        <div className="flex flex-col h-full bg-white font-sans text-gray-800">
            {/* Minimal Header */}
            <div className="flex-shrink-0 py-3 bg-white border-b border-gray-100 flex justify-center items-center z-10 sticky top-0">
                <span className="font-semibold text-gray-700 tracking-tight">Pinclick Genie</span>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto w-full max-w-3xl mx-auto px-4 pb-36">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-6 animate-fade-in px-4">
                        <div className="w-16 h-16 rounded-full bg-gray-50 flex items-center justify-center">
                            <Sparkles className="w-8 h-8 text-red-500" />
                        </div>
                        <h1 className="text-2xl font-semibold text-gray-800">
                            How can I help you today?
                        </h1>
                    </div>
                ) : (
                    <div className="space-y-6 py-6">
                        {messages.map((message) => (
                            <div
                                key={message.id}
                                className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : ''} group`}
                            >
                                {/* Bot Icon */}
                                {message.role === 'assistant' && (
                                    <div className="w-8 h-8 flex-shrink-0 rounded-full bg-green-100 flex items-center justify-center mt-0.5">
                                        <Sparkles className="w-4 h-4 text-green-600" />
                                    </div>
                                )}

                                <div
                                    className={`max-w-[85%] ${message.role === 'user'
                                        ? 'bg-gray-100 text-gray-900 rounded-3xl px-5 py-3'
                                        : 'w-full'
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
                                        <ResponseCard
                                            content={message.content}
                                            confidence={message.confidence}
                                            sources={message.sources}
                                            isRefusal={message.isRefusal}
                                            refusalReason={message.refusalReason}
                                        />
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

            {/* Input Area - Clean & Simple */}
            <div className="fixed bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent pb-6 pt-10 px-4 z-20">
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
                                placeholder="Message Pinclick Genie..."
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
                        Pinclick Genie can make mistakes. Check important info.
                    </p>
                </div>
            </div>
        </div>
    );
}

export default ChatInterface;
