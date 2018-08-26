from eventcapture.models import Cruise

def active_cruise(request):
    context = {}
    try:
        context['cruise'] = Cruise.get_active_cruise()
    except ValueError as e:
        context['error'] = e
    return context
