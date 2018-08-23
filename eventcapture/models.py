import pytz
from django.db import models
from datetime import datetime

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
        on_delete=models.CASCADE
    )
    events = models.ManyToManyField(Event)

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
        default=None
    )

    def __str__(self):
        return '{} ({})'.format(self.name, self.number)

    @classmethod
    def get_active_cruises(cls):
        right_now = datetime.now(pytz.utc)
        start_past = models.Q(start_date__lte=right_now)
        end_null = models.Q(end_date=None)
        end_future = models.Q(end_date__gte=right_now)
        cruise = cls.objects.filter(start_past & (end_null | end_future))
        return cruise

    def get_devices(self):
        devices_ids = self.devices.all()
        return devices

    @classmethod
    def get_devices_for_cruise(cls, cruise):
        devices = [cd.device for cd in CruiseDevice.objects.filter(cruise=cruise.id)]
        return devices

