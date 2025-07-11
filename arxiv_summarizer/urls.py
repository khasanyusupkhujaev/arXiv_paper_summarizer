from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('papers/', include('papers.urls')),
    path('', lambda request: redirect('papers/upload/')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)