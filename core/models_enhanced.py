# 增强的任务进度追踪系统

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
    
    # 分组状态
    group = models.TextField(
        choices=[
            ("", "未分组"),
            ("Exp1", "实验组1"), 
            ("Exp2", "实验组2"), 
            ("Waitlist", "等待组")
        ], 
        default="",
        help_text="用户分组状态"
    )
    
    # 任务进度追踪 - 使用小数表示同一天多个任务
    currentDay = models.FloatField(default=1.0, help_text="当前任务进度，小数表示同一天多个任务")
    startDate = models.DateField(default=timezone.now, help_text="实验开始日期")
    
    # 通知状态
    trainCompleteNotified = models.BooleanField(default=False)
    surveyCompleteNotified = models.BooleanField(default=False)
    
    # Ban状态管理
    banFlag = models.BooleanField(default=False, help_text="是否被ban")
    banReason = models.TextField(max_length=200, null=True, blank=True, help_text="Ban原因")
    banNotified = models.BooleanField(default=False, help_text="是否已通知ban")
    banDay = models.FloatField(default=-1, help_text="被ban时的任务进度")
    banTags = models.JSONField(default=list, help_text="Ban标签列表，用于发送不同消息")
    
    # 任务完成时间追踪
    task_completion_times = models.JSONField(default=dict, help_text="各任务完成时间记录")
    
    # 写作相关字段
    writing1 = models.JSONField(default=dict, null=True, blank=True)
    writing1QualityCheck = models.TextField(default="Null")
    writing1QualityCheckRA = models.TextField(default="Null")
    writing1QualityCheckCS = models.TextField(default="Null")
    writing1QualityCheckNotified = models.BooleanField(default=False)
    
    # 其他写作任务...
    writing4 = models.JSONField(default=dict, null=True, blank=True)
    writing4QualityCheck = models.TextField(default="Null")
    writing4QualityCheckRA = models.TextField(default="Null")
    writing4QualityCheckCS = models.TextField(default="Null")
    writing4QualityCheckNotified = models.BooleanField(default=False)
    
    # 问卷相关
    survey1 = models.CharField(max_length=30, default="Null")
    survey1IsValid = models.CharField(max_length=10, default="Null")
    survey23 = models.CharField(max_length=30, default="Null")
    survey23IsValid = models.CharField(max_length=10, default="Null")
    survey39 = models.CharField(max_length=30, default="Null")
    survey39IsValid = models.CharField(max_length=10, default="Null")
    survey99 = models.CharField(max_length=30, default="Null")
    survey99IsValid = models.CharField(max_length=10, default="Null")
    
    # 游戏相关
    gameFinished = models.BooleanField(default=False)
    score = models.IntegerField(default=0)
    
    # 其他字段...
    writing4Viewed = models.BooleanField(default=False)
    writing5Viewed = models.BooleanField(default=False)
    feedback6Viewed = models.BooleanField(default=False)
    feedback8Viewed = models.BooleanField(default=False)
    feedback6 = models.JSONField(default=dict, null=True, blank=True)
    feedback8 = models.JSONField(default=dict, null=True, blank=True)

    def get_task_progress_info(self):
        """获取任务进度信息"""
        day = int(self.currentDay)
        phase = self.currentDay - day  # 小数部分表示同一天的子任务
        
        return {
            'day': day,
            'phase': phase,
            'currentDay': self.currentDay,
            'is_banned': self.banFlag,
            'ban_day': self.banDay,
            'ban_tags': self.banTags
        }

    def update_task_progress(self, new_day, phase=0.0):
        """更新任务进度"""
        self.currentDay = new_day + phase
        self.save()

    def record_task_completion(self, task_day, task_phase=""):
        """记录任务完成时间"""
        if not hasattr(self, 'task_completion_times'):
            self.task_completion_times = {}
        
        task_key = f"{task_day}_{task_phase}" if task_phase else str(task_day)
        self.task_completion_times[task_key] = timezone.now().isoformat()
        self.save()

    def check_task_timeout(self, task_day, max_hours=48):
        """检查任务是否超时"""
        if task_day not in self.task_completion_times:
            return False
        
        completion_time = datetime.fromisoformat(self.task_completion_times[task_day])
        time_diff = timezone.now() - completion_time
        return time_diff.total_seconds() > (max_hours * 3600)

    def validity_check(self):
        """增强的有效性检查和自动ban逻辑"""
        ban_reasons = []
        ban_tags = []
        
        # 检查问卷有效性
        if self.survey1IsValid == "False":
            ban_reasons.append("前测问卷无效")
            ban_tags.append("pre_survey_invalid")
        
        if self.survey23IsValid == "False" and self.survey39IsValid == "False" and self.survey99IsValid == "False":
            ban_reasons.append("后测问卷无效")
            ban_tags.append("post_survey_invalid")
        
        # 检查任务超时（仅对实验组）
        if self.group in ["Exp1", "Exp2"]:
            # 检查第一天任务超时
            if self.currentDay < 1.1 and self.check_task_timeout(1, 48):
                ban_reasons.append("未按时完成第一天任务")
                ban_tags.append("task1_not_done")
            
            # 检查其他任务超时
            if self.currentDay >= 1.1 and self.currentDay <= 9:
                for day in range(2, int(self.currentDay) + 1):
                    if self.check_task_timeout(day, 48):
                        ban_reasons.append("连续2天未完成新任务")
                        ban_tags.append("task_not_done")
                        break
            
            # 检查写作质量
            invalid_writing = self.check_writing_quality()
            if invalid_writing:
                ban_reasons.append(invalid_writing)
                ban_tags.append("writing_quality_fail")
            
            # 检查游戏分数
            if self.gameFinished and self.score < 61200:
                ban_reasons.append("游戏得分不足61200 (60%)")
                ban_tags.append("game_score_low")
        
        # 更新ban状态
        if ban_reasons:
            if not self.banFlag:
                self.ban_user(ban_reasons, ban_tags)
        else:
            if self.banFlag:
                self.unban_user()
        
        return ban_reasons, ban_tags

    def ban_user(self, reasons, tags):
        """ban用户"""
        self.banFlag = True
        self.banReason = '；'.join(reasons) + f'[{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}]'
        self.banNotified = False
        self.banDay = self.currentDay
        self.banTags = tags
        self.save()

    def unban_user(self):
        """取消ban"""
        self.banFlag = False
        self.banReason = ''
        self.banNotified = False
        self.banDay = -1
        self.banTags = []
        self.save()

    def check_writing_quality(self):
        """检查写作质量"""
        # 第1天写作质量检查
        if self.writing1QualityCheck == "False":
            return "第1天的写作不合格"
        
        # 第4-8天写作质量检查
        invalid_count = 0
        for day in [4, 5, 6, 8]:
            quality_check = getattr(self, f'writing{day}QualityCheck', "Null")
            if quality_check == "False":
                invalid_count += 1
        
        if invalid_count >= 2:
            return "第4～8天的4篇写作中有2篇及以上不合格"
        
        return None

    def can_access_survey(self, survey_day):
        """检查是否可以访问调查问卷"""
        # 被ban用户仍然可以访问调查问卷
        if self.banFlag:
            return survey_day in [23, 39, 99]
        
        # 正常用户可以访问所有调查问卷
        return True

    def can_access_task(self, task_day):
        """检查是否可以访问特定任务"""
        if self.banFlag:
            # 被ban用户只能访问调查问卷
            return task_day in [23, 39, 99]
        
        # 正常用户的任务访问逻辑
        return task_day <= self.currentDay

    def get_task_status(self, task_day):
        """获取任务状态"""
        if self.banFlag:
            if task_day < self.banDay:
                return "completed"  # ban前完成的任务
            elif task_day == self.banDay:
                return "banned_at_this_day"  # ban的那一天
            elif task_day > self.banDay:
                if task_day in [23, 39, 99]:  # 调查问卷
                    return "survey_available"  # 可做调查问卷
                else:
                    return "disabled"  # 其他任务禁用
        else:
            if task_day < self.currentDay:
                return "completed"  # 已完成
            elif task_day == self.currentDay:
                return "current"  # 当前任务
            else:
                return "upcoming"  # 未来任务


class Whitelist(models.Model):
    encryptedPhoneNumber = models.CharField(max_length=500, help_text="Encrypted phone number")
    encryptedWeChat = models.CharField(max_length=500, help_text="Encrypted WeChat number")
    uuid = models.CharField(max_length=200, help_text="Blued uuid")
    has_add_wechat = models.BooleanField(default=False, help_text="Please set it to true after adding user's wechat")
    survey0 = models.CharField(max_length=30, null=True, blank=True)
    
    group = models.TextField(
        choices=[
            ("", "未分组"),
            ("Exp1", "实验组1"), 
            ("Exp2", "实验组2"), 
            ("Waitlist", "等待组")
        ], 
        default="",
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
        """分配组别"""
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
