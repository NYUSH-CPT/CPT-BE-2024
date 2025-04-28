from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WebUser, Whitelist

@receiver(post_save, sender=Whitelist)
def update_webuser_on_whitelist_change(sender, instance, created, **kwargs):
    if not created:
        try:
            webuser_instance = WebUser.objects.get(uuid=instance.uuid)
            if webuser_instance.group != instance.group:
                webuser_instance.group = instance.group
                webuser_instance.save()
                
            if webuser_instance.startDate != instance.startDate:
                webuser_instance.startDate = instance.startDate
                webuser_instance.save()
                
        except WebUser.DoesNotExist:
            pass
