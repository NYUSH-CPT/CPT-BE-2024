# 增强的Views，支持新的任务进度追踪和ban系统

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import WebUser, Whitelist, LSUser, Screen
from .serializers import WebUserSerializer, ScreenSerializer
from .utility import *
import json
from core.services.gameInit import *
from .services import SMS
import random
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from datetime import datetime, timedelta

import logging
logger = logging.getLogger('django')

# 增强的info接口，支持小数进度和ban状态
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@catch_exceptions
def enhanced_info(request):
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        
        if request.method == "GET":
            # 返回增强的用户信息
            serializer = WebUserSerializer(webUser, context={"info": True})
            data = serializer.data
            
            # 添加增强的状态信息
            data['task_progress'] = webUser.get_task_progress_info()
            data['user_status_type'] = get_user_status_type(webUser)
            data['can_access_surveys'] = webUser.can_access_survey(23)  # 检查是否可以访问调查问卷
            
            return Response(data, status=status.HTTP_200_OK)
            
        if request.method == "POST":
            # 处理任务进度更新
            mutable_data = request.data.copy()
            
            # 处理反馈查看后的进度更新
            if request.data.get("feedback6Viewed"):
                mutable_data['currentDay'] = max(webUser.currentDay, 8.0)
            elif request.data.get("feedback8Viewed"):
                mutable_data['currentDay'] = max(webUser.currentDay, 23.0)
            
            # 处理任务完成记录
            if request.data.get("task_completed"):
                task_day = request.data.get("task_day")
                task_phase = request.data.get("task_phase", "")
                webUser.record_task_completion(task_day, task_phase)
            
            serializer = WebUserSerializer(webUser, data=mutable_data, partial=True) 
            if serializer.is_valid():
                serializer.save()
                
                # 返回更新后的增强信息
                data = serializer.data
                data['task_progress'] = webUser.get_task_progress_info()
                data['user_status_type'] = get_user_status_type(webUser)
                data['can_access_surveys'] = webUser.can_access_survey(23)
                
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({"error": f"更新失败{serializer.errors}"}, status=status.HTTP_400_BAD_REQUEST) 
                
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_401_UNAUTHORIZED)

# 增强的写作接口，支持小数进度
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@catch_exceptions
def enhanced_writing(request, day):
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        
        if request.method == "GET":
            # 检查任务访问权限
            if not webUser.can_access_task(day):
                return Response({"error": f"无法访问第 {day} 天的任务"}, status=status.HTTP_403_FORBIDDEN)
            
            if day == 6: 
                prompt = webUser.writing1
            else: 
                prompt = None
                
            if day in [4, 5]:
                with open(f"writings/challenge_writing_day{day}_reference.json", "r") as f:
                    reference = json.load(f)
            else: 
                reference = None
                
            answer = getattr(webUser, f'writing{day}', None)
            if not answer:
                return Response({"error": "回答不存在", 'prompt': prompt}, status=status.HTTP_404_NOT_FOUND)
            
            # 更新进度到下一个子任务
            next_progress = day + 0.1
            webUser.currentDay = max(next_progress, webUser.currentDay)
            webUser.save()
            
            return Response({'answer': answer, 'reference': reference, 'prompt': prompt}, status=status.HTTP_200_OK)
            
        if request.method == "POST":
            # 检查任务访问权限
            if not webUser.can_access_task(day):
                return Response({"error": f"无法访问第 {day} 天的任务"}, status=status.HTTP_403_FORBIDDEN)
            
            writing_field = getattr(webUser, f'writing{day}', None)
            if writing_field:
                return Response({"error": "该写作任务的内容已存在", "exist": True}, status=status.HTTP_400_BAD_REQUEST)
            
            # 记录写作内容
            setattr(webUser, f'writing{day}', request.data)
            
            # 更新进度并记录完成时间
            next_progress = day + 0.1
            webUser.currentDay = max(next_progress, webUser.currentDay)
            webUser.record_task_completion(day, "writing")
            webUser.save()
            
            return Response(status=status.HTTP_200_OK)
            
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    except KeyError:
        return Response({"error": "无效的写作日期"}, status=status.HTTP_404_NOT_FOUND)

# 增强的视频完成接口
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@catch_exceptions
def enhanced_finish_video(request):
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        
        # 更新进度到视频后的下一个任务
        webUser.currentDay = max(2.1, webUser.currentDay)
        webUser.record_task_completion(2, "video")
        webUser.save()
        
        return Response(status=status.HTTP_200_OK)
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

# 增强的Qualtrics提交接口，支持分组更新
@api_view(["POST"])
@csrf_exempt
@catch_exceptions
def enhanced_qualtrics_submission(request):
    body = json.loads(request.body)
    keys = {"invalid", "surveyDay", "uuid", "responseId"}
    if any(k not in body for k in keys):
        return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST) 
    
    day = body["surveyDay"]
    isvalid = "False" if body['invalid'] == 1 else "True"
    responseId = body["responseId"]
    uuid = body['uuid']
    
    try:
        webUser = WebUser.objects.get(uuid=uuid)
        
        # 记录问卷信息
        setattr(webUser, f"survey{day}", responseId)
        setattr(webUser, f"survey{day}IsValid", isvalid)
        
        # 根据问卷类型更新进度
        if day == 1:
            # 第一天问卷完成后，等待外部分组
            webUser.currentDay = max(1.0, webUser.currentDay)
        elif day == 23:
            webUser.currentDay = max(23.0, webUser.currentDay)
        elif day == 39:
            webUser.currentDay = max(39.0, webUser.currentDay)
        elif day == 99:
            webUser.currentDay = max(99.0, webUser.currentDay)
        
        webUser.save()
        
        return Response({"status": "Success", "message": "成功提交"}, status=status.HTTP_200_OK)
        
    except WebUser.DoesNotExist:
        return Response({"status": "Fail", "message": "用户不存在"}, status=status.HTTP_400_BAD_REQUEST)

# 新增：分组更新接口（由Qualtrics调用）
@api_view(["POST"])
@csrf_exempt
@catch_exceptions
def update_user_group(request):
    """更新用户分组，由Qualtrics问卷完成后调用"""
    body = json.loads(request.body)
    keys = {"uuid", "group", "responseId", "isValid"}
    if any(k not in body for k in keys):
        return Response({"status": "Fail", "message": "无效请求"}, status=status.HTTP_400_BAD_REQUEST)
    
    uuid = body['uuid']
    group = body['group']
    responseId = body['responseId']
    isValid = body['isValid']
    
    try:
        webUser = WebUser.objects.get(uuid=uuid)
        
        # 更新分组
        webUser.group = group
        
        # 记录第一天问卷
        webUser.survey1 = responseId
        webUser.survey1IsValid = "True" if isValid else "False"
        
        # 根据分组更新进度
        if group == "Waitlist":
            webUser.currentDay = max(23.0, webUser.currentDay)  # Waitlist直接跳到第23天
        else:
            webUser.currentDay = max(1.1, webUser.currentDay)  # 实验组开始第1.1天
        
        webUser.save()
        
        return Response({
            "status": "Success", 
            "message": "分组更新成功",
            "group": group,
            "currentDay": webUser.currentDay
        }, status=status.HTTP_200_OK)
        
    except WebUser.DoesNotExist:
        return Response({"status": "Fail", "message": "用户不存在"}, status=status.HTTP_400_BAD_REQUEST)

# 新增：任务状态检查接口
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@catch_exceptions
def task_status(request, day):
    """检查特定任务的状态"""
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        
        # 获取任务状态
        task_status = webUser.get_task_status(day)
        can_access = webUser.can_access_task(day)
        
        return Response({
            "day": day,
            "status": task_status,
            "can_access": can_access,
            "current_progress": webUser.get_task_progress_info()
        }, status=status.HTTP_200_OK)
        
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

# 新增：用户有效性检查接口
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@catch_exceptions
def check_user_validity(request):
    """手动触发用户有效性检查"""
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        
        # 执行有效性检查
        ban_reasons, ban_tags = webUser.validity_check()
        
        return Response({
            "is_banned": webUser.banFlag,
            "ban_reasons": ban_reasons,
            "ban_tags": ban_tags,
            "current_progress": webUser.get_task_progress_info()
        }, status=status.HTTP_200_OK)
        
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

# 新增：获取用户任务历史接口
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@catch_exceptions
def task_history(request):
    """获取用户任务完成历史"""
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        
        return Response({
            "task_completion_times": webUser.task_completion_times,
            "current_progress": webUser.get_task_progress_info(),
            "ban_info": {
                "is_banned": webUser.banFlag,
                "ban_reason": webUser.banReason,
                "ban_day": webUser.banDay,
                "ban_tags": webUser.banTags
            }
        }, status=status.HTTP_200_OK)
        
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

# 辅助函数
def get_user_status_type(webUser):
    """获取用户状态类型"""
    if not webUser.group or webUser.group == "":
        return "ungrouped"
    if webUser.banFlag:
        return "banned"
    if webUser.group == "Waitlist":
        return "waitlist"
    if webUser.group in ["Exp1", "Exp2"]:
        return "experimental"
    return "unknown"

# 保持原有的其他接口不变，但可以逐步迁移到增强版本
# 原有的接口仍然保留以确保向后兼容性
