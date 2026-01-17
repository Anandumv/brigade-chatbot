'use client';

import React, { useState } from 'react';
import { ProjectInfo } from '@/types';
import { schedulingApi } from '@/services/scheduling-api';
import { ScheduleVisitRequest } from '@/types/scheduling';
import { X, Calendar, Clock, User, Phone, Mail, MessageSquare, CheckCircle, AlertCircle } from '@/components/icons';

interface ScheduleVisitModalProps {
    project: ProjectInfo;
    userId: string;
    sessionId?: string;
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: (visitId: string) => void;
}

export function ScheduleVisitModal({
    project,
    userId,
    sessionId,
    isOpen,
    onClose,
    onSuccess,
}: ScheduleVisitModalProps) {
    const [formData, setFormData] = useState({
        contactName: '',
        contactPhone: '',
        contactEmail: '',
        requestedDate: '',
        requestedTimeSlot: 'morning' as 'morning' | 'afternoon' | 'evening',
        userNotes: '',
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [visitDetails, setVisitDetails] = useState<any>(null);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsSubmitting(true);

        try {
            const request: ScheduleVisitRequest = {
                user_id: userId,
                session_id: sessionId,
                project_id: project.id || project.project_id || '',
                project_name: project.name || project.project_name || '',
                contact_name: formData.contactName,
                contact_phone: formData.contactPhone,
                contact_email: formData.contactEmail || undefined,
                requested_date: formData.requestedDate || undefined,
                requested_time_slot: formData.requestedTimeSlot,
                user_notes: formData.userNotes || undefined,
            };

            const response = await schedulingApi.scheduleVisit(request);

            if (response.success) {
                setSuccess(true);
                setVisitDetails(response.details);
                if (onSuccess && response.visit_id) {
                    onSuccess(response.visit_id);
                }
            } else {
                setError(response.message || 'Failed to schedule visit');
            }
        } catch (err: any) {
            setError(err.message || 'An error occurred while scheduling the visit');
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
                requestedDate: '',
                requestedTimeSlot: 'morning',
                userNotes: '',
            });
            setError(null);
            setSuccess(false);
            setVisitDetails(null);
            onClose();
        }
    };

    // Get minimum date (tomorrow)
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const minDate = tomorrow.toISOString().split('T')[0];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="relative w-full max-w-lg mx-4 bg-white rounded-lg shadow-xl max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                        <Calendar className="w-5 h-5 text-blue-600" />
                        Schedule Site Visit
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
                                    <h3 className="font-semibold">Visit Scheduled Successfully!</h3>
                                    <p className="text-sm text-green-700 mt-1">
                                        We've sent a confirmation to your email/phone.
                                    </p>
                                </div>
                            </div>

                            {visitDetails && (
                                <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                                    <div className="flex items-start gap-3">
                                        <Calendar className="w-5 h-5 text-gray-600 mt-0.5" />
                                        <div>
                                            <p className="text-sm text-gray-600">Date & Time</p>
                                            <p className="font-medium text-gray-900">
                                                {visitDetails.date} <br />
                                                {visitDetails.time_slot}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-start gap-3">
                                        <User className="w-5 h-5 text-gray-600 mt-0.5" />
                                        <div>
                                            <p className="text-sm text-gray-600">Relationship Manager</p>
                                            <p className="font-medium text-gray-900">{visitDetails.rm_name}</p>
                                            <p className="text-sm text-gray-600">{visitDetails.rm_phone}</p>
                                        </div>
                                    </div>

                                    {visitDetails.reminders_scheduled > 0 && (
                                        <div className="flex items-center gap-2 text-sm text-blue-600 bg-blue-50 p-2 rounded">
                                            <CheckCircle className="w-4 h-4" />
                                            <span>
                                                {visitDetails.reminders_scheduled} reminder(s) scheduled
                                            </span>
                                        </div>
                                    )}
                                </div>
                            )}

                            <button
                                onClick={handleClose}
                                className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                            >
                                Done
                            </button>
                        </div>
                    ) : (
                        /* Form */
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Project Info */}
                            <div className="bg-blue-50 rounded-lg p-4">
                                <h3 className="font-semibold text-gray-900">{project.name}</h3>
                                <p className="text-sm text-gray-600 mt-1">
                                    {project.location} • {project.developer}
                                </p>
                            </div>

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
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    placeholder="your.email@example.com"
                                />
                            </div>

                            {/* Preferred Date */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <Calendar className="w-4 h-4 inline mr-1" />
                                    Preferred Date (Optional)
                                </label>
                                <input
                                    type="date"
                                    min={minDate}
                                    value={formData.requestedDate}
                                    onChange={(e) => setFormData({ ...formData, requestedDate: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Leave blank to schedule tomorrow
                                </p>
                            </div>

                            {/* Time Slot */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <Clock className="w-4 h-4 inline mr-1" />
                                    Preferred Time Slot
                                </label>
                                <div className="grid grid-cols-3 gap-2">
                                    {[
                                        { value: 'morning', label: 'Morning', time: '9 AM - 12 PM' },
                                        { value: 'afternoon', label: 'Afternoon', time: '12 PM - 3 PM' },
                                        { value: 'evening', label: 'Evening', time: '3 PM - 6 PM' },
                                    ].map((slot) => (
                                        <button
                                            key={slot.value}
                                            type="button"
                                            onClick={() =>
                                                setFormData({
                                                    ...formData,
                                                    requestedTimeSlot: slot.value as any,
                                                })
                                            }
                                            className={`p-3 rounded-lg border-2 transition-all ${
                                                formData.requestedTimeSlot === slot.value
                                                    ? 'border-blue-600 bg-blue-50 text-blue-900'
                                                    : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                        >
                                            <div className="text-sm font-medium">{slot.label}</div>
                                            <div className="text-xs text-gray-600 mt-1">{slot.time}</div>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Additional Notes */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    <MessageSquare className="w-4 h-4 inline mr-1" />
                                    Any Specific Requirements? (Optional)
                                </label>
                                <textarea
                                    value={formData.userNotes}
                                    onChange={(e) => setFormData({ ...formData, userNotes: e.target.value })}
                                    rows={3}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                                    placeholder="e.g., interested in specific unit, have questions about amenities..."
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
                                    className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                                >
                                    {isSubmitting ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                            Scheduling...
                                        </>
                                    ) : (
                                        <>
                                            <Calendar className="w-4 h-4" />
                                            Schedule Visit
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
