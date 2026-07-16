"""S3 storage тохиргоо — хүн бүрийн профайл болон зургийн цомгийг S3 дээр
тусдаа хавтаст (people/<pk>-<нэр>/...) байрлуулна.

AWS_S3_BUCKET орчны хувьсагч тохируулагдаагүй бол S3 ашиглахгүй (storage=None
буцааж, Django default локал storage руу автоматаар унана) — локал dev-д
хэвээрээ ажиллана.
"""
from django.conf import settings
from django.utils.text import slugify


def s3_storage():
    """S3 тохируулагдсан бол Storage instance, эс бөгөөс None (локал storage)."""
    if not getattr(settings, 'AWS_S3_BUCKET', ''):
        return None
    from storages.backends.s3 import S3Storage
    return S3Storage()


def _person_folder(person):
    """<pk>-<нэрний-slug> хэлбэрийн хавтасны нэр. Шинэ (хараахан хадгалагдаагүй)
    хүний хувьд pk байхгүй тул 'new' ашиглана (энэ тохиолдол views.py-д
    2 үе шаттай save-аар зайлсхийгддэг)."""
    slug = slugify(person.name, allow_unicode=True) or 'hun'
    pk = person.pk if person.pk else 'new'
    return f'{pk}-{slug}'


def person_photo_path(instance, filename):
    """Person.photo — хувийн (thumbnail) зураг."""
    return f'people/{_person_folder(instance)}/profile/{filename}'


def person_family_photo_path(instance, filename):
    """Person.family_photo — гэр бүлийн зураг (хуучин, одоо цомгоор солигдсон)."""
    return f'people/{_person_folder(instance)}/family/{filename}'


def person_album_path(instance, filename):
    """PersonPhoto.image — зургийн цомог. instance.person-ий хавтаст орно."""
    return f'people/{_person_folder(instance.person)}/album/{filename}'


def spouse_photo_path(instance, filename):
    """Spouse.photo — ханийн зураг. Мөн instance.person-ий хавтаст орно."""
    return f'people/{_person_folder(instance.person)}/spouse/{filename}'
