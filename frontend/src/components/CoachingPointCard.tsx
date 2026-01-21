import React from 'react';
import { MessageCircle, Lightbulb } from 'lucide-react';

interface CoachingPointCardProps {
    coaching_point: string;
}

export const CoachingPointCard: React.FC<CoachingPointCardProps> = ({ coaching_point }) => {
    if (!coaching_point) return null;

    return (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-l-4 border-blue-500 rounded-lg p-4 mt-3 shadow-sm">
            <div className="flex items-start gap-3">
                <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                        <Lightbulb className="w-4 h-4 text-white" />
                    </div>
                </div>
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <MessageCircle className="w-4 h-4 text-blue-600" />
                        <h4 className="text-sm font-semibold text-blue-900">
                            Sales Coaching
                        </h4>
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed">
                        {coaching_point}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default CoachingPointCard;
