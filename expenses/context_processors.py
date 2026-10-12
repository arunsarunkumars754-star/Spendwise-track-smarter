"""
Context processors for SpendWise application.
Provides global template variables such as branding, default currency, and current year.
"""

from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings


def spendwise_global_context(request):
    """Provides application-wide template variables."""
    currency_symbol = '₹' if getattr(settings, 'DEFAULT_CURRENCY', 'INR') == 'INR' else '$'
    
    user_profile = None
    if request.user.is_authenticated:
        try:
            user_profile = getattr(request.user, 'profile', None)
        except (AttributeError, ObjectDoesNotExist):
            user_profile = None

    return {
        'APP_NAME': 'SpendWise',
        'APP_TAGLINE': 'Track smarter. Spend better.',
        'CURRENCY_CODE': getattr(settings, 'DEFAULT_CURRENCY', 'INR'),
        'CURRENCY_SYMBOL': currency_symbol,
        'CURRENT_YEAR': datetime.now().year,
        'user_profile': user_profile,
    }
