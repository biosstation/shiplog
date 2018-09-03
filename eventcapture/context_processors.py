from eventcapture.models import Cruise

def active_cruise(request):
    context = {}
    try:
        context['cruise'] = Cruise.get_active_cruise()
    except ValueError as e:
        context['error'] = e
        context['message'] = "More than one cruise has been configure to occur right now"
    return context
