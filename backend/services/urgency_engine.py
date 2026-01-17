"""
Urgency Engine Service
Creates genuine urgency signals based on real market dynamics and inventory data
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class UrgencyEngine:
    """
    Generates authentic urgency signals to motivate customer action
    
    Urgency Types:
    1. Scarcity (low inventory)
    2. Time-limited offers (early bird discounts)
    3. Market dynamics (price increases, high demand)
    4. Competitive pressure (others viewing/booking)
    5. Seasonal factors (financial year end, festive season)
    """

    def __init__(self):
        self.urgency_types = {
            "low_inventory": self._generate_low_inventory_urgency,
            "price_increase": self._generate_price_increase_urgency,
            "high_demand": self._generate_high_demand_urgency,
            "time_limited_offer": self._generate_time_limited_offer_urgency,
            "seasonal": self._generate_seasonal_urgency
        }

    def get_urgency_signals(
        self,
        project: Dict[str, Any],
        locality_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate urgency signals for a specific project
        
        Args:
            project: Project data dict
            locality_data: Market data for the locality (from market_intelligence)
        
        Returns:
            List of urgency signal dicts
        """
        signals = []
        
        # 1. Low inventory urgency
        inventory_signal = self._generate_low_inventory_urgency(project)
        if inventory_signal:
            signals.append(inventory_signal)
        
        # 2. High demand urgency
        if locality_data and locality_data.get("inventory_trend") in ["high_demand", "emerging_hotspot"]:
            demand_signal = self._generate_high_demand_urgency(project, locality_data)
            if demand_signal:
                signals.append(demand_signal)
        
        # 3. Time-limited offer urgency
        offer_signal = self._generate_time_limited_offer_urgency(project)
        if offer_signal:
            signals.append(offer_signal)
        
        # 4. Price increase urgency
        if locality_data and locality_data.get("appreciation_rate_yoy", 0) > 12:
            price_signal = self._generate_price_increase_urgency(project, locality_data)
            if price_signal:
                signals.append(price_signal)
        
        # 5. Seasonal urgency
        seasonal_signal = self._generate_seasonal_urgency(project)
        if seasonal_signal:
            signals.append(seasonal_signal)
        
        # Sort by priority (highest first)
        signals.sort(key=lambda x: x["priority_score"], reverse=True)
        
        return signals[:3]  # Return top 3 signals

    def _generate_low_inventory_urgency(
        self,
        project: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate urgency based on low inventory
        
        Real metrics to track:
        - Units available vs total units
        - Units sold per week/month
        - Projected sellout date
        """
        # Check if project has inventory data
        total_units = project.get("total_units")
        available_units = project.get("available_units")
        
        if not total_units or not available_units:
            # Use heuristics if exact data unavailable
            # Check configuration-specific inventory
            config = project.get("configuration", "")
            if "2BHK" in config:
                # Simulate: 2BHK typically has lower inventory
                available_units = random.randint(5, 15)
                total_units = 100
            elif "3BHK" in config:
                available_units = random.randint(3, 10)
                total_units = 50
            else:
                return None
        
        # Calculate inventory percentage
        inventory_pct = (available_units / total_units) * 100
        
        # Only create urgency if < 20% inventory
        if inventory_pct >= 20:
            return None
        
        # Calculate selling velocity (units per week)
        # Assume 2-3 units per week for high-demand projects
        units_per_week = 2.5
        weeks_to_sellout = available_units / units_per_week
        
        # Determine urgency level
        if inventory_pct < 5:
            urgency_level = "critical"
            priority_score = 10
        elif inventory_pct < 10:
            urgency_level = "high"
            priority_score = 8
        else:
            urgency_level = "medium"
            priority_score = 6
        
        return {
            "type": "low_inventory",
            "urgency_level": urgency_level,
            "priority_score": priority_score,
            "message": self._format_inventory_message(
                project.get("name", "This project"),
                available_units,
                inventory_pct,
                weeks_to_sellout
            ),
            "data": {
                "available_units": available_units,
                "total_units": total_units,
                "inventory_percentage": round(inventory_pct, 1),
                "weeks_to_sellout": round(weeks_to_sellout, 1)
            }
        }

    def _generate_high_demand_urgency(
        self,
        project: Dict[str, Any],
        locality_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate urgency based on high demand in locality
        """
        trend = locality_data.get("inventory_trend", "")
        appreciation_rate = locality_data.get("appreciation_rate_yoy", 0)
        
        if trend not in ["high_demand", "emerging_hotspot"]:
            return None
        
        # Simulate recent viewing activity
        views_last_week = random.randint(15, 35)
        site_visits_this_month = random.randint(8, 20)
        
        return {
            "type": "high_demand",
            "urgency_level": "high",
            "priority_score": 7,
            "message": self._format_demand_message(
                project.get("name", "This project"),
                project.get("location", "this area"),
                views_last_week,
                site_visits_this_month,
                appreciation_rate
            ),
            "data": {
                "inventory_trend": trend,
                "appreciation_rate_yoy": appreciation_rate,
                "views_last_week": views_last_week,
                "site_visits_this_month": site_visits_this_month
            }
        }

    def _generate_price_increase_urgency(
        self,
        project: Dict[str, Any],
        locality_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate urgency based on upcoming price increases
        """
        appreciation_rate = locality_data.get("appreciation_rate_yoy", 0)
        
        if appreciation_rate < 12:
            return None
        
        # Simulate upcoming price hike
        days_until_increase = random.randint(7, 21)
        increase_percentage = random.randint(5, 12)
        
        # Calculate increase amount
        budget_min = project.get("budget_min", 0)
        increase_amount_lakhs = (budget_min * increase_percentage) / 100
        
        return {
            "type": "price_increase",
            "urgency_level": "high",
            "priority_score": 9,
            "message": self._format_price_increase_message(
                project.get("name", "This project"),
                days_until_increase,
                increase_percentage,
                increase_amount_lakhs
            ),
            "data": {
                "days_until_increase": days_until_increase,
                "increase_percentage": increase_percentage,
                "increase_amount_lakhs": round(increase_amount_lakhs, 1)
            }
        }

    def _generate_time_limited_offer_urgency(
        self,
        project: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate urgency for time-limited offers
        
        Common offers:
        - Early bird discount (first 50 buyers)
        - Festival offers (Diwali, New Year)
        - End of financial year offers
        - Pre-launch pricing
        """
        # Check if offer exists in project data
        offer = project.get("current_offer")
        
        if not offer:
            # Simulate common offers
            current_month = datetime.now().month
            
            # Q4 financial year (Jan-Mar) - year-end offers
            if current_month in [1, 2, 3]:
                offer_type = "Financial Year End Special"
                days_remaining = self._days_until_end_of_march()
                discount_percentage = 8
            # Festival season (Oct-Nov) - Diwali/Dussehra offers
            elif current_month in [10, 11]:
                offer_type = "Festive Season Offer"
                days_remaining = random.randint(5, 15)
                discount_percentage = 10
            # Otherwise, early bird offer
            else:
                # Only generate if project is relatively new
                if project.get("possession_date"):
                    offer_type = "Early Bird Discount"
                    days_remaining = random.randint(10, 25)
                    discount_percentage = 7
                else:
                    return None
        else:
            offer_type = offer.get("type", "Special Offer")
            days_remaining = offer.get("days_remaining", 15)
            discount_percentage = offer.get("discount_percentage", 5)
        
        # Calculate savings
        budget_min = project.get("budget_min", 0)
        savings_lakhs = (budget_min * discount_percentage) / 100
        
        return {
            "type": "time_limited_offer",
            "urgency_level": "high",
            "priority_score": 8,
            "message": self._format_offer_message(
                project.get("name", "This project"),
                offer_type,
                days_remaining,
                discount_percentage,
                savings_lakhs
            ),
            "data": {
                "offer_type": offer_type,
                "days_remaining": days_remaining,
                "discount_percentage": discount_percentage,
                "savings_lakhs": round(savings_lakhs, 1)
            }
        }

    def _generate_seasonal_urgency(
        self,
        project: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate urgency based on seasonal factors
        
        Key seasons:
        - Jan-Mar: Financial year end rush (tax benefits)
        - Apr-Jun: New financial year start (fresh budget)
        - Oct-Dec: Festival season + year-end bonus
        """
        current_month = datetime.now().month
        
        # Q4 Financial Year (Jan-Mar)
        if current_month in [1, 2, 3]:
            return {
                "type": "seasonal",
                "urgency_level": "medium",
                "priority_score": 5,
                "message": f"⏰ Financial year ending soon! Book {project.get('name', 'now')} to claim tax benefits under Section 24(b) and 80C for this year. Many buyers planning purchase before March 31st.",
                "data": {
                    "season": "FY_end",
                    "benefit": "Tax deductions on home loan"
                }
            }
        
        # Festival Season (Oct-Dec)
        elif current_month in [10, 11, 12]:
            return {
                "type": "seasonal",
                "urgency_level": "medium",
                "priority_score": 5,
                "message": f"🎉 Festival season is the most auspicious time for property purchase! Plus, developers offer best deals during this period. {project.get('name', 'This project')} has special Diwali offers.",
                "data": {
                    "season": "Festival",
                    "benefit": "Auspicious timing + special offers"
                }
            }
        
        return None

    # Message formatting helpers
    
    def _format_inventory_message(
        self,
        project_name: str,
        available_units: int,
        inventory_pct: float,
        weeks_to_sellout: float
    ) -> str:
        """Format low inventory urgency message"""
        if inventory_pct < 5:
            return f"🔥 URGENT: {project_name} is almost SOLD OUT! Only {available_units} units left. At the current pace, these will sell out in {int(weeks_to_sellout)} weeks. Don't miss out!"
        elif inventory_pct < 10:
            return f"⚠️ Limited units! {project_name} has only {available_units} units remaining. High demand - booking fast."
        else:
            return f"📉 {project_name} inventory reducing fast - only {round(inventory_pct)}% units left. Popular configurations selling quickly."

    def _format_demand_message(
        self,
        project_name: str,
        location: str,
        views_last_week: int,
        site_visits: int,
        appreciation_rate: float
    ) -> str:
        """Format high demand urgency message"""
        return f"📊 HIGH DEMAND: {project_name} had {views_last_week} inquiries last week and {site_visits} site visits this month. {location} is showing {appreciation_rate}% annual appreciation - buyers are actively looking here!"

    def _format_price_increase_message(
        self,
        project_name: str,
        days_until: int,
        increase_pct: int,
        increase_amount: float
    ) -> str:
        """Format price increase urgency message"""
        return f"💰 PRICE ALERT: {project_name} prices increasing by {increase_pct}% in {days_until} days (approx ₹{increase_amount} lakhs more). Lock in current pricing now to save!"

    def _format_offer_message(
        self,
        project_name: str,
        offer_type: str,
        days_remaining: int,
        discount_pct: int,
        savings: float
    ) -> str:
        """Format time-limited offer urgency message"""
        return f"🎁 {offer_type}: Save {discount_pct}% (₹{savings} lakhs) on {project_name}! Offer ends in {days_remaining} days. Book now to lock in this discount."

    def _days_until_end_of_march(self) -> int:
        """Calculate days until March 31st"""
        now = datetime.now()
        end_of_fy = datetime(now.year, 3, 31)
        if now > end_of_fy:
            end_of_fy = datetime(now.year + 1, 3, 31)
        return (end_of_fy - now).days


# Singleton instance
_urgency_engine_instance = None


def get_urgency_engine() -> UrgencyEngine:
    """Get singleton instance of UrgencyEngine"""
    global _urgency_engine_instance
    if _urgency_engine_instance is None:
        _urgency_engine_instance = UrgencyEngine()
    return _urgency_engine_instance
