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

class ShipLogForm(forms.ModelForm):
    class Meta:
        model = ShipLog
        exclude = []

class ShipLogAdmin(admin.ModelAdmin):
    form = ShipLogForm
    list_display = ('timestamp', 'event', 'device', 'cruise', )
    list_filter = (CruiseListFilter, )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['cruise_id'] = request.GET.get('cruises', 0)
        return super().changelist_view(request, extra_context=extra_context)

class CruiseForm(forms.ModelForm):
    class Meta:
        model = Cruise
        exclude = []

class CruiseAdmin(admin.ModelAdmin):
    form = CruiseForm

admin.site.register(Device)
admin.site.register(Event)
admin.site.register(Cruise, CruiseAdmin)
admin.site.register(ShipLog, ShipLogAdmin)

