'use client';

import React, { useState } from 'react';
import { schedulingApi } from '@/services/scheduling-api';
import { CallbackRequest } from '@/types/scheduling';
import { X, Phone, User, Mail, MessageSquare, CheckCircle, AlertCircle, Clock } from '@/components/icons';

interface CallbackRequestModalProps {
    userId: string;
    sessionId?: string;
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: (callbackId: string) => void;
}

export function CallbackRequestModal({
    userId,
    sessionId,
    isOpen,
    onClose,
    onSuccess,
}: CallbackRequestModalProps) {
    const [formData, setFormData] = useState({
        contactName: '',
        contactPhone: '',
        contactEmail: '',
        callbackReason: 'general_inquiry',
        urgencyLevel: 'medium' as 'low' | 'medium' | 'high' | 'urgent',
        userNotes: '',
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [callbackDetails, setCallbackDetails] = useState<any>(null);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsSubmitting(true);

        try {
            const request: CallbackRequest = {
                user_id: userId,
                session_id: sessionId,
                contact_name: formData.contactName,
                contact_phone: formData.contactPhone,
                contact_email: formData.contactEmail || undefined,
                callback_reason: formData.callbackReason,
                user_notes: formData.userNotes || undefined,
                urgency_level: formData.urgencyLevel,
            };

            const response = await schedulingApi.requestCallback(request);

            if (response.success) {
                setSuccess(true);
                setCallbackDetails(response.details);
                if (onSuccess && response.callback_id) {
                    onSuccess(response.callback_id);
                }
            } else {
                setError(response.message || 'Failed to request callback');
            }
        } catch (err: any) {
            setError(err.message || 'An error occurred while requesting callback');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        if (!isSubmitting) {
            setFormData({
                contactName: '',
                contactPhone: '',
                contactEmail: '',
                callbackReason: 'general_inquiry',
                urgencyLevel: 'medium',
                userNotes: '',
            });
            setError(null);
            setSuccess(false);
            setCallbackDetails(null);
            onClose();
        }
    };

    const reasons = [
        { value: 'general_inquiry', label: 'General Inquiry' },
        { value: 'pricing', label: 'Pricing Details' },
        { value: 'site_visit', label: 'Schedule Site Visit' },
        { value: 'documentation', label: 'Documentation & Legal' },
        { value: 'financing', label: 'Financing Options' },
        { value: 'other', label: 'Other' },
    ];

    const urgencyLevels = [
        { value: 'low', label: 'Low', desc: 'Within 24 hours', color: 'blue' },
        { value: 'medium', label: 'Medium', desc: 'Within 4 hours', color: 'yellow' },
        { value: 'high', label: 'High', desc: 'Within 1-2 hours', color: 'orange' },
        { value: 'urgent', label: 'Urgent', desc: 'Within 30 minutes', color: 'red' },
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="relative w-full max-w-lg mx-4 bg-white rounded-lg shadow-xl max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                        <Phone className="w-5 h-5 text-green-600" />
                        Request a Callback
                    </h2>
                    <button
                        onClick={handleClose}
                        disabled={isSubmitting}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="px-6 py-4">
                    {success ? (
                        /* Success Message */
                        <div className="space-y-4">
                            <div className="flex items-center gap-3 text-green-600 bg-green-50 p-4 rounded-lg">
                                <CheckCircle className="w-6 h-6 flex-shrink-0" />
                                <div>
                                    <h3 className="font-semibold">Callback Requested Successfully!</h3>
                                    <p className="text-sm text-green-700 mt-1">
                                        Our team will contact you soon.
                                    </p>
                                </div>
                            </div>

                            {callbackDetails && (
                                <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                                    <div className="flex items-start gap-3">
                                        <User className="w-5 h-5 text-gray-600 mt-0.5" />
                                        <div>
                                            <p className="text-sm text-gray-600">Assigned Agent</p>
                                            <p className="font-medium text-gray-900">{callbackDetails.agent_name}</p>
                                        </div>
                                    </div>

                                    <div className="flex items-start gap-3">
                                        <Clock className="w-5 h-5 text-gray-600 mt-0.5" />
                                        <div>
                                            <p className="text-sm text-gray-600">Expected Callback</p>
                                            <p className="font-medium text-gray-900">
                                                {callbackDetails.expected_callback}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-start gap-3">
                                        <Phone className="w-5 h-5 text-gray-600 mt-0.5" />
                                        <div>
                                            <p className="text-sm text-gray-600">We'll call you at</p>
                                            <p className="font-medium text-gray-900">{formData.contactPhone}</p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2 text-sm text-blue-600 bg-blue-50 p-2 rounded">
                                        <CheckCircle className="w-4 h-4" />
                                        <span>
                                            Confirmation sent to {formData.contactEmail || 'your phone'}
                                        </span>
                                    </div>
                                </div>
                            )}

                            <button
                                onClick={handleClose}
                                className="w-full py-2 px-4 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
                            >
                                Done
                            </button>
                        </div>
                    ) : (
                        /* Form */
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Error Message */}
                            {error && (
                                <div className="flex items-start gap-3 text-red-600 bg-red-50 p-3 rounded-lg text-sm">
                                    <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                                    <p>{error}</p>
                                </div>
                            )}

                            {/* Contact Name */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <User className="w-4 h-4 inline mr-1" />
                                    Your Name *
                                </label>
                                <input
                                    type="text"
                                    required
                                    value={formData.contactName}
                                    onChange={(e) => setFormData({ ...formData, contactName: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                                    placeholder="Enter your name"
                                />
                            </div>

                            {/* Contact Phone */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <Phone className="w-4 h-4 inline mr-1" />
                                    Phone Number *
                                </label>
                                <input
                                    type="tel"
                                    required
                                    value={formData.contactPhone}
                                    onChange={(e) => setFormData({ ...formData, contactPhone: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                                    placeholder="+91 98765 43210"
                                />
                            </div>

                            {/* Contact Email */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <Mail className="w-4 h-4 inline mr-1" />
                                    Email (Optional)
                                </label>
                                <input
                                    type="email"
                                    value={formData.contactEmail}
                                    onChange={(e) => setFormData({ ...formData, contactEmail: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                                    placeholder="your.email@example.com"
                                />
                            </div>

                            {/* Callback Reason */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    What would you like to discuss? *
                                </label>
                                <select
                                    value={formData.callbackReason}
                                    onChange={(e) => setFormData({ ...formData, callbackReason: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                                >
                                    {reasons.map((reason) => (
                                        <option key={reason.value} value={reason.value}>
                                            {reason.label}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Urgency Level */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <Clock className="w-4 h-4 inline mr-1" />
                                    When do you need a callback?
                                </label>
                                <div className="grid grid-cols-2 gap-2">
                                    {urgencyLevels.map((level) => (
                                        <button
                                            key={level.value}
                                            type="button"
                                            onClick={() =>
                                                setFormData({
                                                    ...formData,
                                                    urgencyLevel: level.value as any,
                                                })
                                            }
                                            className={`p-3 rounded-lg border-2 transition-all text-left ${
                                                formData.urgencyLevel === level.value
                                                    ? `border-${level.color}-600 bg-${level.color}-50`
                                                    : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                        >
                                            <div className="text-sm font-medium">{level.label}</div>
                                            <div className="text-xs text-gray-600 mt-1">{level.desc}</div>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Additional Notes */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <MessageSquare className="w-4 h-4 inline mr-1" />
                                    Additional Details (Optional)
                                </label>
                                <textarea
                                    value={formData.userNotes}
                                    onChange={(e) => setFormData({ ...formData, userNotes: e.target.value })}
                                    rows={3}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
                                    placeholder="Any specific questions or details you'd like to discuss..."
                                />
                            </div>

                            {/* Submit Buttons */}
                            <div className="flex gap-3 pt-2">
                                <button
                                    type="button"
                                    onClick={handleClose}
                                    disabled={isSubmitting}
                                    className="flex-1 py-2 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors font-medium disabled:opacity-50"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isSubmitting}
                                    className="flex-1 py-2 px-4 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                                >
                                    {isSubmitting ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                            Requesting...
                                        </>
                                    ) : (
                                        <>
                                            <Phone className="w-4 h-4" />
                                            Request Callback
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
}
