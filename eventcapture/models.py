import os
import pytz
import ntpath
import numpy as np
import pandas as pd
from glob import glob
from datetime import datetime, timedelta
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
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        limit_choices_to={'events':not None} # only show devices with events
    )
    wire = models.ForeignKey(Wire, on_delete=models.CASCADE, null=True, blank=True)
    winch = models.IntegerField(choices=settings.WINCH_CHOICES)

    def __str__(self):
        winch = 'not on a winch'
        wire = 'not on a wire'
        if self.winch:
            winch = 'on winch #{}'.format(self.winch)
        if self.wire:
            wire = 'on {}'.format(self.wire.name)
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
    parent_devices = models.ManyToManyField(
        Device,
        null=True,
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

    def set_parent_devices(self):
        no_parents = [config.device for config in self.config.all().filter(device__parent_device__isnull=True)]
        has_parent = self.config.all().filter(device__parent_device__isnull=False)
        for config in has_parent:
            parent = config.device.parent_device
            while parent.parent_device is not None:
                parent = parent.parent_device
            if parent not in no_parents:
                no_parents.append(parent)
        self.parent_devices.add(*no_parents)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.set_parent_devices()
        super().save(*args, **kwargs)

class GPS(models.Model):
    latitude_degree = models.IntegerField(default=0)
    longitude_degree = models.IntegerField(default=0)
    latitude_minute = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    longitude_minute = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    def save(self, *args, **kwargs):
        df = self._read_gps_file()
        try:
            gps = self._get_latest_gps_record(df)
            self.latitude_degree = gps.iloc[0]['Lat_deg']
            self.longitude_degree = gps.iloc[0]['Lon_deg']
            self.latitude_minute = gps.iloc[0]['Lat_min']
            self.longitude_minute = gps.iloc[0]['Lon_min']
        except AttributeError:
            pass
        super().save(*args, **kwargs)

    def _read_gps_file(self):
        dtype = {'Lat_deg':float, 'Lat_min':float, 'Lon_deg':float, 'Lon_min':float}
        gps_file = settings.GPS_FILENAME
        if os.path.isfile(gps_file):
            return pd.read_csv(gps_file, skiprows=[0, 2, 3], usecols=dtype.keys(), header=0, dtype=dtype, na_values=['NAN'])
        return None

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

    def find_deployment(self):
        """Given a recover event, find the related deploy event"""
        same_cruise = models.Q(cruise=self.cruise)
        same_device = models.Q(device=self.device)
        deploy_event = models.Q(event__name='Deploy')
        deployments = ShipLog.objects.filter(same_cruise & same_device & deploy_event)
        deployment = deployments.order_by('timestamp').last()
        return deployment

    def save(self, *args, **kwargs):
        gps = GPS()
        gps.save()
        self.gps = gps
        self.timestamp = datetime.now(pytz.utc)
        super().save(*args, **kwargs)
        if self.event.name == 'Recover':
            deployment = self.find_deployment()
            cast = Cast(deployment=deployment, recovery=self)
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
        df['Latitude'] = df['gps'].apply(lambda x: "{}°{}'".format(GPS.objects.get(pk=x).latitude_degree, GPS.objects.get(pk=x).latitude_minute))
        df['Longitude'] = df['gps'].apply(lambda x: "{}°{}'".format(GPS.objects.get(pk=x).longitude_degree, GPS.objects.get(pk=x).longitude_minute))
        df['Date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        df['Time'] = df['timestamp'].dt.strftime('%H:%M:%S')
        df = df.drop(['timestamp', 'gps'], axis=1)
        df = df.rename(columns={'device_id': 'Device', 'event_id': 'Event'})
        df = df[['Date', 'Time', 'Device', 'Event', 'Latitude', 'Longitude']]  # reorder columns
        return df

    def __str__(self):
        return '{:%Y-%m-%d %H:%M:%S}: {} - {} {}'.format(self.timestamp, self.cruise, self.device, self.event)

class CastReport(models.Model):
    cast = models.ForeignKey('Cast', on_delete=models.CASCADE, null=True)
    max_tension = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, default=None)
    max_payout = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, default=None)
    max_speed = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, default=None)
    wire = models.ForeignKey(Wire, on_delete=models.CASCADE, null=True, blank=True)
    winch_number = models.IntegerField(choices=settings.WINCH_CHOICES, default=None)

    @classmethod
    def get_log(cls, cruise_id):
        has_winch_number = models.Q(winch_number__gt=0)
        this_cruise = models.Q(cast__cruise_id=cruise_id)
        return cls.objects.filter(has_winch_number & this_cruise)

    def get_winch_data(self):
        deploy_date = self.cast.deployment.timestamp.date()
        recover_date = self.cast.recovery.timestamp.date()
        device_id = self.cast.recovery.device.id
        winch_number = self.cast.recovery.cruise.config.get(device__id=device_id).winch
        self.winch_number = winch_number
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
                #df = df.set_index('Date')
                winch_data.append(df)
        try:
            df = pd.concat(winch_data)
            #df = df.tz_localize(tz='UTC')
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
            if not df.empty:
                self.max_tension = df['Tension'].max() # in lbs
                self.max_payout = df['Payout'].max()  # in meters
                self.max_speed = df['Speed'].max()   # in meters per minute
        except (AttributeError, TypeError):
            pass

    def save(self, *args, **kwargs):
        self.wire = self.cast.recovery.cruise.config.get(device__id=self.cast.recovery.device.id).wire
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
        df['Wire'] = df['cast_report'].apply(lambda x: CastReport.objects.get(pk=x).wire.serial_number)
        df['Winch #'] = df['cast_report'].apply(lambda x: CastReport.objects.get(pk=x).winch_number)
        df = df.drop(['cast_report', 'deployment', 'recovery'], axis=1)
        return df

    @classmethod
    def get_log(cls, cruise_id):
        return cls.objects.filter(cruise_id=cruise_id)

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

    def get_relevant_casts(self):
        start_date = self.start_date
        end_date = self.end_date
        end_date += timedelta(days=1)  # increment day to get casts through the end of the day

        # query criteria
        deployments_after = models.Q(deployment__timestamp__gte=start_date)
        recoveries_before = models.Q(recovery__timestamp__lte=end_date)
        specific_wire = models.Q(cast_report__wire__serial_number=self.wire.serial_number)

        # query and pull out casts reports
        casts = Cast.objects.filter(deployments_after & recoveries_before & specific_wire)
        return casts

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return 'Wire Report for {} from {} to {}'.format(self.wire.serial_number, self.start_date, self.end_date)
