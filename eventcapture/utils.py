import os
from django.conf import settings
from eventcapture.models import Cruise

def to_csv(cls, cruise_id, filename):
    try:
        cruise = Cruise.objects.get(pk=cruise_id)
    except Cruise.DoesNotExist:
        pass
    if int(cruise_id) > 0:
        cruise_number = cruise.number
        log = cls.get_log(cruise)
    else:
        cruise_number = 'All'
        log = cls.get_all_logs()
    filename = filename.format(cruise_number)
    df = cls._to_df(log)
    root_path = os.path.dirname(__file__)
    outfile = os.path.join(root_path, os.pardir, 'media', filename)
    df.to_csv(outfile)
    return outfile

