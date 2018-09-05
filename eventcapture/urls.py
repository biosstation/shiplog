from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^device/(?P<device_id>[0-9]+)/$', views.device, name='device'),
    url(r'^event/(?P<device_id>[0-9]+)/$', views.event, name='event'),
    url(r'^download/(?P<log>[a-z]+)/(?P<cruise_id>[0-9]+)/$', views.download, name='download'),
    url(r'^eventlog/$', views.eventlog, name='eventlog'),
    url(r'^castlog/$', views.castlog, name='castlog'),
]
