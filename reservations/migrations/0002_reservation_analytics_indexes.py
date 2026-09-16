from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(fields=["date"], name="reservatio_date_7c1a2b_idx"),
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(fields=["status"], name="reservatio_status_3e9d4c_idx"),
        ),
    ]
