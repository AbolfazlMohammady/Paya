from django.urls import path
from users.auth.view import LoginRegisterApiView, VerifyApiView


urlpatterns = [
    path('login/',LoginRegisterApiView.as_view()),
    path('verify/',VerifyApiView.as_view())

]
