from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_paper, name="upload_paper"),
    path("success/<str:pk>/", views.upload_success, name="upload_success"),
    path("download/summary/<str:pk>/", views.download_summary_pdf, name="download_summary_pdf"),
    path("download/original/<str:arxiv_id>/", views.download_original_pdf, name="download_original_pdf"),
    path("search/", views.search_articles, name="search_articles"),
    path('paper/<str:arxiv_id>/', views.paper_summary, name='paper_summary'),
]