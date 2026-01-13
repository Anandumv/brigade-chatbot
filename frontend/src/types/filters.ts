// Filter-related types for property search

export interface FilterOption {
    value: string;
    label: string;
}

export interface BudgetRange extends FilterOption {
    min: number;
    max: number | null;
}

export interface LocationArea {
    value: string;
    label: string;
}

export interface LocationGroup {
    label: string;
    areas: LocationArea[];
}

export interface FilterOptions {
    configurations: FilterOption[];
    locations: {
        north_bangalore: LocationGroup;
        east_bangalore: LocationGroup;
    };
    budget_ranges: BudgetRange[];
    possession_years: FilterOption[];
}

export interface SelectedFilters {
    configuration?: string;
    location?: string;
    budgetRange?: string;
    budgetMin?: number;
    budgetMax?: number | null;
    possessionYear?: string;
}

export interface FilteredSearchRequest {
    query: string;
    filters?: SelectedFilters;
    project_id?: string;
    user_id?: string;
}

export interface GuidedChatRequest {
    query: string;
    filters?: SelectedFilters;
    conversation_context?: {
        last_intent?: string;
        objections?: string[];
        interested_projects?: string[];
    };
}
