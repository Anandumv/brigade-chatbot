'use client';

import React from 'react';
import { PersonaInfo } from '@/types';
import { User, Home, TrendingUp, Heart, Users, ChevronDown } from '@/components/icons';

interface PersonaSelectorProps {
    personas: PersonaInfo[];
    selectedPersona: PersonaInfo | null;
    onSelectPersona: (persona: PersonaInfo | null) => void;
    disabled?: boolean;
}

const personaIcons: Record<string, React.ReactNode> = {
    first_time_buyer: <Home className="w-5 h-5" />,
    investor: <TrendingUp className="w-5 h-5" />,
    senior_citizen: <Heart className="w-5 h-5" />,
    family: <Users className="w-5 h-5" />,
};

const personaColors: Record<string, string> = {
    first_time_buyer: 'from-blue-500 to-blue-600',
    investor: 'from-green-500 to-green-600',
    senior_citizen: 'from-purple-500 to-purple-600',
    family: 'from-orange-500 to-orange-600',
};

export function PersonaSelector({
    personas,
    selectedPersona,
    onSelectPersona,
    disabled = false,
}: PersonaSelectorProps) {
    const [isOpen, setIsOpen] = React.useState(false);

    const handleSelect = (persona: PersonaInfo | null) => {
        onSelectPersona(persona);
        setIsOpen(false);
    };

    const getIcon = (personaId: string) => {
        return personaIcons[personaId] || <User className="w-5 h-5" />;
    };

    const getColorClass = (personaId: string) => {
        return personaColors[personaId] || 'from-gray-500 to-gray-600';
    };

    return (
        <div className="relative">
            <button
                onClick={() => !disabled && setIsOpen(!isOpen)}
                disabled={disabled}
                className={`
          flex items-center gap-2 px-4 py-2.5 rounded-lg border transition-all
          ${disabled
                        ? 'bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed'
                        : 'bg-white border-gray-300 text-gray-700 hover:border-primary-500 hover:shadow-sm'
                    }
        `}
            >
                <User className="w-4 h-4 text-primary-500" />
                <span className="text-sm font-medium">
                    {selectedPersona ? selectedPersona.name : 'General'}
                </span>
                <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && !disabled && (
                <>
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute top-full right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-20 animate-fade-in">
                        <div className="p-3">
                            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 px-2">
                                Buyer Persona
                            </p>

                            {/* General Option */}
                            <button
                                onClick={() => handleSelect(null)}
                                className={`
                  w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left transition-colors
                  ${selectedPersona === null
                                        ? 'bg-primary-50 border border-primary-200'
                                        : 'hover:bg-gray-50'
                                    }
                `}
                            >
                                <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center text-gray-500">
                                    <User className="w-5 h-5" />
                                </div>
                                <div className="flex-1">
                                    <p className="text-sm font-medium">General</p>
                                    <p className="text-xs text-gray-500">Standard responses without persona tailoring</p>
                                </div>
                            </button>

                            <hr className="my-3 border-gray-100" />

                            {/* Persona Options */}
                            <div className="space-y-2">
                                {personas.map((persona) => (
                                    <button
                                        key={persona.id}
                                        onClick={() => handleSelect(persona)}
                                        className={`
                      w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left transition-colors
                      ${selectedPersona?.id === persona.id
                                                ? 'bg-primary-50 border border-primary-200'
                                                : 'hover:bg-gray-50'
                                            }
                    `}
                                    >
                                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${getColorClass(persona.id)} flex items-center justify-center text-white`}>
                                            {getIcon(persona.id)}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium">{persona.name}</p>
                                            <p className="text-xs text-gray-500 truncate">{persona.description}</p>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default PersonaSelector;
