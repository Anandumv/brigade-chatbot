import React from 'react';
import { CheckCircle2, Home, IndianRupee } from 'lucide-react';
import { MatchingUnit } from '@/types';

interface MatchingUnitsCardProps {
    matching_units: MatchingUnit[];
    projectName: string;
}

export const MatchingUnitsCard: React.FC<MatchingUnitsCardProps> = ({
    matching_units,
    projectName
}) => {
    if (!matching_units || matching_units.length === 0) return null;

    const formatPrice = (priceCr: number): string => {
        if (priceCr >= 1) {
            return `₹${priceCr.toFixed(2)} Cr`;
        } else {
            const lakhs = priceCr * 100;
            return `₹${lakhs.toFixed(0)} L`;
        }
    };

    return (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mt-3">
            <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                <h4 className="text-sm font-semibold text-green-900">
                    Units Matching Your Search
                </h4>
            </div>

            <div className="space-y-2">
                {matching_units.map((unit, index) => (
                    <div
                        key={index}
                        className="bg-white rounded-md p-3 border border-green-100 hover:border-green-300 transition-colors"
                    >
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="flex items-center gap-1">
                                    <Home className="w-4 h-4 text-green-600" />
                                    <span className="font-semibold text-gray-900">
                                        {unit.bhk} BHK
                                    </span>
                                </div>
                                {unit.sqft_range && (
                                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                                        {unit.sqft_range} sq.ft
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-1 text-green-700 font-semibold">
                                <IndianRupee className="w-4 h-4" />
                                <span>{formatPrice(unit.price_cr)}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <p className="text-xs text-gray-600 mt-3">
                <CheckCircle2 className="w-3 h-3 inline mr-1" />
                {matching_units.length} unit configuration{matching_units.length > 1 ? 's' : ''} in {projectName} match{matching_units.length === 1 ? 'es' : ''} your budget and BHK requirements
            </p>
        </div>
    );
};

export default MatchingUnitsCard;
