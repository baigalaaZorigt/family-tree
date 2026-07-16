"""familytree төслийн URL тохиргоо."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from tree import views

urlpatterns = [
    path('admin/', admin.site.urls),
    # PWA: service worker болон manifest нь сайтын үндэс (root)-д байх ёстой,
    # эс бөгөөс service worker-ийн scope зөвхөн /static/-аар хязгаарлагдана.
    path(
        'sw.js',
        TemplateView.as_view(
            template_name='tree/sw.js',
            content_type='application/javascript',
        ),
        name='sw',
    ),
    path(
        'manifest.json',
        TemplateView.as_view(
            template_name='tree/manifest.json',
            content_type='application/manifest+json',
        ),
        name='manifest',
    ),
    path('', views.tree_view, name='tree'),
    path('hun/<int:pk>/', views.person_detail, name='person_detail'),
    path('bayar/<int:pk>/', views.event_gallery, name='event_gallery'),
    path('hun/<int:pk>/zurag/', views.person_album, name='person_album'),
    path('zurag-nemeh/<int:person_pk>/', views.add_photos, name='add_photos'),
    path('zurag-ustgah/<int:pk>/', views.delete_photo, name='delete_photo'),
    path('newtreh/', views.login_view, name='login'),
    path('garah/', views.logout_view, name='logout'),
    path('zasah/<int:pk>/', views.edit_person, name='edit_person'),
    path('nemeh/<int:parent_pk>/', views.add_child, name='add_child'),
    path('hani-nemeh/<int:person_pk>/', views.add_spouse, name='add_spouse'),
    path('hani-zasah/<int:pk>/', views.edit_spouse, name='edit_spouse'),
]

# Хөгжүүлэлтийн үед байршуулсан зураг (media)-г үзүүлэх
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
