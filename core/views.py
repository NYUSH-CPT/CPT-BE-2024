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
        encryptedPhoneNumber = encrypt(phoneNumber)
        webUser = WebUser.objects.filter(encryptedPhoneNumber=encryptedPhoneNumber).first()
        if not webUser:
            whitelist = Whitelist.objects.filter(encryptedPhoneNumber=encryptedPhoneNumber).first()
            if not whitelist:
                return Response({"error": "用户信息未加入白名单，请联系管理员"}, status=status.HTTP_404_NOT_FOUND)
            if not whitelist.has_add_wechat:
                return Response({"error": "请等待助教添加您的微信"}, status=status.HTTP_400_BAD_REQUEST)
            if not whitelist.startDate:
                return Response({"error": "实验尚未开始"}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(username=whitelist.uuid).first()
            if not user:
                user = User.objects.create_user(username=whitelist.uuid)
            webUser = WebUser.objects.create(user=user, whitelist=whitelist, 
                                             encryptedPhoneNumber=encryptedPhoneNumber, encryptedWeChat=whitelist.encryptedWeChat,
                                             uuid=whitelist.uuid, startDate=whitelist.startDate,)
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
    password = json.loads(request.body)['passcode']

    if len(phoneNumber) > 8 and phoneNumber.isnumeric() and password:
        try:
            whitelist = Whitelist.objects.get(encryptedPhoneNumber=encrypt(phoneNumber))
            if not whitelist.has_add_wechat:
                return Response({"error": "请等待助教添加您的微信"}, status=status.HTTP_400_BAD_REQUEST)
            if not whitelist.startDate:
                return Response({"error": "实验尚未开始"}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.get(username=whitelist.uuid)
            if user.check_password(password):
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "手机号或密码错误"}, status=status.HTTP_400_BAD_REQUEST)
        except Whitelist.DoesNotExist:
            return Response({"error": "用户信息未加入白名单，请联系管理员"}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "尚未设置密码"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({"error": "手机号码或密码格式不正确"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@catch_exceptions
def signup(request):
    data = json.loads(request.body)
    phoneNumber = data.get("phoneNumber")
    password = data.get("passcode")

    if len(phoneNumber) > 8 and phoneNumber.isnumeric() and password:
        encryptedPhoneNumber = encrypt(phoneNumber)
        try:
            whitelist = Whitelist.objects.get(encryptedPhoneNumber=encryptedPhoneNumber)
            if not whitelist.has_add_wechat:
                return Response({"error": "请等待助教添加您的微信"}, status=status.HTTP_400_BAD_REQUEST)
            if not whitelist.startDate:
                return Response({"error": "实验尚未开始"}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(username=whitelist.uuid).first()
            if not user:
                user = User.objects.create_user(username=whitelist.uuid)
                user.set_password(password)
                user.save()
                webUser = WebUser.objects.create(user=user, whitelist=whitelist, 
                                                encryptedPhoneNumber=encryptedPhoneNumber, encryptedWeChat=whitelist.encryptedWeChat,
                                                uuid=whitelist.uuid, startDate=whitelist.startDate)
                webUser.save()
                return Response({"message": "密码设置成功"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "用户已存在，请联系管理员重设密码"}, status=status.HTTP_400_BAD_REQUEST)
        except Whitelist.DoesNotExist:
            return Response({"error": "用户信息未加入白名单，请联系管理员"}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({"error": "手机号或密码格式不正确"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
@csrf_exempt
@catch_exceptions
def reset_password(request):
    try:
        body = json.loads(request.body)
        uuid = body.get("uuid")
        token = body.get("token")
        new_password = body.get('password')
        if not uuid or not token or not new_password:
            return Response({"error": "无效请求"}, status=status.HTTP_400_BAD_REQUEST)
         
        try:
            webuser = WebUser.objects.get(uuid=uuid)
        except:
            return Response({"error": "无效请求"}, status=status.HTTP_400_BAD_REQUEST) 
        
        user = webuser.user
        if not default_token_generator.check_token(user, token):
            return Response({"error": "无效请求"}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        webuser.save()
        return Response({"message": "密码重置成功"})
    
    except json.JSONDecodeError:
        return Response({"error": "无效请求"}, status=status.HTTP_400_BAD_REQUEST) 
                

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
    
    try:
        webUser = WebUser.objects.get(uuid=uuid)
        setattr(webUser, f"survey{day}", responseId)
        setattr(webUser, f"survey{day}IsValid", isvalid)
        if day == 23: currentDay = 39
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
    if not Screen.objects.filter(uuid=key):
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@catch_exceptions
def collect_info(request):
    body = json.loads(request.body)
    keys = {"QQ", "WeChat", "phoneNumber", 'uuid', "responseId"}
    if any(k not in body for k in keys):
        return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST) 
    QQ = body["QQ"]
    WeChat = body["WeChat"]
    phoneNumber = body["phoneNumber"]
    uuid = body["uuid"]
    responseId = body["responseId"]
    
    if WeChat:
        if not Whitelist.objects.filter(uuid=uuid).exists() and not LSUser.objects.filter(uuid=uuid).exists()\
            and not Whitelist.objects.filter(encryptedPhoneNumber=encrypt(phoneNumber)).exists()\
            and not Whitelist.objects.filter(encryptedWeChat=encrypt(WeChat)).exists():
            whitelist = Whitelist.objects.create(uuid=uuid, encryptedPhoneNumber=encrypt(phoneNumber), encryptedWeChat=encrypt(WeChat), survey0=responseId)
            screen = Screen.objects.filter(uuid=uuid).update(consent=True, submitted=True)
        else:
            return Response({"status": "Fail", "message": "用户已存在"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        if not Whitelist.objects.filter(uuid=uuid).exists() and not LSUser.objects.filter(uuid=uuid).exists()\
            and not LSUser.objects.filter(encryptedPhoneNumber=encrypt(phoneNumber)).exists()\
            and not LSUser.objects.filter(encryptedQQ=encrypt(QQ)).exists():
            lsUser = LSUser.objects.create(uuid=uuid, encryptedPhoneNumber=encrypt(phoneNumber), encryptedQQ=encrypt(QQ), survey0=responseId)
            screen = Screen.objects.filter(uuid=uuid).update(submitted=True)
        else:
            return Response({"status": "Fail", "message": "用户已存在"}, status=status.HTTP_400_BAD_REQUEST)
            
    return Response({"status": "Success", "message": "成功提交"}, status=status.HTTP_200_OK)
    
    
@api_view(["POST", "GET"])
@catch_exceptions
@csrf_exempt
def screen_record(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST)

        keys = {"uuid", "responseId", "invalid", "eligible", "service"}
        if any(k not in body for k in keys):
            return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            uuid = body["uuid"]
            responseId = body["responseId"]
            valid = not bool(int(body["invalid"]))
            eligible = bool(int(body["eligible"]))
            service = bool(int(body["service"]))

        except (ValueError, TypeError):
            return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST)
        
        if Screen.objects.filter(uuid=uuid).exists():
            return Response({"status": "Fail", "message": "用户已存在"}, status=status.HTTP_400_BAD_REQUEST)
        Screen.objects.create(
            uuid=uuid,
            responseId=responseId,
            valid=valid,
            eligible=eligible,
            service=service
        )
        return Response({"status": "Success", "message": "成功提交"}, status=status.HTTP_201_CREATED)
        
    if request.method == "GET":
        uuid = request.query_params.get("uuid")
        try: 
            screen = Screen.objects.get(uuid=uuid)
            serialized = ScreenSerializer(screen)
            return Response(serialized.data, status=status.HTTP_200_OK)
        except Screen.DoesNotExist:
            return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(["POST"])
@csrf_exempt
@catch_exceptions
def assign_group(request):
    body = json.loads(request.body)
    keys = {"invalid", "group", "uuid", "responseId"}
    if any(k not in body for k in keys):
        return Response({"status": "Fail", "message": "无效问卷"}, status=status.HTTP_400_BAD_REQUEST) 
    
    isvalid = "False" if body['invalid'] == 1 else "True"
    responseId =  body["responseId"]
    uuid = body['uuid']
    group = body['group']
    
    try:
        webUser = WebUser.objects.get(uuid=uuid)
        
        if webUser.group != "Null":
            return Response({"status": "Fail", "message": "用户已分组"}, status=status.HTTP_400_BAD_REQUEST)
            
        webUser.group = group
        webUser.survey1 = responseId
        webUser.survey1IsValid = isvalid
        if isvalid == "False":  
            currentDay = 1
            webUser.banDay = 1
        elif group == "Waitlist": currentDay = 23
        else: currentDay = 1.1
        webUser.currentDay = currentDay
        webUser.save()
        
    except WebUser.DoesNotExist:
        return Response({"status": "Fail", "message": "用户不存在"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"status": "Success", "message": "成功提交"}, status=status.HTTP_200_OK)
