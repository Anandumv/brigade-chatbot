"""
Budget Relaxation Service (Deterministic)
Applies exact budget relaxation logic: 1.0x → 1.1x → 1.2x → 1.3x
Stop at first match. No GPT involved - pure code logic.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from services.hybrid_retrieval import hybrid_retrieval
from services.filter_extractor import PropertyFilters

logger = logging.getLogger(__name__)

# Spec-compliant relaxation steps
RELAX_STEPS = [1.0, 1.1, 1.2, 1.3]


class BudgetRelaxationService:
    """
    Deterministic budget relaxation logic.
    GPT only explains results - never participates in the logic.
    """

    async def relax_and_find(
        self,
        budget: int,
        location: Optional[str],
        filters: PropertyFilters,
        query: str = ""
    ) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        """
        Apply budget relaxation: 1.0x → 1.1x → 1.2x → 1.3x
        Stop at first match.

        Args:
            budget: Original budget in INR
            location: Location string (optional)
            filters: PropertyFilters object with all other filters
            query: Original query (for logging)

        Returns:
            Tuple of (projects_list, multiplier_applied)
            multiplier_applied is None if no results found even at 1.3x
        """
        logger.info(f"Starting budget relaxation for budget={budget}, location={location}")

        for multiplier in RELAX_STEPS:
            relaxed_budget = int(budget * multiplier)

            # Update filters with relaxed budget
            filters_copy = filters.model_copy(deep=True)
            filters_copy.max_price_inr = relaxed_budget

            # If location is provided, set it in filters
            if location:
                if not filters_copy.locality:
                    filters_copy.locality = location
                if not filters_copy.area:
                    filters_copy.area = location

            # Query database with relaxed budget
            logger.info(f"Trying relaxation step {multiplier}x: budget={relaxed_budget}")

            try:
                result = await hybrid_retrieval.search_with_filters(
                    query=query or f"projects under {relaxed_budget}",
                    filters=filters_copy,
                    use_llm_extraction=False
                )

                projects = result.get("projects", [])

                if projects:
                    logger.info(
                        f"✅ Found {len(projects)} projects at {multiplier}x relaxation "
                        f"(budget: {budget} → {relaxed_budget})"
                    )
                    return projects, multiplier

            except Exception as e:
                logger.error(f"Error querying at {multiplier}x: {e}", exc_info=True)
                continue

        # No results found even at 1.3x
        logger.warning(f"❌ No projects found even after 1.3x relaxation (budget: {budget} → {int(budget * 1.3)})")
        return [], None

    def explain_relaxation(self, original_budget: int, relaxed_budget: int, multiplier: float) -> str:
        """
        Generate explanation text for budget relaxation.
        This is what GPT will include in bullet points.

        Args:
            original_budget: Original budget in INR
            relaxed_budget: Relaxed budget in INR
            multiplier: Multiplier applied (1.1, 1.2, or 1.3)

        Returns:
            Human-readable explanation string
        """
        percentage = int((multiplier - 1.0) * 100)

        explanations = {
            1.1: f"Relaxed budget by 10% ({self._format_inr(original_budget)} → {self._format_inr(relaxed_budget)}) to show nearby options",
            1.2: f"Relaxed budget by 20% ({self._format_inr(original_budget)} → {self._format_inr(relaxed_budget)}) - no exact matches found",
            1.3: f"Relaxed budget by 30% ({self._format_inr(original_budget)} → {self._format_inr(relaxed_budget)}) - showing best available options"
        }

        return explanations.get(multiplier, f"Adjusted budget to {self._format_inr(relaxed_budget)}")

    def _format_inr(self, amount: int) -> str:
        """
        Format INR amount in lakhs/crores.
        Example: 8000000 -> "80L", 13000000 -> "1.3Cr"
        """
        if amount >= 10000000:  # 1 crore+
            crores = amount / 10000000
            if crores == int(crores):
                return f"{int(crores)}Cr"
            return f"{crores:.1f}Cr"
        else:  # lakhs
            lakhs = amount / 100000
            if lakhs == int(lakhs):
                return f"{int(lakhs)}L"
            return f"{lakhs:.1f}L"

    def should_apply_relaxation(
        self,
        exact_results: List[Dict[str, Any]],
        budget: Optional[int]
    ) -> bool:
        """
        Determine if budget relaxation should be applied.

        Args:
            exact_results: Results from exact budget query
            budget: User's budget (None means no budget specified)

        Returns:
            True if relaxation should be attempted, False otherwise
        """
        # Don't relax if no budget specified
        if budget is None:
            return False

        # Don't relax if exact results found
        if exact_results:
            return False

        # Apply relaxation
        return True


# Global instance
budget_relaxer = BudgetRelaxationService()


async def relax_and_find(
    budget: int,
    location: Optional[str],
    filters: PropertyFilters,
    query: str = ""
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    """
    Convenience function to call global budget_relaxer instance.

    Args:
        budget: Original budget in INR
        location: Location string (optional)
        filters: PropertyFilters object
        query: Original query (for logging)

    Returns:
        Tuple of (projects_list, multiplier_applied)
    """
    return await budget_relaxer.relax_and_find(budget, location, filters, query)
