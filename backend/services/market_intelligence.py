"""
Market Intelligence Service
Provides competitive pricing analysis, appreciation forecasts, and ROI calculations
"""

import json
import logging
import os
from typing import Dict, Optional, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class MarketIntelligence:
    """
    Provides market comparison and investment intelligence for real estate
    """

    def __init__(self):
        # Load market data from JSON
        data_path = Path(__file__).parent.parent / "data" / "market_data.json"
        try:
            with open(data_path, 'r') as f:
                self.market_data = json.load(f)
            logger.info(f"Loaded market data for {len(self.market_data)} localities")
        except Exception as e:
            logger.error(f"Failed to load market data: {e}")
            self.market_data = {}

    def get_price_comparison(
        self,
        project: Dict[str, Any],
        locality: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Compare project pricing against market average

        Args:
            project: Project dict with price, location, configuration
            locality: Optional locality override (defaults to project location)

        Returns:
            Dict with comparison data or None if data unavailable
        """
        # Determine locality
        location = locality or project.get("location", "")
        if not location:
            logger.warning("No location found for project")
            return None

        # Get market data for locality
        market_info = self.market_data.get(location)
        if not market_info:
            logger.warning(f"No market data available for {location}")
            return None

        # Calculate project price per sqft
        project_price_per_sqft = self._calculate_price_per_sqft(project)
        if not project_price_per_sqft:
            return None

        # Get market average
        market_avg = market_info["avg_price_per_sqft"]

        # Calculate savings
        savings_percentage = ((market_avg - project_price_per_sqft) / market_avg) * 100
        savings_absolute = self._calculate_absolute_savings(
            project,
            savings_percentage
        )

        return {
            "project_price_per_sqft": round(project_price_per_sqft),
            "market_avg_per_sqft": market_avg,
            "savings_percentage": round(savings_percentage, 1),
            "savings_absolute_lakhs": round(savings_absolute / 100000, 1),  # Convert to lakhs
            "price_position": self._get_price_position(savings_percentage),
            "value_proposition": self._generate_value_proposition(
                project.get("name", "This project"),
                savings_percentage,
                savings_absolute,
                location
            ),
            "market_range_min": market_info["price_range_min"],
            "market_range_max": market_info["price_range_max"]
        }

    def get_appreciation_forecast(
        self,
        project: Dict[str, Any],
        locality: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get appreciation forecasts and ROI potential for a locality

        Args:
            project: Project dict
            locality: Optional locality override

        Returns:
            Dict with appreciation data or None
        """
        location = locality or project.get("location", "")
        if not location:
            return None

        market_info = self.market_data.get(location)
        if not market_info:
            return None

        # Calculate projected ROI
        current_price = project.get("budget_min", 0)  # In lakhs
        yoy_rate = market_info["appreciation_rate_yoy"]

        # 3-year projection
        projected_3yr = current_price * ((1 + yoy_rate/100) ** 3)
        roi_3yr = ((projected_3yr - current_price) / current_price) * 100

        # 5-year projection
        projected_5yr = current_price * ((1 + yoy_rate/100) ** 5)
        roi_5yr = ((projected_5yr - current_price) / current_price) * 100

        return {
            "historical_5yr_percent": market_info["appreciation_5yr"],
            "yoy_rate_percent": yoy_rate,
            "forecast_3yr_percent": round(roi_3yr, 1),
            "forecast_5yr_percent": round(roi_5yr, 1),
            "roi_potential": self._classify_roi_potential(yoy_rate),
            "projected_value_3yr_lakhs": round(projected_3yr, 1),
            "projected_value_5yr_lakhs": round(projected_5yr, 1),
            "gain_3yr_lakhs": round(projected_3yr - current_price, 1),
            "gain_5yr_lakhs": round(projected_5yr - current_price, 1)
        }

    def get_locality_insights(self, locality: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive insights about a locality

        Args:
            locality: Locality name (e.g., "Whitefield", "Sarjapur")

        Returns:
            Dict with locality insights or None
        """
        market_info = self.market_data.get(locality)
        if not market_info:
            return None

        return {
            "locality": locality,
            "avg_price_per_sqft": market_info["avg_price_per_sqft"],
            "appreciation_rate_yoy": market_info["appreciation_rate_yoy"],
            "inventory_trend": market_info["inventory_trend"],
            "upcoming_infrastructure": market_info["upcoming_infrastructure"],
            "key_attractions": market_info["key_attractions"],
            "demographics": market_info["demographics"],
            "rental_yield_percent": market_info["rental_yield"],
            "investment_grade": self._calculate_investment_grade(market_info)
        }

    def compare_localities(
        self,
        locality1: str,
        locality2: str
    ) -> Optional[Dict[str, Any]]:
        """
        Compare two localities side-by-side

        Args:
            locality1: First locality name
            locality2: Second locality name

        Returns:
            Comparison dict or None
        """
        data1 = self.market_data.get(locality1)
        data2 = self.market_data.get(locality2)

        if not data1 or not data2:
            return None

        return {
            "locality1": {
                "name": locality1,
                "avg_price": data1["avg_price_per_sqft"],
                "appreciation": data1["appreciation_rate_yoy"],
                "rental_yield": data1["rental_yield"],
                "trend": data1["inventory_trend"]
            },
            "locality2": {
                "name": locality2,
                "avg_price": data2["avg_price_per_sqft"],
                "appreciation": data2["appreciation_rate_yoy"],
                "rental_yield": data2["rental_yield"],
                "trend": data2["inventory_trend"]
            },
            "winner_appreciation": locality1 if data1["appreciation_rate_yoy"] > data2["appreciation_rate_yoy"] else locality2,
            "winner_affordability": locality1 if data1["avg_price_per_sqft"] < data2["avg_price_per_sqft"] else locality2,
            "winner_rental_yield": locality1 if data1["rental_yield"] > data2["rental_yield"] else locality2,
            "price_difference_percent": round(
                abs(data1["avg_price_per_sqft"] - data2["avg_price_per_sqft"]) / min(data1["avg_price_per_sqft"], data2["avg_price_per_sqft"]) * 100,
                1
            )
        }

    def _calculate_price_per_sqft(self, project: Dict[str, Any]) -> Optional[float]:
        """Calculate price per sqft from project data"""
        # Try to get from project directly
        if "price_per_sqft" in project:
            return project["price_per_sqft"]

        # Calculate from budget and typical sqft
        # Assuming typical sizes: 2BHK=1200sqft, 3BHK=1600sqft, 4BHK=2200sqft
        config = project.get("configuration", "")
        budget_min = project.get("budget_min", 0)  # In lakhs

        if "2" in config:
            sqft = 1200
        elif "3" in config:
            sqft = 1600
        elif "4" in config:
            sqft = 2200
        else:
            sqft = 1400  # Default

        if budget_min > 0:
            price_inr = budget_min * 100000  # Convert lakhs to INR
            return price_inr / sqft

        return None

    def _calculate_absolute_savings(
        self,
        project: Dict[str, Any],
        savings_percentage: float
    ) -> float:
        """Calculate absolute savings in INR"""
        budget_min = project.get("budget_min", 0) * 100000  # Lakhs to INR
        return (savings_percentage / 100) * budget_min

    def _get_price_position(self, savings_percentage: float) -> str:
        """Classify price position relative to market"""
        if savings_percentage > 15:
            return "excellent_value"
        elif savings_percentage > 5:
            return "good_value"
        elif savings_percentage > -5:
            return "market_average"
        elif savings_percentage > -15:
            return "premium"
        else:
            return "luxury_premium"

    def _generate_value_proposition(
        self,
        project_name: str,
        savings_percentage: float,
        savings_absolute: float,
        locality: str
    ) -> str:
        """Generate a compelling value proposition message"""
        if savings_percentage > 10:
            return f"{project_name} offers exceptional value at {abs(round(savings_percentage))}% below the {locality} market average - you save approximately ₹{round(savings_absolute/100000, 1)} lakhs!"
        elif savings_percentage > 0:
            return f"{project_name} is priced {round(savings_percentage, 1)}% below the {locality} market average, offering good value for money."
        elif savings_percentage > -10:
            return f"{project_name} is priced near the {locality} market average, reflecting fair market value for its features."
        else:
            return f"{project_name} is a premium offering, priced {abs(round(savings_percentage))}% above market average due to exceptional amenities and location advantages."

    def _classify_roi_potential(self, yoy_rate: float) -> str:
        """Classify ROI potential based on appreciation rate"""
        if yoy_rate > 14:
            return "very_high"
        elif yoy_rate > 11:
            return "high"
        elif yoy_rate > 8:
            return "moderate"
        else:
            return "stable"

    def _calculate_investment_grade(self, market_info: Dict[str, Any]) -> str:
        """Calculate overall investment grade for a locality"""
        appreciation = market_info["appreciation_rate_yoy"]
        rental_yield = market_info["rental_yield"]
        trend = market_info["inventory_trend"]

        score = 0

        # Appreciation score (0-40 points)
        if appreciation > 14:
            score += 40
        elif appreciation > 11:
            score += 30
        elif appreciation > 8:
            score += 20
        else:
            score += 10

        # Rental yield score (0-30 points)
        if rental_yield > 3.5:
            score += 30
        elif rental_yield > 3.0:
            score += 20
        else:
            score += 10

        # Trend score (0-30 points)
        if trend == "emerging_hotspot":
            score += 30
        elif trend in ["high_demand", "growing"]:
            score += 25
        elif trend == "stable":
            score += 15
        else:
            score += 10

        # Convert to grade
        if score >= 80:
            return "A+"
        elif score >= 70:
            return "A"
        elif score >= 60:
            return "B+"
        elif score >= 50:
            return "B"
        else:
            return "C"


# Singleton instance
_market_intelligence_instance = None


def get_market_intelligence() -> MarketIntelligence:
    """Get singleton instance of MarketIntelligence"""
    global _market_intelligence_instance
    if _market_intelligence_instance is None:
        _market_intelligence_instance = MarketIntelligence()
    return _market_intelligence_instance
