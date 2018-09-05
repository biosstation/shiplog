import os
import pytz
import ntpath
import pandas as pd
from glob import glob
from datetime import datetime
from django.db import models
from django.conf import settings


class Event(models.Model):
    name = models.CharField(
        max_length=25,
        unique=True
    )

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

    def __str__(self):
        return self.name

class Wire(models.Model):
    name = models.CharField(max_length=30)
    serial_number = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return '{} ({})'.format(self.name, self.serial_number)

class Config(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    wire = models.ForeignKey(Wire, on_delete=models.CASCADE, null=True, blank=True)
    WINCH_CHOICES = (
        (0, ''),
        (1, '1'),
        (2, '2'),
        (3, '3'),
    )
    winch = models.IntegerField(choices=WINCH_CHOICES)

    def __str__(self):
        if self.winch:
            return '{} on winch #{}'.format(self.device, self.winch)
        return '{} not on a winch'.format(self.device)

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
    config = models.ManyToManyField(
        Config,
        default=None,
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
        return '{}°{}'', {}°{}'''.format(self.latitude_degree, self.latitude_minute, self.longitude_degree, self.longitude_minute)

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
    def find_deployment(cls, recovery):
        """Given a recover event, find the related deploy event"""
        same_cruise = models.Q(cruise=recovery.cruise)
        same_device = models.Q(device=recovery.device)
        deploy_event = models.Q(event__name='Deploy')
        deployments = cls.objects.filter(same_cruise & same_device & deploy_event)
        deployment = deployments.order_by('timestamp').last()
        return deployment

    @classmethod
    def log_entry(cls, cruise, device, event):
        gps = GPS()
        gps.save()
        right_now = datetime.now(pytz.utc)
        shiplog = cls(cruise=cruise, device=device, event=event, gps=gps, timestamp=right_now)
        shiplog.save()
        if event.name == 'Recover':
            deployment = cls.find_deployment(shiplog)
            cast = Cast(deployment=deployment, recovery=shiplog)
            cast.save()

    @classmethod
    def get_log(cls, cruise_id):
        return cls.objects.filter(cruise_id=cruise_id)

    @classmethod
    def get_all_logs(cls):
        return cls.objects.all()

    @classmethod
    def _to_df(cls, log):
        columns = list(log.values('timestamp', 'device_id', 'event_id', 'gps'))
        df = pd.DataFrame(columns)
        df['device_id'] = df['device_id'].apply(lambda x: Device.objects.get(pk=x))
        df['event_id'] = df['event_id'].apply(lambda x: Event.objects.get(pk=x))
        df['gps'] = df['gps'].apply(lambda x: GPS.objects.get(pk=x))
        df = df.set_index('timestamp')
        df = df.rename(columns={'device_id': 'device', 'event_id': 'event'})
        return df
    
    def __str__(self):
        return '{:%Y-%m-%d %H:%M:%S}: {} - {} {}'.format(self.timestamp, self.cruise, self.device, self.event)

class CastReport(models.Model):
    max_tension = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, default=None)
    max_payout = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, default=None)
    max_speed = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, default=None)

    def get_winch_data(self, cast):
        deploy_date = cast.deployment.timestamp.date()
        recover_date = cast.recovery.timestamp.date()
        device_id = cast.recovery.device.id
        winch_number = cast.recovery.cruise.config.get(device__id=device_id).winch
        
        # TODO: put some of these in settings
        winch_cols = [2, 3, 4]
        usecols = [0, 1]
        usecols.extend([a + 3 * (winch_number - 1) for a in winch_cols])
        names = ['Seconds', 'Date', 'Tension', 'Speed', 'Payout']
        skiprows = [0, 1, 2, 3, 4, 5, 6, 7, 9]
        winch_data = []
        for f in glob(settings.WINCH_DATAFILE_PATH):
            winch_date = datetime.strptime(ntpath.basename(f), '%Y-%m-%d %H-%M-%S WinchDAC.csv').date()
            if deploy_date <= winch_date and winch_date <= recover_date:
                df = pd.read_csv(f, skiprows=skiprows, usecols=usecols)
                df['Clock'] = pd.to_datetime(df['Clock'], format='%m/%d/%Y %I:%M:%S %p', utc=True)
                df.columns = names
                winch_data.append(df)
        winch_data = pd.concat(winch_data)
        deploy_time = cast.deployment.timestamp
        recover_time = cast.recovery.timestamp
        cast_winch_data = winch_data[((deploy_time <= winch_data['Date']) & (winch_data['Date'] <= recover_time))]
        return cast_winch_data 

    def set_cast_report(self, df):
        if not df.empty:
            self.max_tension = df['Tension'].max() # in lbs
            self.max_payout = df['Payout'].max()  # in meters
            self.max_speed = df['Speed'].max()   # in meters per minute

    def save(self, *args, **kwargs):
        cast = kwargs.get('cast')
        df = self.get_winch_data(cast)
        self.set_cast_report(df)
        super().save()
    
class Cast(models.Model):
    cruise = models.ForeignKey(
        'Cruise',
        on_delete=models.CASCADE,
    )
    deployment = models.ForeignKey(
        'ShipLog',
        on_delete=models.CASCADE,
        related_name='deploy_event',
    )
    recovery = models.ForeignKey(
        'ShipLog',
        on_delete=models.CASCADE,
        related_name='recover_event',
    )
    cast_report = models.ForeignKey(
        'CastReport',
        on_delete=models.CASCADE,
    )
    
    @classmethod
    def _to_df(cls, log):
        columns = list(log.values('deployment', 'recovery', 'cast_report'))
        df = pd.DataFrame(columns)
        df['Deployed'] = df['deployment'].apply(lambda x: ShipLog.objects.get(pk=x).timestamp)
        df['Recovered'] = df['recovery'].apply(lambda x: ShipLog.objects.get(pk=x).timestamp)
        df['Device'] = df['recovery'].apply(lambda x: ShipLog.objects.get(pk=x).device)
        df['Max Tension'] = df['cast_report'].apply(lambda x: CastReport.objects.get(pk=x).max_tension)
        df['Max Speed'] = df['cast_report'].apply(lambda x: CastReport.objects.get(pk=x).max_tension)
        df['Max Payout'] = df['cast_report'].apply(lambda x: CastReport.objects.get(pk=x).max_tension)
        df = df.drop(['cast_report', 'deployment', 'recovery'], axis=1)
        return df
    
    @classmethod
    def get_log(cls, cruise_id):
        return cls.objects.filter(cruise_id=cruise_id)

    def save(self, *args, **kwargs):
        cast_report = CastReport()
        cast_report.save(cast=self)
        self.cast_report = cast_report
        self.cruise = self.recovery.cruise
        super().save(*args, **kwargs)

    def __str__(self):
        return '{cruise} {device} cast recovered at {ts:%H:%M} on {ts:%Y-%m-%d}'.format(cruise=self.recovery.cruise.name, device=self.recovery.device.name, ts=self.recovery.timestamp)

