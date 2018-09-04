import os
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from eventcapture.models import Cruise, Device, Event, ShipLog
from eventcapture import utils

def index(request):
    if request.method != 'POST':
        return render(request, 'index.html')
    cruise_id = request.POST.get('cruise', None)
    device_id = request.POST.get('device', None)
    event_id = request.POST.get('event', None)
    if cruise_id is None or device_id is None or event_id is None:
        return render(request, 'index.html', {'error': 'Unknown cruise, device, or event'})
    cruise = Cruise.objects.get(pk=int(cruise_id))
    device = Device.objects.get(pk=int(device_id))
    event = Event.objects.get(pk=int(event_id))
    ShipLog.log_entry(cruise, device, event)
    context = {
        'success': True,
        'device': device,
        'event': event
    }
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

def download(request, cruise_id):
    csv_path = utils.to_csv(cruise_id)
    with open(csv_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='text/csv')
        response['Content-Disposition'] = 'inline; filename=' + os.path.basename(csv_path)
        return response

def log(request):
    cruise = Cruise.get_active_cruise()
    if not cruise:
        return render(request, 'log.html')
    context = {}
    context['log'] = ShipLog.get_log(cruise)
    if request.method != 'POST':
        return render(request, 'log.html', context)
    action = request.POST.get('action', None)
    if action == 'download':
        return HttpResponseRedirect(reverse('download', args=[cruise.id]))

