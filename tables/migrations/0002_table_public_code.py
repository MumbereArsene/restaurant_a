from django.db import migrations, models

import tables.models


def _fill_public_codes(apps, schema_editor):
    Table = apps.get_model("tables", "Table")
    from tables.codes import generate_code

    used = set(
        Table.objects.exclude(public_code="").values_list("public_code", flat=True)
    )

    for table in Table.objects.all():
        if table.public_code:
            used.add(table.public_code)
            continue
        for _ in range(64):
            code = generate_code()
            if code not in used:
                table.public_code = code
                table.save(update_fields=["public_code"])
                used.add(code)
                break
        else:
            raise RuntimeError(f"Impossible de générer un code pour la table {table.number}.")


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tables", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="table",
            name="public_code",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Code court permanent saisi par le client et le serveur.",
                max_length=8,
                verbose_name="code table",
            ),
        ),
        migrations.AlterField(
            model_name="table",
            name="qr_token",
            field=models.CharField(
                default=tables.models._new_token,
                editable=False,
                max_length=64,
                unique=True,
                verbose_name="identifiant interne",
            ),
        ),
        migrations.RunPython(_fill_public_codes, _noop),
        migrations.AlterField(
            model_name="table",
            name="public_code",
            field=models.CharField(
                blank=True,
                help_text="Code court permanent saisi par le client et le serveur.",
                max_length=8,
                unique=True,
                verbose_name="code table",
            ),
        ),
    ]
