"""
URL configuration for YouTube Analyzer project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('youtube.urls')),
    path('api-auth/', include('rest_framework.urls')),
]