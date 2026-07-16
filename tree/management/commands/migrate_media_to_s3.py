"""Хуучин (S3-руу шилжихээс өмнөх) локал дискэн дэх зургуудыг S3 руу,
хүн бүрийн хавтаст (people/<pk>-<нэр>/...) шилжүүлнэ.

Ашиглах: python manage.py migrate_media_to_s3 [--dry-run] [--keep-local]
"""
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from tree.models import Person, PersonPhoto, Spouse


class Command(BaseCommand):
    help = 'Хуучин локал зургуудыг S3 руу (хүн бүрийн хавтаст) шилжүүлнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Юу ч бичихгүй, зөвхөн юу хийхээ хэвлэнэ.')
        parser.add_argument('--keep-local', action='store_true',
                            help='Амжилттай шилжсэний дараа ч гэсэн хуучин локал файлыг устгахгүй.')

    def handle(self, *args, **opts):
        if not getattr(settings, 'AWS_S3_BUCKET', ''):
            self.stderr.write(self.style.ERROR(
                'AWS_S3_BUCKET тохируулагдаагүй байна — S3 идэвхгүй үед шилжүүлэх шаардлагагүй.'))
            return

        dry = opts['dry_run']
        keep_local = opts['keep_local']
        moved, skipped, missing = 0, 0, 0

        def migrate_field(obj, field_name):
            nonlocal moved, skipped, missing
            field = getattr(obj, field_name)
            if not field:
                return
            name = field.name
            if name.startswith('people/'):
                skipped += 1  # аль хэдийн S3-д шилжсэн
                return
            local_path = settings.MEDIA_ROOT / name
            if not local_path.exists():
                missing += 1
                self.stdout.write(self.style.WARNING(f'  файл олдсонгүй: {local_path}'))
                return

            label = f'{obj.__class__.__name__}#{obj.pk} · {field_name} · {name}'
            if dry:
                self.stdout.write(f'  [DRY-RUN] шилжинэ: {label}')
                moved += 1
                return

            with open(local_path, 'rb') as fh:
                data = fh.read()
            filename = os.path.basename(name)
            # storage.py дахь upload_to callable-ууд шинэ S3 замыг автоматаар зохионо
            field.save(filename, ContentFile(data), save=True)
            if not keep_local:
                try:
                    os.remove(local_path)
                except OSError:
                    pass
            self.stdout.write(self.style.SUCCESS(f'  шилжлээ: {label} -> {field.name}'))
            moved += 1

        self.stdout.write('=== Person.photo / Person.family_photo ===')
        for p in Person.objects.all():
            migrate_field(p, 'photo')
            migrate_field(p, 'family_photo')

        self.stdout.write('=== Spouse.photo ===')
        for s in Spouse.objects.all():
            migrate_field(s, 'photo')

        self.stdout.write('=== PersonPhoto.image (цомог) ===')
        for ph in PersonPhoto.objects.all():
            migrate_field(ph, 'image')

        self.stdout.write(self.style.SUCCESS(
            f'\nДууслаа. Шилжсэн: {moved} | Аль хэдийн S3-д байсан: {skipped} | Файл олдоогүй: {missing}'))
