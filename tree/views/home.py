import json

from django.shortcuts import render

from ..models import Event, Notification, Person
from .permissions import current_person, is_admin
from .stats import compute_stats


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
