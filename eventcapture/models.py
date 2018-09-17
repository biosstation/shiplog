from __future__ import absolute_import, unicode_literals
import os
import pytz
import ntpath
import numpy as np
import pandas as pd
from glob import glob
from datetime import datetime, timedelta
from django.db import models
from django.conf import settings
from celery import shared_task

@shared_task
def analyze_cast(recovery_id):
    recovery = ShipLog.objects.get(pk=int(recovery_id))
    config = recovery.find_config()
    deployment = recovery.find_deployment()
    cast = Cast(deployment=deployment, recovery=recovery, config=config)
    cast.save()
    return 'Saved cast with id of {}'.format(cast.id)

def config_device_choices():
    devices = Device.objects.filter(events__isnull=False)
    return {'id__in': devices}

def get_default_cruise():
    return Cruise.get_active_cruise()

def get_default_gps():
    gps = GPS()
    gps.save(timestamp=None)
    return gps

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
        blank=True
    )

    def get_child_devices(self, cruise):
        """Get child devices for this cruise only"""
        return [config.device for config in cruise.config.filter(device__parent_device=self.id)]

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
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        limit_choices_to=config_device_choices,
    )
    wire = models.ForeignKey(Wire, on_delete=models.CASCADE, null=True, blank=True)
    winch = models.IntegerField(
        choices=settings.WINCH_CHOICES,
        default=0,
        help_text='The winch selection is only used if it is part of the LCI-90i Winch Monitoring System (aka winches 1, 2, and 3).  If the winch is not instrumented with a tensiometer or meter wheel, then skip the winch selection.'
    )

    def __str__(self):
        winch = 'not on a winch'
        wire = 'not on a wire'
        if self.winch:
            winch = 'on winch #{}'.format(self.winch)
        if self.wire:
            wire = 'on {}'.format(self.wire)
        return '{} {} {}'.format(self.device, winch, wire)

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
        ended = 'ENDED' if self.has_cruise_ended() else 'FUTURE' if self.has_cruise_started() else 'ACTIVE'
        return '{} - {} ({})'.format(ended, self.name, self.number)

    def has_cruise_ended(self):
        right_now = datetime.now(pytz.utc)
        return self.end_date is not None and self.end_date < right_now

    def has_cruise_started(self):
        right_now = datetime.now(pytz.utc)
        return self.start_date is not None and self.start_date > right_now

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

    def get_parent_devices(self):
        """Unique list of highest-level parents devices"""
        no_parents = [config.device for config in self.config.all().filter(device__parent_device__isnull=True)]
        has_parent = self.config.all().filter(device__parent_device__isnull=False)
        for config in has_parent:
            parent = config.device.parent_device
            while parent.parent_device is not None:
                parent = parent.parent_device
            if parent not in no_parents:
                no_parents.append(parent)
        return no_parents

class GPS(models.Model):
    latitude_degree = models.IntegerField(default=0)
    longitude_degree = models.IntegerField(default=0)
    latitude_minute = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    longitude_minute = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    def save(self, timestamp=None, *args, **kwargs):
        df = self._read_gps_file()
        try:
            gps = self._get_gps_record(df, timestamp)
            self.latitude_degree = gps['Lat_deg']
            self.longitude_degree = gps['Lon_deg']
            self.latitude_minute = gps['Lat_min']
            self.longitude_minute = gps['Lon_min']
        except TypeError:
            pass
        super().save(*args, **kwargs)

    def _read_gps_file(self):
        dtype = {'TIMESTAMP':str, 'Lat_deg':float, 'Lat_min':float, 'Lon_deg':float, 'Lon_min':float}
        gps_file = settings.GPS_FILENAME
        if not os.path.isfile(gps_file):
            return None
        df = pd.read_csv(gps_file, skiprows=[0, 2, 3], usecols=dtype.keys(), header=0, dtype=dtype, na_values=['NAN'], parse_dates=['TIMESTAMP'], index_col='TIMESTAMP')
        df = df.tz_localize('UTC')
        return df

    def _get_gps_record(self, df, timestamp):
        try:
            row = df.iloc[df.index.get_loc(timestamp, method='nearest', tolerance=pd.Timedelta('30 seconds'))]
        except (AttributeError, KeyError):
            row = None
        return row

    def __str__(self):
        return '{}°{}'', {}°{}'''.format(self.latitude_degree, self.latitude_minute, self.longitude_degree, self.longitude_minute)

class ShipLog(models.Model):
    cruise = models.ForeignKey(
        'Cruise',
        on_delete=models.CASCADE,
        default=get_default_cruise,
    )
    device = models.ForeignKey(
        'Device',
        on_delete=models.CASCADE,
        help_text='Please only choose devices that are configured for the current cruise',
    )
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        help_text='Please only choose events that are configured for the current cruise',
    )
    gps = models.ForeignKey(
        'GPS',
        on_delete=models.CASCADE,
        default=None,
        help_text='The timestamp will be used to find GPS data. If not GPS data is available, 0°0.0, 0°,0.0 will be used',
    )
    timestamp = models.DateTimeField()

    def find_deployment(self):
        """Given a recover event, find the related deploy event. Does not consider if a deployment already has a recovery"""
        same_cruise = models.Q(cruise=self.cruise)
        same_device = models.Q(device=self.device)
        deploy_event = models.Q(event__name='Deploy')
        deployments = ShipLog.objects.filter(same_cruise & same_device & deploy_event)
        deployment = deployments.order_by('timestamp').last()
        return deployment

    def find_config(self):
        configs = self.cruise.config.filter(device__id=self.device.id)
        if len(configs) > 1:
            raise ValueError('More than one of the same device configured for this cruise')
        return configs.first()

    @classmethod
    def get_log(cls, cruise):
        return cls.objects.filter(cruise__id=cruise.id).order_by('timestamp')

    @classmethod
    def get_all_logs(cls):
        return cls.objects.all().order_by('timestamp')

    @classmethod
    def _to_df(cls, log):
        columns = list(log.values('timestamp', 'device_id', 'event_id', 'gps'))
        df = pd.DataFrame(columns)
        df['device_id'] = df['device_id'].apply(lambda x: Device.objects.get(pk=x))
        df['event_id'] = df['event_id'].apply(lambda x: Event.objects.get(pk=x))
        df['Latitude'] = df['gps'].apply(lambda x: "{}°{}'".format(GPS.objects.get(pk=x).latitude_degree, GPS.objects.get(pk=x).latitude_minute))
        df['Longitude'] = df['gps'].apply(lambda x: "{}°{}'".format(GPS.objects.get(pk=x).longitude_degree, GPS.objects.get(pk=x).longitude_minute))
        df['Date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        df['Time'] = df['timestamp'].dt.strftime('%H:%M:%S')
        df = df.drop(['timestamp', 'gps'], axis=1)
        df = df.rename(columns={'device_id': 'Device', 'event_id': 'Event'})
        df = df[['Date', 'Time', 'Device', 'Event', 'Latitude', 'Longitude']]  # reorder columns
        return df

    def save(self, *args, **kwargs):
        # when adding a shiplog in admin, there will be no GPS by default. Use the timestamp to try and find GPS data
        if not hasattr(self, 'gps'):
            gps = GPS()
            gps.save(timestamp=self.timestamp)
            self.gps = gps
        super().save(*args, **kwargs)
        if self.event.name == 'Recover':
            if settings.ASYNC:
                analyze_cast.delay(self.id)
            else:
                analyze_cast(self.id)

    def __str__(self):
        return '{:%Y-%m-%d %H:%M:%S}: {} - {} {}'.format(self.timestamp, self.cruise, self.device, self.event)

class CastReport(models.Model):
    cast = models.ForeignKey('Cast', on_delete=models.CASCADE, null=True)
    max_tension = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, default=None)
    max_payout = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, default=None)
    max_speed = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, default=None)

    @classmethod
    def get_all_logs(cls):
        return cls.objects.all().order_by('cast__recovery__timestamp')

    @classmethod
    def _to_df(cls, log):
        columns = list(log.values('cast', 'max_tension', 'max_speed', 'max_payout'))
        df = pd.DataFrame(columns)
        df['Deployed'] = df['cast'].apply(lambda x: Cast.objects.get(pk=x).deployment.timestamp)
        df['Recovered'] = df['cast'].apply(lambda x: Cast.objects.get(pk=x).recovery.timestamp)
        df['Device'] = df['cast'].apply(lambda x: Cast.objects.get(pk=x).recovery.device)
        df['Wire'] = df['cast'].apply(lambda x: Cast.objects.get(pk=x).config.wire.serial_number)
        df['Winch #'] = df['cast'].apply(lambda x: Cast.objects.get(pk=x).config.winch)
        df = df.drop(['cast'], axis=1)
        df = df.rename(columns={
            'max_tension': 'Max Tension',
            'max_speed': 'Max Speed',
            'max_payout': 'Max Payout',
        })
        df = df[['Deployed', 'Recovered', 'Device', 'Max Tension', 'Max Speed', 'Max Payout', 'Wire', 'Winch #']] # reorder columns
        return df

    @classmethod
    def get_log(cls, cruise):
        has_winch_number = models.Q(cast__config__winch__gt=0)
        this_cruise = models.Q(cast__cruise_id=cruise.id)
        return cls.objects.filter(has_winch_number & this_cruise).order_by('cast__recovery__timestamp')

    def get_winch_data(self):
        deploy_date = self.cast.deployment.timestamp.date()
        recover_date = self.cast.recovery.timestamp.date()
        device_id = self.cast.config.device.id
        winch_number = self.cast.config.winch
        if not winch_number:
            return None

        # TODO: put some of these in settings
        winch_cols = [2, 3, 4]
        usecols = [0, 1]
        usecols.extend([a + 3 * (winch_number - 1) for a in winch_cols])
        names = ['Seconds', 'Date', 'Tension', 'Speed', 'Payout']
        skiprows = [0, 1, 2, 3, 4, 5, 6, 7, 9]
        winch_data = []
        for f in glob(settings.WINCH_DATAFILE_PATH):
            if not os.path.isfile(f):
                continue
            winch_date = datetime.strptime(ntpath.basename(f), '%Y-%m-%d %H-%M-%S WinchDAC.csv').date()
            if deploy_date <= winch_date and winch_date <= recover_date:
                df = pd.read_csv(f, skiprows=skiprows, usecols=usecols)
                df['Clock'] = pd.to_datetime(df['Clock'], format='%m/%d/%Y %I:%M:%S %p')
                df.columns = names
                winch_data.append(df)
        try:
            df = pd.concat(winch_data)
        except ValueError:
            return None # winch data was not found
        return df

    def subset_winch_data(self, df):
        deploy_time = self.cast.deployment.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        recover_time= self.cast.recovery.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        subset = df[(deploy_time <= df['Date']) & (df['Date'] <= recover_time)]
        return subset

    def set_cast_report(self, df):
        try:
            df = self.subset_winch_data(df)
            if not df.empty and not df['Tension'].isnull().all():
                self.max_tension = float(df['Tension'].max()) # in lbs
                self.max_payout = float(df['Payout'].max()) # in meters
                self.max_speed = float(df['Speed'].max()) # in meters per minute
        except (AttributeError, TypeError):
            pass

    def save(self, *args, **kwargs):
        df = self.get_winch_data()
        self.set_cast_report(df)
        super().save(*args, **kwargs)

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
    config = models.ForeignKey(
        'Config',
        on_delete=models.CASCADE
    )

    @classmethod
    def get_log(cls, cruise):
        return cls.objects.filter(cruise__id=cruise.id).order_by('recovery__timestamp')

    def save(self, *args, **kwargs):
        self.cruise = self.recovery.cruise
        super().save(*args, **kwargs)
        cast_report = CastReport(cast=self)
        cast_report.save()

    def __str__(self):
        return '{cruise} {device} cast recovered at {ts:%H:%M} on {ts:%Y-%m-%d}'.format(cruise=self.recovery.cruise.name, device=self.recovery.device.name, ts=self.recovery.timestamp)

class WireReport(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    wire = models.ForeignKey(Wire, on_delete=models.CASCADE, default=None)

    def _make_df(self, casts):
        columns = list(casts.values('cast', 'max_tension', 'max_speed', 'max_payout'))
        df = pd.DataFrame(columns)
        df['Date'] = df['cast'].apply(lambda x: Cast.objects.get(pk=x).recovery.timestamp)
        df = df.rename(columns={
            'max_tension': 'Max Tension',
            'max_speed': 'Max Speed',
            'max_payout': 'Max Payout',
        })
        df = df.drop(['cast'], axis=1)
        df = df[['Date', 'Max Tension', 'Max Speed', 'Max Payout']] # reorder columns
        return df

    def _save_wire_report(self, casts):
        df = self._make_df(casts)
        filename = settings.WIRE_REPORT_FILENAME.format(self.wire.serial_number)
        root_path = os.path.dirname(__file__)
        outfile = os.path.join(root_path, os.pardir, 'media', filename)
        df.to_csv(outfile)

    def run_wire_report(self):
        casts = self._get_relevant_casts()
        self._save_wire_report(casts)
        return casts

    def _get_relevant_casts(self):
        start_date = self.start_date
        end_date = self.end_date
        end_date += timedelta(days=1)  # increment day to get casts through the end of the day

        # query criteria
        deployments_after = models.Q(cast__deployment__timestamp__gte=start_date)
        recoveries_before = models.Q(cast__recovery__timestamp__lte=end_date)
        specific_wire = models.Q(cast__config__wire__serial_number=self.wire.serial_number)

        # query and pull out casts
        casts = CastReport.objects.filter(deployments_after & recoveries_before & specific_wire).order_by('cast__recovery__timestamp')
        return casts

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return 'Wire Report for {} from {} to {}'.format(self.wire.serial_number, self.start_date, self.end_date)
