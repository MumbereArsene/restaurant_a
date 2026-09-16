from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_order_discount_amount_order_discount_approved_by_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["created_at"], name="orders_orde_created_4a4a6e_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["paid_at"], name="orders_orde_paid_at_8f0d1c_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["status"], name="orders_orde_status_25e1e0_idx"),
        ),
    ]
