import os

from django.core.wsgi import get_wsgi_application

# Set the DJANGO_SETTINGS_MODULE to the production settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arxiv_summarizer.settings.production')

# Initialize the WSGI application
application = get_wsgi_application()