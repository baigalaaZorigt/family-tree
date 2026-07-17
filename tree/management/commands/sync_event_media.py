import io
import os
import subprocess
import tempfile
from urllib.parse import urlparse

import boto3
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageOps

from tree.models import Event, EventMedia

PHOTO_EXTS = {'.jpg', '.jpeg', '.png', '.heic', '.webp'}
VIDEO_EXTS = {'.mov', '.mp4', '.m4v'}
THUMB_WIDTH = 700


class Command(BaseCommand):
    help = (
        'S3 дээрх баярын хавтаснаас шинээр орсон зураг/видеог EventMedia-д '
        'синк хийнэ: thumbnail (700px зураг, видеонд эхний секундын кадр) '
        'үүсгэж S3-д байршуулаад, DB бичлэг үүсгээд, gallery кэшийг цэвэрлэнэ. '
        'Аль хэдийн синк хийсэн файлыг дахин алгасна (URL-аар ялгана).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--event', type=int, required=True, help='Event pk')
        parser.add_argument(
            '--prefix', type=str, default=None,
            help='S3 хавтасны prefix, ж: urgiin_bayar_2026/. Өгөгдөөгүй бол '
                 'тухайн үйл явдлын одоо байгаа зургуудаас автоматаар тодорхойлно.')
        parser.add_argument('--thumb-width', type=int, default=THUMB_WIDTH)
        parser.add_argument('--dry-run', action='store_true',
                             help='Юу нэмэгдэхийг зөвхөн харуулаад, бичихгүй.')

    def handle(self, *args, **opts):
        if not settings.AWS_S3_BUCKET:
            raise CommandError('AWS_S3_BUCKET тохируулаагүй байна — энэ команд зөвхөн S3 идэвхтэй орчинд ажиллана.')

        try:
            event = Event.objects.get(pk=opts['event'])
        except Event.DoesNotExist:
            raise CommandError(f'Event pk={opts["event"]} олдсонгүй.')

        bucket = settings.AWS_STORAGE_BUCKET_NAME
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        existing = list(EventMedia.objects.filter(event=event))
        prefix = opts['prefix'] or self._infer_prefix(existing)
        if not prefix:
            raise CommandError(
                '--prefix заавал өгнө үү (энэ үйл явдалд одоогоор зураг '
                'байхгүй тул автоматаар тодорхойлох боломжгүй).')
        if not prefix.endswith('/'):
            prefix += '/'

        self.stdout.write(f'Bucket: {bucket}  Prefix: {prefix}')

        base_url = f'https://{bucket}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/'
        existing_urls = {m.url for m in existing}
        keys = self._list_keys(s3, bucket, prefix)
        new_keys = [k for k in keys if (base_url + k) not in existing_urls]
        self.stdout.write(f'S3-д нийт {len(keys)} файл, шинэ {len(new_keys)}.')

        if opts['dry_run']:
            for k in new_keys:
                self.stdout.write(f'  + {k}')
            return

        thumb_width = opts['thumb_width']
        order_base = max((m.order for m in existing), default=-1) + 1
        added_photo = added_video = skipped = 0

        for i, key in enumerate(new_keys):
            ext = os.path.splitext(key)[1].lower()
            stem = key.rsplit('/', 1)[-1].rsplit('.', 1)[0]
            thumb_key = f'{prefix}thumbs/{stem}.jpg'

            try:
                if ext in PHOTO_EXTS:
                    media_type = 'photo'
                    data = s3.get_object(Bucket=bucket, Key=key)['Body'].read()
                    thumb_bytes = self._make_photo_thumb(data, thumb_width)
                elif ext in VIDEO_EXTS:
                    media_type = 'video'
                    thumb_bytes = self._make_video_thumb(s3, bucket, key, thumb_width)
                else:
                    self.stdout.write(self.style.WARNING(f'  алгасав (танихгүй өргөтгөл): {key}'))
                    skipped += 1
                    continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  АЛДАА {key}: {e}'))
                skipped += 1
                continue

            s3.put_object(Bucket=bucket, Key=thumb_key, Body=thumb_bytes, ContentType='image/jpeg')
            EventMedia.objects.create(
                event=event, media_type=media_type,
                url=base_url + key, thumbnail_url=base_url + thumb_key,
                order=order_base + i,
            )
            if media_type == 'photo':
                added_photo += 1
            else:
                added_video += 1
            self.stdout.write(f'  + [{media_type}] {key}')

        cache.delete(f'event_media_{event.pk}')
        self.stdout.write(self.style.SUCCESS(
            f'Дууслаа: {added_photo} зураг, {added_video} видео нэмэгдлээ '
            f'({skipped} алгассан). Gallery кэш цэвэрлэгдлээ.'))

    def _infer_prefix(self, existing):
        for m in existing:
            path = urlparse(m.url).path.lstrip('/')
            if '/' in path:
                return path.rsplit('/', 1)[0] + '/'
        return None

    def _list_keys(self, s3, bucket, prefix):
        paginator = s3.get_paginator('list_objects_v2')
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                k = obj['Key']
                if k == prefix or k.startswith(f'{prefix}thumbs/'):
                    continue
                keys.append(k)
        return keys

    def _make_photo_thumb(self, data, width):
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert('RGB')
        w, h = im.size
        if w >= h:
            new_w, new_h = width, round(h * width / w)
        else:
            new_h, new_w = width, round(w * width / h)
        thumb = im.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        thumb.save(buf, format='JPEG', quality=85)
        return buf.getvalue()

    def _make_video_thumb(self, s3, bucket, key, width):
        with tempfile.TemporaryDirectory() as tmp:
            local_path = os.path.join(tmp, 'src' + os.path.splitext(key)[1])
            frame_path = os.path.join(tmp, 'frame.jpg')
            s3.download_file(bucket, key, local_path)
            subprocess.run(
                ['ffmpeg', '-y', '-ss', '1', '-i', local_path, '-frames:v', '1', '-q:v', '3', frame_path],
                capture_output=True, text=True,
            )
            if not os.path.exists(frame_path):
                subprocess.run(
                    ['ffmpeg', '-y', '-i', local_path, '-frames:v', '1', '-q:v', '3', frame_path],
                    capture_output=True, text=True,
                )
            if not os.path.exists(frame_path):
                raise RuntimeError('ffmpeg кадр гаргаж чадсангүй')
            with open(frame_path, 'rb') as f:
                data = f.read()
        return self._make_photo_thumb(data, width)
