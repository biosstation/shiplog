import os
import pandas as pd
from django.conf import settings
from eventcapture.models import Device, Event

def _to_df(log):
    df = pd.DataFrame(list(log.values('timestamp', 'device_id', 'event_id')))
    events = Event.event_dict()
    devices = Device.device_dict()
    df = df.set_index('timestamp')
    df = df.replace({'device_id': devices, 'event_id': events})
    df = df.rename(columns={'device_id': 'device', 'event_id': 'event'})
    return df

def to_csv(log, cruise):
    df = _to_df(log)
    filename = settings.EVENT_LOG_FILENAME.format(cruise.number)
    outfile = os.path.join(settings.MEDIA_ROOT, filename)
    df.to_csv(outfile)
    return outfile
