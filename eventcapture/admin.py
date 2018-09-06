import pytz
from datetime import datetime
from django import forms
from django.http import HttpResponseRedirect
from django.contrib import admin
from .models import Cruise, Device, Event, ShipLog, Cast, CastReport, Wire, Config

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
        exclude = ['end_date']

class CruiseAdmin(admin.ModelAdmin):
    form = CruiseForm
    change_form_template = None
    readonly_fields = ['end_date']

    def get_form(self, request, obj=None, **kwargs):
        self.change_form_template = None
        self.readonly_fields = ['end_date']
        if obj is None:
            return super().get_form(request, obj, **kwargs)
        if not obj.has_cruise_ended():
            self.change_form_template = 'admin/eventcapture/cruise/end_cruise_change_form.html'
        else:
            self.readonly_fields = ['start_date', 'end_date', 'name', 'number', 'config']
        return super().get_form(request, obj, **kwargs)

    def response_change(self, request, obj):
        if "end_cruise" in request.POST:
            obj.end_date = datetime.now(pytz.utc)
            obj.save()
            self.message_user(request, "This cruise is now over")
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)


admin.site.register(Device)
admin.site.register(Event)
admin.site.register(Cruise, CruiseAdmin)
admin.site.register(ShipLog, ShipLogAdmin)
admin.site.register(Wire)
admin.site.register(Config)

