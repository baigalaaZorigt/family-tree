import io
import os
import shutil
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

THUMB_WIDTH = 700          # grid дэх жижиг thumbnail
PHOTO_MAX_DIM = 2000       # харах зургийн дээд хэмжээ (lightbox)
PHOTO_QUALITY = 88
VIDEO_MAX_DIM = 1920       # харах видеоны дээд хэмжээ
VIDEO_BITRATE = '3M'
VIDEO_MAXRATE = '4M'
VIDEO_BUFSIZE = '6M'


class Command(BaseCommand):
    help = (
        'S3 дээрх баярын хавтаснаас шинээр орсон зураг/видеог EventMedia-д '
        'синк хийнэ: жижиг thumbnail (700px) болон хөнгөн, хурдан ачаалагдах '
        '«харах» хувилбар (зурагт 2000px JPEG, видеонд H.264 1080p) үүсгэж '
        'S3-д байршуулаад, DB бичлэг үүсгээд, gallery кэшийг цэвэрлэнэ. '
        'Эх (raw) файлыг хэвээр нь S3-д үлдээнэ, зөвхөн үзэх URL-ийг '
        'хөнгөн хувилбар руу чиглүүлнэ. Аль хэдийн синк хийсэн файлыг алгасна.\n\n'
        '--reprocess: аль хэдийн синк хийсэн бичлэгүүдийг (жишээ нь эх '
        'raw файл руу URL нь чиглэсэн хуучин бичлэгүүдийг) дахин боловсруулж, '
        'хөнгөн хувилбар руу шилжүүлнэ.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--event', type=int, required=True, help='Event pk')
        parser.add_argument(
            '--prefix', type=str, default=None,
            help='S3 хавтасны prefix, ж: urgiin_bayar_2026/. Өгөгдөөгүй бол '
                 'тухайн үйл явдлын одоо байгаа зургуудаас автоматаар тодорхойлно.')
        parser.add_argument('--thumb-width', type=int, default=THUMB_WIDTH)
        parser.add_argument('--reprocess', action='store_true',
                             help='Шинэ файл хайхын оронд аль хэдийн байгаа бичлэгүүдийг дахин боловсруулна.')
        parser.add_argument('--dry-run', action='store_true',
                             help='Юу хийхийг зөвхөн харуулаад, бичихгүй.')

    def handle(self, *args, **opts):
        if not settings.AWS_S3_BUCKET:
            raise CommandError('AWS_S3_BUCKET тохируулаагүй байна — энэ команд зөвхөн S3 идэвхтэй орчинд ажиллана.')
        if not shutil.which('ffmpeg'):
            raise CommandError('ffmpeg олдсонгүй (видео боловсруулахад шаардлагатай).')

        try:
            event = Event.objects.get(pk=opts['event'])
        except Event.DoesNotExist:
            raise CommandError(f'Event pk={opts["event"]} олдсонгүй.')

        bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        self.bucket = bucket
        self.base_url = f'https://{bucket}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/'
        self.hw_encoder = self._has_videotoolbox()

        existing = list(EventMedia.objects.filter(event=event))
        prefix = opts['prefix'] or self._infer_prefix(existing)
        if not prefix:
            raise CommandError(
                '--prefix заавал өгнө үү (энэ үйл явдалд одоогоор зураг '
                'байхгүй тул автоматаар тодорхойлох боломжгүй).')
        if not prefix.endswith('/'):
            prefix += '/'
        self.prefix = prefix

        self.stdout.write(f'Bucket: {bucket}  Prefix: {prefix}  HW encoder: {self.hw_encoder}')

        keys = self._list_keys(prefix)
        by_stem = {k.rsplit('/', 1)[-1].rsplit('.', 1)[0]: k for k in keys}
        existing_by_stem = {self._stem_of(m): m for m in existing}

        thumb_width = opts['thumb_width']

        if opts['reprocess']:
            targets = [(stem, key) for stem, key in by_stem.items() if stem in existing_by_stem]
            self.stdout.write(f'S3-д нийт {len(keys)} файл, дахин боловсруулах {len(targets)}.')
            if opts['dry_run']:
                for stem, key in targets:
                    self.stdout.write(f'  ~ {key}')
                return
            done_photo = done_video = failed = 0
            for stem, key in targets:
                media = existing_by_stem[stem]
                try:
                    optimized_url = self._process(key, thumb_width, media_type=media.media_type)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  АЛДАА {key}: {e}'))
                    failed += 1
                    continue
                media.url = optimized_url
                media.save(update_fields=['url'])
                if media.media_type == 'video':
                    done_video += 1
                else:
                    done_photo += 1
                self.stdout.write(f'  ~ [{media.media_type}] {key}')
            cache.delete(f'event_media_{event.pk}')
            self.stdout.write(self.style.SUCCESS(
                f'Дууслаа: {done_photo} зураг, {done_video} видео дахин боловсрууллаа '
                f'({failed} алдаатай). Gallery кэш цэвэрлэгдлээ.'))
            return

        new_items = [(stem, key) for stem, key in by_stem.items() if stem not in existing_by_stem]
        self.stdout.write(f'S3-д нийт {len(keys)} файл, шинэ {len(new_items)}.')
        if opts['dry_run']:
            for stem, key in new_items:
                self.stdout.write(f'  + {key}')
            return

        order_base = max((m.order for m in existing), default=-1) + 1
        added_photo = added_video = skipped = 0
        for i, (stem, key) in enumerate(new_items):
            ext = os.path.splitext(key)[1].lower()
            if ext in PHOTO_EXTS:
                media_type = 'photo'
            elif ext in VIDEO_EXTS:
                media_type = 'video'
            else:
                self.stdout.write(self.style.WARNING(f'  алгасав (танихгүй өргөтгөл): {key}'))
                skipped += 1
                continue
            try:
                optimized_url = self._process(key, thumb_width, media_type=media_type)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  АЛДАА {key}: {e}'))
                skipped += 1
                continue
            EventMedia.objects.create(
                event=event, media_type=media_type,
                url=optimized_url, thumbnail_url=self.base_url + f'{prefix}thumbs/{stem}.jpg',
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

    # ---- туслах функцүүд ----

    def _stem_of(self, media):
        path = urlparse(media.thumbnail_url or media.url).path
        return path.rsplit('/', 1)[-1].rsplit('.', 1)[0]

    def _infer_prefix(self, existing):
        for m in existing:
            path = urlparse(m.url).path.lstrip('/')
            if '/' in path:
                # эх файл нь thumbs/ эсвэл web/ дэд хавтаст байж болзошгүй тул хамгийн эх (root) prefix-ийг тооцно
                parts = path.split('/')
                if parts[-2] in ('thumbs', 'web'):
                    return '/'.join(parts[:-2]) + '/'
                return '/'.join(parts[:-1]) + '/'
        return None

    def _list_keys(self, prefix):
        """Зөвхөн prefix-ийн ЭХ (root) түвшний файлуудыг буцаана — дэд хавтаст
        (thumbs/, web/, featured/ гэх мэт аль ч нэртэй) байгаа зүйлийг үл хэрэгсэнэ."""
        paginator = self.s3.get_paginator('list_objects_v2')
        keys = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                k = obj['Key']
                if k == prefix or '/' in k[len(prefix):]:
                    continue
                keys.append(k)
        return keys

    def _has_videotoolbox(self):
        r = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True)
        return 'h264_videotoolbox' in r.stdout

    def _process(self, key, thumb_width, media_type):
        """Тухайн S3 key-г татаж, thumbnail + хөнгөн «харах» хувилбарыг S3-д
        байршуулаад, харах хувилбарын нийтийн URL-ийг буцаана."""
        stem = key.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        thumb_key = f'{self.prefix}thumbs/{stem}.jpg'

        if media_type == 'photo':
            data = self.s3.get_object(Bucket=self.bucket, Key=key)['Body'].read()
            thumb_bytes = self._resize_jpeg(data, thumb_width, quality=85)
            web_bytes = self._resize_jpeg(data, PHOTO_MAX_DIM, quality=PHOTO_QUALITY)
            web_key = f'{self.prefix}web/{stem}.jpg'
            self.s3.put_object(Bucket=self.bucket, Key=thumb_key, Body=thumb_bytes, ContentType='image/jpeg')
            self.s3.put_object(Bucket=self.bucket, Key=web_key, Body=web_bytes, ContentType='image/jpeg')
            return self.base_url + web_key

        # видео
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'src' + os.path.splitext(key)[1])
            frame = os.path.join(tmp, 'frame.jpg')
            out_mp4 = os.path.join(tmp, 'out.mp4')
            self.s3.download_file(self.bucket, key, src)

            subprocess.run(['ffmpeg', '-y', '-ss', '1', '-i', src, '-frames:v', '1', '-q:v', '3', frame],
                            capture_output=True, text=True)
            if not os.path.exists(frame):
                subprocess.run(['ffmpeg', '-y', '-i', src, '-frames:v', '1', '-q:v', '3', frame],
                                capture_output=True, text=True)
            if not os.path.exists(frame):
                raise RuntimeError('ffmpeg кадр гаргаж чадсангүй')
            with open(frame, 'rb') as f:
                thumb_bytes = self._resize_jpeg(f.read(), thumb_width, quality=85)
            self.s3.put_object(Bucket=self.bucket, Key=thumb_key, Body=thumb_bytes, ContentType='image/jpeg')

            scale = f"scale='min({VIDEO_MAX_DIM},iw)':'min({VIDEO_MAX_DIM},ih)':force_original_aspect_ratio=decrease"
            if self.hw_encoder:
                vcodec = ['-c:v', 'h264_videotoolbox', '-b:v', VIDEO_BITRATE,
                          '-maxrate', VIDEO_MAXRATE, '-bufsize', VIDEO_BUFSIZE]
            else:
                vcodec = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23']
            r = subprocess.run(
                ['ffmpeg', '-y', '-i', src, '-vf', scale, *vcodec,
                 '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', out_mp4],
                capture_output=True, text=True,
            )
            if not os.path.exists(out_mp4) or os.path.getsize(out_mp4) == 0:
                raise RuntimeError(f'ffmpeg транскод амжилтгүй: {r.stderr[-500:]}')

            web_key = f'{self.prefix}web/{stem}.mp4'
            with open(out_mp4, 'rb') as f:
                self.s3.put_object(Bucket=self.bucket, Key=web_key, Body=f.read(), ContentType='video/mp4')
            return self.base_url + web_key

    def _resize_jpeg(self, data, max_dim, quality):
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert('RGB')
        w, h = im.size
        if max(w, h) > max_dim:
            if w >= h:
                new_w, new_h = max_dim, round(h * max_dim / w)
            else:
                new_h, new_w = max_dim, round(w * max_dim / h)
            im = im.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=quality)
        return buf.getvalue()
