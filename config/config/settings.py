import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = os.environ.get('SECRET_KEY',"fallback_secret_key")
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = [
    '127.0.0.1'
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # App System
    # 'uvicorn',
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    'debug_toolbar',
    "phonenumber_field",
    'axes',
    'modeltranslation',
    "corsheaders",
    
    # My app
    'users.core.apps.CoreConfig',

]

INTERNAL_IPS = [
    '127.0.0.1', 
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "django.middleware.locale.LocaleMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',  
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'data/database/db.sqlite3',
        # Use an isolated in-memory database for Django's test runner/pytest
        'TEST': {
            'NAME': ':memory:',
        },
    }
}
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('POSTGRES_DB', 'paya_user'),
#         'USER': os.getenv('POSTGRES_USER', 'paya_user'),
#         'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'supersecretpassword'),
#         'HOST': os.getenv('POSTGRES_HOST', 'postgres'),
#         'PORT': os.getenv('POSTGRES_PORT', '5432'),
#     }
# }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# زبان پیش‌فرض
LANGUAGE_CODE = 'en'

USE_I18N = True
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
# Where compiled/po locale files live
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
# Store collected static where Nginx serves
STATIC_ROOT = os.path.join(BASE_DIR, "data/static/")

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, "data/media/")
# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Config Rest
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}


# Config JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "SIGNING_KEY": SECRET_KEY, 
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Config User
AUTH_USER_MODEL = 'core.User'


# Config Swagir
SPECTACULAR_SETTINGS = {
    'TITLE': 'Paya API',
    'DESCRIPTION': 'django rest and fast api',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': True,
}

# Config Celery
# 'amqp://guest:guest@rabbitmq:5672//'
CELERY_BROKER_URL = os.environ.get('CELERY_URL', "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get('CELERY_BACKEND', "redis://redis:6379/0")



# config axes
# تعداد تلاش‌های ناموفق قبل از بلاک شدن
# config axes (for django-axes v5)
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(hours=1)


AXES_CACHE = 'default'

# authentication backend
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]


# cashing "redis://redis:6379/1",  
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/1",  
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


CORS_ALLOWED_ORIGINS = [
    "https://macoui.net",
    "https://www.macoui.net",
    "https://tailwindrose.com",
    "https://www.tailwindrose.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOW_CREDENTIALS = True

# Allow all methods for development
CORS_ALLOW_ALL_ORIGINS = False  # Keep this False for security, use CORS_ALLOWED_ORIGINS instead

CORS_ALLOW_HEADERS = [
    'content-type',
    'authorization',
    'accept',
    'origin',
    'user-agent',
    'dnt',
    'x-csrftoken',
    'x-requested-with',
    'cache-control',
    'pragma',
]

# Allow all methods for development
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# External services / API keys
# RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

RESEND_API_KEY=os.environ.get('RESEND_API_KEY', 're_dUAfRuPj_KP9q36Sa2x9UGNXp263qAPMM')

# Chat bot
MAMMOUTH_API_KEY = os.getenv('MAMMOUTH_API_KEY')
