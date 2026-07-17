import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Notification, Person
from .permissions import can_edit, current_person
from .photos import MAX_ALBUM_PHOTOS

EDITABLE_FIELDS = ['name', 'birth', 'death', 'spouse', 'bio', 'phone', 'social', 'address']


def person_detail(request, pk):
    """Дарсан хүний дэлгэрэнгүй намтрыг тусдаа хуудсанд харуулна."""
    person = get_object_or_404(Person.objects.select_related('parent'), pk=pk)
    me = current_person(request)
    album = list(person.album.all())
    album_json = json.dumps([
        {'type': 'photo', 'url': p.image.url, 'poster': '', 'caption': p.caption}
        for p in album
    ], ensure_ascii=False).replace('</', '<\\/')
    return render(request, 'tree/detail.html', {
        'person': person,
        'me': me,
        'can_edit': can_edit(request, person),
        'spouses': person.spouse_details.all(),
        'children': person.children.all(),
        'descendants_count': len(person.descendant_ids()),
        'album': album,
        'album_json': album_json,
        'album_remaining': max(0, MAX_ALBUM_PHOTOS - len(album)),
    })


@login_required
def remove_avatar(request, pk):
    """Хувийн зургийг (thumbnail/аватар) шууд устгана — засах хуудаснаас дарж."""
    person = get_object_or_404(Person, pk=pk)
    if not can_edit(request, person):
        messages.error(request, 'Танд энэ зургийг устгах эрх байхгүй байна.')
        return redirect('person_detail', pk=person.pk)
    if request.method == 'POST' and person.photo:
        person.photo.delete(save=False)
        person.photo = None
        person.save(update_fields=['photo'])
        messages.success(request, 'Хувийн зураг устгагдлаа.')
    return redirect('edit_person', pk=person.pk)


@login_required
def edit_person(request, pk):
    person = get_object_or_404(Person, pk=pk)
    me = current_person(request)
    if not can_edit(request, person):
        messages.error(request, 'Танд энэ хүнийг засах эрх байхгүй байна.')
        return redirect('/')

    if request.method == 'POST':
        for f in EDITABLE_FIELDS:
            setattr(person, f, request.POST.get(f, '').strip())
        if request.POST.get('remove_avatar') == '1' and person.photo:
            person.photo.delete(save=False)
            person.photo = None
        if request.FILES.get('photo'):
            person.photo = request.FILES['photo']
        if request.POST.get('remove_photo') == '1' and person.family_photo:
            person.family_photo.delete(save=False)
            person.family_photo = None
        if request.FILES.get('family_photo'):
            person.family_photo = request.FILES['family_photo']
        person.save()
        messages.success(request, 'Мэдээлэл амжилттай хадгалагдлаа.')
        return redirect('person_detail', pk=person.pk)

    return render(request, 'tree/edit.html',
                  {'person': person, 'me': me, 'spouses': person.spouse_details.all()})


@login_required
def add_child(request, parent_pk):
    """Өөрийн болон үр удмынхаа доор (доош үе) шинэ хүн нэмнэ."""
    parent = get_object_or_404(Person, pk=parent_pk)
    me = current_person(request)
    if not can_edit(request, parent):
        messages.error(request, 'Танд энэ хүн дээр хүүхэд нэмэх эрх байхгүй байна.')
        return redirect('/')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return render(request, 'tree/add.html',
                          {'parent': parent, 'me': me, 'error': 'Нэрийг заавал оруулна уу.'})
        child = Person(
            parent=parent,
            gen=parent.gen + 1,
            order=parent.children.count(),
            gender=request.POST.get('gender', 'm'),
        )
        for f in EDITABLE_FIELDS:
            setattr(child, f, request.POST.get(f, '').strip())
        # Эхлээд зурагтгүйгээр хадгалж pk-г нь авна — S3 дээрх хавтасны нэрэнд
        # (people/<pk>-<нэр>/...) pk шаардлагатай тул зурагийг хоёр дахь удаагийн
        # save-ээр л хавсаргана.
        child.save()
        if request.FILES.get('photo'):
            child.photo = request.FILES['photo']
        if request.FILES.get('family_photo'):
            child.family_photo = request.FILES['family_photo']
        if request.FILES.get('photo') or request.FILES.get('family_photo'):
            child.save()
        Notification.objects.create(
            kind='birth', person=child,
            title=f'🎉 Баяр хүргэе! {child.name} ургийн гэр бүлд нэмэгдлээ',
            body=f'{parent.name}-ийн {"хүү" if child.gender == "m" else "охин"} · {child.gen}-р үе'
                 + (f' · {child.birth}' if child.birth else '')
                 + '. Шинэ гишүүн, эцэг эхэд нь өсөж торнихыг ерөөе! 🌱',
        )
        messages.success(request, f'«{child.name}» нэмэгдлээ.')
        return redirect('person_detail', pk=child.pk)

    return render(request, 'tree/add.html', {'parent': parent, 'me': me})
