"""Нэвтрэлт: username = утасны дугаар, password = төрсөн он-сар-өдөр.

Хүн бүр Person бичлэгтэй. Утас нь тодорхойлогдсон хүн (ихэвчлэн насанд хүрсэн)
өөрийн утсаар нэвтэрч, нууц үг нь өөрийнх нь төрсөн огноо байна.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from .models import Person, normalize_birth

User = get_user_model()


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

        # Нууц үг = төрсөн огноо (цифрүүдээр жишнэ)
        if not person.birth_key or normalize_birth(password) != person.birth_key:
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
