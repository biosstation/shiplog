import os
from eventcapture.models import Cruise
from django.conf import settings

def to_csv(cls, cruise_id, filename):
    cruise_id = int(cruise_id)
    if cruise_id > 0:
        cruise = Cruise.objects.get(pk=cruise_id)
        cruise_number = cruise.number
        log = cls.get_log(cruise)
    else:
        cruise_number = 'All'
        log = cls.get_all_logs()
    filename = filename.format(cruise_number)
    df = cls._to_df(log)
    outfile = os.path.join(settings.MEDIA_ROOT, filename)
    df.to_csv(outfile)
    return outfile
