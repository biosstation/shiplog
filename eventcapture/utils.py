import os
from django.conf import settings

def to_csv(cls, cruise, filename):
    if int(cruise.id) > 0:
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
