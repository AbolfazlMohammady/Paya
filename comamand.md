# FastApi

uvicorn main:app --reload
tasklist | findstr uvicorn
اگر پردازشی با uvicorn.exe دیدی، این دستور را بزن:
taskkill /F /IM uvicorn.exe

uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload

# Docker

chmod +x ./config/entrypoint.sh

docker compose exec django python manage.py migrate

docker compose exec django python manage.py createsuperuser

docker compose exec django python manage.py collectstatic

docker compose logs -f django

docker build -f config/Dockerfile.base -t marian_base:latest .

docker-compose up -d --build

docker-compose down

docker exec -it django /bin/sh

docker-compose exec django python manage.py makemessages -l fa --ignore=*.txt --ignore=*.md --ignore=venv --ignore=env

docker-compose exec django python manage.py makemessages -l fa -l ar --ignore=*.txt --ignore=*.md --ignore=venv --ignore=env

docker-compose exec django python manage.py compilemessages

docker exec -it django python manage.py backfill_translations

docker compose exec -T django sh -lc "pip install -r requirements-test.txt"

# for axes

python manage.py axes_reset

python manage.py axes_reset_username admin

# Celery

celery -A config.celery_config:app worker -l INFO -Q tasks
