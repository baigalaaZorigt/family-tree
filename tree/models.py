import re

from django.conf import settings
from django.db import models


def normalize_birth(value):
    """Төрсөн огнооноос зөвхөн цифрүүдийг үлдээж жиших хэлбэрт оруулна.
    Ж: '1965.02.26' -> '19650226', '1959' -> '1959'."""
    if not value:
        return ''
    return re.sub(r'\D', '', str(value))


class Person(models.Model):
    GENDER_CHOICES = [('m', 'Эрэгтэй'), ('f', 'Эмэгтэй')]

    # ==== Ургийн модны үндсэн мэдээлэл (HTML-ээс ирсэн) ====
    name = models.CharField('Нэр', max_length=120)
    gender = models.CharField('Хүйс', max_length=1, choices=GENDER_CHOICES, default='m')
    gen = models.PositiveSmallIntegerField('Үе', default=1)
    role = models.CharField('Хочит / үүрэг', max_length=200, blank=True)
    birth = models.CharField('Төрсөн', max_length=40, blank=True)
    death = models.CharField('Өөд болсон', max_length=40, blank=True)
    spouse = models.CharField('Гэр бүл (нөхөр/эхнэр)', max_length=300, blank=True)
    bio = models.TextField('Намтар', blank=True)

    # ==== Шинээр нэмсэн холбоо барих мэдээлэл ====
    phone = models.CharField('Утас', max_length=30, blank=True,
                             help_text='Нэвтрэх нэр (username) болно.')
    social = models.CharField('Сошиал хаяг', max_length=300, blank=True,
                              help_text='Facebook / Instagram / и-мэйл г.м.')
    address = models.CharField('Гэрийн хаяг', max_length=300, blank=True)

    # ==== Хувийн зураг (thumbnail/аватар дээр харагдана) ====
    photo = models.ImageField('Хувийн зураг', upload_to='person_photos/',
                              blank=True, null=True,
                              help_text='Модон дээрх дугуй зураг (thumbnail) болно.')

    # ==== Гэр бүлийн (өрхийн) зураг ====
    family_photo = models.ImageField('Гэр бүлийн зураг', upload_to='family_photos/',
                                     blank=True, null=True)

    # ==== Модны бүтэц ====
    parent = models.ForeignKey('self', verbose_name='Эцэг/эх', null=True, blank=True,
                               related_name='children', on_delete=models.CASCADE)
    order = models.PositiveIntegerField('Эрэмбэ', default=0,
                                        help_text='Ах дүүсийн дунд эрэмбэлэх дугаар.')

    # Нэвтрэлтийн Django хэрэглэгчтэй холбоос
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                related_name='person', on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Хүн'
        verbose_name_plural = 'Хүмүүс'
        ordering = ['gen', 'order', 'id']

    def __str__(self):
        who = self.name
        if self.birth:
            who += f' ({self.birth})'
        return who

    # ---- Туслах шинжүүд ----
    @property
    def is_household(self):
        """Урх болсон буюу гэр бүлтэй (эхнэр/нөхөртэй) хүн эсэх."""
        if self.spouse and self.spouse.strip():
            return True
        return self.spouse_details.exists()

    @property
    def birth_key(self):
        return normalize_birth(self.birth)

    def ancestors(self):
        """Өөрөөс дээших бүх өвөг дээдэс (эцэг, өвөг...)."""
        node, chain = self.parent, []
        while node is not None:
            chain.append(node)
            node = node.parent
        return chain

    def descendant_ids(self, _acc=None):
        """Өөрөөс доош бүх үр удмын id-ууд (өөрийг оруулахгүй)."""
        if _acc is None:
            _acc = []
        for child in self.children.all():
            _acc.append(child.id)
            child.descendant_ids(_acc)
        return _acc

    def editable_by(self, editor):
        """editor (Person) энэ хүнийг засах эрхтэй эсэх.
        Хүн өөрийгөө болон өөрөөсөө доош бүх үр удмаа засаж болно."""
        if editor is None:
            return False
        if editor.id == self.id:
            return True
        # editor нь энэ хүний өвөг дээдсийн дунд байвал (editor -> ... -> self)
        return editor.id in [a.id for a in self.ancestors()]


class Notification(models.Model):
    """Мэдэгдэл — шинэ хүүхэд төрөх, хань нэмэгдэх зэрэг үйл явдал бүртгэнэ."""
    KIND_CHOICES = [
        ('birth', 'Шинэ гишүүн'),
        ('spouse', 'Гэр бүл'),
        ('edit', 'Мэдээлэл шинэчлэл'),
    ]
    kind = models.CharField('Төрөл', max_length=20, choices=KIND_CHOICES, default='birth')
    title = models.CharField('Гарчиг', max_length=200)
    body = models.CharField('Тайлбар', max_length=400, blank=True)
    person = models.ForeignKey(Person, verbose_name='Холбоотой хүн', null=True, blank=True,
                               related_name='notifications', on_delete=models.SET_NULL)
    created_at = models.DateTimeField('Огноо', auto_now_add=True)

    class Meta:
        verbose_name = 'Мэдэгдэл'
        verbose_name_plural = 'Мэдэгдэл'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.title

    @property
    def icon(self):
        return {'birth': '👶', 'spouse': '💍', 'edit': '✏️'}.get(self.kind, '🔔')


class Event(models.Model):
    """Ургийн баяр (3 жилд нэг удаа) / Цагаан сар (жил бүр) зэрэг ойн үйл явдал."""
    KIND_CHOICES = [
        ('urgiin_bayar', 'Ургийн баяр'),
        ('tsagaan_sar', 'Цагаан сар'),
        ('other', 'Бусад'),
    ]
    kind = models.CharField('Төрөл', max_length=20, choices=KIND_CHOICES, default='urgiin_bayar')
    year = models.PositiveIntegerField('Он')
    title = models.CharField('Гарчиг', max_length=200, blank=True,
                             help_text='Хоосон бол «Төрөл · Он» гэж автоматаар харагдана.')
    description = models.TextField('Тайлбар', blank=True)
    date = models.CharField('Огноо', max_length=60, blank=True,
                            help_text='Ж: «2024.02.10» эсвэл «Хаврын дунд сар».')

    class Meta:
        verbose_name = 'Баяр / үйл явдал'
        verbose_name_plural = 'Баяр / үйл явдал'
        ordering = ['-year', 'kind']

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title or f'{self.get_kind_display()} · {self.year}'

    @property
    def icon(self):
        return {'urgiin_bayar': '🎉', 'tsagaan_sar': '🌙'}.get(self.kind, '📅')


class EventMedia(models.Model):
    """Үйл явдлын онцлох зураг/видео — S3 дээрх файлын URL-ээр харуулна."""
    TYPE_CHOICES = [('photo', 'Зураг'), ('video', 'Видео')]
    event = models.ForeignKey(Event, verbose_name='Үйл явдал',
                              related_name='media', on_delete=models.CASCADE)
    media_type = models.CharField('Төрөл', max_length=10, choices=TYPE_CHOICES, default='photo')
    url = models.URLField('S3 URL', max_length=600,
                          help_text='S3 дээрх зураг/видеоны нийтийн (public) URL.')
    thumbnail_url = models.URLField('Видеоны poster (thumbnail) URL', max_length=600, blank=True,
                                    help_text='Видеоны хувьд урьдчилан харах зураг (заавал биш).')
    caption = models.CharField('Тайлбар', max_length=200, blank=True)
    order = models.PositiveIntegerField('Эрэмбэ', default=0)

    class Meta:
        verbose_name = 'Зураг / видео'
        verbose_name_plural = 'Зураг / видео'
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.get_media_type_display()} · {self.event.display_title}'


class Spouse(models.Model):
    """Гэр бүлийн хань (нөхөр/эхнэр) — өөрийн бүрэн мэдээлэлтэй."""
    GENDER_CHOICES = [('m', 'Эрэгтэй'), ('f', 'Эмэгтэй')]

    person = models.ForeignKey(Person, verbose_name='Гэр бүлийн гишүүн',
                               related_name='spouse_details', on_delete=models.CASCADE)
    name = models.CharField('Нэр', max_length=120)
    gender = models.CharField('Хүйс', max_length=1, choices=GENDER_CHOICES, default='f')
    birth = models.CharField('Төрсөн', max_length=40, blank=True)
    death = models.CharField('Өөд болсон', max_length=40, blank=True)
    phone = models.CharField('Утас', max_length=30, blank=True)
    social = models.CharField('Сошиал хаяг', max_length=300, blank=True)
    address = models.CharField('Гэрийн хаяг', max_length=300, blank=True)
    bio = models.TextField('Намтар', blank=True)
    photo = models.ImageField('Хувийн зураг', upload_to='spouse_photos/', blank=True, null=True)
    order = models.PositiveIntegerField('Эрэмбэ', default=0)

    class Meta:
        verbose_name = 'Хань (нөхөр/эхнэр)'
        verbose_name_plural = 'Хань (нөхөр/эхнэр)'
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.name} · {self.person.name}-ийн хань'


class PersonPhoto(models.Model):
    """Хүний зургийн цомог — олон зураг оруулж, дараа нь нэмж болно."""
    person = models.ForeignKey(Person, verbose_name='Хүн',
                               related_name='album', on_delete=models.CASCADE)
    image = models.ImageField('Зураг', upload_to='album/')
    caption = models.CharField('Тайлбар', max_length=200, blank=True)
    order = models.PositiveIntegerField('Эрэмбэ', default=0)
    created_at = models.DateTimeField('Нэмсэн огноо', auto_now_add=True)

    class Meta:
        verbose_name = 'Цомгийн зураг'
        verbose_name_plural = 'Зургийн цомог'
        ordering = ['order', '-created_at', 'id']

    def __str__(self):
        return f'{self.person.name} · зураг #{self.pk}'
