from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cash", "0002_cashclosure"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="cashentry",
            index=models.Index(fields=["created_at"], name="cash_cashen_created_b2a91e_idx"),
        ),
        migrations.AddIndex(
            model_name="cashentry",
            index=models.Index(fields=["type"], name="cash_cashen_type_6d4c0a_idx"),
        ),
    ]
