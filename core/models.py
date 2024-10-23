from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
import random

# Create your models here.

class WebUser(models.Model):
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text="Auth user")
    uuid = models.CharField(null=True, blank=True, max_length=200, help_text="Blued uuid")
    sms = models.CharField(null=True, blank=True, max_length=20)
    phoneNumber = models.CharField(max_length=500, help_text="Encrypted phone number")
    whitelist = models.OneToOneField("Whitelist", on_delete=models.CASCADE, related_name="webUser")
    
    group = models.TextField(choices=[("Exp1", "Exp1"), ("Exp2", "Exp2"), ("Waitlist", "Waitlist")], default="Null")
    currentDay = models.FloatField(default=1, help_text="User task progress - note that this number might be a float")
    startDate = models.DateField(default=timezone.now, help_text="Experiment start date")
    trainCompleteNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
    surveyCompleteNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
    
    banFlag = models.BooleanField(default=False, help_text="This field is managed by automatic rules which cannot be changed by admin")
    banReason = models.TextField(max_length=200, null=True, blank=True, help_text="Reason for banning user, visible to user")
    banReasonInternal = models.TextField(max_length=500, null=True, blank=True, help_text="Reason for banning user, auto generated")
    banNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
    banDay = models.FloatField(default=-1, help_text="The task progress when the user is banned at")

    writing1 = models.JSONField(default=dict, null=True, blank=True)
    writing1QualityCheck = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Auto generated quality check")
    writing1QualityCheckRA = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="RA quality check")
    writing1QualityCheckCS = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="CS quality check")
    writing1QualityCheckNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
    
    writing4 = models.JSONField(default=dict, null=True, blank=True)
    writing4Viewed = models.BooleanField(default=False, help_text="Auto set to true when user views feedback")
    writing4QualityCheck = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Auto generated quality check")
    writing4QualityCheckRA = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="RA quality check")
    writing4QualityCheckCS = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="CS quality check")
    writing4QualityCheckNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
     
    writing5 = models.JSONField(default=dict, null=True, blank=True)
    writing5Viewed = models.BooleanField(default=False, help_text="Auto set to true when user views feedback")
    writing5QualityCheck = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Auto generated quality check")
    writing5QualityCheckRA = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="RA quality check")
    writing5QualityCheckCS = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="CS quality check")
    writing5QualityCheckNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
     
    writing6 = models.JSONField(default=dict, null=True, blank=True)
    writing6QualityCheck = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Auto generated quality check")
    writing6QualityCheckRA = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="RA quality check")
    writing6QualityCheckCS = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="CS quality check")
    writing6QualityCheckNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
     
    feedback6 = models.TextField(null=True, blank=True, help_text="Please write feedback in Markdown format")
    feedback6Viewed = models.BooleanField(default=False, help_text="Auto set to true when user views feedback")
    
    writing8 = models.JSONField(default=dict, null=True, blank=True)
    writing8QualityCheck = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Auto generated quality check")
    writing8QualityCheckRA = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="RA quality check")
    writing8QualityCheckCS = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="CS quality check")
    writing8QualityCheckNotified = models.BooleanField(default=False, help_text="Auto set to true when user is notified")
    
    feedback8 = models.TextField(null=True, blank=True, help_text="Please write feedback in Markdown format")
    feedback8Viewed = models.BooleanField(default=False, help_text="Auto set to true when user views feedback")
    
    game = models.BinaryField(null=True)
    gameBreakFlag = models.BooleanField(default=False)
    gameFinished = models.BooleanField(default=False)
    gameData = models.JSONField(default=dict,null=True, blank=True)
    score = models.IntegerField(default=0)
    
    survey1 = models.TextField(max_length=30, null=True, blank=True)
    survey1IsValid = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Inherited from qualtrics survey")
    survey23 = models.TextField(max_length=30, null=True, blank=True)
    survey23IsValid = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Inherited from qualtrics survey")
    survey39 = models.TextField(max_length=30, null=True, blank=True)
    survey39IsValid = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Inherited from qualtrics survey")
    survey99 = models.TextField(max_length=30, null=True, blank=True)
    survey99IsValid = models.TextField(choices=[("True", "True"), ("False", "False"), ("Null", "Null")], default="Null", help_text="Inherited from qualtrics survey")
    
    def __str__(self):
        return f'{self.uuid} | {self.group} | startDate: {self.startDate} | currentDay: {self.currentDay}'

    def reset_game(self): 
        self.game = None
        self.gameBreakFlag = False
        self.gameFinished = False
        self.gameData = {}
        self.score = 0
        self.save()
    
    def update_quality_check(self, day_attr, ra_check, cs_check):
        if ra_check == "False" and cs_check == "False":
            setattr(self, day_attr, "False")
        elif ra_check != "Null" and cs_check != "Null":
            setattr(self, day_attr, "True")
        else:
            setattr(self, day_attr, "Null")
        self.save()

    def count_invalid_checks(self, days: list[int]):
        invalid_count = 0
        for day in days:
            if getattr(self, f'writing{day}QualityCheck') == "False":
                invalid_count += 1
        return invalid_count
    
    def update_date_after_survey_due(self):
        startDate = datetime.combine(self.startDate, datetime.min.time()).date() 
        now = datetime.now().date()
        survey_days = {23: 39, 39: 99, 99: 100}
        for day, next_day in survey_days.items():
            if (now - startDate).days > day + 6 and self.currentDay == day:
                setattr(self, f'survey{day}IsValid', "False")
                setattr(self, f'survey{day}', "Overdue")
                self.currentDay = next_day

        self.save()
        
    def validity_check(self):
        banReasons = []
        banTags = []
        # Criteria 1: Qualtrics Survey
        self.update_date_after_survey_due()
        if self.survey1IsValid == "False":
            banReasons.append("前测问卷无效")
            banTags.append("pre_survey_invalid")
        if self.survey23IsValid == "False" and self.survey39IsValid == "False" and self.survey99IsValid == "False":
            banReasons.append("后测问卷无效")
            banTags.append("post_survey_invalid")
        if self.group in ["Exp1", "Exp2"]:
            # Criteria 2: Writing Quality
            for day in [1, 4, 5, 6, 8]:
                ra_attr = f'writing{day}QualityCheckRA'
                cs_attr = f'writing{day}QualityCheckCS'
                self.update_quality_check(f'writing{day}QualityCheck', getattr(self, ra_attr), getattr(self, cs_attr))
            invalid1 = self.count_invalid_checks([1])
            invalid4to8 = self.count_invalid_checks([4,5,6,8])
            if invalid1 >= 1:
                banReasons.append("第1天的写作不合格")
                banTags.append("quality_check_fail")
            if invalid4to8 >= 2:
                banReasons.append("第4～8天的4篇写作中有2篇及以上不合格")
                banTags.append("quality_check_fail")
            # Criteria 3: Overdue
            if self.currentDay <= 9:
                startDate = datetime.combine(self.startDate, datetime.min.time())
                currenrtTaskStartDate = startDate + timedelta(days=self.currentDay - 1)  # minimum date to start current task
                currentTaskEndDate = currenrtTaskStartDate + timedelta(days=2) + timedelta(hours=4)  # maximum date to finish current task
                if datetime.now() > currentTaskEndDate:
                    banReasons.append("连续2天未完成新任务")
                    banTags.append("task_not_done")
            # Criteria 4: Game
            if self.gameFinished and self.score < 61200:
                    banReasons.append("游戏得分不足61200 (60%)")
                    banTags.append("game_score_low")
        # Criteria 5: Manual ban
        if self.banReason is not None and self.banReason != "":
            banReasons.append("手动标记为不合格")
            
        if len(banReasons) > 0:
            self.banReasonInternal = '；'.join(banReasons) + f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]'
            if not self.banFlag:
                self.banFlag = True
                self.banDay = self.currentDay
        else:
            self.banReasonInternal = ''
            self.banFlag = False
            self.banDay = -1

        self.save()
        return banReasons, banTags


class Whitelist(models.Model):
    
    phoneNumber = models.CharField(max_length=500, help_text="Encypted phone number")
    uuid = models.CharField(max_length=200, help_text="Blued uuid")
    has_add_wechat = models.BooleanField(default=False, help_text="Please set it to true after adding user's wechat")
    survey0 = models.TextField(max_length=30, null=True, blank=True)
    group = models.TextField(choices=[("Exp1", "Exp1"), ("Exp2", "Exp2"), ("Waitlist", "Waitlist")], default=None, null=True, blank=True)
    startDate = models.DateField(null=True, blank=True, help_text="Experiment start date")
    
    def __str__(self):
        return self.uuid
    
    def assign_group(self):
        if self.has_add_wechat and not self.group:
            rand = random.randint(1, 3)
            if rand == 1:
                self.group = "Exp1"
            elif rand == 2:
                self.group = "Exp2"
            else:
                self.group = "Waitlist"
            self.save()
                
    
class Log(models.Model):
    
    time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(WebUser, on_delete=models.CASCADE, null=True, blank=True)
    log = models.TextField()

    def __str__(self) -> str:
        return f'Log [{self.id}] | {self.log}'

class BannedLog(models.Model):
    
    time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(WebUser, on_delete=models.CASCADE, null=True, blank=True)
    log = models.TextField()
    
    def __str__(self) -> str:
        return f'BannedLog [{self.id}] | {self.user.uuid} | {self.log}'