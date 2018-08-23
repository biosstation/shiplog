from django.shortcuts import render
from eventcapture.models import Cruise, Device

def index(request):
    context = {}
    cruises = Cruise.get_active_cruises()
    if len(cruises) > 1:
        context['error'] = 'Overlapping cruises not allowed'
    cruise = cruises.first()
    context['cruise'] = cruise
    return render(request, 'index.html', context)

def event(request):
    context = {}
    device_id = request.POST.get('device',None)
    device = Device.objects.get(id=int(device_id))
    context['device'] = device
    return render(request, 'event.html', context)
