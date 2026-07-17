"""Нэвтрэлт: username = утасны дугаар, password = төрсөн ОН (жилээр).

Хүн бүр Person бичлэгтэй. Утас нь тодорхойлогдсон хүн (ихэвчлэн насанд хүрсэн)
өөрийн утсаар нэвтэрч, нууц үг нь зөвхөн төрсөн оны 4 оронтой тоо байна
(жишээ нь birth талбар «1965.02.26» байсан ч нууц үг нь зөвхөн «1965»).
"""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from .models import Person

User = get_user_model()

YEAR_RE = re.compile(r'(18|19|20)\d\d')


class PhoneBirthBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        # Утсыг цифрээр нь жишихийн тулд хоёр талыг цэвэрлэнэ
        typed_phone = ''.join(ch for ch in str(username) if ch.isdigit())
        if not typed_phone:
            return None

        # Утас тохирох хүнийг олох (цифрүүдээр)
        person = None
        for p in Person.objects.exclude(phone=''):
            if ''.join(ch for ch in p.phone if ch.isdigit()) == typed_phone:
                person = p
                break
        if person is None:
            return None

        # Нууц үг = төрсөн оны 4 оронтой тоо (birth талбараас оныг ялгаж авна)
        m = YEAR_RE.search(person.birth or '')
        typed_year = ''.join(ch for ch in str(password) if ch.isdigit())
        if not m or typed_year != m.group(0):
            return None

        return self._get_or_create_user(person)

    def _get_or_create_user(self, person):
        """Person-д харгалзах Django хэрэглэгчийг үүсгэх/авах."""
        if person.user is not None:
            return person.user
        username = ''.join(ch for ch in person.phone if ch.isdigit()) or f'person{person.id}'
        user, _ = User.objects.get_or_create(username=username)
        user.set_unusable_password()  # нууц үгийг backend шалгана
        user.first_name = person.name[:30]
        user.save()
        person.user = user
        person.save(update_fields=['user'])
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
