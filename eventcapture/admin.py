import pytz
from datetime import datetime
from django import forms
from django.http import HttpResponseRedirect
from django.contrib import admin
from django.shortcuts import render
from .models import Cruise, Device, Event, ShipLog, CastReport, WireReport, Wire, Config, GPS

admin.site.site_header = 'ShipLog Admin Site'
admin.site.index_title = 'ShipLog administration'

class CastReportCruiseListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'cruise'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'cruises'

    def lookups(self, request, model_admin):
        list_of_cruises = []
        queryset = Cruise.objects.all()
        for cruise in queryset:
            list_of_cruises.append(
                (str(cruise.id), cruise.name)
            )
        return list_of_cruises

    def queryset(self, request, queryset):
        # Compare the requested value to decide how to filter the queryset.
        if self.value():
            return queryset.filter(cast__cruise_id=self.value())

class ShipLogCruiseListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'cruise'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'cruises'

    def lookups(self, request, model_admin):
        list_of_cruises = []
        queryset = Cruise.objects.all()
        for cruise in queryset:
            list_of_cruises.append(
                (str(cruise.id), cruise.name)
            )
        return list_of_cruises

    def queryset(self, request, queryset):
        # Compare the requested value to decide how to filter the queryset.
        if self.value():
            return queryset.filter(cruise_id=self.value())

class CastReportForm(forms.ModelForm):
    class Meta:
        model = CastReport
        exclude = []

class CastReportAdmin(admin.ModelAdmin):
    form = CastReportForm
    list_display = ('cast', 'max_tension', 'max_speed', 'max_payout', )
    list_filter = (CastReportCruiseListFilter, )

    def get_form(self, request, obj=None, **kwargs):
        self.readonly_fields = ['cast', 'max_tension', 'max_payout', 'max_speed']
        return super().get_form(request, obj, **kwargs)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['cruise_id'] = request.GET.get('cruises', 0)
        return super().changelist_view(request, extra_context=extra_context)

class ShipLogForm(forms.ModelForm):
    class Meta:
        model = ShipLog
        exclude = []

class ShipLogAdmin(admin.ModelAdmin):
    form = ShipLogForm
    list_display = ('timestamp', 'event', 'device', 'cruise', )
    list_filter = (ShipLogCruiseListFilter, )

    def get_form(self, request, obj=None, **kwargs):
        # shiplog entries are read only by default
        self.readonly_fields = ['cruise', 'device', 'event', 'gps', 'timestamp']
        if not obj:
            # adding a new shiplog entry from the admin panel is okay for the current cruise
            self.readonly_fields = ['cruise', 'gps']
        return super().get_form(request, obj, **kwargs)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['cruise_id'] = request.GET.get('cruises', 0)
        return super().changelist_view(request, extra_context=extra_context)

    def render_change_form(self, request, context, *args, **kwargs):
        self.change_form_template = 'admin/eventcapture/shiplog/change_form_help_text.html'
        extra = {
            'help_text': 'WARNING: Do not click the save button unless you know what you are doing!'
        }
        context.update(extra)
        return super().render_change_form(request, context, *args, **kwargs)

class CruiseForm(forms.ModelForm):
    class Meta:
        model = Cruise
        exclude = ['end_date', 'parent_devices']

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

class WireReportAdmin(admin.ModelAdmin):

    def response_add(self, request, obj):
        return self.view_wire_report(request, obj)

    def response_change(self, request, obj):
        return self.view_wire_report(request, obj)

    def view_wire_report(self, request, obj):
        if "run_wire_report" in request.POST:
            context = {}
            context['cast_reports'] = obj.run_wire_report()
            context['wire'] = obj.wire
            context['start_date'] = obj.start_date
            context['end_date'] = obj.end_date
            return render(request, 'admin/wirereport.html', context)

class ConfigForm(forms.ModelForm):
    wire = forms.ModelChoiceField(
        queryset=Wire.objects,
        empty_label='No wire',
        required=False
    )

    class Meta:
        model = Config
        exclude = []

class GPSAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}

class ConfigAdmin(admin.ModelAdmin):
    form = ConfigForm

    def get_form(self, request, obj=None, **kwargs):
        # existing configs are read only
        self.readonly_fields = ['device', 'wire', 'winch']
        if not obj:
            self.readonly_fields = []
        return super().get_form(request, obj, **kwargs)

admin.site.register(Device)
admin.site.register(Event)
admin.site.register(Cruise, CruiseAdmin)
admin.site.register(CastReport, CastReportAdmin)
admin.site.register(ShipLog, ShipLogAdmin)
admin.site.register(Config, ConfigAdmin)
admin.site.register(Wire)
admin.site.register(GPS, GPSAdmin)
admin.site.register(WireReport, WireReportAdmin)

