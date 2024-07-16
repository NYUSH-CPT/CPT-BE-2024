from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import jwt
from dotenv import load_dotenv
import os
from .models import WebUser, Whitelist
from .serializers import WebUserSerializer
from .utility import *
import json
from core.services.gameInit import *
from .services import SMS
import random
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken


import logging
logger = logging.getLogger('django')

# Create your views here.
 
# /info，包括进度、用户权限（能否继续实验）、反馈信息、用户实验开始时间、用户的组
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def info(request):
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        serializer = WebUserSerializer(webUser, context={"info": True})
        if request.method == "GET":
            return Response(serializer.data, status=status.HTTP_200_OK)
        if request.method == "POST":
            mutable_data = request.data.copy()
            if request.data.get("feedback6Viewed"):
                mutable_data['currentDay'] = max(webUser.currentDay, 8)
            elif request.data.get("feedback8Viewed"):
                mutable_data['currentDay'] = max(webUser.currentDay, 10)
            serializer = WebUserSerializer(webUser, data=mutable_data, partial=True) 
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({"error": f"更新失败{serializer.errors}"}, status=status.HTTP_400_BAD_REQUEST) 
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("An error occurred: %s", e, exc_info=True)
        return Response({'error': "这是一个程序错误。请通知管理员联系开发者"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# /writing/[day]，所有的写作（POST、GET)，GET 需要包含参考答案，数据库里面全部用JSON，一张表一个field
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def writing(request, day):
    field_map = {
        1: 'freeWriting',
        4: 'challengeWriting1',
        5: 'challengeWriting2',
        6: 'challengeWriting3',
        8: 'virtualLetter',
    }
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        if request.method == "GET":
            if day > webUser.currentDay:
                return Response({"error": f"当前进度尚未达到第 {day} 天"}, status=status.HTTP_403_FORBIDDEN)
            if day == 6: prompt = webUser.freeWriting
            else: prompt = None
            if day in [4, 5]:
                with open(f"writings/challenge_writing_day{day}_reference.json", "r") as f:
                    reference = json.load(f)
            else: reference = None
            answer = getattr(webUser, field_map[day], None)
            if not answer:
                return Response({"error": "回答不存在", 'prompt': prompt}, status=status.HTTP_404_NOT_FOUND)
            return Response({'answer': answer, 'reference': reference, 'prompt': prompt}, status=status.HTTP_200_OK)
        if request.method == "POST":
            if day > webUser.currentDay:
                return Response({"error": f"当前进度尚未达到第 {day} 天"}, status=status.HTTP_403_FORBIDDEN)
            writing_field = getattr(webUser, field_map[day], None)
            if writing_field:
                return Response({"error": "该写作任务的内容已存在", "exist": True}, status=status.HTTP_400_BAD_REQUEST)
            webUser.currentDay = day+1
            setattr(webUser, field_map[day], request.data)
            webUser.save()
            return Response(status=status.HTTP_200_OK)
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    except KeyError:
        return Response({"error": "无效的写作日期"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("An error occurred: %s", e, exc_info=True)
        return Response({"error": "这是一个程序错误。请通知管理员联系开发者"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def game(request):
    try:
        # if use phonenumber, need encryption in the future
        user = request.user
        return getNewGame(user).handleRequest(request)
    except Exception as e:
        logger.error("An error occurred: %s", e, exc_info=True)
        return Response({"error": "这是一个程序错误。请通知管理员联系开发者"}, status=500)
    
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def finishVideo(request):
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        webUser.currentDay = max(2.1, webUser.currentDay)
        webUser.save()
        return Response(status=status.HTTP_200_OK)
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    
    
@api_view(['POST'])
def handleSendSMSRequest(request):

    phoneNumber = json.loads(request.body)['phoneNumber']
    uuid = request.query_params.get('uuid') 

    if len(phoneNumber)>8 and phoneNumber.isnumeric(): # 一般手机号长度 大于 8
        try:
            whitelist = Whitelist.objects.get(phoneNumber=encryptPhoneNumber(phoneNumber))
            encryptedPhoneNumber = whitelist.phoneNumber
            generated_passcode = str(random.randint(1000, 9999))
            response = SMS.SmsService.send(phoneNumber, generated_passcode)
            if response['statusCode'] == 200:
                try:
                    user = User.objects.get(username=encryptedPhoneNumber)
                except User.DoesNotExist:
                    user = User.objects.create_user(username=encryptedPhoneNumber)
                    WebUser.objects.create(user=user, phoneNumber=encryptedPhoneNumber)
                webUser = WebUser.objects.get(phoneNumber=encryptedPhoneNumber)
                webUser.sms = generated_passcode
                
                #TODO
                if uuid:  
                    webUser.bludId = uuid
                    
                webUser.save()
                user.set_password(generated_passcode)
                user.save()
                return Response({'message': 'SMS sent', 'uuid': uuid}, status=status.HTTP_200_OK)
            else:
                return Response({"error": response[1]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Whitelist.DoesNotExist:
            return Response({"error": "用户信息未加入白名单，请联系管理员"}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({"error": "手机号码不合规"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def login(request):
    phoneNumber = json.loads(request.body)['phoneNumber']
    passcode = json.loads(request.body)['passcode']

    if len(phoneNumber) > 8 and phoneNumber.isnumeric() and len(passcode) == 4 and passcode.isnumeric():
        try:
            user = User.objects.get(username=encryptPhoneNumber(phoneNumber))
            if user.check_password(passcode):
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "验证码错误"}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"error": "尚未获取验证码"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({"error": "手机号码或验证码不合规"}, status=status.HTTP_400_BAD_REQUEST)
