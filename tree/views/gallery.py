import json

from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from ..models import Event

GALLERY_PAGE_SIZE = 24
GALLERY_CACHE_TTL = 600  # 10 мин — S3 жагсаалтыг дахин уншихгүйн тулд кэшлэнэ


def event_gallery(request, pk):
    """Нэг баярын зураг/видеог хуудаслаж, кэштэйгээр (lightbox-той) харуулна.
    Ачаалал тэнцвэржүүлэх: grid дээр жижиг thumbnail ачаална, бүтэн зургийг зөвхөн
    lightbox нээх үед л татна; том жагсаалтыг хуудас хуудсаар нь ачаална.
    Зураг/видео тус тусдаа таб (?type=photo|video)-аар шүүнэ."""
    event = get_object_or_404(Event, pk=pk)

    cache_key = f'event_media_{pk}'
    all_media = cache.get(cache_key)
    if all_media is None:
        all_media = [
            {
                'id': m.id, 'media_type': m.media_type, 'url': m.url,
                'thumbnail_url': m.thumbnail_url, 'caption': m.caption,
            }
            for m in event.media.all()
        ]
        cache.set(cache_key, all_media, GALLERY_CACHE_TTL)

    photo_media = [m for m in all_media if m['media_type'] == 'photo']
    video_media = [m for m in all_media if m['media_type'] == 'video']

    media_type = request.GET.get('type', 'photo')
    if media_type not in ('photo', 'video'):
        media_type = 'photo'
    tab_media = video_media if media_type == 'video' else photo_media

    paginator = Paginator(tab_media, GALLERY_PAGE_SIZE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # JS lightbox-ийн хүлээж буй товч нэрс (type/poster) рүү хөрвүүлнэ
    js_media = [
        {'type': m['media_type'], 'url': m['url'], 'poster': m['thumbnail_url'], 'caption': m['caption']}
        for m in page_obj.object_list
    ]
    media_json = json.dumps(js_media, ensure_ascii=False).replace('</', '<\\/')
    return render(request, 'tree/gallery.html', {
        'event': event,
        'media': page_obj.object_list,
        'media_json': media_json,
        'page_obj': page_obj,
        'total_count': len(tab_media),
        'media_type': media_type,
        'photo_count': len(photo_media),
        'video_count': len(video_media),
    })
