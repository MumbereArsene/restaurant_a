import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cash", "0003_cashentry_analytics_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cashentry",
            name="amount",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="montant",
            ),
        ),
        migrations.AddConstraint(
            model_name="cashentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gte", 0)),
                name="cash_entry_amount_gte_0",
            ),
        ),
    ]
