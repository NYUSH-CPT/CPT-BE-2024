# 优化后的模型设计建议

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
import random

class WebUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text="Auth user")
    uuid = models.CharField(null=True, blank=True, max_length=200, help_text="Blued uuid")
    sms = models.CharField(null=True, blank=True, max_length=20)
    encryptedPhoneNumber = models.CharField(max_length=500, help_text="Encrypted phone number")
    encryptedWeChat = models.CharField(max_length=500, help_text="Encrypted WeChat number")
    whitelist = models.OneToOneField("Whitelist", on_delete=models.CASCADE, related_name="webUser")
    
    # 优化：更清晰的分组状态
    group = models.TextField(
        choices=[
            ("", "未分组"),  # 新增：未分组状态
            ("Exp1", "实验组1"), 
            ("Exp2", "实验组2"), 
            ("Waitlist", "等待组")
        ], 
        default="",  # 默认为未分组
        help_text="用户分组状态"
    )
    
    # 优化：分离任务进度和阶段
    current_task_day = models.IntegerField(default=1, help_text="当前任务天数（整数）")
    current_task_phase = models.CharField(
        max_length=20,
        choices=[
            ("pre_start", "实验前"),
            ("survey", "问卷调查"),
            ("writing", "写作任务"),
            ("video", "视频任务"),
            ("game", "游戏任务"),
            ("intervention", "干预阶段"),
            ("followup_1", "随访1"),
            ("followup_2", "随访2"),
            ("followup_3", "随访3"),
            ("completed", "已完成")
        ],
        default="pre_start",
        help_text="当前任务阶段"
    )
    
    startDate = models.DateField(default=timezone.now, help_text="Experiment start date")
    trainCompleteNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
    surveyCompleteNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
    
    # 优化：更清晰的ban状态管理
    is_banned = models.BooleanField(default=False, help_text="用户是否被ban")
    ban_reason = models.TextField(max_length=200, null=True, blank=True, help_text="Ban的原因")
    ban_notified = models.BooleanField(default=False, help_text="是否已通知用户被ban")
    ban_task_day = models.IntegerField(default=-1, help_text="被ban时的任务天数")
    ban_task_phase = models.CharField(max_length=20, default="", help_text="被ban时的任务阶段")
    
    # 其他字段保持不变...
    writing1 = models.JSONField(default=dict, null=True, blank=True)
    # ... 其他字段

    def get_current_progress(self):
        """获取当前进度信息"""
        return {
            'day': self.current_task_day,
            'phase': self.current_task_phase,
            'is_banned': self.is_banned,
            'ban_day': self.ban_task_day,
            'ban_phase': self.ban_task_phase
        }

    def update_task_progress(self, new_day, new_phase):
        """更新任务进度"""
        self.current_task_day = new_day
        self.current_task_phase = new_phase
        self.save()

    def ban_user(self, reason, task_day=None, task_phase=None):
        """ban用户"""
        self.is_banned = True
        self.ban_reason = reason
        self.ban_task_day = task_day or self.current_task_day
        self.ban_task_phase = task_phase or self.current_task_phase
        self.save()

    def unban_user(self):
        """取消ban"""
        self.is_banned = False
        self.ban_reason = ""
        self.ban_task_day = -1
        self.ban_task_phase = ""
        self.save()

    def can_access_survey(self, survey_day):
        """检查是否可以访问调查问卷"""
        # 被ban用户仍然可以访问调查问卷
        if self.is_banned:
            return survey_day in [23, 39, 99]  # 只允许访问随访调查
        
        # 正常用户可以访问所有调查问卷
        return True

    def can_access_task(self, task_day):
        """检查是否可以访问特定任务"""
        if self.is_banned:
            # 被ban用户只能访问调查问卷
            return task_day in [23, 39, 99]
        
        # 正常用户的任务访问逻辑
        return task_day <= self.current_task_day

    def validity_check(self):
        """优化后的有效性检查"""
        ban_reasons = []
        ban_tags = []
        
        # 检查问卷有效性
        if self.survey1IsValid == "False":
            ban_reasons.append("前测问卷无效")
            ban_tags.append("pre_survey_invalid")
        
        # 检查后测问卷
        if self.survey23IsValid == "False" and self.survey39IsValid == "False" and self.survey99IsValid == "False":
            ban_reasons.append("后测问卷无效")
            ban_tags.append("post_survey_invalid")
        
        # 检查任务完成情况（仅对实验组）
        if self.group in ["Exp1", "Exp2"]:
            # 写作质量检查
            invalid_writing = self.check_writing_quality()
            if invalid_writing:
                ban_reasons.append(invalid_writing)
                ban_tags.append("writing_quality_fail")
            
            # 任务超时检查
            if self.is_task_overdue():
                ban_reasons.append("任务超时")
                ban_tags.append("task_overdue")
            
            # 游戏分数检查
            if self.gameFinished and self.score < 61200:
                ban_reasons.append("游戏得分不足")
                ban_tags.append("game_score_low")
        
        # 更新ban状态
        if ban_reasons:
            if not self.is_banned:
                self.ban_user(
                    reason='；'.join(ban_reasons),
                    task_day=self.current_task_day,
                    task_phase=self.current_task_phase
                )
        else:
            if self.is_banned:
                self.unban_user()
        
        return ban_reasons, ban_tags

    def check_writing_quality(self):
        """检查写作质量"""
        # 实现写作质量检查逻辑
        pass

    def is_task_overdue(self):
        """检查任务是否超时"""
        # 实现超时检查逻辑
        pass


class Whitelist(models.Model):
    encryptedPhoneNumber = models.CharField(max_length=500, help_text="Encrypted phone number")
    encryptedWeChat = models.CharField(max_length=500, help_text="Encrypted WeChat number")
    uuid = models.CharField(max_length=200, help_text="Blued uuid")
    has_add_wechat = models.BooleanField(default=False, help_text="Please set it to true after adding user's wechat")
    survey0 = models.CharField(max_length=30, null=True, blank=True)
    
    # 优化：分组状态管理
    group = models.TextField(
        choices=[
            ("", "未分组"),
            ("Exp1", "实验组1"), 
            ("Exp2", "实验组2"), 
            ("Waitlist", "等待组")
        ], 
        default="",  # 默认为未分组
        null=True, 
        blank=True,
        help_text="用户分组状态"
    )
    
    startDate = models.DateField(null=True, blank=True, help_text="Experiment start date")
    
    def __str__(self):
        return self.uuid

    @classmethod
    @transaction.atomic
    def assign_group(cls):
        """分配组别（现在由外部调用，不再自动分配）"""
        from .models import GroupState  

        state, _ = GroupState.objects.select_for_update().get_or_create(id=1)

        if state.block_index >= len(state.current_block):
            block = ['Exp1'] * 2 + ['Exp2'] * 2 + ['Waitlist'] * 2
            random.shuffle(block)
            state.current_block = block
            state.block_index = 0

        group = state.current_block[state.block_index]
        state.block_index += 1
        state.updated_at = timezone.now()
        state.save()
        return group
    
    def save(self, *args, **kwargs):
        # 移除自动分组逻辑，改为手动分组
        super().save(*args, **kwargs)
