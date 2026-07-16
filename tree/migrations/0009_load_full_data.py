"""Одоогийн БҮХ өгөгдлийг (хүн + талбар + зураг + хань + цомог) эх өгөгдөл
болгон `initial_data.json`-оос ачаална.

Бүх модель (PersonPhoto/цомог хүртэл) үүссэний дараа ажилладаг тул бүгдийг
бүрэн сэргээж чадна. DB-д аль хэдийн өгөгдөл байвал алгасна.
"""
import json
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).resolve().parent.parent / 'initial_data.json'


def load_full(apps, schema_editor):
    Person = apps.get_model('tree', 'Person')
    Spouse = apps.get_model('tree', 'Spouse')
    PersonPhoto = apps.get_model('tree', 'PersonPhoto')
    if Person.objects.exists():
        return  # аль хэдийн өгөгдөлтэй бол давхардуулахгүй

    with open(DATA_FILE, encoding='utf-8') as fh:
        root = json.load(fh)

    def create(node, parent):
        person = Person.objects.create(
            name=node.get('name', ''),
            gender=node.get('g', 'm'),
            gen=node.get('gen', 1),
            role=node.get('role', '') or '',
            birth=node.get('birth', '') or '',
            death=node.get('death', '') or '',
            spouse=node.get('spouse', '') or '',
            bio=node.get('bio', '') or '',
            phone=node.get('phone', '') or '',
            social=node.get('social', '') or '',
            address=node.get('address', '') or '',
            photo=node.get('photo', '') or '',
            family_photo=node.get('family_photo', '') or '',
            parent=parent,
            order=node.get('order', 0),
        )
        for i, sp in enumerate(node.get('spouses', []) or []):
            Spouse.objects.create(
                person=person,
                name=sp.get('name', ''),
                gender=sp.get('g', 'f'),
                birth=sp.get('birth', '') or '',
                death=sp.get('death', '') or '',
                phone=sp.get('phone', '') or '',
                social=sp.get('social', '') or '',
                address=sp.get('address', '') or '',
                bio=sp.get('bio', '') or '',
                photo=sp.get('photo', '') or '',
                order=i,
            )
        for i, al in enumerate(node.get('album', []) or []):
            PersonPhoto.objects.create(
                person=person,
                image=al.get('image', ''),
                caption=al.get('caption', '') or '',
                order=al.get('order', i),
            )
        for child in node.get('ch', []) or []:
            create(child, person)
        return person

    create(root, None)


def unload_full(apps, schema_editor):
    Person = apps.get_model('tree', 'Person')
    Person.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('tree', '0008_personphoto')]
    operations = [migrations.RunPython(load_full, unload_full)]
