"""
Sales Intelligence Service
Provides on-call assistance for sales agents with:
- Objection handling
- EMI calculations
- Comparison pitches
- Quick selling points
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class SalesIntelligence:
    """Sales-focused intelligence for on-call assistance."""
    
    def __init__(self):
        # Objection handling templates
        self.objection_handlers = {
            "expensive": self._handle_price_objection,
            "costly": self._handle_price_objection,
            "budget": self._handle_price_objection,
            "far": self._handle_location_objection,
            "distance": self._handle_location_objection,
            "construction": self._handle_construction_objection,
            "not ready": self._handle_construction_objection,
            "risk": self._handle_construction_objection,
        }
    
    def calculate_emi(self, price_inr: int, years: int = 20, interest_rate: float = 8.5) -> Dict[str, Any]:
        """Calculate EMI for a property."""
        principal = price_inr * 0.80  # 80% loan
        down_payment = price_inr * 0.20
        
        monthly_rate = interest_rate / 100 / 12
        num_payments = years * 12
        
        if monthly_rate > 0:
            emi = principal * monthly_rate * (1 + monthly_rate)**num_payments / ((1 + monthly_rate)**num_payments - 1)
        else:
            emi = principal / num_payments
        
        return {
            "price_inr": price_inr,
            "price_display": self._format_price(price_inr),
            "down_payment": down_payment,
            "down_payment_display": self._format_price(int(down_payment)),
            "loan_amount": principal,
            "loan_display": self._format_price(int(principal)),
            "emi": int(emi),
            "emi_display": f"₹{int(emi):,}/month",
            "tenure_years": years,
            "interest_rate": interest_rate
        }
    
    def generate_sales_pitch(self, project: Dict[str, Any]) -> str:
        """Generate a quick sales pitch for a project."""
        name = project.get('project_name', project.get('name', 'This project'))
        builder = project.get('developer_name', project.get('builder', ''))
        location = project.get('location', '')
        highlights = project.get('highlights', '')
        amenities = project.get('amenities', '')
        price_range = project.get('price_range', {})
        possession = project.get('possession_year', '')
        
        pitch = f"🎯 **Quick Pitch for {name}**\n\n"
        
        # Opening hook
        pitch += f"*\"{name} by {builder} is one of the most sought-after projects in {location}.\"*\n\n"
        
        # Key selling points
        pitch += "**Why This Project:**\n"
        
        if highlights:
            # Extract key points
            key_points = highlights.split('.')[:3]
            for point in key_points:
                if point.strip():
                    pitch += f"✅ {point.strip()}\n"
        
        # Price advantage
        if price_range:
            min_price = price_range.get('min_display', '')
            max_price = price_range.get('max_display', '')
            if min_price:
                pitch += f"\n💰 **Starting at just {min_price}** - excellent value for this location!\n"
                
                # Add EMI
                min_price_val = price_range.get('min', 0)
                if min_price_val and isinstance(min_price_val, (int, float)):
                    emi_info = self.calculate_emi(int(min_price_val * 10000000))
                    pitch += f"📊 EMI as low as **{emi_info['emi_display']}** (20% down payment)\n"
        
        # Amenities hook
        if amenities:
            pitch += f"\n🏊 World-class amenities including {amenities[:100]}...\n"
        
        # Possession
        if possession:
            pitch += f"\n📅 Possession by **{possession}**"
            if 'underconstruction' in project.get('status', '').lower():
                pitch += " - Book now at pre-launch prices!"
        
        pitch += "\n"
        return pitch
    
    def handle_objection(self, objection_type: str, project: Dict[str, Any] = None) -> str:
        """Generate response to common sales objections."""
        for keyword, handler in self.objection_handlers.items():
            if keyword in objection_type.lower():
                return handler(project)
        
        return self._generic_objection_response(project)
    
    def _handle_price_objection(self, project: Dict[str, Any] = None) -> str:
        """Handle 'too expensive' objections."""
        response = "💡 **Handling Price Objection:**\n\n"
        
        if project:
            price_range = project.get('price_range', {})
            min_price = price_range.get('min', 0)
            if min_price and isinstance(min_price, (int, float)):
                emi_info = self.calculate_emi(int(min_price * 10000000))
                response += f"**Key Points to Share:**\n\n"
                response += f"1️⃣ \"Let me break this down for you:\"\n"
                response += f"   • Down payment: Just **{emi_info['down_payment_display']}** (20%)\n"
                response += f"   • Monthly EMI: Only **{emi_info['emi_display']}**\n"
                response += f"   • That's similar to current rent, but you're *building equity!*\n\n"
        
        response += "2️⃣ **Value Appreciation:**\n"
        response += "   • Properties in this area have appreciated 8-12% annually\n"
        response += "   • Early buyers always get the best units and prices\n\n"
        
        response += "3️⃣ **Compare to Renting:**\n"
        response += "   • Rent is an expense that gives you nothing back\n"
        response += "   • EMI builds your own asset\n"
        response += "   • Tax benefits on home loan interest (up to ₹2L/year)\n\n"
        
        response += "📞 *\"Would you like me to send you a detailed payment plan?\"*"
        return response
    
    def _handle_location_objection(self, project: Dict[str, Any] = None) -> str:
        """Handle 'location is far' objections."""
        response = "💡 **Handling Location Objection:**\n\n"
        
        if project:
            highlights = project.get('highlights', '')
            location = project.get('location', '')
            if highlights:
                response += f"**For {location}:**\n"
                response += f"✅ {highlights[:200]}\n\n"
        
        response += "**Key Points to Share:**\n\n"
        response += "1️⃣ \"This location is developing rapidly:\"\n"
        response += "   • Metro connectivity coming soon\n"
        response += "   • Major IT hubs within 15-20 min drive\n"
        response += "   • Schools, hospitals, malls already operational\n\n"
        
        response += "2️⃣ **Price Advantage:**\n"
        response += "   • 15-20% less than central locations\n"
        response += "   • Same amenities, better lifestyle\n"
        response += "   • Early movers get best appreciation\n\n"
        
        response += "3️⃣ **Infrastructure:**\n"
        response += "   • Ring road connectivity\n"
        response += "   • Upcoming metro stations\n"
        response += "   • Airport access improving\n\n"
        
        response += "🚗 *\"Shall I arrange a site visit? You'll see the development firsthand.\"*"
        return response
    
    def _handle_construction_objection(self, project: Dict[str, Any] = None) -> str:
        """Handle 'under construction' risk objections."""
        response = "💡 **Handling Construction Risk Objection:**\n\n"
        
        if project:
            builder = project.get('developer_name', project.get('builder', ''))
            if builder:
                response += f"**About {builder}:**\n"
                response += f"✅ Trusted developer with on-time delivery track record\n"
                response += f"✅ RERA registered - fully compliant\n\n"
        
        response += "**Key Points to Share:**\n\n"
        response += "1️⃣ \"Here's why under-construction is actually *better*:\"\n"
        response += "   • **10-15% lower price** than ready-to-move\n"
        response += "   • **Flexible payment plans** during construction\n"
        response += "   • **Customization options** still available\n\n"
        
        response += "2️⃣ **RERA Protection:**\n"
        response += "   • Project is RERA registered\n"
        response += "   • 70% of funds in escrow account\n"
        response += "   • Penalties for delay - you're protected\n\n"
        
        response += "3️⃣ **Builder Track Record:**\n"
        response += "   • Show past completed projects\n"
        response += "   • Delivery timeline history\n"
        response += "   • Bank approvals confirm credibility\n\n"
        
        response += "📋 *\"Would you like me to share the RERA details and past project photos?\"*"
        return response
    
    def _generic_objection_response(self, project: Dict[str, Any] = None) -> str:
        """Generic objection handling."""
        return """💡 **Handling Customer Concern:**

**Listen First, Then Respond:**
1. "I completely understand your concern..."
2. "Let me address that specifically..."
3. "Many of our happy customers had the same question..."

**Follow Up:**
📞 "Would you like to speak with someone who recently purchased here?"
🏠 "A site visit might help you see the value firsthand."
📧 "Let me send you some additional information."
"""
    
    def get_comparison_points(self, project1: Dict, project2: Dict) -> str:
        """Generate comparison talking points between two projects."""
        response = f"📊 **Comparison: {project1.get('project_name')} vs {project2.get('project_name')}**\n\n"
        
        response += "| Feature | " + project1.get('project_name', 'Project 1') + " | " + project2.get('project_name', 'Project 2') + " |\n"
        response += "|---------|----------|----------|\n"
        response += f"| Builder | {project1.get('developer_name', 'N/A')} | {project2.get('developer_name', 'N/A')} |\n"
        response += f"| Location | {project1.get('location', 'N/A')} | {project2.get('location', 'N/A')} |\n"
        
        p1_price = project1.get('price_range', {}).get('min_display', 'N/A')
        p2_price = project2.get('price_range', {}).get('min_display', 'N/A')
        response += f"| Starting Price | {p1_price} | {p2_price} |\n"
        
        response += f"| Possession | {project1.get('possession_year', 'N/A')} | {project2.get('possession_year', 'N/A')} |\n"
        
        return response
    
    def _format_price(self, amount_inr: int) -> str:
        """Format price in Indian numbering."""
        if amount_inr >= 10000000:
            return f"₹{amount_inr / 10000000:.2f} Cr"
        elif amount_inr >= 100000:
            return f"₹{amount_inr / 100000:.0f} Lac"
        else:
            return f"₹{amount_inr:,}"
    
    def get_faq_response(self, faq_type: str, context: Optional[Dict] = None) -> Optional[str]:
        """
        Get FAQ response by type string.
        """
        handlers = {
            "stretch_budget": self.faq_stretch_budget,
            "convince_location": self.faq_convince_location,
            "under_construction": self.faq_convince_under_construction,
            "face_to_face": self.faq_convince_face_to_face,
            "site_visit": self.faq_convince_site_visit,
            "pinclick_value": self.faq_pinclick_value_prop
        }
        
        handler = handlers.get(faq_type)
        if handler:
            # Simplification: handlers currently don't use much context, just return static text
            # In future we can pass project/context
            return handler()
        
        return None

    # ============ 6 CORE FAQs FROM FLOWCHART ============
    
    # ============ 6 CORE FAQs FROM FLOWCHART ============
    
    def faq_stretch_budget(self, current_budget: str = None, project: Dict = None) -> str:
        """FAQ 1: How to stretch the budget"""
        response = "💡 *I understand budget is a key consideration. However, let me show you why stretching slightly could be a financial masterstroke:*\n\n"
        
        response += "1️⃣ **EMI vs Rent:**\n"
        response += "If you're paying ₹30-40K in rent, that's an expense. A slightly higher EMI is an **investment** that builds your own asset.\n\n"
        
        response += "2️⃣ **Tax Savings:**\n"
        response += "You save ~₹50-60K annually through Section 80C (Principal) and Section 24 (Interest) benefits. This effectively subsidies your EMI!\n\n"
        
        response += "3️⃣ **Higher Appreciation:**\n"
        response += "Properties in this segment appreciate 8-12% annually. A ₹10L stretch today could mean ₹15L+ extra value in just 3 years.\n\n"
        
        response += "4️⃣ **Flexible Payment Plans:**\n"
        response += "We have construction-linked plans (e.g., 10:80:10) that reduce your immediate burden significantly.\n\n"
        
        response += "📞 *Shall we look at options just 10-15% above your range? The monthly difference is often less than a weekend dinner, but the lifestyle upgrade is massive.*"
        return response
    
    def faq_convince_location(self, preferred_location: str = None, suggested_location: str = None) -> str:
        """FAQ 2: How to convince customer for other location"""
        response = "📍 *I completely understand your preference. But let me share why this upcoming location might actually be the smarter choice right now:*\n\n"
        
        response += "1️⃣ **More Vaule for Money:**\n"
        response += "You get a larger home with better amenities for **15-20% less** cost than established areas.\n\n"
        
        response += "2️⃣ **Explosive Growth Potential:**\n"
        response += "With upcoming Metro lines and IT park expansions, early investors here are seeing the highest appreciation rates in the city.\n\n"
        
        response += "3️⃣ **Better Quality of Life:**\n"
        response += "Wider roads, less congestion, and better air quality compared to the dense city center.\n\n"
        
        response += "4️⃣ **Commute Reality:**\n"
        response += "With the new ring road connectivity, major hubs are just a 20-30 min drive away.\n\n"
        
        response += "🚗 *Why not visit the site once? seeing the infrastructure development firsthand will give you a much better perspective.*"
        return response
    
    def faq_convince_under_construction(self, project: Dict = None) -> str:
        """FAQ 3: How to convince for under-construction when customer wants ready-to-move"""
        response = "🏗️ *I understand you'd prefer to move in immediately. However, buying Under-Construction has distinct financial advantages:*\n\n"
        
        response += "1️⃣ **Huge Price Savings:**\n"
        response += "You save **15-20%** compared to ready properties. On a ₹1.5Cr home, that's a saving of ₹20-25 Lakhs!\n\n"
        
        response += "2️⃣ **Easy Payment Flow:**\n"
        response += "You don't need to pay the full amount now. Pay just 10% to book, and the rest in small stages over 2-3 years.\n\n"
        
        response += "3️⃣ **Capital Appreciation:**\n"
        response += "By the time you get possession, your property value would have already appreciated significantly.\n\n"
        
        response += "4️⃣ **RERA Security:**\n"
        response += "Since this project is RERA registered with 70% funds in escrow, your investment is legally protected against delays.\n\n"
        
        response += "📋 *Most of our smart investors choose this route. Would you likeme to share the RERA certificate and the staggered payment schedule?*"
        return response
    
    def faq_face_to_face_meeting(self) -> str:
        """FAQ 4: How to pitch for face-to-face meeting"""
        response = "🤝 *Sir/Ma'am, while I can share basic details online, a quick meeting would be much more beneficial for you. Here's why:*\n\n"
        
        response += "1️⃣ **Exclusive 'Offline' Inventory:**\n"
        response += "We often have special units and pre-launch pricing that we are not allowed to publish online.\n\n"
        
        response += "2️⃣ **Personalized Financial Planning:**\n"
        response += "I can help structure your payment plan and calculate exact tax benefits based on your specific profile.\n\n"
        
        response += "3️⃣ **Legal & Documentation:**\n"
        response += "I can walk you through the RERA approvals, title deeds, and legal clearance documents in person.\n\n"
        
        response += "📅 *It's a no-obligation meeting, just 30 minutes. Would you prefer tomorrow evening or the weekend? I can come to your location.*"
        return response
    
    def faq_site_visit(self, project: Dict = None) -> str:
        """FAQ 5: How to pitch for site visit"""
        response = "🏠 *Photos and videos are great, but they only tell half the story. You really need to experience it:* \n\n"
        
        response += "1️⃣ **See the Construction Quality:**\n"
        response += "Inspect the finish, the materials used, and the actual room sizes in our sample apartment.\n\n"
        
        response += "2️⃣ **Feel the Neighborhood:**\n"
        response += "Check the approach roads, nearby shops, and the overall vibe of the locality yourself.\n\n"
        
        response += "3️⃣ **Spot Offers:**\n"
        response += "We often run special 'Site Visit Only' offers and discounts for visitors.\n\n"
        
        response += "🚗 *We provide a free pick-up and drop service! Can I book a cab for you this Saturday?*"
        return response
    
    def faq_pinclick_value(self) -> str:
        """FAQ 6: What values does Pinclick add in home buying journey"""
        response = "✨ *Great question! Here is why thousands of homebuyers choose Pinclick over going direct:*\n\n"
        
        response += "1️⃣ **Unbiased Advice:**\n"
        response += "We work with 100+ developers, not just one. We recommend what's best for **YOU**, not what a builder wants to sell.\n\n"
        
        response += "2️⃣ **Zero Additional Cost:**\n"
        response += "Our services are completely clear. You get the same (or better) price as buying direct, with zero service fees.\n\n"
        
        response += "3️⃣ **End-to-End Support:**\n"
        response += "From shortlisting -> Site visits -> Negotiation -> Home Loans -> Registration. We handle it all.\n\n"
        
        response += "4️⃣ **Professional Expertise:**\n"
        response += "Our property advisors are area experts who can verify legal aspects and future appreciation potential for you.\n\n"
        
        response += "🎯 *Think of us as your personal real estate wealth manager. How can I assist you further today?*"
        return response
    
    def get_faq_response(self, faq_type: str, **kwargs) -> str:
        """Get response for any of the 6 core FAQs."""
        faq_map = {
            "stretch_budget": self.faq_stretch_budget,
            "budget": self.faq_stretch_budget,
            "expensive": self.faq_stretch_budget,
            "location": self.faq_convince_location,
            "convince_location": self.faq_convince_location,
            "other_location": self.faq_convince_location,
            "under_construction": self.faq_convince_under_construction,
            "construction": self.faq_convince_under_construction,
            "ready_to_move": self.faq_convince_under_construction,
            "face_to_face": self.faq_face_to_face_meeting,
            "meeting": self.faq_face_to_face_meeting,
            "f2f": self.faq_face_to_face_meeting,
            "site_visit": self.faq_site_visit,
            "visit": self.faq_site_visit,
            "pinclick": self.faq_pinclick_value,
            "value": self.faq_pinclick_value,
            "why_pinclick": self.faq_pinclick_value,
        }
        
        faq_type_lower = faq_type.lower()
        for key, func in faq_map.items():
            if key in faq_type_lower:
                return func(**kwargs) if kwargs else func()
        
        return self._generic_objection_response()


# Global instance
sales_intelligence = SalesIntelligence()
