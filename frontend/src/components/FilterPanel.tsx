'use client';

import React, { useState, useEffect } from 'react';
import { FilterOptions, SelectedFilters, BudgetRange } from '@/types/filters';
import { apiService } from '@/services/api';
import { ChevronDown, X, SlidersHorizontal } from './icons';

interface FilterPanelProps {
    onFiltersChange: (filters: SelectedFilters) => void;
    selectedFilters: SelectedFilters;
    isCollapsed?: boolean;
    onToggleCollapse?: () => void;
}

export function FilterPanel({
    onFiltersChange,
    selectedFilters,
    isCollapsed = true,
    onToggleCollapse,
}: FilterPanelProps) {
    const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        loadFilterOptions();
    }, []);

    const loadFilterOptions = async () => {
        try {
            setIsLoading(true);
            const options = await apiService.getFilterOptions();
            setFilterOptions(options);
        } catch (error) {
            console.error('Failed to load filter options:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleFilterChange = (
        key: keyof SelectedFilters,
        value: string | number | null
    ) => {
        const newFilters = { ...selectedFilters };

        if (value === '' || value === null) {
            delete newFilters[key];
        } else {
            (newFilters as any)[key] = value;
        }

        // Handle budget range special case
        if (key === 'budgetRange' && filterOptions) {
            const budgetRange = filterOptions.budget_ranges.find(
                (b) => b.value === value
            );
            if (budgetRange) {
                newFilters.budgetMin = budgetRange.min;
                newFilters.budgetMax = budgetRange.max;
            } else {
                delete newFilters.budgetMin;
                delete newFilters.budgetMax;
            }
        }

        onFiltersChange(newFilters);
    };

    const clearAllFilters = () => {
        onFiltersChange({});
    };

    const getActiveFilterCount = () => {
        return Object.keys(selectedFilters).filter(
            (key) => !key.includes('Min') && !key.includes('Max') && selectedFilters[key as keyof SelectedFilters]
        ).length;
    };

    const getActiveFilterLabels = (): string[] => {
        const labels: string[] = [];

        if (selectedFilters.configuration && filterOptions) {
            const config = filterOptions.configurations.find(
                (c) => c.value === selectedFilters.configuration
            );
            if (config) labels.push(config.label);
        }

        if (selectedFilters.location) {
            labels.push(selectedFilters.location);
        }

        if (selectedFilters.budgetRange && filterOptions) {
            const budget = filterOptions.budget_ranges.find(
                (b) => b.value === selectedFilters.budgetRange
            );
            if (budget) labels.push(budget.label);
        }

        if (selectedFilters.possessionYear && filterOptions) {
            const possession = filterOptions.possession_years.find(
                (p) => p.value === selectedFilters.possessionYear
            );
            if (possession) labels.push(possession.label);
        }

        return labels;
    };

    if (isLoading) {
        return (
            <div className="bg-gray-50 rounded-xl p-3 mb-4">
                <div className="flex items-center justify-center gap-2 text-gray-400">
                    <div className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
                    <span className="text-sm">Loading filters...</span>
                </div>
            </div>
        );
    }

    if (!filterOptions) {
        return null;
    }

    const activeCount = getActiveFilterCount();

    return (
        <div className="mb-4">
            {/* Collapsed View - Filter Tags */}
            <div
                className={`bg-gray-50 rounded-xl transition-all duration-200 ${isCollapsed ? 'p-3' : 'p-4'
                    }`}
            >
                {/* Header */}
                <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={onToggleCollapse}
                >
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal className="w-4 h-4 text-gray-500" />
                        <span className="text-sm font-medium text-gray-700">Filters</span>
                        {activeCount > 0 && (
                            <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                                {activeCount}
                            </span>
                        )}
                    </div>
                    <ChevronDown
                        className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${!isCollapsed ? 'rotate-180' : ''
                            }`}
                    />
                </div>

                {/* Active Filter Tags */}
                {isCollapsed && activeCount > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                        {getActiveFilterLabels().map((label, idx) => (
                            <span
                                key={idx}
                                className="inline-flex items-center gap-1 bg-white border border-gray-200 text-gray-700 text-xs px-2 py-1 rounded-full"
                            >
                                {label}
                            </span>
                        ))}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                clearAllFilters();
                            }}
                            className="text-xs text-red-500 hover:text-red-600 px-2"
                        >
                            Clear all
                        </button>
                    </div>
                )}

                {/* Expanded Filter Dropdowns */}
                {!isCollapsed && (
                    <div className="mt-4 space-y-4">
                        {/* Configuration */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1.5">
                                Configuration
                            </label>
                            <select
                                value={selectedFilters.configuration || ''}
                                onChange={(e) =>
                                    handleFilterChange('configuration', e.target.value)
                                }
                                className="w-full p-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            >
                                <option value="">All Configurations</option>
                                {filterOptions.configurations.map((config) => (
                                    <option key={config.value} value={config.value}>
                                        {config.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Location */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1.5">
                                Location
                            </label>
                            <select
                                value={selectedFilters.location || ''}
                                onChange={(e) =>
                                    handleFilterChange('location', e.target.value)
                                }
                                className="w-full p-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            >
                                <option value="">All Locations</option>
                                <optgroup label={filterOptions.locations.north_bangalore.label}>
                                    {filterOptions.locations.north_bangalore.areas.map((area) => (
                                        <option key={area.value} value={area.label}>
                                            {area.label}
                                        </option>
                                    ))}
                                </optgroup>
                                <optgroup label={filterOptions.locations.east_bangalore.label}>
                                    {filterOptions.locations.east_bangalore.areas.map((area) => (
                                        <option key={area.value} value={area.label}>
                                            {area.label}
                                        </option>
                                    ))}
                                </optgroup>
                            </select>
                        </div>

                        {/* Budget */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1.5">
                                Budget
                            </label>
                            <select
                                value={selectedFilters.budgetRange || ''}
                                onChange={(e) =>
                                    handleFilterChange('budgetRange', e.target.value)
                                }
                                className="w-full p-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            >
                                <option value="">Any Budget</option>
                                {filterOptions.budget_ranges.map((budget) => (
                                    <option key={budget.value} value={budget.value}>
                                        {budget.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Possession */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1.5">
                                Possession By
                            </label>
                            <select
                                value={selectedFilters.possessionYear || ''}
                                onChange={(e) =>
                                    handleFilterChange('possessionYear', e.target.value)
                                }
                                className="w-full p-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            >
                                <option value="">Any Time</option>
                                {filterOptions.possession_years.map((year) => (
                                    <option key={year.value} value={year.value}>
                                        {year.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Actions */}
                        <div className="flex gap-2 pt-2">
                            <button
                                onClick={clearAllFilters}
                                className="flex-1 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                            >
                                Clear All
                            </button>
                            <button
                                onClick={onToggleCollapse}
                                className="flex-1 py-2 text-sm text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors"
                            >
                                Apply Filters
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default FilterPanel;
