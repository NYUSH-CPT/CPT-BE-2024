# 增强的任务调度系统
# 支持根据不同ban条件发送不同的blue消息

import os
import django
import sys

sys.path.append(os.getcwd())
os.environ['DJANGO_SETTINGS_MODULE'] = 'CPTBackend.settings'
django.setup()

import json
from core.models import WebUser, Log, BannedLog, Whitelist
from datetime import datetime
from core.services import blued_msg
from core.utility import catch_exceptions

# Ban标签对应的消息ID映射
BAN_MESSAGE_MAPPING = {
    'pre_survey_invalid': 22,      # 前测问卷无效
    'post_survey_invalid': 23,     # 后测问卷无效
    'task1_not_done': 14,          # 第1天任务未完成
    'task_not_done': 15,           # 任务未完成
    'writing_quality_fail': 20,    # 写作质量不合格
    'game_score_low': 17,          # 游戏分数低
    'general_ban': 16              # 一般ban消息
}

# 调查问卷消息ID映射
SURVEY_MESSAGE_MAPPING = {
    1: 3,      # 第1天问卷
    23: 12,    # 第23天问卷
    39: 13,    # 第39天问卷
    99: 29     # 第99天问卷
}

@catch_exceptions
def launch_enhanced_tasks(time: int):
    """增强的任务调度函数"""
    print(f"Enhanced task launched at {datetime.now()}, time: {time}.")
    
    # 记录任务启动日志
    log = Log.objects.create(
        user=None,
        log=f"Enhanced task launched at {datetime.now()}, time: {time}."
    )
    log.save()

    # 处理未分组用户的前测问卷
    handle_ungrouped_users(time)
    
    # 处理已分组用户的任务
    handle_grouped_users(time)
    
    # 处理被ban用户的消息
    handle_banned_users(time)

def handle_ungrouped_users(time: int):
    """处理未分组用户"""
    if time != 8:  # 只在早上8点处理
        return
    
    for whitelist in Whitelist.objects.filter(group=""):
        if not whitelist.has_add_wechat or not whitelist.startDate:
            continue
            
        # 发送前测问卷消息
        res = blued_msg.send(whitelist.uuid, 1)  # 使用消息ID 1
        log_message = f"Ungrouped user message sent to {whitelist.uuid}"
        
        if res['code'] == 200:
            log_message += " successfully."
        else:
            log_message += f" failed: {res['msg']}"
        
        Log.objects.create(log=log_message).save()

def handle_grouped_users(time: int):
    """处理已分组用户的任务"""
    for user in WebUser.objects.all():
        if not user.group or user.group == "":
            continue
            
        # 更新用户有效性检查
        ban_reasons, ban_tags = user.validity_check()
        
        # 如果用户被ban，跳过正常任务处理
        if user.banFlag:
            continue
        
        # 处理正常任务
        handle_normal_tasks(user, time)

def handle_banned_users(time: int):
    """处理被ban用户的消息"""
    for user in WebUser.objects.filter(banFlag=True, banNotified=False):
        # 根据ban标签发送相应消息
        message_id = get_ban_message_id(user.banTags)
        
        if message_id:
            res = blued_msg.send(user.uuid, message_id)
            
            if res['code'] == 200:
                user.banNotified = True
                user.save()
                
                Log.objects.create(
                    user=user,
                    log=f"Ban message {message_id} sent to {user.uuid} successfully."
                ).save()
            else:
                Log.objects.create(
                    user=user,
                    log=f"Ban message {message_id} failed for {user.uuid}: {res['msg']}"
                ).save()

def handle_normal_tasks(user, time: int):
    """处理正常用户的任务"""
    current_date = datetime.now().date()
    current_day = (current_date - user.startDate).days + 1
    
    # 检查是否需要发送任务消息
    if should_send_task_message(user, current_day, time):
        message_id = get_task_message_id(user.group, current_day)
        
        if message_id:
            res = blued_msg.send(user.uuid, message_id)
            
            if res['code'] == 200:
                Log.objects.create(
                    user=user,
                    log=f"Task message {message_id} sent to {user.uuid} successfully."
                ).save()
            else:
                Log.objects.create(
                    user=user,
                    log=f"Task message {message_id} failed for {user.uuid}: {res['msg']}"
                ).save()

def should_send_task_message(user, current_day, time: int):
    """检查是否应该发送任务消息"""
    # 检查时间
    if time not in [8, 20]:  # 只在早上8点和晚上8点发送
        return False
    
    # 检查用户分组
    if user.group not in ['Exp1', 'Exp2', 'Waitlist']:
        return False
    
    # 检查任务进度
    if current_day > user.currentDay:
        return False
    
    return True

def get_ban_message_id(ban_tags):
    """根据ban标签获取消息ID"""
    if not ban_tags:
        return BAN_MESSAGE_MAPPING['general_ban']
    
    for tag in ban_tags:
        if tag in BAN_MESSAGE_MAPPING:
            return BAN_MESSAGE_MAPPING[tag]
    
    return BAN_MESSAGE_MAPPING['general_ban']

def get_task_message_id(group, day):
    """根据分组和天数获取任务消息ID"""
    if group == 'Waitlist':
        if day == 1:
            return 3  # Waitlist第1天问卷
        elif day == 23:
            return 12  # Waitlist第23天问卷
        else:
            return None
    
    elif group in ['Exp1', 'Exp2']:
        if day == 1:
            return 3  # 实验组第1天问卷
        elif day in [2, 3, 4, 5, 6, 7, 8, 9]:
            return 4  # 实验组日常任务
        elif day == 23:
            return 12  # 实验组第23天问卷
        else:
            return None
    
    return None

def send_survey_reminder(time: int):
    """发送调查问卷提醒"""
    if time not in [8, 20]:
        return
    
    # 发送给所有用户（包括被ban用户）
    for user in WebUser.objects.all():
        if not user.group or user.group == "":
            continue
        
        # 检查是否需要发送调查问卷提醒
        survey_days = [23, 39, 99]
        for survey_day in survey_days:
            if should_send_survey_reminder(user, survey_day):
                message_id = SURVEY_MESSAGE_MAPPING.get(survey_day)
                
                if message_id:
                    res = blued_msg.send(user.uuid, message_id)
                    
                    if res['code'] == 200:
                        Log.objects.create(
                            user=user,
                            log=f"Survey reminder {message_id} sent to {user.uuid} for day {survey_day}"
                        ).save()

def should_send_survey_reminder(user, survey_day):
    """检查是否应该发送调查问卷提醒"""
    # 被ban用户仍然可以收到调查问卷提醒
    survey_key = f'survey{survey_day}IsValid'
    survey_value = getattr(user, survey_key, 'Null')
    
    # 如果问卷已完成或无效，不发送提醒
    if survey_value in ['True', 'False']:
        return False
    
    # 检查时间窗口
    current_date = datetime.now().date()
    current_day = (current_date - user.startDate).days + 1
    
    # 在问卷日期的前1天到后6天内发送提醒
    if survey_day - 1 <= current_day <= survey_day + 6:
        return True
    
    return False

if __name__ == "__main__":
    launch_enhanced_tasks(8)
    launch_enhanced_tasks(20)
