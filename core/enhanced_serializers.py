# 增强的序列化器，支持新的任务进度追踪功能

from rest_framework import serializers
from .models import WebUser, Whitelist, Screen, LSUser

class EnhancedWebUserSerializer(serializers.ModelSerializer):
    """增强的WebUser序列化器"""
    
    # 添加计算字段
    task_progress = serializers.SerializerMethodField()
    user_status_type = serializers.SerializerMethodField()
    can_access_surveys = serializers.SerializerMethodField()
    ban_message_type = serializers.SerializerMethodField()
    
    class Meta:
        model = WebUser
        fields = '__all__'
    
    def get_task_progress(self, obj):
        """获取任务进度信息"""
        return obj.get_task_progress_info()
    
    def get_user_status_type(self, obj):
        """获取用户状态类型"""
        if not obj.group or obj.group == "":
            return "ungrouped"
        if obj.banFlag:
            return "banned"
        if obj.group == "Waitlist":
            return "waitlist"
        if obj.group in ["Exp1", "Exp2"]:
            return "experimental"
        return "unknown"
    
    def get_can_access_surveys(self, obj):
        """检查是否可以访问调查问卷"""
        return obj.can_access_survey(23)  # 检查第23天问卷
    
    def get_ban_message_type(self, obj):
        """获取ban消息类型"""
        if not obj.banFlag or not obj.banTags:
            return None
        
        ban_message_mapping = {
            'pre_survey_invalid': 'pre_survey_invalid',
            'post_survey_invalid': 'post_survey_invalid',
            'task1_not_done': 'task1_not_done',
            'task_not_done': 'task_not_done',
            'writing_quality_fail': 'writing_quality_fail',
            'game_score_low': 'game_score_low'
        }
        
        for tag in obj.banTags:
            if tag in ban_message_mapping:
                return ban_message_mapping[tag]
        
        return 'general_ban'

class TaskStatusSerializer(serializers.Serializer):
    """任务状态序列化器"""
    day = serializers.IntegerField()
    status = serializers.CharField()
    can_access = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)

class TaskProgressSerializer(serializers.Serializer):
    """任务进度序列化器"""
    day = serializers.IntegerField()
    phase = serializers.FloatField()
    currentDay = serializers.FloatField()
    is_banned = serializers.BooleanField()
    ban_day = serializers.FloatField()
    ban_tags = serializers.ListField(child=serializers.CharField())

class BanInfoSerializer(serializers.Serializer):
    """Ban信息序列化器"""
    is_banned = serializers.BooleanField()
    ban_reason = serializers.CharField(allow_blank=True)
    ban_day = serializers.FloatField()
    ban_tags = serializers.ListField(child=serializers.CharField())
    ban_message_type = serializers.CharField(allow_blank=True)

class TaskHistorySerializer(serializers.Serializer):
    """任务历史序列化器"""
    task_completion_times = serializers.DictField()
    current_progress = TaskProgressSerializer()
    ban_info = BanInfoSerializer()

class GroupUpdateSerializer(serializers.Serializer):
    """分组更新序列化器"""
    uuid = serializers.CharField(max_length=200)
    group = serializers.ChoiceField(choices=[
        ("Exp1", "实验组1"),
        ("Exp2", "实验组2"),
        ("Waitlist", "等待组")
    ])
    responseId = serializers.CharField(max_length=30)
    isValid = serializers.BooleanField()

class SurveySubmissionSerializer(serializers.Serializer):
    """问卷提交序列化器"""
    invalid = serializers.IntegerField()
    surveyDay = serializers.IntegerField()
    uuid = serializers.CharField(max_length=200)
    responseId = serializers.CharField(max_length=30)

class TaskCompletionSerializer(serializers.Serializer):
    """任务完成序列化器"""
    task_day = serializers.IntegerField()
    task_phase = serializers.CharField(allow_blank=True, required=False)

class ValidityCheckSerializer(serializers.Serializer):
    """有效性检查序列化器"""
    is_banned = serializers.BooleanField()
    ban_reasons = serializers.ListField(child=serializers.CharField())
    ban_tags = serializers.ListField(child=serializers.CharField())
    current_progress = TaskProgressSerializer()

# 保持原有的序列化器
class WebUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebUser
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        context = kwargs.get('context', {})
        if context.get('info'):
            # 在info上下文中，移除敏感字段
            sensitive_fields = ['sms', 'encryptedPhoneNumber', 'encryptedWeChat']
            for field in sensitive_fields:
                if field in self.fields:
                    self.fields.pop(field)

class ScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Screen
        fields = '__all__'
