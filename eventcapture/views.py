from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from eventcapture.models import Device

def index(request):
    context = {}
    if request.method == 'POST':
        device = request.POST.get('device', None)
        event = request.POST.get('event', None)
        # TODO log event
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
    return render(request, 'log.html')
