from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Administrateur"),
                    ("manager", "Manager"),
                    ("caissier", "Caissier"),
                    ("serveur", "Serveur"),
                    ("cuisine", "Cuisine"),
                    ("client", "Client"),
                ],
                default="serveur",
                max_length=20,
                verbose_name="rôle",
            ),
        ),
    ]
