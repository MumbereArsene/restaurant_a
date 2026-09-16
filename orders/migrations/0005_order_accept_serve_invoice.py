import uuid

from django.db import migrations, models


def _new_invoice_token():
    return uuid.uuid4().hex


def fill_invoice_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.all():
        order.invoice_token = uuid.uuid4().hex
        order.save(update_fields=["invoice_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_analytics_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="accepted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="acceptée le"),
        ),
        migrations.AddField(
            model_name="order",
            name="served_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="servie le"),
        ),
        migrations.AddField(
            model_name="order",
            name="invoice_token",
            field=models.CharField(
                default=_new_invoice_token,
                editable=False,
                max_length=64,
                verbose_name="token facture",
            ),
        ),
        migrations.RunPython(fill_invoice_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="invoice_token",
            field=models.CharField(
                default=_new_invoice_token,
                editable=False,
                max_length=64,
                unique=True,
                verbose_name="token facture",
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("en_attente", "En attente"),
                    ("acceptee", "Acceptée"),
                    ("en_preparation", "En préparation"),
                    ("prete", "Prête"),
                    ("servie", "Servie"),
                    ("payee", "Payée"),
                    ("annulee", "Annulée"),
                ],
                default="en_attente",
                max_length=20,
                verbose_name="statut",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["invoice_token"], name="orders_orde_invoice_token_idx"),
        ),
    ]
