"""tree.views — сэдвээр нь модул болгож хуваасан.
familytree/urls.py нь `from tree import views` + `views.<нэр>` хэлбэрээр
дуудах тул энд бүх public симболыг дахин экспортолно."""
from .auth import login_view, logout_view
from .gallery import GALLERY_CACHE_TTL, GALLERY_PAGE_SIZE, event_gallery
from .home import _serialize_base, tree_view
from .permissions import can_edit, current_person, is_admin
from .person import (
    EDITABLE_FIELDS,
    add_child,
    edit_person,
    person_detail,
    remove_avatar,
)
from .photos import add_photos, delete_photo, person_album
from .spouse import (
    SPOUSE_FIELDS,
    _apply_spouse_fields,
    add_spouse,
    edit_spouse,
)
from .stats import YEAR_RE, _base_name, _year_of, compute_stats

__all__ = [
    'login_view', 'logout_view',
    'GALLERY_CACHE_TTL', 'GALLERY_PAGE_SIZE', 'event_gallery',
    '_serialize_base', 'tree_view',
    'can_edit', 'current_person', 'is_admin',
    'EDITABLE_FIELDS', 'add_child', 'edit_person', 'person_detail', 'remove_avatar',
    'add_photos', 'delete_photo', 'person_album',
    'SPOUSE_FIELDS', '_apply_spouse_fields', 'add_spouse', 'edit_spouse',
    'YEAR_RE', '_base_name', '_year_of', 'compute_stats',
]
