# 增强的URL配置，支持新的功能

from django.urls import path
from . import views, enhanced_views
from rest_framework_simplejwt import views as jwt_views

urlpatterns = [
    # 原有接口（保持向后兼容）
    path('info', views.info, name="info"),
    path('writing/<int:day>', views.writing, name="writing"),
    path('game', views.game, name="game"),
    path('video', views.finishVideo, name='video'),
    path('token/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
    path('sms', views.handleSendSMSRequest, name='handleSendSMSRequest'),
    path('login', views.login, name='login'),
    path('qualtrics_submission', views.qualtrics_submission, name='qualtrics_submission'),
    path('key', views.key, name="key"),
    path('collect_info', views.collect_info, name="collect_info"),
    path('signup', views.signup, name="signup"),
    path('reset_password', views.reset_password, name="reset_password"),
    path('screen_record', views.screen_record, name="screen_record"),
    path('assign_group', views.assign_group, name="assign_group"),
    
    # 增强接口
    path('enhanced/info', enhanced_views.enhanced_info, name="enhanced_info"),
    path('enhanced/writing/<int:day>', enhanced_views.enhanced_writing, name="enhanced_writing"),
    path('enhanced/video', enhanced_views.enhanced_finish_video, name="enhanced_finish_video"),
    path('enhanced/qualtrics_submission', enhanced_views.enhanced_qualtrics_submission, name="enhanced_qualtrics_submission"),
    
    # 新增接口
    path('update_group', enhanced_views.update_user_group, name="update_user_group"),
    path('task_status/<int:day>', enhanced_views.task_status, name="task_status"),
    path('check_validity', enhanced_views.check_user_validity, name="check_user_validity"),
    path('task_history', enhanced_views.task_history, name="task_history"),
]
