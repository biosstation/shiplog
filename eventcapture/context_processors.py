from eventcapture.models import Cruise

def active_cruise(request):
    context = {}
    cruises = Cruise.get_active_cruises()
    if len(cruises) > 1:
        context['error'] = 'Overlapping cruises not allowed'
    cruise = cruises.first()
    context['cruise'] = cruise
    return context
