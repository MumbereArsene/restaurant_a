from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.media_cleanup import delete_file


@receiver(post_delete, sender="core.Restaurant")
def delete_restaurant_images(sender, instance, **kwargs):
    delete_file(instance, "logo", "cover_image")