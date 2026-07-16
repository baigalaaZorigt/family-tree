from django.contrib import admin
from django.utils.html import format_html

from .models import Event, EventMedia, Notification, Person, PersonPhoto, Spouse


class PersonPhotoInline(admin.TabularInline):
    model = PersonPhoto
    extra = 1
    fields = ('image', 'caption', 'order')


class EventMediaInline(admin.TabularInline):
    model = EventMedia
    extra = 1
    fields = ('media_type', 'url', 'thumbnail_url', 'caption', 'order')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    inlines = [EventMediaInline]
    list_display = ('display_title', 'kind', 'year', 'date', 'media_count')
    list_filter = ('kind', 'year')
    search_fields = ('title', 'description')
    ordering = ('-year', 'kind')

    @admin.display(description='Зураг/видео')
    def media_count(self, obj):
        return obj.media.count()


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'person', 'created_at')
    list_filter = ('kind',)
    search_fields = ('title', 'body')
    readonly_fields = ('created_at',)


class SpouseInline(admin.StackedInline):
    model = Spouse
    extra = 0
    fields = ('name', 'gender', 'birth', 'death', 'phone', 'social', 'address', 'bio', 'photo', 'order')


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    inlines = [SpouseInline, PersonPhotoInline]
    list_display = ('name', 'gen', 'gender', 'birth', 'phone', 'has_photo', 'parent')
    list_filter = ('gen', 'gender')
    search_fields = ('name', 'spouse', 'phone', 'social', 'address', 'bio')
    list_select_related = ('parent',)
    autocomplete_fields = ('parent',)
    ordering = ('gen', 'order', 'id')
    readonly_fields = ('photo_preview',)

    fieldsets = (
        ('Үндсэн мэдээлэл', {
            'fields': ('name', 'gender', 'gen', 'role', 'birth', 'death', 'spouse', 'bio')
        }),
        ('Холбоо барих (шинэ)', {
            'fields': ('phone', 'social', 'address')
        }),
        ('Зураг', {
            'fields': ('photo', 'family_photo', 'photo_preview')
        }),
        ('Модны бүтэц ба нэвтрэлт', {
            'fields': ('parent', 'order', 'user')
        }),
    )

    @admin.display(description='Зурагтай', boolean=True)
    def has_photo(self, obj):
        return bool(obj.family_photo)

    @admin.display(description='Урьдчилан харах')
    def photo_preview(self, obj):
        html = ''
        if obj.photo:
            html += format_html('<div>Хувийн: <img src="{}" style="max-height:150px;border-radius:8px" /></div>',
                                obj.photo.url)
        if obj.family_photo:
            html += format_html('<div>Гэр бүл: <img src="{}" style="max-height:180px;border-radius:8px" /></div>',
                                obj.family_photo.url)
        return format_html(html) if html else 'Зураг байхгүй'
