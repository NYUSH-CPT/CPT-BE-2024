from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import WebUser, Whitelist
from .serializers import WebUserSerializer
from .utility import *
import json
from core.services.gameInit import *
from .services import SMS
import random
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt

import logging
logger = logging.getLogger('django')

# Create your views here.

# /info，包括进度、用户权限（能否继续实验）、反馈信息、用户实验开始时间、用户的组
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@catch_exceptions
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
                mutable_data['currentDay'] = max(webUser.currentDay, 23)
            serializer = WebUserSerializer(webUser, data=mutable_data, partial=True) 
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({"error": f"更新失败{serializer.errors}"}, status=status.HTTP_400_BAD_REQUEST) 
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_401_UNAUTHORIZED)

# /writing/[day]，所有的写作（POST、GET)，GET 需要包含参考答案，数据库里面全部用JSON，一张表一个field
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@catch_exceptions
def writing(request, day):
    try:
        user = request.user
        webUser = WebUser.objects.get(user=user)
        if request.method == "GET":
            if day > webUser.currentDay:
                return Response({"error": f"当前进度尚未达到第 {day} 天"}, status=status.HTTP_403_FORBIDDEN)
            if day == 6: prompt = webUser.writing1
            else: prompt = None
            if day in [4, 5]:
                with open(f"writings/challenge_writing_day{day}_reference.json", "r") as f:
                    reference = json.load(f)
            else: reference = None
            answer = getattr(webUser, f'writing{day}', None)
            if not answer:
                return Response({"error": "回答不存在", 'prompt': prompt}, status=status.HTTP_404_NOT_FOUND)
            webUser.currentDay = max(day+1, webUser.currentDay)
            webUser.save()
            return Response({'answer': answer, 'reference': reference, 'prompt': prompt}, status=status.HTTP_200_OK)
        if request.method == "POST":
            if day > webUser.currentDay:
                return Response({"error": f"当前进度尚未达到第 {day} 天"}, status=status.HTTP_403_FORBIDDEN)
            writing_field = getattr(webUser, f'writing{day}', None)
            if writing_field:
                return Response({"error": "该写作任务的内容已存在", "exist": True}, status=status.HTTP_400_BAD_REQUEST)
            webUser.currentDay = max(day+1, webUser.currentDay)
            setattr(webUser, f'writing{day}', request.data)
            webUser.save()
            return Response(status=status.HTTP_200_OK)
    except WebUser.DoesNotExist:
        return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    except KeyError:
        return Response({"error": "无效的写作日期"}, status=status.HTTP_404_NOT_FOUND)
   
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@catch_exceptions
def game(request):
    user = request.user
    return getNewGame(user).handleRequest(request)

    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@catch_exceptions
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
@catch_exceptions
def handleSendSMSRequest(request):
    phoneNumber = json.loads(request.body)['phoneNumber']
    if len(phoneNumber)>8 and phoneNumber.isnumeric(): # 一般手机号长度 大于 8
        encryptedPhoneNumber = encryptPhoneNumber(phoneNumber)
        webUser = WebUser.objects.filter(phoneNumber=encryptedPhoneNumber).first()
        if not webUser:
            whitelist = Whitelist.objects.filter(phoneNumber=encryptedPhoneNumber).first()
            if not whitelist:
                return Response({"error": "用户信息未加入白名单，请联系管理员"}, status=status.HTTP_404_NOT_FOUND)
            if not whitelist.has_add_wechat:
                return Response({"error": "请等待助教添加您的微信"}, status=status.HTTP_400_BAD_REQUEST)
            if not whitelist.startDate:
                return Response({"error": "实验尚未开始"}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(username=whitelist.uuid).first()
            if not user:
                user = User.objects.create_user(username=whitelist.uuid)
            webUser = WebUser.objects.create(user=user, whitelist=whitelist, phoneNumber=encryptedPhoneNumber, group=whitelist.group, uuid=whitelist.uuid, startDate=whitelist.startDate)
        generated_passcode = str(random.randint(1000, 9999))
        response = SMS.SmsService.send(phoneNumber, generated_passcode)
        if response['statusCode'] == 200:
            user = webUser.user
            webUser.sms = generated_passcode
            webUser.save()
            user.set_password(generated_passcode)
            user.save()
            return Response({'message': 'SMS sent'}, status=status.HTTP_200_OK)
        else:
            return Response({"error": response[1]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response({"error": "手机号码不合规"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@catch_exceptions
def login(request):
    phoneNumber = json.loads(request.body)['phoneNumber']
    passcode = json.loads(request.body)['passcode']

    if len(phoneNumber) > 8 and phoneNumber.isnumeric() and len(passcode) == 4 and passcode.isnumeric():
        try:
            whitelist = Whitelist.objects.get(phoneNumber=encryptPhoneNumber(phoneNumber))
            user = User.objects.get(username=whitelist.uuid)
            if user.check_password(passcode):
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "验证码错误"}, status=status.HTTP_400_BAD_REQUEST)
        except Whitelist.DoesNotExist:
            return Response({"error": "用户信息未加入白名单，请联系管理员"}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "尚未获取验证码"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({"error": "手机号码或验证码不合规"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@csrf_exempt
@catch_exceptions
def qualtrics_submission(request):
    body = json.loads(request.body)
    keys = {"invalid", "surveyDay", "uuid", "responseId"}
    if any(k not in body for k in keys):
        return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST) 
    
    day = body["surveyDay"]
    isvalid = "False" if body['invalid'] == 1 else "True"
    responseId =  body["responseId"]
    uuid = body['uuid']
    
    if (day == 0 and 'phoneNumber' not in body) or not uuid:
        return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST) 
            
    if day == 0:
        phoneNumber = encryptPhoneNumber(body["phoneNumber"])
        if isvalid == "True":
            if not Whitelist.objects.filter(phoneNumber=encryptPhoneNumber(phoneNumber)).exists() \
                and not Whitelist.objects.filter(uuid=encryptPhoneNumber(uuid)).exists():
                whitelist = Whitelist.objects.create(phoneNumber=phoneNumber, uuid=uuid, survey0=responseId)
                whitelist.save()
            else:
                return Response({"status": "Fail", "message": "用户已存在"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        try:
            webUser = WebUser.objects.get(uuid=body['uuid'])
            setattr(webUser, f"survey{day}", responseId)
            setattr(webUser, f"survey{day}IsValid", isvalid)
            if day == 1:
                if webUser.group == "Waitlist": currentDay = 23
                else: currentDay = 1.1
            elif day == 23: currentDay = 39
            elif day == 39: currentDay = 99
            elif day == 99: currentDay = 100
            webUser.currentDay = max(webUser.currentDay, currentDay)
            webUser.save()
        except WebUser.DoesNotExist:
            return Response({"status": "Fail", "message": "用户不存在"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"status": "Success", "message": "成功提交"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@catch_exceptions
def key(request):
    key = request.query_params.get("key")
    if not Whitelist.objects.filter(uuid=key):
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_200_OK)