import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Person, PersonPhoto
from .permissions import can_edit


def person_album(request, pk):
    """Хүний зургийн бүх цомгийг тусдаа хуудсанд (lightbox-той) харуулна."""
    person = get_object_or_404(Person, pk=pk)
    album = list(person.album.all())
    album_json = json.dumps([
        {'type': 'photo', 'url': p.image.url, 'poster': '', 'caption': p.caption}
        for p in album
    ], ensure_ascii=False).replace('</', '<\\/')
    return render(request, 'tree/album.html', {
        'person': person,
        'album': album,
        'album_json': album_json,
        'can_edit': can_edit(request, person),
    })


@login_required
def add_photos(request, person_pk):
    """Хүний зургийн цомогт олон зураг нэмнэ (дараа нь дахин нэмж болно)."""
    person = get_object_or_404(Person, pk=person_pk)
    if not can_edit(request, person):
        messages.error(request, 'Танд энэ хүний цомогт зураг нэмэх эрх байхгүй байна.')
        return redirect('person_detail', pk=person.pk)
    if request.method == 'POST':
        files = request.FILES.getlist('photos')
        base = person.album.count()
        for i, f in enumerate(files):
            PersonPhoto.objects.create(person=person, image=f, order=base + i)
        if files:
            messages.success(request, f'{len(files)} зураг цомогт нэмэгдлээ.')
    return redirect('person_detail', pk=person.pk)


@login_required
def delete_photo(request, pk):
    """Цомгийн нэг зургийг устгана."""
    photo = get_object_or_404(PersonPhoto, pk=pk)
    person = photo.person
    if not can_edit(request, person):
        messages.error(request, 'Танд энэ зургийг устгах эрх байхгүй байна.')
        return redirect('person_detail', pk=person.pk)
    if request.method == 'POST':
        photo.image.delete(save=False)
        photo.delete()
        messages.success(request, 'Зураг устгагдлаа.')
    return redirect('person_detail', pk=person.pk)
