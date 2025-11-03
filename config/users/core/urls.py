from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from users.auth.view import LoginRegisterApiView, VerifyApiView
from users.profile.view import ProfileViewSet

profile_get = ProfileViewSet.as_view({'get':'retrive',
                                      'patch':'update',
                                      })



urlpatterns = [
    path('login/',LoginRegisterApiView.as_view()),
    path('verify/',VerifyApiView.as_view()),
    path('refresh/',TokenRefreshView.as_view(), name="token_refresh"),
    path('me/',profile_get,name="profile"),

]
