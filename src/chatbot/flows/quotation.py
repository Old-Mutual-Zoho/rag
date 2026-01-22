"""
Quotation flow - Generate and present insurance quote
"""
from typing import Dict
from decimal import Decimal


class QuotationFlow:
    def __init__(self, product_catalog, db):
        self.catalog = product_catalog
        self.db = db
    
    async def start(self, user_id: str, initial_data: Dict) -> Dict:
        """Start quotation flow"""
        # Calculate premium based on underwriting data
        quote_data = await self._calculate_premium(initial_data)
        
        return {
            'response': {
                'type': 'quote_presentation',
                'message': '💰 Here\'s your personalized quote',
                'quote': quote_data
            },
            'next_step': 0,
            'collected_data': initial_data
        }
    
    async def process_step(
        self,
        user_input: str,
        current_step: int,
        collected_data: Dict,
        user_id: str
    ) -> Dict:
        """Process quotation flow"""
        
        if current_step == 0:  # Present quote
            quote_data = await self._calculate_premium(collected_data)
            
            return {
                'response': {
                    'type': 'quote',
                    'quote_details': quote_data,
                    'actions': [
                        {'type': 'accept', 'label': '✅ Accept Quote'},
                        {'type': 'modify', 'label': '✏️ Modify Coverage'},
                        {'type': 'decline', 'label': '❌ Not Now'}
                    ]
                },
                'next_step': 1,
                'collected_data': collected_data
            }
        
        elif current_step == 1:  # Handle user action
            action = user_input.lower()
            
            if action == 'accept':
                # Save quote to database
                quote = self.db.create_quote(
                    user_id=user_id,
                    product_id=collected_data.get('product_id', 'li_002'),
                    premium_amount=collected_data.get('monthly_premium'),
                    sum_assured=collected_data.get('sum_assured'),
                    underwriting_data=collected_data
                )
                
                return {
                    'response': {
                        'type': 'quote_accepted',
                        'message': '🎉 Great! Your quote has been saved.',
                        'quote_id': str(quote.id),
                        'valid_until': quote.valid_until.isoformat(),
                        'next_steps': 'Proceed to payment or save for later'
                    },
                    'complete': True,
                    'next_flow': 'payment',
                    'data': {'quote_id': str(quote.id)}
                }
            
            elif action == 'modify':
                return {
                    'response': {
                        'type': 'modification',
                        'message': 'What would you like to change?',
                        'options': [
                            {'id': 'sum_assured', 'label': 'Coverage Amount'},
                            {'id': 'term', 'label': 'Policy Term'},
                            {'id': 'start_over', 'label': 'Start Over'}
                        ]
                    },
                    'next_step': 0,  # Loop back
                    'collected_data': collected_data
                }
            
            else:  # decline
                return {
                    'response': {
                        'type': 'declined',
                        'message': 'No problem! Your quote will be saved for 30 days. You can come back anytime.',
                        'options': [
                            {'type': 'explore', 'label': 'Explore Other Products'},
                            {'type': 'end', 'label': 'Exit'}
                        ]
                    },
                    'complete': True
                }
    
    async def _calculate_premium(self, data: Dict) -> Dict:
        """Calculate premium based on underwriting data"""
        # Base premium calculation
        sum_assured = Decimal(str(data.get('sum_assured', 10000000)))
        term = int(data.get('policy_term', 20))
        
        # Get base rate (per 1000 of sum assured per year)
        base_rate = Decimal('2.50')  # UGX 2.50 per 1000 per year
        
        # Calculate annual premium
        annual_premium = (sum_assured / 1000) * base_rate
        
        # Apply age factor
        dob = data.get('date_of_birth')
        if dob:
            from datetime import datetime
            age = (datetime.now() - datetime.fromisoformat(dob)).days // 365
            age_factor = Decimal('1.0') + (Decimal(str(age)) - 30) * Decimal('0.01')
            annual_premium *= age_factor
        
        # Apply health loadings
        health_loading = Decimal('0')
        health_info = data.get('health_info', {})
        if health_info.get('chronic_conditions', {}).get('answer') == 'yes':
            health_loading += Decimal('0.25')  # 25% loading
        
        if health_loading > 0:
            annual_premium *= (Decimal('1.0') + health_loading)
        
        # Apply lifestyle loadings
        lifestyle = data.get('lifestyle_info', {})
        if lifestyle.get('smoker') == 'Yes - regularly':
            annual_premium *= Decimal('1.30')  # 30% loading for smokers
        
        # Monthly premium
        monthly_premium = annual_premium / 12
        
        # Total premium over term
        total_premium = annual_premium * term
        
        return {
            'product_name': 'Family Life Protection',
            'sum_assured': float(sum_assured),
            'policy_term': term,
            'monthly_premium': float(monthly_premium.quantize(Decimal('0.01'))),
            'annual_premium': float(annual_premium.quantize(Decimal('0.01'))),
            'total_over_term': float(total_premium.quantize(Decimal('0.01'))),
            'breakdown': {
                'base_premium': float((sum_assured / 1000) * base_rate * 12),
                'age_adjustment': f"{((age_factor - 1) * 100):.1f}%" if 'age_factor' in locals() else '0%',
                'health_loading': f"{(health_loading * 100):.0f}%" if health_loading > 0 else 'None',
                'lifestyle_loading': '30%' if lifestyle.get('smoker') == 'Yes - regularly' else 'None'
            },
            'features': [
                'Death benefit to beneficiaries',
                'Terminal illness cover',
                'Funeral benefit included',
                'Optional riders available'
            ]
        }