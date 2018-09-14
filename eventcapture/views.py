import os
import pytz
from datetime import datetime
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.conf import settings
from eventcapture import utils
from eventcapture.models import Cruise, Device, Event, ShipLog, Cast, CastReport, GPS
from eventcapture.tasks import analyze_cast

def index(request):
    context = {}
    cruise = Cruise.get_active_cruise()
    try:
        context['devices'] = cruise.get_parent_devices()
    except AttributeError:
        pass
    if request.method != 'POST':
        return render(request, 'index.html', context)
    cruise_id = request.POST.get('cruise', None)
    device_id = request.POST.get('device', None)
    event_id = request.POST.get('event', None)
    if cruise_id is None or device_id is None or event_id is None:
        return render(request, 'index.html', {'error': 'Unknown cruise, device, or event'})
    cruise = Cruise.objects.get(pk=int(cruise_id))
    device = Device.objects.get(pk=int(device_id))
    event = Event.objects.get(pk=int(event_id))
    gps = GPS()
    gps.save()
    timestamp = datetime.now(pytz.utc)
    shiplog = ShipLog(cruise=cruise, device=device, event=event, gps=gps, timestamp=timestamp)
    shiplog.save()
    if shiplog.event.name == 'Recover':
        if settings.ASYNC:
            analyze_cast.delay(shiplog.id)
        else:
            analyze_cast(shiplog.id)
    context['event_was_logged'] = True
    return render(request, 'index.html', context)

def device(request, device_id):
    context = {}
    device = Device.objects.get(pk=int(device_id))
    if any(device.events.all()):
        return HttpResponseRedirect(reverse('event', args=[device_id]))
    cruise = Cruise.get_active_cruise()
    context['children'] = device.get_child_devices(cruise)
    context['device'] = device
    context['parents'] = device.get_lineage()
    return render(request, 'device.html', context)

def event(request, device_id):
    context = {}
    device = Device.objects.get(pk=int(device_id))
    context['device'] = device
    context['parents'] = device.get_lineage()
    return render(request, 'event.html', context)

def download(request, log, cruise_id):
    cruise = Cruise.objects.get(pk=cruise_id)
    if log == 'eventlog':
        csv_path = utils.to_csv(ShipLog, cruise, settings.EVENT_LOG_FILENAME)
    elif log == 'wirelog':
        csv_path = utils.to_csv(Cast, cruise, settings.WIRE_LOG_FILENAME)
    else:
        raise ValueError('Unknown log type')
    with open(csv_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='text/csv')
        response['Content-Disposition'] = 'inline; filename=' + os.path.basename(csv_path)
        return response

def eventlog(request):
    cruise = Cruise.get_active_cruise()
    if not cruise:
        return render(request, 'eventlog.html')
    context = {}
    context['log'] = ShipLog.get_log(cruise)
    if request.method != 'POST':
        return render(request, 'eventlog.html', context)
    action = request.POST.get('action', None)
    if action == 'download':
        return HttpResponseRedirect(reverse('download', args=['eventlog', cruise.id]))

def wirelog(request):
    cruise = Cruise.get_active_cruise()
    if not cruise:
        return render(request, 'wirelog.html')
    context = {}
    context['log'] = CastReport.get_log(cruise)
    if request.method != 'POST':
        return render(request, 'wirelog.html', context)
    action = request.POST.get('action', None)
    if action == 'download':
        return HttpResponseRedirect(reverse('download', args=['wirelog', cruise.id]))

