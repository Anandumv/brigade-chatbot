'use client';

import React from 'react';
import { ProjectInfo } from '@/types';
import { Building2, MapPin, ChevronDown } from 'lucide-react';

interface ProjectSelectorProps {
    projects: ProjectInfo[];
    selectedProject: ProjectInfo | null;
    onSelectProject: (project: ProjectInfo | null) => void;
    disabled?: boolean;
}

export function ProjectSelector({
    projects,
    selectedProject,
    onSelectProject,
    disabled = false,
}: ProjectSelectorProps) {
    const [isOpen, setIsOpen] = React.useState(false);

    const handleSelect = (project: ProjectInfo | null) => {
        onSelectProject(project);
        setIsOpen(false);
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
                        : 'bg-white border-gray-300 text-gray-700 hover:border-brigade-gold hover:shadow-sm'
                    }
        `}
            >
                <Building2 className="w-4 h-4 text-brigade-gold" />
                <span className="text-sm font-medium">
                    {selectedProject ? selectedProject.name : 'All Projects'}
                </span>
                <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && !disabled && (
                <>
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute top-full left-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 z-20 animate-fade-in">
                        <div className="p-2">
                            {/* All Projects Option */}
                            <button
                                onClick={() => handleSelect(null)}
                                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors
                  ${selectedProject === null
                                        ? 'bg-brigade-gold/10 text-brigade-dark'
                                        : 'hover:bg-gray-50'
                                    }
                `}
                            >
                                <Building2 className="w-5 h-5 text-gray-400" />
                                <div>
                                    <p className="text-sm font-medium">All Projects</p>
                                    <p className="text-xs text-gray-500">Search across all properties</p>
                                </div>
                            </button>

                            <hr className="my-2 border-gray-100" />

                            {/* Individual Projects */}
                            {projects.map((project) => (
                                <button
                                    key={project.id}
                                    onClick={() => handleSelect(project)}
                                    className={`
                    w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors
                    ${selectedProject?.id === project.id
                                            ? 'bg-brigade-gold/10 text-brigade-dark'
                                            : 'hover:bg-gray-50'
                                        }
                  `}
                                >
                                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-brigade-gold/20 to-brigade-gold/5 flex items-center justify-center">
                                        <Building2 className="w-5 h-5 text-brigade-gold" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{project.name}</p>
                                        {project.location && (
                                            <p className="text-xs text-gray-500 flex items-center gap-1">
                                                <MapPin className="w-3 h-3" />
                                                {project.location}
                                            </p>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default ProjectSelector;
