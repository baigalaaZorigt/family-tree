from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Notification, Person, Spouse
from .permissions import can_edit, current_person

SPOUSE_FIELDS = ['name', 'birth', 'death', 'phone', 'social', 'address', 'bio']


def _apply_spouse_fields(sp, request):
    for f in SPOUSE_FIELDS:
        setattr(sp, f, request.POST.get(f, '').strip())
    sp.gender = request.POST.get('gender', 'f')
    if request.POST.get('remove_photo') == '1' and sp.photo:
        sp.photo.delete(save=False)
        sp.photo = None
    if request.FILES.get('photo'):
        sp.photo = request.FILES['photo']


@login_required
def add_spouse(request, person_pk):
    """Гэр бүлийн гишүүнд хань (нөхөр/эхнэр)-ийн бүрэн мэдээлэл нэмнэ."""
    person = get_object_or_404(Person, pk=person_pk)
    me = current_person(request)
    if not can_edit(request, person):
        messages.error(request, 'Танд энэ хүн дээр хань нэмэх эрх байхгүй байна.')
        return redirect('/')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return render(request, 'tree/spouse.html',
                          {'person': person, 'me': me, 'error': 'Нэрийг заавал оруулна уу.'})
        sp = Spouse(person=person, order=person.spouse_details.count())
        _apply_spouse_fields(sp, request)
        sp.save()
        # Хэрэв өмнө нь текст хань байгаагүй бол summary-д нэрийг нь нэмнэ
        # (хуучин текстийг ДАРААХГҮЙ — олон ханьтай хүний мэдээллийг хамгаална)
        if not (person.spouse or '').strip():
            person.spouse = sp.name
            person.save(update_fields=['spouse'])
        Notification.objects.create(
            kind='spouse', person=person,
            title=f'🎉 Баяр хүргэе! {person.name} гэр бүлтэй боллоо',
            body=f'{person.name} ба {sp.name} — шинэ өрх гэрт нь амар амгалан, '
                 f'аз жаргалыг хүсэн ерөөе! 💍',
        )
        messages.success(request, f'«{sp.name}» хань нэмэгдлээ.')
        return redirect('person_detail', pk=person.pk)

    return render(request, 'tree/spouse.html', {'person': person, 'me': me})


@login_required
def edit_spouse(request, pk):
    sp = get_object_or_404(Spouse, pk=pk)
    person = sp.person
    me = current_person(request)
    if not can_edit(request, person):
        messages.error(request, 'Танд энэ ханийг засах эрх байхгүй байна.')
        return redirect('/')

    if request.method == 'POST':
        if request.POST.get('delete') == '1':
            removed_name = sp.name
            sp.delete()
            # «Гэр бүл (нөхөр/эхнэр)» текст талбараас нэрийг нь хасна
            if person.spouse:
                parts = [x.strip() for x in person.spouse.split('·')]
                parts = [x for x in parts if x and removed_name not in x]
                person.spouse = ' · '.join(parts)
                person.save(update_fields=['spouse'])
            messages.success(request, 'Хани устгагдлаа.')
            return redirect('person_detail', pk=person.pk)
        name = request.POST.get('name', '').strip()
        if not name:
            return render(request, 'tree/spouse.html',
                          {'person': person, 'me': me, 'spouse': sp, 'error': 'Нэрийг заавал оруулна уу.'})
        _apply_spouse_fields(sp, request)
        sp.save()
        messages.success(request, 'Ханийн мэдээлэл хадгалагдлаа.')
        return redirect('person_detail', pk=person.pk)

    return render(request, 'tree/spouse.html', {'person': person, 'me': me, 'spouse': sp})
