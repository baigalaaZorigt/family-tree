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
