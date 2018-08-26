from django.contrib import admin
from .models import Cruise, Device, Event, ShipLog

admin.site.site_header = 'ShipLog Admin Site'
admin.site.index_title = 'ShipLog administration'

admin.site.register(Cruise)
admin.site.register(Device)
admin.site.register(Event)
admin.site.register(ShipLog)
