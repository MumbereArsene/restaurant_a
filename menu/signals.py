from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.media_cleanup import delete_file


@receiver(post_delete, sender="menu.Dish")
def delete_dish_image(sender, instance, **kwargs):
    delete_file(instance, "image")