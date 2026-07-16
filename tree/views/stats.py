import datetime
import re
from collections import defaultdict

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
