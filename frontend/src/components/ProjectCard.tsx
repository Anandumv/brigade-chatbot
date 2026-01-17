import React, { useState } from 'react';
import { 
    MapPin, 
    IndianRupee, 
    Calendar, 
    ChevronDown, 
    ChevronUp,
    Phone,
    FileText,
    Building2,
    Info,
    Home,
    CheckCircle,
    Navigation,
    ExternalLink
} from 'lucide-react';
import { ProjectInfo } from '@/types';

interface ProjectCardProps {
    project: ProjectInfo;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    // Parse configuration string to extract unit details
    const parseConfiguration = (config: string | undefined): Array<{type: string, area: string, price: string}> => {
        if (!config) return [];
        
        try {
            // Format: "{2BHK, 1249 - 1310, 1.35 Cr* }, {3 BHK + 2 T, 1539 - 1590, 1.65 Cr* }"
            const units = config.match(/\{([^}]+)\}/g);
            if (!units) return [];
            
            return units.map(unit => {
                const parts = unit.replace(/[{}]/g, '').split(',').map(s => s.trim());
                return {
                    type: parts[0] || '',
                    area: parts[1] || '',
                    price: parts[2] || ''
                };
            });
        } catch (e) {
            return [];
        }
    };

    // Parse amenities string to array
    const parseAmenities = (amenities: string | undefined): string[] => {
        if (!amenities) return [];
        return amenities.split(',').map(a => a.trim()).filter(a => a.length > 0);
    };

    // Parse USP
    const getUSPArray = (usp: string | string[] | undefined): string[] => {
        if (!usp) return [];
        if (Array.isArray(usp)) return usp;
        if (typeof usp === 'string' && usp.trim().length > 0) {
            return usp.split(',').map(u => u.trim()).filter(u => u.length > 0);
        }
        return [];
    };

    // Parse registration process
    const parseRegistrationProcess = (process: string | undefined): string[] => {
        if (!process) return [];
        // Split by numbered steps like "1. ", "2. ", etc.
        const steps = process.split(/\d+\.\s+/).filter(s => s.trim().length > 0);
        return steps;
    };

    const configUnits = parseConfiguration(project.configuration || project.config_summary);
    const amenitiesList = parseAmenities(project.amenities);
    const uspList = getUSPArray(project.usp);
    const registrationSteps = parseRegistrationProcess(project.registration_process);

    // Get price range display
    const getPriceDisplay = () => {
        if (typeof project.price_range === 'string') {
            return project.price_range;
        }
        if (project.price_range) {
            return project.price_range.min_display || project.price_range.max_display || 'Price on Request';
        }
        return 'Price on Request';
    };

    // Get configuration display - clean format without JSON-like braces
    const getConfigDisplay = () => {
        const config = project.configuration || project.config_summary;
        if (!config) return '2, 3 BHK';
        
        // Check if config contains curly braces (JSON-like format)
        if (config.includes('{') && config.includes('}')) {
            // Parse and extract only unit types
            const units = config.match(/\{([^}]+)\}/g);
            if (units && units.length > 0) {
                const types = units.map(unit => {
                    const parts = unit.replace(/[{}]/g, '').split(',').map(s => s.trim());
                    return parts[0] || ''; // Just the type (2BHK, 3BHK, etc.)
                }).filter(t => t.length > 0);
                
                if (types.length > 0) {
                    return types.join(', ');
                }
            }
        }
        
        // Fallback to original if parsing fails or no braces found
        return config;
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-all duration-200 w-full mb-4">
            {project.image_url && (
                <div className="h-48 sm:h-40 w-full bg-gray-100 relative">
                    <img
                        src={project.image_url}
                        alt={project.project_name || project.name}
                        className="w-full h-full object-cover"
                    />
                    <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-1 rounded text-xs font-medium text-gray-700">
                        {project.status}
                    </div>
                </div>
            )}

            <div className="p-4 sm:p-5">
                {/* Header Section */}
                <div className="flex justify-between items-start mb-3 gap-3">
                    <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-lg sm:text-xl text-gray-900 leading-tight truncate">
                            {project.project_name || project.name}
                        </h3>
                        <p className="text-sm text-gray-500 mt-0.5">{project.developer_name || project.developer}</p>
                    </div>
                    <span className="bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap flex-shrink-0">
                        {getConfigDisplay()}
                    </span>
                </div>

                {/* Basic Info Section */}
                <div className="space-y-2.5 mt-4">
                    <div className="flex items-center justify-between text-sm text-gray-600">
                        <div className="flex items-center flex-1 min-w-0">
                            <MapPin className="w-4 h-4 mr-2 text-gray-400 flex-shrink-0" />
                            <span className="truncate">{project.location}</span>
                        </div>
                        {/* Distance badge if available */}
                        {(project as any)._distance && (
                            <span className="ml-2 text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full font-medium whitespace-nowrap flex-shrink-0">
                                {(project as any)._distance} km
                            </span>
                        )}
                    </div>

                    <div className="flex items-center text-sm text-gray-600">
                        <IndianRupee className="w-4 h-4 mr-2 text-gray-400 flex-shrink-0" />
                        <span className="font-medium">{getPriceDisplay()}</span>
                    </div>

                    {project.possession_year && (
                        <div className="flex items-center text-sm text-gray-600">
                            <Calendar className="w-4 h-4 mr-2 text-gray-400 flex-shrink-0" />
                            <span>Possession: {project.possession_year}{project.possession_quarter ? ` (${project.possession_quarter})` : ''}</span>
                        </div>
                    )}
                </div>

                {/* Quick info: RM contact, location link, brochure link */}
                {(project.rm_details?.name || project.rm_details?.contact || project.rm_contact || project.location_link || project.brochure_url || project.brochure_link) && (
                    <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap items-center gap-2">
                        {/* RM contact: Call + WhatsApp */}
                        {(project.rm_details?.contact || project.rm_contact) && (
                            <>
                                {project.rm_details?.name && (
                                    <span className="text-xs text-gray-500">RM: {project.rm_details.name}</span>
                                )}
                                <a
                                    href={`tel:${project.rm_details?.contact || project.rm_contact}`}
                                    className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline px-2 py-1 rounded bg-blue-50 hover:bg-blue-100 transition-colors"
                                >
                                    <Phone className="w-3 h-3" />
                                    Call
                                </a>
                                <a
                                    href={`https://wa.me/${(project.rm_details?.contact || project.rm_contact)?.replace(/[^0-9]/g, '')}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-xs text-green-600 hover:underline px-2 py-1 rounded bg-green-50 hover:bg-green-100 transition-colors"
                                >
                                    WhatsApp
                                </a>
                            </>
                        )}
                        {/* Location link */}
                        {project.location_link && (
                            <a
                                href={project.location_link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 transition-colors"
                            >
                                <ExternalLink className="w-3 h-3" />
                                View on map
                            </a>
                        )}
                        {/* Brochure link */}
                        {(project.brochure_url || project.brochure_link) && (
                            <a
                                href={project.brochure_url || project.brochure_link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 transition-colors"
                            >
                                <FileText className="w-3 h-3" />
                                Brochure
                            </a>
                        )}
                    </div>
                )}

                {/* USP Preview */}
                {uspList.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-gray-50">
                        <div className="flex flex-wrap gap-1.5">
                            {uspList.slice(0, 2).map((item, idx) => (
                                <span key={idx} className="text-xs bg-gray-50 text-gray-600 px-2.5 py-1.5 rounded">
                                    {item}
                                </span>
                            ))}
                            {uspList.length > 2 && !isExpanded && (
                                <span className="text-xs text-gray-400 py-1.5">+{uspList.length - 2} more</span>
                            )}
                        </div>
                    </div>
                )}

                {/* Expand/Collapse Button */}
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors duration-200 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    aria-expanded={isExpanded}
                >
                    {isExpanded ? (
                        <>
                            <ChevronUp className="w-4 h-4" />
                            Hide Details
                        </>
                    ) : (
                        <>
                            <ChevronDown className="w-4 h-4" />
                            View Full Details
                        </>
                    )}
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                    <div className="mt-4 space-y-4 border-t pt-4 animate-fadeIn">
                        
                        {/* Description */}
                        {project.description && (
                            <div>
                                <div className="flex items-center gap-2 mb-2">
                                    <Info className="w-4 h-4 text-blue-600 flex-shrink-0" />
                                    <h4 className="font-semibold text-sm text-gray-900">Overview</h4>
                                </div>
                                <p className="text-sm text-gray-600 leading-relaxed">{project.description}</p>
                            </div>
                        )}

                        {/* Configuration Details */}
                        {configUnits.length > 0 && (
                            <div>
                                <div className="flex items-center gap-2 mb-2">
                                    <Home className="w-4 h-4 text-blue-600 flex-shrink-0" />
                                    <h4 className="font-semibold text-sm text-gray-900">Unit Configuration</h4>
                                </div>
                                <div className="space-y-2">
                                    {configUnits.map((unit, idx) => (
                                        <div key={idx} className="bg-gray-50 rounded-lg p-3 text-sm">
                                            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1">
                                                <span className="font-medium text-gray-900">{unit.type}</span>
                                                <span className="text-blue-600 font-semibold">{unit.price}</span>
                                            </div>
                                            {unit.area && (
                                                <div className="text-gray-600 text-xs mt-1">
                                                    Area: {unit.area} sq.ft
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Amenities */}
                        {amenitiesList.length > 0 && (
                            <div>
                                <div className="flex items-center gap-2 mb-2">
                                    <Building2 className="w-4 h-4 text-blue-600 flex-shrink-0" />
                                    <h4 className="font-semibold text-sm text-gray-900">Amenities</h4>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {amenitiesList.map((amenity, idx) => (
                                        <span key={idx} className="inline-flex items-center gap-1 text-xs bg-green-50 text-green-700 px-2.5 py-1.5 rounded">
                                            <CheckCircle className="w-3 h-3 flex-shrink-0" />
                                            <span className="break-words">{amenity}</span>
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* All USPs in expanded view */}
                        {uspList.length > 2 && (
                            <div>
                                <h4 className="font-semibold text-sm text-gray-900 mb-2">Highlights</h4>
                                <div className="flex flex-wrap gap-2">
                                    {uspList.map((item, idx) => (
                                        <span key={idx} className="text-xs bg-amber-50 text-amber-700 px-2.5 py-1.5 rounded break-words">
                                            {item}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Legal & Project Details */}
                        {(project.rera_number || project.total_land_area || project.towers || project.floors) && (
                            <div>
                                <h4 className="font-semibold text-sm text-gray-900 mb-2">Project Details</h4>
                                <div className="bg-gray-50 rounded-lg p-3 space-y-2 text-sm">
                                    {project.rera_number && (
                                        <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                                            <span className="text-gray-600">RERA:</span>
                                            <span className="text-gray-900 font-medium break-words">{project.rera_number}</span>
                                        </div>
                                    )}
                                    {project.total_land_area && (
                                        <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                                            <span className="text-gray-600">Total Area:</span>
                                            <span className="text-gray-900">{project.total_land_area}</span>
                                        </div>
                                    )}
                                    {project.towers && (
                                        <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                                            <span className="text-gray-600">Towers:</span>
                                            <span className="text-gray-900">{project.towers}</span>
                                        </div>
                                    )}
                                    {project.floors && (
                                        <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                                            <span className="text-gray-600">Floors:</span>
                                            <span className="text-gray-900">{project.floors}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* RM Contact */}
                        {(project.rm_details?.name || project.rm_details?.contact || project.rm_contact) && (
                            <div>
                                <div className="flex items-center gap-2 mb-2">
                                    <Phone className="w-4 h-4 text-blue-600 flex-shrink-0" />
                                    <h4 className="font-semibold text-sm text-gray-900">Contact Information</h4>
                                </div>
                                <div className="bg-blue-50 rounded-lg p-3">
                                    {project.rm_details?.name && (
                                        <div className="text-sm font-medium text-gray-900 mb-2">
                                            {project.rm_details.name}
                                        </div>
                                    )}
                                    {(project.rm_details?.contact || project.rm_contact) && (
                                        <div className="flex flex-wrap gap-2">
                                            <a
                                                href={`tel:${project.rm_details?.contact || project.rm_contact}`}
                                                className="inline-flex items-center gap-1.5 text-sm bg-white text-blue-600 px-3 py-2 rounded hover:bg-blue-100 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            >
                                                <Phone className="w-3.5 h-3.5" />
                                                Call Now
                                            </a>
                                            <a
                                                href={`https://wa.me/${(project.rm_details?.contact || project.rm_contact)?.replace(/[^0-9]/g, '')}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1.5 text-sm bg-white text-green-600 px-3 py-2 rounded hover:bg-green-100 transition-colors focus:outline-none focus:ring-2 focus:ring-green-500"
                                            >
                                                WhatsApp
                                            </a>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Brochure Download */}
                        {(project.brochure_url || project.brochure_link) && (
                            <div>
                                <a
                                    href={project.brochure_url || project.brochure_link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
                                >
                                    <FileText className="w-4 h-4" />
                                    Download Brochure
                                </a>
                            </div>
                        )}

                        {/* Registration Process */}
                        {registrationSteps.length > 0 && (
                            <div>
                                <h4 className="font-semibold text-sm text-gray-900 mb-3">Registration Process</h4>
                                <div className="space-y-3">
                                    {registrationSteps.map((step, idx) => (
                                        <div key={idx} className="flex gap-3">
                                            <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">
                                                {idx + 1}
                                            </div>
                                            <p className="text-sm text-gray-600 leading-relaxed flex-1 pt-0.5">
                                                {step.replace(/\*\*/g, '')}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
