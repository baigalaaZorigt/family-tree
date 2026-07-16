"""Эх өгөгдлийн бүрэн ачаалалт `0009_load_full_data` руу шилжсэн
(PersonPhoto/цомог 0008-д нэмэгдсэн тул түүний дараа ачаалах ёстой).

Энэ migration одоо хоосон (no-op) — хуучин DB-д нөлөөлөхгүй.
"""
from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('tree', '0005_person_photo')]
    operations = [migrations.RunPython(noop, noop)]
