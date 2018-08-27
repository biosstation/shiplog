from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from eventcapture.models import Cruise, Device, Event, ShipLog

def index(request):
    context = {}
    if request.method == 'POST':
        cruise_id = request.POST.get('cruise', None)
        device_id = request.POST.get('device', None)
        event_id = request.POST.get('event', None)
        shiplog = ShipLog.log_entry(cruise_id, device_id, event_id)
    return render(request, 'index.html', context)

def device(request, device_id):
    context = {}
    device = Device.objects.get(pk=int(device_id))
    if any(device.events.all()):
        return HttpResponseRedirect(reverse('event', args=[device_id]))
    child_devices = Device.objects.filter(parent_device=device_id)
    context['children'] = child_devices
    context['device'] = device
    context['parents'] = device.get_lineage()
    return render(request, 'device.html', context)

def event(request, device_id):
    context = {}
    device = Device.objects.get(pk=int(device_id))
    context['device'] = device
    context['parents'] = device.get_lineage()
    return render(request, 'event.html', context)

def log(request):
    context = {}
    cruise = Cruise.get_active_cruise()
    if cruise:
        context['shiplog'] = ShipLog.get_shiplog(cruise)
    return render(request, 'log.html', context)
