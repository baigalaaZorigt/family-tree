import datetime
import json
import re
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Event, Notification, Person, PersonPhoto, Spouse

YEAR_RE = re.compile(r'(18|19|20)\d\d')


def _year_of(birth):
    m = YEAR_RE.search(birth or '')
    return int(m.group(0)) if m else None


def _base_name(name):
    return re.sub(r'^[А-ЯӨҮ]\.', '', name or '').strip()


def compute_stats(people):
    """Бүх статистикийг DB-ээс сервер талд тооцоолно (динамик)."""
    total = len(people)
    if total == 0:
        return {}

    children = defaultdict(list)
    for p in people:
        if p.parent_id:
            children[p.parent_id].append(p)

    # Үр удмын тоо (memoized)
    desc_cache = {}

    def desc_count(pid):
        if pid in desc_cache:
            return desc_cache[pid]
        c = 0
        for ch in children.get(pid, []):
            c += 1 + desc_count(ch.id)
        desc_cache[pid] = c
        return c

    males = sum(1 for p in people if p.gender == 'm')
    females = total - males
    deceased = sum(1 for p in people if p.death)
    living = total - deceased
    def is_household(p):
        return bool((p.spouse or '').strip()) or len(p.spouse_details.all()) > 0

    married = sum(1 for p in people if is_household(p))
    photos = sum(1 for p in people if is_household(p) and p.family_photo)
    twins = sum(1 for p in people if 'ихэр' in (p.role or ''))
    generations = max((p.gen or 1) for p in people)

    years = [y for y in (_year_of(p.birth) for p in people) if y]
    min_y = min(years) if years else 0
    max_y = max(years) if years else 0

    # Үе бүрийн гишүүдийн тоо
    by_gen = defaultdict(int)
    for p in people:
        by_gen[p.gen or 1] += 1
    biggest_gen = max(by_gen.items(), key=lambda kv: kv[1])  # (gen, count)

    # Хамгийн олон хүүхэдтэй хүн
    top_kids = max(people, key=lambda p: len(children.get(p.id, [])))
    # Хамгийн олон үр удамтай (3-р үеэс)
    gen3 = [p for p in people if (p.gen or 1) >= 3] or people
    top_desc = max(gen3, key=lambda p: desc_count(p.id))

    # Дундаж хүүхэд (хүүхэдтэй хүн тус бүрд)
    parents = [p for p in people if children.get(p.id)]
    avg_children = round(
        sum(len(children[p.id]) for p in parents) / len(parents), 1
    ) if parents else 0

    # Хамгийн түгээмэл нэр
    name_count = defaultdict(int)
    for p in people:
        name_count[_base_name(p.name)] += 1
    top_name, top_name_c = max(name_count.items(), key=lambda kv: kv[1])

    # Хамгийн залуу гишүүн
    with_year = [(p, _year_of(p.birth)) for p in people]
    with_year = [(p, y) for p, y in with_year if y]
    youngest = max(with_year, key=lambda t: t[1]) if with_year else (people[0], 0)

    # Арван жил тус бүрийн төрөлт (гистограм)
    dec = defaultdict(int)
    for y in years:
        dec[(y // 10) * 10] += 1
    decades = sorted(dec.items())
    peak_decade = max(decades, key=lambda kv: kv[1]) if decades else (0, 0)
    max_dec_c = max((c for _, c in decades), default=1)
    decade_bars = [
        {'label': str(d), 'count': c,
         'pct': max(6, round(c / max_dec_c * 100)), 'peak': c == max_dec_c}
        for d, c in decades
    ]

    this_year = datetime.date.today().year

    # ---- Наслалт ----
    # Өөд болсон хүмүүсийн нас (төрсөн ба өөд болсон он хоёул мэдэгдэж байвал)
    lifespans = []
    for p in people:
        by, dy = _year_of(p.birth), _year_of(p.death)
        if by and dy and 0 < dy - by < 120:
            lifespans.append((p, dy - by))
    avg_lifespan = round(sum(a for _, a in lifespans) / len(lifespans)) if lifespans else 0
    oldest = max(lifespans, key=lambda t: t[1]) if lifespans else None

    # Амьд гишүүдийн дундаас хамгийн ахмад нь
    living_aged = []
    for p in people:
        by = _year_of(p.birth)
        if by and not p.death and 0 < this_year - by < 120:
            living_aged.append((p, this_year - by))
    eldest_living = max(living_aged, key=lambda t: t[1]) if living_aged else None

    # ---- Ургийн гол мөчрүүд ----
    # Язгуур өвгийн хүүхэд бүр нэг мөчрийн тэргүүн болно.
    root = next((p for p in people if not p.parent_id), None)
    branches = []
    if root:
        for head in sorted(children.get(root.id, []), key=lambda p: (p.order, p.id)):
            branches.append({
                'name': head.name,
                'gender': head.gender,
                'count': 1 + desc_count(head.id),   # тэргүүнийг нь оруулаад
            })
        branches.sort(key=lambda b: -b['count'])

    # ---- Үе бүрийн тархалт ----
    gen_rows = [{'gen': g, 'count': by_gen[g]} for g in sorted(by_gen)]

    # ---- Мэдээллийн бүрдэлт (админд хэр их мэдээлэл дутуу байгааг харуулна) ----
    with_photo = sum(1 for p in people if p.photo)
    with_phone = sum(1 for p in people if (p.phone or '').strip())
    with_bio = sum(1 for p in people if (p.bio or '').strip())
    with_birth = sum(1 for p in people if _year_of(p.birth))

    def pct(n):
        return round(n / total * 100)

    # ---- Хамгийн түгээмэл нэрс (эхний 5) ----
    top_names = sorted(name_count.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    # ---- Сүүлийн 10 жилд төрсөн (ургийн залуу үе) ----
    recent_births = sum(1 for y in years if y > this_year - 10)

    spouses_total = sum(len(p.spouse_details.all()) for p in people)

    return {
        'total': total,
        'generations': generations,
        'males': males,
        'females': females,
        'male_pct': round(males / total * 100),
        'married': married,
        'living': living,
        'deceased': deceased,
        'living_pct': pct(living),
        'photos': photos,
        'twin_pairs': twins // 2,
        'min_year': min_y,
        'max_year': max_y,
        'span': max_y - min_y,
        'avg_children': avg_children,
        'biggest_gen': {'gen': biggest_gen[0], 'count': biggest_gen[1]},
        'top_kids': {'name': top_kids.name, 'count': len(children.get(top_kids.id, []))},
        'top_desc': {'name': top_desc.name, 'count': desc_count(top_desc.id)},
        'top_name': {'name': top_name, 'count': top_name_c},
        'youngest': {'name': youngest[0].name, 'year': youngest[1]},
        'decades': [[d, c] for d, c in decades],
        'decade_bars': decade_bars,
        'peak_decade': {'decade': peak_decade[0], 'count': peak_decade[1]},

        # ==== Шинэ ====
        'spouses_total': spouses_total,
        'recent_births': recent_births,
        'avg_lifespan': avg_lifespan,
        'oldest': {'name': oldest[0].name, 'age': oldest[1]} if oldest else None,
        'eldest_living': ({'name': eldest_living[0].name, 'age': eldest_living[1]}
                          if eldest_living else None),
        'branches': branches,
        'gen_rows': gen_rows,
        'top_names': [{'name': n, 'count': c} for n, c in top_names],
        'completeness': {
            'photo': with_photo, 'photo_pct': pct(with_photo),
            'phone': with_phone, 'phone_pct': pct(with_phone),
            'bio': with_bio, 'bio_pct': pct(with_bio),
            'birth': with_birth, 'birth_pct': pct(with_birth),
        },
    }


def current_person(request):
    """Нэвтэрсэн хэрэглэгчийн Person бичлэгийг буцаана (эсвэл None)."""
    if request.user.is_authenticated:
        return getattr(request.user, 'person', None)
    return None


def is_admin(request):
    """Админ (superuser эсвэл staff) эсэх."""
    user = request.user
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def can_edit(request, person):
    """Админ бүх хүний мэдээллийг засна.
    Бусад нь өөрийгөө болон өөрөөсөө доош үр удмаа л засна."""
    if is_admin(request):
        return True
    return person.editable_by(current_person(request))


def _serialize(request):
    """Бүх Person-г ургийн модны нэст JSON бүтэц болгож хувиргана.
    Frontend-ийн хүлээж буй түлхүүрүүд: name, g, gen, role, birth, death,
    spouse, bio, ch — дээр нь id, phone, social, address, photo, editable."""
    people = list(Person.objects.select_related('parent').prefetch_related('spouse_details').all())

    # Засах эрхтэй id-уудын багц.
    # Админ — бүх хүн. Бусад — өөрийн + доош бүх үр удам.
    me = current_person(request)
    editable_ids = set()
    if is_admin(request):
        editable_ids = {p.id for p in people}
    elif me is not None:
        editable_ids.add(me.id)
        editable_ids.update(me.descendant_ids())

    nodes = {}
    for p in people:
        node = {
            'id': p.id,
            'name': p.name,
            'g': p.gender,
            'gen': p.gen,
        }
        if p.role:
            node['role'] = p.role
        if p.birth:
            node['birth'] = p.birth
        if p.death:
            node['death'] = p.death
        if p.spouse:
            node['spouse'] = p.spouse
        if p.bio:
            node['bio'] = p.bio
        if p.phone:
            node['phone'] = p.phone
        if p.social:
            node['social'] = p.social
        if p.address:
            node['address'] = p.address
        if p.photo:
            node['avatar'] = p.photo.url          # хувийн зураг — thumbnail дээр
        if p.family_photo:
            node['photo'] = p.family_photo.url     # гэр бүлийн зураг — дэлгэрэнгүйд
        # Бүрэн бүртгэлтэй хань (нөхөр/эхнэр)
        sp_list = []
        for sp in p.spouse_details.all():
            s = {'id': sp.id, 'name': sp.name, 'g': sp.gender}
            if sp.birth:
                s['birth'] = sp.birth
            if sp.death:
                s['death'] = sp.death
            if sp.phone:
                s['phone'] = sp.phone
            if sp.social:
                s['social'] = sp.social
            if sp.address:
                s['address'] = sp.address
            if sp.bio:
                s['bio'] = sp.bio
            if sp.photo:
                s['photo'] = sp.photo.url
            sp_list.append(s)
        if sp_list:
            node['spouses'] = sp_list
        if p.id in editable_ids:
            node['editable'] = True
        nodes[p.id] = node

    root = None
    for p in people:
        node = nodes[p.id]
        if p.parent_id and p.parent_id in nodes:
            nodes[p.parent_id].setdefault('ch', []).append(node)
        else:
            root = node
    return root


def tree_view(request):
    root = _serialize(request)
    # </script> тарайлтаас сэргийлэх
    data_json = json.dumps(root, ensure_ascii=False).replace('</', '<\\/')
    stats = compute_stats(list(Person.objects.prefetch_related('spouse_details').all()))

    events = list(Event.objects.prefetch_related('media').all())
    # Дараагийн Ургийн баяр (3 жилд нэг удаа) — сүүлийн баярын оноос тооцно
    ub_years = [e.year for e in events if e.kind == 'urgiin_bayar']
    next_bayar = (max(ub_years) + 3) if ub_years else None

    return render(request, 'tree/tree.html', {
        'data_json': data_json,
        'stats': stats,
        'me': current_person(request),
        'notifications': Notification.objects.all()[:50],
        'events': events,
        'next_bayar': next_bayar,
    })


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
    })


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


def event_gallery(request, pk):
    """Нэг баярын бүх зураг/видеог тусдаа хуудсанд (lightbox-той) харуулна."""
    event = get_object_or_404(Event.objects.prefetch_related('media'), pk=pk)
    media = list(event.media.all())
    media_json = json.dumps([
        {'type': m.media_type, 'url': m.url, 'poster': m.thumbnail_url, 'caption': m.caption}
        for m in media
    ], ensure_ascii=False).replace('</', '<\\/')
    return render(request, 'tree/gallery.html', {
        'event': event,
        'media': media,
        'media_json': media_json,
    })


def login_view(request):
    # Гэр бүлийн хүнээр аль хэдийн нэвтэрсэн бол нүүр рүү.
    # (admin superuser — Person холбоосгүй — нэвтрэх боломжтой хэвээр үлдэнэ)
    if request.method == 'GET' and current_person(request) is not None:
        return redirect('/')
    error = None
    if request.method == 'POST':
        phone = request.POST.get('username', '').strip()
        birth = request.POST.get('password', '').strip()
        user = authenticate(request, username=phone, password=birth)
        if user is not None:
            login(request, user)
            return redirect('/')
        error = 'Утас эсвэл төрсөн огноо буруу байна. (Нууц үг = төрсөн огноо, ж: 1965.02.26)'
    return render(request, 'tree/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('/')


EDITABLE_FIELDS = ['name', 'birth', 'death', 'spouse', 'bio', 'phone', 'social', 'address']


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
        if request.FILES.get('photo'):
            child.photo = request.FILES['photo']
        if request.FILES.get('family_photo'):
            child.family_photo = request.FILES['family_photo']
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
