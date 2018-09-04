import pytz
import pandas as pd
from django.db import models
from django.conf import settings
from datetime import datetime


class Event(models.Model):
    name = models.CharField(
        max_length=25,
        unique=True
    )

    @classmethod
    def event_dict(cls):
        return {val['id']: val['name'] for val in cls.objects.values()}

    def __str__(self):
        return self.name

class Device(models.Model):
    name = models.CharField(
        max_length=25,
        unique=True
    )
    parent_device = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text='A parent device for a ZooPlankton Tow is a Plankton Tow for example. Parent devices should not have any events associated with them.'
    )
    events = models.ManyToManyField(
        Event,
        null=True,
        blank=True
    )

    def get_lineage(self):
        lineage = []
        device = self
        while True:
            try:
                device = device.parent_device
            except AttributeError:
                break
            if device is None:
                break
            lineage.insert(0, device)
        return lineage

    @classmethod
    def device_dict(cls):
        return {val['id']: val['name'] for val in cls.objects.values()}

    def __str__(self):
        return self.name

class Cruise(models.Model):
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    name = models.CharField(
        max_length=50,
        unique=True
    )
    number = models.CharField(
        max_length=16,
        unique=True
    )
    devices = models.ManyToManyField(
        Device,
        default=None,
        limit_choices_to={'parent_device': None} #TODO: only showing parent devices
    )

    def __str__(self):
        return '{} ({})'.format(self.name, self.number)

    @classmethod
    def get_active_cruise(cls):
        right_now = datetime.now(pytz.utc)
        start_past = models.Q(start_date__lte=right_now)
        end_null = models.Q(end_date=None)
        end_future = models.Q(end_date__gte=right_now)
        cruises = cls.objects.filter(start_past & (end_null | end_future))
        if len(cruises) > 1:
            raise ValueError('Overlapping cruises not allowed')
        return cruises.first()

class GPS(models.Model):
    latitude_degree = models.IntegerField()
    longitude_degree = models.IntegerField()
    latitude_minute = models.DecimalField(max_digits=8, decimal_places=4)
    longitude_minute = models.DecimalField(max_digits=8, decimal_places=4)

    def save(self, *args, **kwargs):
        df = self._read_gps_file()
        gps = self._get_latest_gps_record(df)
        self.latitude_degree = gps.iloc[0]['Lat_deg']
        self.longitude_degree = gps.iloc[0]['Lon_deg']
        self.latitude_minute = gps.iloc[0]['Lat_min']
        self.longitude_minute = gps.iloc[0]['Lon_min']
        super().save(*args, **kwargs)

    def _read_gps_file(self):
        dtype = {'Lat_deg':int, 'Lat_min':float, 'Lon_deg':int, 'Lon_min':float}
        df = pd.read_csv(settings.GPS_FILENAME, skiprows=[0, 2, 3], usecols=dtype.keys(), header=0, dtype=dtype)
        return df

    def _get_latest_gps_record(self, df):
        return df.tail(1)

    def __str__(self):
        return '{}.{}, {}.{}'.format(self.latitude_degree, self.latitude_minute, self.longitude_degree, self.longitude_minute)

class ShipLog(models.Model):
    cruise = models.ForeignKey(
        'Cruise',
        on_delete=models.CASCADE,
    )
    device = models.ForeignKey(
        'Device',
        on_delete=models.CASCADE,
    )
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
    )
    gps = models.ForeignKey(
        'GPS',
        on_delete=models.CASCADE,
    )
    timestamp = models.DateTimeField()

    @classmethod
    def log_entry(cls, cruise, device, event):
        gps = GPS()
        gps.save()
        right_now = datetime.now(pytz.utc)
        shiplog = cls(cruise=cruise, device=device, event=event, gps=gps, timestamp=right_now)
        shiplog.save()

    @classmethod
    def get_log(cls, cruise_id):
        return cls.objects.filter(cruise_id=cruise_id)

    @classmethod
    def get_all_logs(cls):
        return cls.objects.all()

    def __str__(self):
        return '{:%Y-%m-%d %H:%M:%S}: {} - {} {}'.format(self.timestamp, self.cruise, self.device, self.event)
