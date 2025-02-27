from django.urls import path

from . import views
from rest_framework_simplejwt import views as jwt_views


urlpatterns = [
    path('info', views.info, name="info"),
    path('writing/<int:day>', views.writing, name="writing"),
    path('game', views.game, name="game"),
    path('video', views.finishVideo, name='video'),
    path('token/', jwt_views.TokenObtainPairView.as_view(), name ='token_obtain_pair'),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name ='token_refresh'),
    path('sms', views.handleSendSMSRequest, name='handleSendSMSRequest'),
    path('login', views.login, name='login'),
    path('qualtrics_submission', views.qualtrics_submission, name='qualtrics_submission'),
    path('key', views.key, name="key"),
    path('collect_info', views.collect_info, name="collect_info")
]