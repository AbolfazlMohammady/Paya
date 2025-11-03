import os
from celery import Celery
from kombu import Queue, Exchange


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.task_queues = [
    Queue('tasks', Exchange('tasks', type='direct'), routing_key='tasks')
]
app.conf.broker_transport_options = {
    'priority_steps': list(range(10))  
}


app.conf.task_default_priority = 5 
app.conf.task_acks_late = True
app.conf.task_default_priority= 5
app.conf.worker_prefetch_multiplier= 1
app.conf.worker_concurrency =1
app.conf.task_reject_on_worker_lost = True
app.conf.task_acks_on_failure_or_timeout = True
app.autodiscover_tasks(['config.celery_tasks'])

base_dir = os.getcwd()
task_folder = os.path.join(base_dir, 'config','celery_tasks')

if os.path.isdir(task_folder):
    for filename in os.listdir(task_folder):
        if filename.startswith('ex') and filename.endswith('.py'):
            module_name = f'config.celery_tasks.{filename[:-3]}'
            __import__(module_name, fromlist=['*'])  

app.autodiscover_tasks()