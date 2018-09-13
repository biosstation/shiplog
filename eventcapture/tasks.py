from __future__ import absolute_import, unicode_literals
from celery import shared_task
from eventcapture.models import Cast, ShipLog

@shared_task
def analyze_cast(recovery_id):
    recovery = ShipLog.objects.get(pk=int(recovery_id))
    config = recovery.find_config()
    deployment = recovery.find_deployment()
    cast = Cast(deployment=deployment, recovery=recovery, config=config)
    cast.save()
    return 'Saved cast with id of {}'.format(cast.id)
