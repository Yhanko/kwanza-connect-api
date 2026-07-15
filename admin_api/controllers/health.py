from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from app.permissions import IsAdminUser
from django.db import connection
from django.conf import settings
import redis
import psutil
from app.celery import app as celery_app

class AdminSystemHealthView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        # 1. Database
        db_status = 'ok'
        try:
            connection.ensure_connection()
        except Exception:
            db_status = 'error'

        # 2. Redis
        redis_status = 'ok'
        try:
            r = redis.from_url(settings.REDIS_URL)
            r.ping()
        except Exception:
            redis_status = 'error'

        # 3. Celery
        celery_status = 'ok'
        try:
            # ping returns a list of dicts: [{'celery@worker': {'ok': 'pong'}}]
            ping_result = celery_app.control.ping(timeout=0.5)
            if not ping_result:
                celery_status = 'error'
        except Exception:
            celery_status = 'error'

        # 4. System Resources
        cpu_usage = psutil.cpu_percent(interval=None)
        
        virtual_mem = psutil.virtual_memory()
        ram_total = virtual_mem.total
        ram_used = virtual_mem.used
        ram_percent = virtual_mem.percent
        
        disk_usage = psutil.disk_usage('/')
        disk_total = disk_usage.total
        disk_used = disk_usage.used
        disk_percent = disk_usage.percent

        return Response({
            'services': {
                'database': db_status,
                'redis': redis_status,
                'celery': celery_status,
            },
            'resources': {
                'cpu_percent': cpu_usage,
                'ram_total_gb': round(ram_total / (1024**3), 2),
                'ram_used_gb': round(ram_used / (1024**3), 2),
                'ram_percent': ram_percent,
                'disk_total_gb': round(disk_total / (1024**3), 2),
                'disk_used_gb': round(disk_used / (1024**3), 2),
                'disk_percent': disk_percent,
            }
        })
