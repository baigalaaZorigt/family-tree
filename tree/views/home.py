import copy
import json

from django.core.cache import cache
from django.shortcuts import render

from ..models import Event, Notification, Person
from .permissions import current_person, is_admin
from .stats import compute_stats

# Нүүр хуудасны мод/статистикийг кэшлэнэ — Person/Spouse хадгалагдах бүрд
# (models.py-ийн save/delete) цэвэрлэгдэнэ. TTL нь зөвхөн нөөц хамгаалалт.
HOME_TREE_CACHE_KEY = 'home_tree_base'
HOME_STATS_CACHE_KEY = 'home_stats'
HOME_CACHE_TTL = 600


def _serialize_base(people):
    """Бүх Person-г ургийн модны нэст JSON бүтэц болгож хувиргана (хэрэглэгчээс
    үл хамаарах хэсэг — 'editable' энд ОРОХГҮЙ, кэшлэгдэнэ). Frontend-ийн хүлээж
    буй түлхүүрүүд: name, g, gen, role, birth, death, spouse, bio, ch — дээр нь
    id, phone, social, address, photo."""
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
        nodes[p.id] = node

    root = None
    for p in people:
        node = nodes[p.id]
        if p.parent_id and p.parent_id in nodes:
            nodes[p.parent_id].setdefault('ch', []).append(node)
        else:
            root = node
    return root


def _apply_editable(node, editable_ids):
    """Кэшлэгдсэн модон дээр тухайн хэрэглэгчид зориулсан 'editable' тэмдгийг
    дарж бичнэ (кэш дэх эх хувийг өөрчлөхгүй, дуудагч аль хэдийн хуулбар өгсөн)."""
    if node['id'] in editable_ids:
        node['editable'] = True
    for ch in node.get('ch', []):
        _apply_editable(ch, editable_ids)


def _editable_ids(request, me):
    """Одоогийн хэрэглэгчийн засах эрхтэй id-уудын багц (зочин бол хоосон,
    нэмэлт DB хайлт хийхгүй)."""
    if is_admin(request):
        return set(Person.objects.values_list('id', flat=True))
    if me is not None:
        return {me.id, *me.descendant_ids()}
    return set()


def tree_view(request):
    base_tree = cache.get(HOME_TREE_CACHE_KEY)
    stats = cache.get(HOME_STATS_CACHE_KEY)
    if base_tree is None or stats is None:
        people = list(Person.objects.select_related('parent').prefetch_related('spouse_details').all())
        if base_tree is None:
            base_tree = _serialize_base(people)
            cache.set(HOME_TREE_CACHE_KEY, base_tree, HOME_CACHE_TTL)
        if stats is None:
            stats = compute_stats(people)
            cache.set(HOME_STATS_CACHE_KEY, stats, HOME_CACHE_TTL)

    # editable тэмдгийг хэрэглэгч тус бүрд өөрчилдөг тул кэшийг хуулбарлаад дараад бичнэ
    root = copy.deepcopy(base_tree)
    me = current_person(request)
    editable_ids = _editable_ids(request, me)
    if editable_ids:
        _apply_editable(root, editable_ids)

    # </script> тарайлтаас сэргийлэх
    data_json = json.dumps(root, ensure_ascii=False).replace('</', '<\\/')

    events = list(Event.objects.prefetch_related('media').all())
    # Дараагийн Ургийн баяр (3 жилд нэг удаа) — сүүлийн баярын оноос тооцно
    ub_years = [e.year for e in events if e.kind == 'urgiin_bayar']
    next_bayar = (max(ub_years) + 3) if ub_years else None

    return render(request, 'tree/tree.html', {
        'data_json': data_json,
        'stats': stats,
        'me': me,
        'notifications': Notification.objects.all()[:50],
        'events': events,
        'next_bayar': next_bayar,
    })
