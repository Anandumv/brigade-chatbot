'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { ConfidenceLevel, SourceInfo } from '@/types';
import { CheckCircle, AlertCircle, XCircle, FileText, ExternalLink, ChevronDown, ChevronUp } from '@/components/icons';

// Lazy load ReactMarkdown for better initial bundle size
const ReactMarkdown = dynamic(() => import('react-markdown'), {
    loading: () => <div className="animate-pulse bg-gray-100 h-20 rounded" />,
    ssr: true, // Keep SSR for markdown content
});

interface ResponseCardProps {
    content: string;
    confidence?: ConfidenceLevel;
    sources?: SourceInfo[];
    isRefusal?: boolean;
    refusalReason?: string;
}

export function ResponseCard({
    content,
    confidence,
    sources = [],
    isRefusal = false,
    refusalReason,
}: ResponseCardProps) {
    const [sourcesExpanded, setSourcesExpanded] = React.useState(false);

    const getConfidenceIcon = () => {
        switch (confidence) {
            case 'High':
                return <CheckCircle className="w-4 h-4 text-green-500" />;
            case 'Medium':
                return <AlertCircle className="w-4 h-4 text-yellow-500" />;
            case 'Not Available':
                return <XCircle className="w-4 h-4 text-red-500" />;
            default:
                return null;
        }
    };

    const getConfidenceColor = () => {
        switch (confidence) {
            case 'High':
                return 'bg-green-50 border-green-200 text-green-700';
            case 'Medium':
                return 'bg-yellow-50 border-yellow-200 text-yellow-700';
            case 'Not Available':
                return 'bg-red-50 border-red-200 text-red-700';
            default:
                return 'bg-gray-50 border-gray-200 text-gray-700';
        }
    };

    return (
        <div className="w-full">
            {/* Main Content */}
            <div className={`rounded-2xl rounded-tl-sm p-5 shadow-sm ${isRefusal ? 'bg-amber-50 border border-amber-200' : 'bg-white border border-gray-200'}`}>
                {isRefusal && refusalReason && (
                    <div className="flex items-center gap-2 mb-3 text-amber-700 text-sm font-medium">
                        <AlertCircle className="w-4 h-4" />
                        <span>Information Not Available</span>
                    </div>
                )}

                <div className="prose prose-sm sm:prose-base max-w-none text-gray-700 prose-p:leading-relaxed prose-headings:text-gray-900 prose-strong:text-gray-900 prose-strong:font-semibold">
                    <ReactMarkdown>{content}</ReactMarkdown>
                </div>

                {/* Confidence Badge - simplified */}
                {confidence && !isRefusal && (
                    <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-3">
                        <div className="flex items-center gap-2">
                            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wider font-semibold ${getConfidenceColor()}`}>
                                {getConfidenceIcon()}
                                {confidence}
                            </span>
                        </div>
                    </div>
                )}
            </div>

            {/* Sources Section */}
            {sources.length > 0 && (
                <div className="mt-3">
                    <button
                        onClick={() => setSourcesExpanded(!sourcesExpanded)}
                        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                    >
                        <FileText className="w-4 h-4" />
                        <span>{sources.length} source{sources.length > 1 ? 's' : ''}</span>
                        {sourcesExpanded ? (
                            <ChevronUp className="w-4 h-4" />
                        ) : (
                            <ChevronDown className="w-4 h-4" />
                        )}
                    </button>

                    {sourcesExpanded && (
                        <div className="mt-2 space-y-2 animate-fade-in">
                            {sources.map((source, index) => (
                                <div
                                    key={index}
                                    className="bg-gray-50 rounded-lg p-3 border border-gray-100"
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-center gap-2">
                                            <FileText className="w-4 h-4 text-red-500" />
                                            <span className="font-medium text-sm text-gray-800">
                                                {source.document_name}
                                            </span>
                                        </div>
                                        <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
                                            {(source.similarity_score * 100).toFixed(0)}% match
                                        </span>
                                    </div>

                                    {source.page_number && (
                                        <p className="text-xs text-gray-500 mt-1">
                                            Page {source.page_number}
                                        </p>
                                    )}

                                    <p className="text-xs text-gray-600 mt-2 italic line-clamp-2">
                                        &ldquo;{source.content_preview}&rdquo;
                                    </p>

                                    <div className="mt-2">
                                        <span className="inline-flex items-center gap-1 text-xs text-gray-500 capitalize">
                                            <ExternalLink className="w-3 h-3" />
                                            {source.source_type.replace('_', ' ')}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default ResponseCard;
