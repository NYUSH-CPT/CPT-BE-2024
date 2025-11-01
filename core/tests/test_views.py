"""
Comprehensive test suite for API endpoints in core/views.py

Tests cover:
- Authentication and authorization
- Success and failure cases
- Edge cases and error handling
- Data validation and business logic
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import date, timedelta
import json
from unittest.mock import patch, MagicMock

from core.models import WebUser, Whitelist, Screen, LSUser
from core.utility import encrypt


class BaseAPITestCase(TestCase):
    """Base test class with common setup utilities"""
    
    def setUp(self):
        self.client = APIClient()
        self.today = date.today()
        
    def create_whitelist(self, uuid="test_uuid", has_wechat=True, start_date=None, phone="13800138000"):
        """Helper to create a Whitelist entry"""
        if start_date is None:
            start_date = self.today
        return Whitelist.objects.create(
            uuid=uuid,
            encryptedPhoneNumber=encrypt(phone),
            encryptedWeChat=encrypt("wechat_" + uuid),
            has_add_wechat=has_wechat,
            startDate=start_date
        )
    
    def create_webuser(self, uuid="test_user", group="Exp1", start_date=None, 
                      current_day=1, ban_day=-1, ban_flag=False, phone="13800138000", **kwargs):
        """Helper to create a WebUser with authentication"""
        if start_date is None:
            start_date = self.today
        whitelist = self.create_whitelist(uuid=uuid, start_date=start_date, phone=phone)
        user = User.objects.create_user(username=uuid, password="testpass")
        webuser = WebUser.objects.create(
            user=user,
            uuid=uuid,
            whitelist=whitelist,
            encryptedPhoneNumber=encrypt(phone),
            encryptedWeChat=encrypt("wechat_" + uuid),
            group=group,
            startDate=start_date,
            currentDay=current_day,
            banDay=ban_day,
            banFlag=ban_flag,
            **kwargs
        )
        return webuser, user


class TestInfoAPI(BaseAPITestCase):
    """Tests for /info endpoint"""
    
    def test_info_get_success(self):
        """Test GET /info returns user info for authenticated user"""
        webuser, user = self.create_webuser(uuid="info_user", group="Exp1", current_day=5)
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/info')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('uuid', response.data)
        self.assertIn('currentDay', response.data)
        self.assertEqual(response.data['uuid'], "info_user")
        self.assertEqual(response.data['currentDay'], 5)
    
    def test_info_get_unauthorized(self):
        """Test GET /info returns 401 for unauthenticated user"""
        response = self.client.get('/api/info')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_info_get_user_not_found(self):
        """Test GET /info returns 401 when WebUser doesn't exist"""
        user = User.objects.create_user(username="no_webuser", password="test")
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/info')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('用户不存在', response.data['error'])
    
    def test_info_post_update_feedback6_viewed(self):
        """Test POST /info updates feedback6Viewed and currentDay"""
        webuser, user = self.create_webuser(uuid="feedback_user", current_day=6)
        
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/info', {'feedback6Viewed': True}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertTrue(webuser.feedback6Viewed)
        self.assertGreaterEqual(webuser.currentDay, 8)
    
    def test_info_post_update_feedback8_viewed(self):
        """Test POST /info updates feedback8Viewed and currentDay to 23"""
        webuser, user = self.create_webuser(uuid="feedback8_user", current_day=8)
        
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/info', {'feedback8Viewed': True}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertTrue(webuser.feedback8Viewed)
        self.assertGreaterEqual(webuser.currentDay, 23)
    
    def test_info_post_invalid_data(self):
        """Test POST /info returns 400 for invalid data"""
        webuser, user = self.create_webuser()
        
        self.client.force_authenticate(user=user)
        # Send invalid data that serializer will reject
        response = self.client.post('/api/info', {'currentDay': 'invalid'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('更新失败', response.data['error'])


class TestWritingAPI(BaseAPITestCase):
    """Tests for /writing/<day> endpoint"""
    
    def test_writing_get_success(self):
        """Test GET /writing/<day> returns writing content"""
        webuser, user = self.create_webuser(uuid="writing_user", current_day=5)
        webuser.writing4 = {"content": "Test writing content"}
        webuser.save()
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/writing/4')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('answer', response.data)
        self.assertEqual(response.data['answer'], {"content": "Test writing content"})
    
    def test_writing_get_not_reached(self):
        """Test GET /writing/<day> returns 403 if day not reached"""
        webuser, user = self.create_webuser(uuid="writing_user", current_day=3)
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/writing/4')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('当前进度尚未达到', response.data['error'])
    
    def test_writing_get_not_exists(self):
        """Test GET /writing/<day> returns 404 if writing doesn't exist"""
        webuser, user = self.create_webuser(uuid="writing_user", current_day=5)
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/writing/4')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('回答不存在', response.data['error'])
    
    def test_writing_get_day6_includes_prompt(self):
        """Test GET /writing/6 includes prompt from writing1"""
        webuser, user = self.create_webuser(uuid="writing_user", current_day=7)
        webuser.writing1 = {"prompt": "Day 1 prompt"}
        webuser.writing6 = {"content": "Day 6 writing"}
        webuser.save()
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/writing/6')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('prompt', response.data)
        self.assertEqual(response.data['prompt'], {"prompt": "Day 1 prompt"})
    
    @patch('builtins.open', create=True)
    def test_writing_get_day4_includes_reference(self, mock_open):
        """Test GET /writing/4 includes reference file"""
        mock_open.return_value.__enter__.return_value.read.return_value = '{"reference": "data"}'
        mock_open.return_value.__enter__.return_value.__iter__ = lambda x: iter([])
        
        webuser, user = self.create_webuser(uuid="writing_user", current_day=5)
        webuser.writing4 = {"content": "Test"}
        webuser.save()
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/writing/4')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reference', response.data)
    
    def test_writing_post_success(self):
        """Test POST /writing/<day> creates writing entry"""
        webuser, user = self.create_webuser(uuid="writing_user", current_day=4)
        
        self.client.force_authenticate(user=user)
        writing_data = {"content": "My writing response"}
        response = self.client.post('/api/writing/4', writing_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertEqual(webuser.writing4, writing_data)
        self.assertGreaterEqual(webuser.currentDay, 5)
    
    def test_writing_post_not_reached(self):
        """Test POST /writing/<day> returns 403 if day not reached"""
        webuser, user = self.create_webuser(uuid="writing_user", current_day=3)
        
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/writing/4', {"content": "Test"}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_writing_post_already_exists(self):
        """Test POST /writing/<day> returns 400 if writing already exists"""
        webuser, user = self.create_webuser(uuid="writing_user", current_day=5)
        webuser.writing4 = {"content": "Existing"}
        webuser.save()
        
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/writing/4', {"content": "New"}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('该写作任务的内容已存在', response.data['error'])
        self.assertTrue(response.data.get('exist'))


class TestFinishVideoAPI(BaseAPITestCase):
    """Tests for /video endpoint"""
    
    def test_finish_video_success(self):
        """Test POST /video updates currentDay to 2.1"""
        webuser, user = self.create_webuser(uuid="video_user", current_day=2)
        
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/video')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertGreaterEqual(webuser.currentDay, 2.1)
    
    def test_finish_video_user_not_found(self):
        """Test POST /video returns 404 if user doesn't exist"""
        user = User.objects.create_user(username="no_webuser", password="test")
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/video')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestSMSAPI(BaseAPITestCase):
    """Tests for /sms endpoint"""
    
    @patch('core.services.SMS.SmsService.send')
    def test_send_sms_success_new_webuser(self, mock_send):
        """Test POST /sms creates new WebUser and sends SMS"""
        mock_send.return_value = {'statusCode': 200, 'body': {'Message': 'OK'}}
        whitelist = self.create_whitelist(uuid="sms_user", phone="13800138000")
        user = User.objects.create_user(username="sms_user")
        
        response = self.client.post(
            '/api/sms',
            json.dumps({'phoneNumber': '13800138000'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('SMS sent', response.data['message'])
        self.assertTrue(WebUser.objects.filter(uuid="sms_user").exists())
        mock_send.assert_called_once()
    
    @patch('core.services.SMS.SmsService.send')
    def test_send_sms_success_existing_webuser(self, mock_send):
        """Test POST /sms sends SMS for existing WebUser"""
        mock_send.return_value = {'statusCode': 200, 'body': {'Message': 'OK'}}
        webuser, user = self.create_webuser(uuid="sms_existing", phone="13800138001")
        
        response = self.client.post(
            '/api/sms',
            json.dumps({'phoneNumber': '13800138001'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once()
    
    def test_send_sms_not_in_whitelist(self):
        """Test POST /sms returns 404 if phone not in whitelist"""
        response = self.client.post(
            '/api/sms',
            json.dumps({'phoneNumber': '13800138999'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('用户信息未加入白名单', response.data['error'])
    
    def test_send_sms_no_wechat(self):
        """Test POST /sms returns 400 if WeChat not added"""
        whitelist = self.create_whitelist(uuid="no_wechat", has_wechat=False, phone="13800138002")
        
        response = self.client.post(
            '/api/sms',
            json.dumps({'phoneNumber': '13800138002'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('请等待助教添加您的微信', response.data['error'])
    
    def test_send_sms_no_start_date(self):
        """Test POST /sms returns 400 if experiment hasn't started"""
        whitelist = self.create_whitelist(uuid="no_start", phone="13800138003")
        whitelist.startDate = None
        whitelist.save()
        
        response = self.client.post(
            '/api/sms',
            json.dumps({'phoneNumber': '13800138003'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('实验尚未开始', response.data['error'])
    
    @patch('core.services.SMS.SmsService.send')
    def test_send_sms_failure(self, mock_send):
        """Test POST /sms returns 500 if SMS service fails"""
        mock_send.return_value = {'statusCode': 500, 'msg': 'Service error'}
        
        whitelist = self.create_whitelist(uuid="sms_fail", phone="13800138004")
        
        response = self.client.post(
            '/api/sms',
            json.dumps({'phoneNumber': '13800138004'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def test_send_sms_invalid_phone(self):
        """Test POST /sms returns 400 for invalid phone number"""
        response = self.client.post(
            '/api/sms',
            json.dumps({'phoneNumber': '123'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('手机号码不合规', response.data['error'])


class TestLoginAPI(BaseAPITestCase):
    """Tests for /login endpoint"""
    
    def test_login_success(self):
        """Test POST /login returns JWT tokens on successful login"""
        whitelist = self.create_whitelist(uuid="login_user", phone="13800138005")
        user = User.objects.create_user(username="login_user", password="1234")
        
        response = self.client.post(
            '/api/login',
            json.dumps({'phoneNumber': '13800138005', 'passcode': '1234'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_login_wrong_password(self):
        """Test POST /login returns 400 for wrong password"""
        whitelist = self.create_whitelist(uuid="login_user", phone="13800138006")
        user = User.objects.create_user(username="login_user", password="1234")
        
        response = self.client.post(
            '/api/login',
            json.dumps({'phoneNumber': '13800138006', 'passcode': 'wrong'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('手机号或密码错误', response.data['error'])
    
    def test_login_not_in_whitelist(self):
        """Test POST /login returns 404 if phone not in whitelist"""
        response = self.client.post(
            '/api/login',
            json.dumps({'phoneNumber': '13800138999', 'passcode': '1234'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_login_user_not_found(self):
        """Test POST /login returns 400 if user doesn't exist"""
        whitelist = self.create_whitelist(uuid="no_user", phone="13800138007")
        
        response = self.client.post(
            '/api/login',
            json.dumps({'phoneNumber': '13800138007', 'passcode': '1234'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('尚未设置密码', response.data['error'])


class TestSignupAPI(BaseAPITestCase):
    """Tests for /signup endpoint"""
    
    def test_signup_success(self):
        """Test POST /signup creates user and WebUser"""
        whitelist = self.create_whitelist(uuid="signup_user", phone="13800138008")
        
        response = self.client.post(
            '/api/signup',
            json.dumps({'phoneNumber': '13800138008', 'passcode': '1234'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('密码设置成功', response.data['message'])
        self.assertTrue(WebUser.objects.filter(uuid="signup_user").exists())
        self.assertTrue(User.objects.filter(username="signup_user").exists())
    
    def test_signup_user_already_exists(self):
        """Test POST /signup returns 400 if user already exists"""
        whitelist = self.create_whitelist(uuid="signup_existing", phone="13800138009")
        user = User.objects.create_user(username="signup_existing", password="oldpass")
        
        response = self.client.post(
            '/api/signup',
            json.dumps({'phoneNumber': '13800138009', 'passcode': '1234'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('用户已存在', response.data['error'])


class TestQualtricsSubmissionAPI(BaseAPITestCase):
    """Tests for /qualtrics_submission endpoint"""
    
    def test_qualtrics_submission_success_survey23(self):
        """Test POST /qualtrics_submission updates survey23 and currentDay"""
        webuser, _ = self.create_webuser(uuid="survey_user", current_day=23)
        
        response = self.client.post(
            '/api/qualtrics_submission',
            json.dumps({
                'surveyDay': 23,
                'uuid': 'survey_user',
                'responseId': 'RESP123',
                'invalid': 0
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertEqual(webuser.survey23, 'RESP123')
        self.assertEqual(webuser.survey23IsValid, 'True')
        self.assertGreaterEqual(webuser.currentDay, 39)
    
    def test_qualtrics_submission_invalid_survey(self):
        """Test POST /qualtrics_submission marks survey as invalid"""
        webuser, _ = self.create_webuser(uuid="survey_invalid", current_day=23)
        
        response = self.client.post(
            '/api/qualtrics_submission',
            json.dumps({
                'surveyDay': 23,
                'uuid': 'survey_invalid',
                'responseId': 'RESP456',
                'invalid': 1
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertEqual(webuser.survey23IsValid, 'False')
    
    def test_qualtrics_submission_missing_fields(self):
        """Test POST /qualtrics_submission returns 400 if fields missing"""
        response = self.client.post(
            '/api/qualtrics_submission',
            json.dumps({'surveyDay': 23}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_qualtrics_submission_user_not_found(self):
        """Test POST /qualtrics_submission returns 400 if user not found"""
        response = self.client.post(
            '/api/qualtrics_submission',
            json.dumps({
                'surveyDay': 23,
                'uuid': 'nonexistent',
                'responseId': 'RESP789',
                'invalid': 0
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestCollectInfoAPI(BaseAPITestCase):
    """Tests for /collect_info endpoint"""
    
    def test_collect_info_with_wechat_success(self):
        """Test POST /collect_info creates Whitelist with WeChat"""
        screen = Screen.objects.create(uuid="collect_user", valid=True, eligible=True)
        
        response = self.client.post(
            '/api/collect_info',
            json.dumps({
                'uuid': 'collect_user',
                'phoneNumber': '13800138010',
                'WeChat': 'wechat123',
                'QQ': '',
                'responseId': 'RESP_COLLECT'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Whitelist.objects.filter(uuid='collect_user').exists())
        screen.refresh_from_db()
        self.assertTrue(screen.consent)
        self.assertTrue(screen.submitted)
    
    def test_collect_info_without_wechat_success(self):
        """Test POST /collect_info creates LSUser without WeChat"""
        screen = Screen.objects.create(uuid="collect_ls", valid=True, eligible=True)
        
        response = self.client.post(
            '/api/collect_info',
            json.dumps({
                'uuid': 'collect_ls',
                'phoneNumber': '13800138011',
                'WeChat': '',
                'QQ': 'qq123',
                'responseId': 'RESP_LS'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(LSUser.objects.filter(uuid='collect_ls').exists())
    
    def test_collect_info_duplicate_user(self):
        """Test POST /collect_info returns 400 if user already exists"""
        screen = Screen.objects.create(uuid="duplicate", valid=True, eligible=True)
        Whitelist.objects.create(
            uuid='duplicate',
            encryptedPhoneNumber=encrypt('13800138012'),
            encryptedWeChat=encrypt('wechat')
        )
        
        response = self.client.post(
            '/api/collect_info',
            json.dumps({
                'uuid': 'duplicate',
                'phoneNumber': '13800138012',
                'WeChat': 'wechat',
                'QQ': '',
                'responseId': 'RESP_DUP'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('用户已存在', response.data['message'])


class TestScreenRecordAPI(BaseAPITestCase):
    """Tests for /screen_record endpoint"""
    
    def test_screen_record_post_success(self):
        """Test POST /screen_record creates Screen entry"""
        response = self.client.post(
            '/api/screen_record',
            json.dumps({
                'uuid': 'screen_user',
                'responseId': 'RESP_SCREEN',
                'invalid': 0,
                'eligible': 1,
                'service': 0
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Screen.objects.filter(uuid='screen_user').exists())
        screen = Screen.objects.get(uuid='screen_user')
        self.assertTrue(screen.valid)
        self.assertTrue(screen.eligible)
        self.assertFalse(screen.service)
    
    def test_screen_record_post_duplicate(self):
        """Test POST /screen_record returns 400 if uuid already exists"""
        Screen.objects.create(uuid='screen_dup', valid=True)
        
        response = self.client.post(
            '/api/screen_record',
            json.dumps({
                'uuid': 'screen_dup',
                'responseId': 'RESP_DUP',
                'invalid': 0,
                'eligible': 1,
                'service': 0
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('用户已存在', response.data['message'])
    
    def test_screen_record_get_success(self):
        """Test GET /screen_record returns Screen data"""
        screen = Screen.objects.create(
            uuid='screen_get',
            valid=True,
            eligible=True,
            service=False,
            responseId='RESP_GET'
        )
        
        response = self.client.get('/api/screen_record', {'uuid': 'screen_get'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], 'screen_get')
        self.assertTrue(response.data['valid'])
    
    def test_screen_record_get_not_found(self):
        """Test GET /screen_record returns 404 if uuid not found"""
        response = self.client.get('/api/screen_record', {'uuid': 'nonexistent'})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestAssignGroupAPI(BaseAPITestCase):
    """Tests for /assign_group endpoint"""
    
    def test_assign_group_exp1_success(self):
        """Test POST /assign_group assigns Exp1 group"""
        webuser, _ = self.create_webuser(uuid="assign_user", group="Null", current_day=1)
        
        response = self.client.post(
            '/api/assign_group',
            json.dumps({
                'uuid': 'assign_user',
                'group': 'Exp1',
                'responseId': 'RESP_ASSIGN',
                'invalid': 0
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertEqual(webuser.group, 'Exp1')
        self.assertEqual(webuser.currentDay, 1.1)
    
    def test_assign_group_waitlist(self):
        """Test POST /assign_group assigns Waitlist group"""
        webuser, _ = self.create_webuser(uuid="assign_waitlist", group="Null")
        
        response = self.client.post(
            '/api/assign_group',
            json.dumps({
                'uuid': 'assign_waitlist',
                'group': 'Waitlist',
                'responseId': 'RESP_WL',
                'invalid': 0
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertEqual(webuser.group, 'Waitlist')
        self.assertEqual(webuser.currentDay, 23)
    
    def test_assign_group_invalid_survey(self):
        """Test POST /assign_group sets banDay=1 for invalid survey"""
        webuser, _ = self.create_webuser(uuid="assign_invalid", group="Null")
        
        response = self.client.post(
            '/api/assign_group',
            json.dumps({
                'uuid': 'assign_invalid',
                'group': 'Exp1',
                'responseId': 'RESP_INVALID',
                'invalid': 1
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        webuser.refresh_from_db()
        self.assertEqual(webuser.banDay, 1)
        self.assertEqual(webuser.survey1IsValid, 'False')
    
    def test_assign_group_already_assigned(self):
        """Test POST /assign_group returns 400 if already assigned"""
        webuser, _ = self.create_webuser(uuid="assign_dup", group="Exp1")
        
        response = self.client.post(
            '/api/assign_group',
            json.dumps({
                'uuid': 'assign_dup',
                'group': 'Exp2',
                'responseId': 'RESP_DUP',
                'invalid': 0
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('用户已分组', response.data['message'])


class TestKeyAPI(BaseAPITestCase):
    """Tests for /key endpoint"""
    
    def test_key_exists(self):
        """Test GET /key returns 200 if key exists"""
        Screen.objects.create(uuid='test_key')
        
        response = self.client.get('/api/key', {'key': 'test_key'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_key_not_found(self):
        """Test GET /key returns 404 if key doesn't exist"""
        response = self.client.get('/api/key', {'key': 'nonexistent'})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestResetPasswordAPI(BaseAPITestCase):
    """Tests for /reset_password endpoint"""
    
    def test_reset_password_success(self):
        """Test POST /reset_password successfully resets password"""
        webuser, user = self.create_webuser(uuid="reset_user")
        token = default_token_generator.make_token(user)
        
        response = self.client.post(
            '/api/reset_password',
            json.dumps({
                'uuid': 'reset_user',
                'token': token,
                'password': 'newpassword123'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('密码重置成功', response.data['message'])
        user.refresh_from_db()
        self.assertTrue(user.check_password('newpassword123'))
    
    def test_reset_password_invalid_token(self):
        """Test POST /reset_password returns 400 for invalid token"""
        webuser, _ = self.create_webuser(uuid="reset_invalid")
        
        response = self.client.post(
            '/api/reset_password',
            json.dumps({
                'uuid': 'reset_invalid',
                'token': 'invalid_token',
                'password': 'newpass'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_reset_password_missing_fields(self):
        """Test POST /reset_password returns 400 if fields missing"""
        response = self.client.post(
            '/api/reset_password',
            json.dumps({'uuid': 'test'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

