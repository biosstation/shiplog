import pytz
from datetime import datetime
from django import forms
from django.contrib import admin
from .models import Cruise, Device, Event, ShipLog

admin.site.site_header = 'ShipLog Admin Site'
admin.site.index_title = 'ShipLog administration'

class CruiseListFilter(admin.SimpleListFilter):

    """
    This filter will always return a subset of the instances in a Model, either filtering by the
    user choice or by a default value.
    """
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'cruise'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'cruises'
    default_value = None

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        list_of_cruises = []
        queryset = Cruise.objects.all()
        for cruise in queryset:
            list_of_cruises.append(
                (str(cruise.id), cruise.name)
            )
        return list_of_cruises

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value to decide how to filter the queryset.
        if self.value():
            return queryset.filter(cruise_id=self.value())
        return queryset

    def value(self):
        """
        Overriding this method will allow us to always have a default value.
        """
        value = super(CruiseListFilter, self).value()
        if value is None:
            if self.default_value is None:
                # If there is at least one Cruise, return the first by latest start date. Otherwise, None.
                first_cruise = Cruise.objects.order_by('start_date').last()
                value = None if first_cruise is None else first_cruise.id
                self.default_value = value
            else:
                value = self.default_value
        return str(value)

class ShipLogForm(forms.ModelForm):
    class Meta:
        model = ShipLog
        exclude = []

class ShipLogAdmin(admin.ModelAdmin):
    form = ShipLogForm
    list_display = ('device', 'event', 'timestamp', )
    list_filter = (CruiseListFilter, )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        form = self.form()
        if form.instance.has_cruise_ended():
            # disable changing past cruise logs
            self.list_display_links = None

class CruiseForm(forms.ModelForm):
    class Meta:
        model = Cruise
        exclude = []

    def has_cruise_ended(self):
        right_now = datetime.now(pytz.utc)
        end_date = self.instance.end_date
        return end_date is not None and end_date < right_now

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if not instance or not instance.id:
            return
        if not self.has_cruise_ended():
            return
        # if the cruise has not ended, user can still edit
        for field in self.fields:
            self.fields[field].disabled = True

class CruiseAdmin(admin.ModelAdmin):
    form = CruiseForm

admin.site.register(Device)
admin.site.register(Event)
admin.site.register(Cruise, CruiseAdmin)
admin.site.register(ShipLog, ShipLogAdmin)

