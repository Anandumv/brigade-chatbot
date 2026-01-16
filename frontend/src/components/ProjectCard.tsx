import React from 'react';
import { MapPin, Home, IndianRupee, Calendar } from 'lucide-react';

interface ProjectCardProps {
    project: {
        project_name: string;
        developer_name: string;
        location: string;
        price_range: string;
        configuration: string;
        status: string;
        possession_year?: string;
        rera_number?: string;
        image_url?: string;
        usp?: string[];
    };
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project }) => {
    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow duration-200 w-full max-w-sm mb-4">
            {project.image_url && (
                <div className="h-40 w-full bg-gray-100 relative">
                    <img
                        src={project.image_url}
                        alt={project.project_name}
                        className="w-full h-full object-cover"
                    />
                    <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-1 rounded text-xs font-medium text-gray-700">
                        {project.status}
                    </div>
                </div>
            )}

            <div className="p-4">
                <div className="flex justify-between items-start mb-2">
                    <div>
                        <h3 className="font-semibold text-lg text-gray-900 leading-tight">
                            {project.project_name}
                        </h3>
                        <p className="text-sm text-gray-500">{project.developer_name}</p>
                    </div>
                    <span className="bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap">
                        {project.configuration}
                    </span>
                </div>

                <div className="space-y-2 mt-4">
                    <div className="flex items-center text-sm text-gray-600">
                        <MapPin className="w-4 h-4 mr-2 text-gray-400" />
                        <span className="truncate">{project.location}</span>
                    </div>

                    <div className="flex items-center text-sm text-gray-600">
                        <IndianRupee className="w-4 h-4 mr-2 text-gray-400" />
                        <span>{project.price_range}</span>
                    </div>

                    {project.possession_year && (
                        <div className="flex items-center text-sm text-gray-600">
                            <Calendar className="w-4 h-4 mr-2 text-gray-400" />
                            <span>Possession: {project.possession_year}</span>
                        </div>
                    )}
                </div>

                {project.usp && project.usp.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-gray-50">
                        <div className="flex flex-wrap gap-1">
                            {project.usp.slice(0, 2).map((item, idx) => (
                                <span key={idx} className="text-xs bg-gray-50 text-gray-600 px-2 py-1 rounded">
                                    {item}
                                </span>
                            ))}
                            {project.usp.length > 2 && (
                                <span className="text-xs text-gray-400 py-1">+{project.usp.length - 2} more</span>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
