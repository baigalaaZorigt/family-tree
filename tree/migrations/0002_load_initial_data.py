"""Эх өгөгдлийн ачаалалт нь бүх модель (Spouse, photo г.м.) үүссэний дараа
`0006_load_full_data`-д шилжсэн тул энэ migration одоо хоосон (no-op).

Хуучин ачаалагдсан DB-д нөлөөлөхгүй; шинэ DB дээр 0006 бүрэн өгөгдлийг ачаална.
"""
from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('tree', '0001_initial')]
    operations = [migrations.RunPython(noop, noop)]
