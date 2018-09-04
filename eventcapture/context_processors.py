from eventcapture.models import Cruise

def active_cruise(request):
    context = {}
    try:
        context['cruise'] = Cruise.get_active_cruise()
    except ValueError as e:
        context['error'] = e
        context['message'] = "More than one cruise has been configure to occur right now"
    return context

def color_mode(request):
    context = {}
    try:
        if request.session['color_mode'] is None:
            request.session['color_mode'] = 'light'
        if request.GET.get('color_mode', None) is None:
            return context
        request.session['color_mode'] = request.GET.get('color_mode', 'light')
    except KeyError:
        request.session['color_mode'] = 'light'
    return context
