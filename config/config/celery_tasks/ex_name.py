from config.celery_config import app


@app.task(queue='tasks')
def my_tasks():
    pass