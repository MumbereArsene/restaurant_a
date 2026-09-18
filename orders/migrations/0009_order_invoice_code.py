from django.db import migrations, models


def _fill_invoice_codes(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Table = apps.get_model("tables", "Table")
    from tables.codes import generate_code

    used = set(Table.objects.exclude(public_code="").values_list("public_code", flat=True))
    used.update(
        Order.objects.exclude(invoice_code="").values_list("invoice_code", flat=True)
    )

    for order in Order.objects.all():
        if order.invoice_code:
            used.add(order.invoice_code)
            continue
        for _ in range(64):
            code = generate_code()
            if code not in used:
                order.invoice_code = code
                order.save(update_fields=["invoice_code"])
                used.add(code)
                break
        else:
            raise RuntimeError(f"Impossible de générer un code facture pour la commande {order.pk}.")


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_order_payment_method"),
        ("tables", "0002_table_public_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="invoice_code",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Code court saisi par le serveur pour encaisser.",
                max_length=8,
                verbose_name="code facture",
            ),
        ),
        migrations.RunPython(_fill_invoice_codes, _noop),
        migrations.AlterField(
            model_name="order",
            name="invoice_code",
            field=models.CharField(
                blank=True,
                help_text="Code court saisi par le serveur pour encaisser.",
                max_length=8,
                unique=True,
                verbose_name="code facture",
            ),
        ),
    ]
