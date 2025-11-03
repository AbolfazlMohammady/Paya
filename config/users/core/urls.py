from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from users.auth.view import LoginRegisterApiView, VerifyApiView



urlpatterns = [
    path('login/',LoginRegisterApiView.as_view()),
    path('verify/',VerifyApiView.as_view()),
    path('refresh/',TokenRefreshView.as_view(), name="token_refresh"),

]
