import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0005_order_accept_serve_invoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="customer_orders",
                to=settings.AUTH_USER_MODEL,
                verbose_name="compte client",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="guest_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="email client"),
        ),
        migrations.AddField(
            model_name="order",
            name="guest_phone",
            field=models.CharField(blank=True, max_length=30, verbose_name="WhatsApp client"),
        ),
    ]
