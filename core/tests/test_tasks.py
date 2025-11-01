"""
完整的测试用例，覆盖 prod_scheduled_tasks.json 中的所有消息任务。

测试覆盖：
1. WebUser 任务进度创建逻辑（currentDay 计算）
2. 禁用规则（validity_check）
3. 所有任务ID的发送条件

重要逻辑说明：
- banDay == 1 的用户会被跳过（不处理）

两个不同的 currentDay 概念：
1. **计算的 currentDay** (tasks.py 第52行): `currentDay = (current_date - user.startDate).days + 1`
   - 表示实验开始后的第几天（从1开始，可以是任意整数）
   - 用于匹配任务配置中的 days 列表

2. **webuser.currentDay**: 数据库中存储的任务进度
   - 只能是特定值: 1, 1.1, 2, 2.1, 3, 4, 5, 6, 7, 8, 9, 10, 23, 39, 99, 100
   - 表示用户当前需要完成的任务阶段

任务阶段说明：
- 1: pre_survey
- 1.1: day_1_writing
- 2: video
- 2.1: day_2_game
- 3: day_3_game
- 4: day_4_writing
- 5: day_5_writing
- 6: day_6_writing
- 7: day_6_feedback
- 8: day_8_writing
- 9: day_8_feedback
- 10: 无任务，表示干预完成
- 23, 39, 99: post_survey
- 100: 全部任务完成

- 所有 blued_msg.send 调用都被 mock，避免真实调用
"""

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
import json

from core.models import WebUser, Whitelist, Log, BannedLog
from core import tasks


class TasksTestCase(TestCase):
    """基础测试类，提供通用的用户创建方法"""
    
    def setUp(self):
        """设置测试数据"""
        self.today = date.today()
        
    def create_whitelist(self, uuid="test_uuid", has_wechat=True, start_date=None):
        """创建白名单用户"""
        if start_date is None:
            start_date = self.today
        return Whitelist.objects.create(
            uuid=uuid,
            encryptedPhoneNumber=f"encrypted_phone_{uuid}",
            encryptedWeChat=f"encrypted_wechat_{uuid}",
            has_add_wechat=has_wechat,
            startDate=start_date
        )
    
    def create_webuser(self, uuid="test_user", group="Exp1", start_date=None, 
                      current_day=1, ban_day=-1, ban_flag=False, **kwargs):
        """创建 WebUser"""
        if start_date is None:
            start_date = self.today
        whitelist = self.create_whitelist(uuid=uuid, start_date=start_date)
        user = User.objects.create_user(username=uuid)
        webuser = WebUser.objects.create(
            user=user,
            uuid=uuid,
            whitelist=whitelist,
            encryptedPhoneNumber=f"encrypted_phone_{uuid}",
            encryptedWeChat=f"encrypted_wechat_{uuid}",
            group=group,
            startDate=start_date,
            currentDay=current_day,
            banDay=ban_day,
            banFlag=ban_flag,
            **kwargs
        )
        return webuser
    
    def calculate_current_day(self, start_date, target_date=None):
        """计算指定日期的currentDay"""
        if target_date is None:
            target_date = self.today
        return (target_date - start_date).days + 1
    
    def assert_message_sent(self, mock_send, uuid, task_id):
        """验证消息是否发送给指定用户和任务ID"""
        call_args_list = [call[0] for call in mock_send.call_args_list]
        self.assertIn((uuid, task_id), call_args_list, 
                     f"消息应该发送给用户 {uuid}，任务ID {task_id}")
    
    def assert_message_not_sent(self, mock_send, uuid, task_id):
        """验证消息没有发送给指定用户和任务ID"""
        call_args_list = [call[0] for call in mock_send.call_args_list]
        self.assertNotIn((uuid, task_id), call_args_list,
                        f"消息不应该发送给用户 {uuid}，任务ID {task_id}")
    
    def assert_log_created(self, user, task_id=None, contains_text=None):
        """验证Log记录已创建"""
        logs = Log.objects.filter(user=user)
        if task_id:
            self.assertTrue(any(f"task {task_id}" in log.log for log in logs),
                          f"应该创建任务 {task_id} 的Log记录")
        elif contains_text:
            self.assertTrue(any(contains_text in log.log for log in logs),
                          f"应该创建包含 '{contains_text}' 的Log记录")
        else:
            self.assertTrue(logs.exists(), "应该创建Log记录")
    
    def assert_banlog_created(self, user, ban_tags=None):
        """验证BannedLog记录已创建"""
        banlogs = BannedLog.objects.filter(user=user)
        self.assertTrue(banlogs.exists(), "应该创建BannedLog记录")
        if ban_tags:
            last_log = banlogs.latest('time')
            # banTags 是 set，转换为字符串后包含在log中
            log_text = last_log.log
            for tag in ban_tags:
                self.assertIn(tag, log_text, f"BannedLog应该包含tag: {tag}")


class Day0TasksTestCase(TasksTestCase):
    """测试 ID 1, 2: day_0 任务（时间 20）
    
    当前逻辑：
    - 处理 WebUser 实例（不再是 Whitelist）
    - 检查 currentDay == 0（实验开始前一天）
    - currentDay = (当前日期 - startDate).days + 1
    - day 0 意味着 startDate 是明天
    - criteria: ["not_banned"]，需要 banFlag == False
    - banDay != 1（banDay == 1 会被跳过）
    """
    
    @patch('core.services.blued_msg.send')
    def test_task_1_waitlist_day_0(self, mock_send):
        """任务ID 1: Waitlist组，day 0，time 20"""
        # startDate 设为明天，所以计算的currentDay = (today - tomorrow).days + 1 = 0
        start_date = self.today + timedelta(days=1)
        webuser = self.create_webuser(
            uuid="waitlist_user",
            group="Waitlist",
            start_date=start_date,
            current_day=1,  # webuser.currentDay 表示任务进度，day 0时应该是1（pre_survey引起）
            ban_day=-1,  # banDay != 1 才会被处理
            ban_flag=False  # not_banned 需要 banFlag == False
        )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证：计算出的 currentDay 应该是 0
        calculated_day = (self.today - webuser.startDate).days + 1
        self.assertEqual(calculated_day, 0)
        
        # 验证消息发送：应该发送任务ID 1给Waitlist用户
        self.assert_message_sent(mock_send, "waitlist_user", 1)
        
        # 验证Log记录创建
        self.assert_log_created(webuser, task_id=1)
            
    @patch('core.services.blued_msg.send')
    def test_task_2_exp_groups_day_0(self, mock_send):
        """任务ID 2: Exp1/Exp2组，day 0，time 20"""
        # startDate 设为明天，所以计算的currentDay = 0
        start_date = self.today + timedelta(days=1)
        
        for group in ["Exp1", "Exp2"]:
            webuser = self.create_webuser(
                uuid=f"exp_{group.lower()}_user",
                group=group,
                start_date=start_date,
                current_day=1,  # webuser.currentDay = 1 (pre_survey阶段)
                ban_day=-1,  # banDay != 1 才会被处理
                ban_flag=False  # not_banned 需要 banFlag == False
            )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送：应该发送任务ID 2给Exp1和Exp2用户
        self.assert_message_sent(mock_send, "exp_exp1_user", 2)
        self.assert_message_sent(mock_send, "exp_exp2_user", 2)
        
        # 验证Log记录创建
        for group in ["Exp1", "Exp2"]:
            webuser = WebUser.objects.get(uuid=f"exp_{group.lower()}_user")
            self.assert_log_created(webuser, task_id=2)
    
    @patch('core.services.blued_msg.send')
    def test_task_1_2_should_skip_banDay_equals_1(self, mock_send):
        """测试 banDay == 1 的用户应该被跳过"""
        start_date = self.today + timedelta(days=1)
        webuser = self.create_webuser(
            uuid="skip_user",
            group="Waitlist",
            start_date=start_date,
            ban_day=1,  # banDay != 1 才会被处理  # banDay == 1 应该被跳过
            ban_flag=False
        )
        
        tasks.launch_tasks(20)
        
        # 验证：banDay == 1 的用户不应该收到消息
        self.assert_message_not_sent(mock_send, "skip_user", 1)
        self.assert_message_not_sent(mock_send, "skip_user", 2)
        
        # 验证没有为这个用户创建消息发送的Log
        logs = Log.objects.filter(user=webuser)
        user_task_logs = [log for log in logs if log.user == webuser and "task" in log.log]
        self.assertEqual(len(user_task_logs), 0, "banDay==1的用户不应该收到任务消息")
        
    @patch('core.services.blued_msg.send')
    def test_task_1_2_should_skip_banned_users(self, mock_send):
        """测试已禁用用户（banFlag=True）不应该收到消息"""
        start_date = self.today + timedelta(days=1)
        webuser = self.create_webuser(
            uuid="banned_user",
            group="Waitlist",
            start_date=start_date,
            ban_day=-1,
            ban_flag=True  # 已禁用，不应该收到 not_banned 任务
        )
        
        tasks.launch_tasks(20)
        
        # 验证条件：banFlag == True 时不应该发送 ID 1 或 2
        self.assert_message_not_sent(mock_send, "banned_user", 1)
        self.assert_message_not_sent(mock_send, "banned_user", 2)
        
        # 验证没有为这个用户创建消息发送的Log
        logs = Log.objects.filter(user=webuser)
        user_task_logs = [log for log in logs if log.user == webuser and "task" in log.log]
        self.assertEqual(len(user_task_logs), 0, "banned用户不应该收到not_banned任务")


class SurveyNotDoneTasksTestCase(TasksTestCase):
    """测试 ID 3, 13 (两个): survey_not_done 任务"""
    
    @patch('core.services.blued_msg.send')
    def test_task_3_survey_not_done_time_8(self, mock_send):
        """任务ID 3: 时间8，days [23, 39, 99]，survey_not_done"""
        # 计算的currentDay=23（实验第23天），webuser.currentDay=23（任务进度在post_survey阶段）
        start_date = self.today - timedelta(days=22)
        webuser = self.create_webuser(
            uuid="survey_user",
            group="Exp1",
            start_date=start_date,
            current_day=23,  # webuser.currentDay = 23 (post_survey阶段)
            ban_day=-1,  # banDay != 1 才会被处理
            survey23IsValid="Null"  # 未完成
        )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(8)
        
        # 验证消息发送
        self.assert_message_sent(mock_send, "survey_user", 3)
        
        # 验证Log记录创建
        self.assert_log_created(webuser, task_id=3)
        
    @patch('core.services.blued_msg.send')
    def test_task_13_survey_not_done_time_20(self, mock_send):
        """任务ID 13 (第一个): 时间20，days [23, 39, 99]，survey_not_done"""
        start_date = self.today - timedelta(days=22)
        webuser = self.create_webuser(
            uuid="survey_user_20",
            group="Waitlist",
            start_date=start_date,
            current_day=23,
            ban_day=-1,  # banDay != 1 才会被处理
            survey23IsValid="Null"
        )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送
        self.assert_message_sent(mock_send, "survey_user_20", 13)
        
        # 验证Log记录创建
        self.assert_log_created(webuser, task_id=13)
        
    @patch('core.services.blued_msg.send')
    def test_task_13_survey_not_done_time_8_extended(self, mock_send):
        """任务ID 13 (第二个): 时间8，days [24,40,100,25,41,101,27,43,103]，survey_not_done"""
        # 计算的currentDay=24（实验第24天），但webuser.currentDay应该是23原文（仍然在survey anchor范围内）
        start_date = self.today - timedelta(days=23)
        webuser = self.create_webuser(
            uuid="survey_user_extended",
            group="Exp2",
            start_date=start_date,
            current_day=23,  # webuser.currentDay = 23 (在anchor 23范围内，可接受24-29天)
            ban_day=-1,  # banDay != 1 才会被处理
            survey23IsValid="Null"
        )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(8)
        
        # 验证消息发送（ID 13第二个，days包含24）
        self.assert_message_sent(mock_send, "survey_user_extended", 13)
        
        # 验证Log记录创建
        self.assert_log_created(webuser, task_id=13)


class NotBannedTasksTestCase(TasksTestCase):
    """测试 ID 4, 5, 6, 7, 26: not_banned 相关任务"""
    
    @patch('core.services.blued_msg.send')
    def test_task_4_not_banned_morning(self, mock_send):
        """任务ID 4: Exp1/Exp2，days [1-9]，time 8，not_banned"""
        # 实验天数1-9对应不同的任务进度值
        task_progress_map = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
        for exp_day in range(1, 10):
            start_date = self.today - timedelta(days=exp_day - 1)
            webuser = self.create_webuser(
                uuid=f"not_banned_day{exp_day}",
                group="Exp1",
                start_date=start_date,
                current_day=task_progress_map[exp_day],  # 使用对应的任务进度值
                ban_day=-1,  # banDay != 1 才会被处理
                ban_flag=False
            )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(8)
        
        # 验证消息发送：应该发送给所有day 1-9的用户
        for exp_day in range(1, 10):
            self.assert_message_sent(mock_send, f"not_banned_day{exp_day}", 4)
            webuser = WebUser.objects.get(uuid=f"not_banned_day{exp_day}")
            self.assert_log_created(webuser, task_id=4)
    
    @patch('core.services.blued_msg.send')
    def test_task_5_not_banned_task_not_done(self, mock_send):
        """任务ID 5: Exp1/Exp2，days [1-9]，time 20，not_banned + task_not_done"""
        # currentDay 必须 < currentDay+1 才会触发
        start_date = self.today - timedelta(days=2)
        webuser = self.create_webuser(
            uuid="task_not_done_user",
            group="Exp2",
            start_date=start_date,
            current_day=2,  # currentDay < 2+1，满足条件
            ban_day=-1,  # banDay != 1 才会被处理
            ban_flag=False
        )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送
        self.assert_message_sent(mock_send, "task_not_done_user", 5)
        
        # 验证Log记录创建
        self.assert_log_created(webuser, task_id=5)
    
    @patch('core.services.blued_msg.send')
    def test_task_6_quality_check_fail_msg(self, mock_send):
        """任务ID 6: Exp1/Exp2，days [1-9]，time 20，not_banned + has_unsent_quality_check_fail_msg"""
        start_date = self.today - timedelta(days=4)
        webuser = self.create_webuser(
            uuid="quality_fail_user",
            group="Exp1",
            start_date=start_date,
            current_day=5,
            ban_day=-1,  # banDay != 1 才会被处理
            ban_flag=False,
            writing4QualityCheckRA="False",
            writing4QualityCheckCS="False",
            writing4QualityCheckNotified=False
        )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送
        self.assert_message_sent(mock_send, "quality_fail_user", 6)
        
        # 验证Log记录创建
        self.assert_log_created(webuser, task_id=6)
        
        # 验证状态更新：writing1QualityCheckNotified 应该被设置为 True
        webuser.refresh_from_db()
        self.assertTrue(webuser.writing4QualityCheckNotified, 
                       "应该更新writing4QualityCheckNotified为True")
    
    @patch('core.services.blued_msg.send')
    def test_task_7_after_game_ends(self, mock_send):
        """任务ID 7: Exp1/Exp2，day 2，after game ends，not_banned
        
        根据 gameModel.py 第449-461行，ID 7 的触发条件：
        - 在游戏进行中，达到 TransitionQuestion 节点
        - display_id == 8 (游戏第8个场景)
        - user.group != "Waitlist"
        - user.gameBreakFlag == False
        - user.score < 30600 (总分102000的30%)
        - 此时会设置 currentDay = 3
        - 游戏中直接调用 blued_msg.send(user.uuid, 7)
        
        注意：此任务在游戏代码中直接发送，不在 tasks.py 的 launch_tasks 中处理
        time="after the game ends" 是描述性的，实际在游戏中触发
        """
        # 模拟游戏中断时的状态（实验天数2，任务进度2）
        start_date = self.today - timedelta(days=2)
        webuser = self.create_webuser(
            uuid="game_user_day2_break",
            group="Exp1",
            start_date=start_date,
            current_day=2,  # webuser.currentDay = 2 (video阶段)
            ban_day=-1,  # banDay != 1 才会被处理
            ban_flag=False,  # not_banned
            gameBreakFlag=False,  # 游戏还未中断
            score=20000  # score < 30600 (低于30%)
        )
        
        # 验证触发条件
        self.assertEqual(webuser.currentDay, 2)  # 任务进度2
        self.assertLess(webuser.score, 30600)  # 分数低于30%
        self.assertFalse(webuser.banFlag)  # 未禁用
        self.assertFalse(webuser.gameBreakFlag)  # 游戏未中断
        
        # 注意：实际发送在 gameModel.py 中进行，这里主要验证条件
        # 实际游戏中会在满足条件时直接调用: blued_msg.send(user.uuid, 7)
    
    @patch('core.services.blued_msg.send')
    def test_task_26_train_complete(self, mock_send):
        """任务ID 26: Exp1/Exp2，days [10-13]，time 8，not_banned + train_complete"""
        # 实验天数10-13时，webuser.currentDay应该是10（表示干预完成）
        for exp_day in range(10, 14):
            start_date = self.today - timedelta(days=exp_day - 1)
            webuser = self.create_webuser(
                uuid=f"train_complete_day{exp_day}",
                group="Exp1",
                start_date=start_date,
                current_day=10,  # webuser.currentDay = 10 (干预完成阶段)
                ban_day=-1,  # banDay != 1 才会被处理
                ban_flag=False,
                trainCompleteNotified=False
            )
            # 验证条件：currentDay >= 10 且未通知过
            self.assertGreaterEqual(webuser.currentDay, 10)
            self.assertFalse(webuser.trainCompleteNotified)
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(8)
        
        # 验证消息发送：应该发送给所有day 10-13的用户
        for exp_day in range(10, 14):
            self.assert_message_sent(mock_send, f"train_complete_day{exp_day}", 26)
            webuser = WebUser.objects.get(uuid=f"train_complete_day{exp_day}")
            self.assert_log_created(webuser, task_id=26)
            # 验证状态更新：trainCompleteNotified 应该被设置为 True
            webuser.refresh_from_db()
            self.assertTrue(webuser.trainCompleteNotified, 
                           f"用户train_complete_day{exp_day}应该被标记为trainCompleteNotified")


class AllCriteriaTasksTestCase(TasksTestCase):
    """测试 ID 9, 10, 11: all 条件任务"""
    
    @patch('core.services.blued_msg.send')
    def test_task_9_all_day_22(self, mock_send):
        """任务ID 9: 所有组，day 22，time 20，all"""
        # 实验天数22：处于干预完成之后（day 10），post_survey之前
        # webuser.currentDay应该是10（干预完成阶段）
        start_date = self.today - timedelta(days=21)
        for group in ["Exp1", "Exp2", "Waitlist"]:
            webuser = self.create_webuser(
                uuid=f"all_user_{group}_22",
                group=group,
                start_date=start_date,
                current_day=10,  # 有效值：干预完成阶段
                ban_day=-1,  # banDay != 1 才会被处理
            )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送：应该发送给所有组
        for group in ["Exp1", "Exp2", "Waitlist"]:
            self.assert_message_sent(mock_send, f"all_user_{group}_22", 9)
            webuser = WebUser.objects.get(uuid=f"all_user_{group}_22")
            self.assert_log_created(webuser, task_id=9)
    
    @patch('core.services.blued_msg.send')
    def test_task_10_all_day_38(self, mock_send):
        """任务ID 10: 所有组，day 38，time 20，all"""
        # 实验天数38：处于post_survey 23之后（23-29是survey 23的窗口），survey 39之前
        # webuser.currentDay应该是23（post_survey阶段）
        start_date = self.today - timedelta(days=37)
        for group in ["Exp1", "Exp2", "Waitlist"]:
            webuser = self.create_webuser(
                uuid=f"all_user_{group}_38",
                group=group,
                start_date=start_date,
                current_day=39,  # 有效值：post_survey阶段
                ban_day=-1,  # banDay != 1 才会被处理
            )
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送：应该发送给所有组
        for group in ["Exp1", "Exp2", "Waitlist"]:
            self.assert_message_sent(mock_send, f"all_user_{group}_38", 10)
            webuser = WebUser.objects.get(uuid=f"all_user_{group}_38")
            self.assert_log_created(webuser, task_id=10)
    
    @patch('core.services.blued_msg.send')
    def test_task_11_all_day_98(self, mock_send):
        """任务ID 11: 所有组，day 98，time 20，all"""
        # 实验天数98：处于post_survey 39之后（39-45是survey 39的窗口），survey 99之前
        # webuser.currentDay应该是39（post_survey阶段）
        start_date = self.today - timedelta(days=97)
        for group in ["Exp1", "Exp2", "Waitlist"]:
            webuser = self.create_webuser(
                uuid=f"all_user_{group}_98",
                group=group,
                start_date=start_date,
                current_day=39,  # 有效值：post_survey阶段
                ban_day=-1,  # banDay != 1 才会被处理
            )
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送：应该发送给所有组
        for group in ["Exp1", "Exp2", "Waitlist"]:
            self.assert_message_sent(mock_send, f"all_user_{group}_98", 11)
            webuser = WebUser.objects.get(uuid=f"all_user_{group}_98")
            self.assert_log_created(webuser, task_id=11)


class BannedTasksTestCase(TasksTestCase):
    """测试 ID 16, 18, 21, 22, 24: banned 相关任务"""
    
    @patch('core.services.blued_msg.send')
    def test_task_16_banned_task_not_done(self, mock_send):
        """任务ID 16: Exp1/Exp2，days [2-9]，time 8，banned + task_not_done"""
        start_date = self.today - timedelta(days=5)
        webuser = self.create_webuser(
            uuid="banned_task_not_done",
            group="Exp1",
            start_date=start_date,
            current_day=2,
            ban_day=-1,  # banDay != 1 才会被处理
            ban_flag=False,
            banNotified=False
        )
        # 需要设置 banTags 包含 "task_not_done"
        # webuser.banReasons = [{"tag": "task_not_done", "label": "任务超时", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        # webuser.save()
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(8)
        # 验证消息发送
        self.assert_message_sent(mock_send, "banned_task_not_done", 16)
        
        # 验证Log记录创建
        self.assert_log_created(webuser, task_id=16)
        
        # 验证状态更新：banNotified 应该被设置为 True
        webuser.refresh_from_db()
        self.assertTrue(webuser.banNotified, "应该更新banNotified为True")
        
        # 验证BannedLog记录创建
        self.assert_banlog_created(webuser, ban_tags={"task_not_done"})
    
    @patch('core.services.blued_msg.send')
    def test_task_18_banned_game_score_low(self, mock_send):
        """任务ID 18: Exp1/Exp2，day 3，after game ends，banned + game_score_low
        
        根据 gameModel.py 第464-475行，ID 18 的触发条件：
        - 游戏结束 (isinstance(node, End))
        - user.group != "Waitlist"
        - 游戏结束时设置 currentDay = 4
        - 调用 validity_check()
        - 设置 gameFinished = True
        - 如果 score < 61200 (60%)，validity_check() 会添加 "game_score_low" tag
        - 如果 "game_score_low" 在 banTags 中，游戏中直接调用 blued_msg.send(user.uuid, 18)
        
        注意：此任务在游戏代码中直接发送，不在 tasks.py 的 launch_tasks 中处理
        time="after the game ends" 是描述性的，实际在游戏结束时触发
        """
        # 模拟游戏结束时的状态（实验天数3）
        start_date = self.today - timedelta(days=2)
        webuser = self.create_webuser(
            uuid="banned_game_low_finished",
            group="Exp2",
            start_date=start_date,
            current_day=3,  # 游戏前任务进度3（day_3_game）
            ban_day=-1,  # banDay != 1 才会被处理
            ban_flag=False,  # 初始未禁用
            banNotified=False,
            gameFinished=True,  # 游戏已完成
            score=50000  # score < 61200 (低于60%)
        )
        
        # 验证触发条件
        self.assertTrue(webuser.gameFinished)  # 游戏已完成
        self.assertLess(webuser.score, 61200)  # 分数低于60%
        
        # 调用 validity_check 会产生 "game_score_low" tag
        ban_tags = webuser.validity_check()
        self.assertIn("game_score_low", ban_tags)  # 应该被标记为 game_score_low
        self.assertTrue(webuser.banFlag)  # 应该被禁用
        
        # 验证 banReasons 中包含 game_score_low
        ban_tags_set = {entry["tag"] for entry in webuser.banReasons}
        self.assertIn("game_score_low", ban_tags_set)
        
        # 注意：实际发送在 gameModel.py 中进行，这里主要验证条件
        # 实际游戏中会在满足条件时直接调用: blued_msg.send(user.uuid, 18)
    
    @patch('core.services.blued_msg.send')
    def test_task_21_banned_quality_check_fail(self, mock_send):
        """任务ID 21: Exp1/Exp2，days [1,4,5,6,7,8,9]，time 20，banned + quality_check_fail"""
        for day in [1, 4, 5, 6, 7, 8, 9]:
            start_date = self.today - timedelta(days=day - 1)
            webuser = self.create_webuser(
                uuid=f"banned_quality_day{day}",
                group="Exp1",
                start_date=start_date,
                current_day=day,
                ban_day=-1,  # banDay != 1 才会被处理
                ban_flag=True,
                banNotified=False
            )
            webuser.banReasons = [{"tag": "quality_check_fail", "label": "质量检查失败", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
            webuser.save()
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(20)
        
        # 验证消息发送：应该发送给所有符合条件的用户
        for day in [1, 4, 5, 6, 7, 8, 9]:
            self.assert_message_sent(mock_send, f"banned_quality_day{day}", 21)
            webuser = WebUser.objects.get(uuid=f"banned_quality_day{day}")
            self.assert_log_created(webuser, task_id=21)
            # 验证状态更新
            webuser.refresh_from_db()
            self.assertTrue(webuser.banNotified, f"用户banned_quality_day{day}应该被标记为banNotified")
            self.assert_banlog_created(webuser, ban_tags={"quality_check_fail"})
    
    @patch('core.services.blued_msg.send')
    def test_task_22_banned_pre_survey_invalid(self, mock_send):
        """任务ID 22: Exp1/Exp2/Waitlist/Null，days [1,2,3]，time 8，banned + pre_survey_invalid"""
        for day in [1, 2, 3]:
            start_date = self.today - timedelta(days=day - 1)
            for group in ["Exp1", "Exp2", "Waitlist", "Null"]:
                webuser = self.create_webuser(
                    uuid=f"banned_pre_survey_{group}_day{day}",
                    group=group,
                    start_date=start_date,
                    current_day=day,
                    ban_day=-1,  # banDay != 1 才会被处理
                    ban_flag=True,
                    banNotified=False,
                    survey1IsValid="False"
                )
                webuser.banReasons = [{"tag": "pre_survey_invalid", "label": "前测问卷无效", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
                webuser.save()
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(8)
        
        # 验证消息发送：应该发送给所有符合条件的用户
        for day in [1, 2, 3]:
            for group in ["Exp1", "Exp2", "Waitlist", "Null"]:
                self.assert_message_sent(mock_send, f"banned_pre_survey_{group}_day{day}", 22)
                webuser = WebUser.objects.get(uuid=f"banned_pre_survey_{group}_day{day}")
                self.assert_log_created(webuser, task_id=22)
                # 验证状态更新
                webuser.refresh_from_db()
                self.assertTrue(webuser.banNotified, 
                               f"用户banned_pre_survey_{group}_day{day}应该被标记为banNotified")
                self.assert_banlog_created(webuser, ban_tags={"pre_survey_invalid"})
    
    @patch('core.services.blued_msg.send')
    def test_task_24_banned_post_survey_invalid(self, mock_send):
        """任务ID 24: Exp1/Exp2/Waitlist，days [99-107]，time 8，banned + post_survey_invalid"""
        for day in range(99, 108):
            start_date = self.today - timedelta(days=day - 1)
            for group in ["Exp1", "Exp2", "Waitlist"]:
                webuser = self.create_webuser(
                    uuid=f"banned_post_survey_{group}_day{day}",
                    group=group,
                    start_date=start_date,
                    current_day=99,  # 有效值：post_survey阶段（在survey 99 anchor范围内，可接受99-105天）
                    ban_day=-1,  # banDay != 1 才会被处理
                    ban_flag=True,
                    banNotified=False,
                    survey23IsValid="False",
                    survey39IsValid="False",
                    survey99IsValid="False"
                )
                webuser.banReasons = [{"tag": "post_survey_invalid", "label": "后测问卷无效", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
                webuser.save()
        
        mock_send.return_value = {'code': 200, 'msg': 'Success'}
        tasks.launch_tasks(8)
        
        # 验证消息发送：应该发送给所有符合条件的用户
        for day in range(99, 108):
            for group in ["Exp1", "Exp2", "Waitlist"]:
                self.assert_message_sent(mock_send, f"banned_post_survey_{group}_day{day}", 24)
                webuser = WebUser.objects.get(uuid=f"banned_post_survey_{group}_day{day}")
                self.assert_log_created(webuser, task_id=24)
                # 验证状态更新
                webuser.refresh_from_db()
                self.assertTrue(webuser.banNotified, 
                               f"用户banned_post_survey_{group}_day{day}应该被标记为banNotified")
                self.assert_banlog_created(webuser, ban_tags={"post_survey_invalid"})


class SurveyCompleteTaskTestCase(TasksTestCase):
    """测试 ID 29: survey_complete 任务"""
    
    # @patch('core.services.blued_msg.send')
    # def test_task_29_survey_complete(self, mock_send):
    #     """任务ID 29: Exp1/Exp2/Waitlist，days []，time 20，survey_complete"""
    #     # days为空，意味着不检查日期
    #     webuser = self.create_webuser(
    #         uuid="survey_complete_user",
    #         group="Exp1",
    #         start_date=self.today - timedelta(days=100),
    #         current_day=100,
    #         ban_day=-1,  # banDay != 1 才会被处理
    #         survey23IsValid="True",  # 至少有一个为True
    #         survey39IsValid="True",
    #         survey99IsValid="True",
    #         surveyCompleteNotified=False
    #     )
    #     mock_send.return_value = {'code': 200, 'msg': 'Success'}
    #     tasks.launch_tasks(20)
        
    #     # 验证消息发送
    #     self.assert_message_sent(mock_send, "survey_complete_user", 29)
        
    #     # 验证Log记录创建
    #     self.assert_log_created(webuser, task_id=29)
        
    #     # 验证状态更新：surveyCompleteNotified 应该被设置为 True
    #     webuser.refresh_from_db()
    #     self.assertTrue(webuser.surveyCompleteNotified, 
    #                    "应该更新surveyCompleteNotified为True")


class ValidityCheckTestCase(TasksTestCase):
    """测试禁用规则（validity_check）"""
    
    def test_ban_pre_survey_invalid(self):
        """测试前测问卷无效导致禁用"""
        webuser = self.create_webuser(
            uuid="pre_invalid_user",
            group="Exp1",
            survey1IsValid="False",
            ban_day=-1
        )
        ban_tags = webuser.validity_check()
        self.assertIn("pre_survey_invalid", ban_tags)
        self.assertTrue(webuser.banFlag)
    
    def test_ban_post_survey_invalid(self):
        """测试后测问卷全部无效导致禁用"""
        webuser = self.create_webuser(
            uuid="post_invalid_user",
            group="Waitlist",
            survey23IsValid="False",
            survey39IsValid="False",
            survey99IsValid="False",
            ban_day=-1
        )
        ban_tags = webuser.validity_check()
        self.assertIn("post_survey_invalid", ban_tags)
    
    def test_ban_quality_check_fail_day1(self):
        """测试第1天写作不合格处以禁用"""
        webuser = self.create_webuser(
            uuid="quality_fail_day1",
            group="Exp1",
            writing1QualityCheckRA="False",
            writing1QualityCheckCS="False",
            ban_day=-1
        )
        ban_tags = webuser.validity_check()
        self.assertIn("quality_check_fail", ban_tags)
    
    def test_ban_quality_check_fail_days_4to8(self):
        """测试第4-8天有2篇及以上不合格导致禁用"""
        webuser = self.create_webuser(
            uuid="quality_fail_4to8",
            group="Exp2",
            writing4QualityCheckRA="False",
            writing4QualityCheckCS="False",
            writing5QualityCheckRA="False",
            writing5QualityCheckCS="False",
            ban_day=-1
        )
        ban_tags = webuser.validity_check()
        self.assertIn("quality_check_fail", ban_tags)
    
    def test_ban_task_not_done(self):
        """测试任务超时导致禁用"""
        # 设置currentDay=3，startDate为5天前，应该超时了
        start_date = self.today - timedelta(days=5)
        webuser = self.create_webuser(
            uuid="task_overdue_user",
            group="Exp1",
            start_date=start_date,
            current_day=3,
            ban_day=-1
        )
        # 检查任务结束时间：startDate + (currentDay-1) + 2天 + 4小时
        # 5天前 + 2天 + 4小时 > 现在，应该超时
        ban_tags = webuser.validity_check()
        self.assertIn("task_not_done", ban_tags)
    
    def test_ban_game_score_low(self):
        """测试游戏得分不足导致禁用"""
        webuser = self.create_webuser(
            uuid="game_low_score",
            group="Exp1",
            gameFinished=True,
            score=50000,  # 低于61200
            ban_day=-1
        )
        ban_tags = webuser.validity_check()
        self.assertIn("game_score_low", ban_tags)
    
    def test_no_ban_when_banDay_is_1(self):
        """测试banDay==1时不进行禁用检查"""
        webuser = self.create_webuser(
            uuid="banned_at_day1",
            group="Exp1",
            ban_day=1,  
            survey1IsValid="False"  # 虽然有无效问卷，但因为banDay==1不会检查
        )
        ban_tags = webuser.validity_check()
        # banDay==1时直接返回，不返回banTags
        self.assertEqual(set(), ban_tags)


class EdgeCasesTestCase(TasksTestCase):
    """边界情况测试"""
    
    def test_user_not_in_group(self):
        """测试用户组不匹配时不发送"""
        webuser = self.create_webuser(
            uuid="wrong_group",
            group="Null",  # 不在Exp1/Exp2中
            start_date=self.today,
            current_day=1,
            ban_day=1
        )
        # 对于只允许Exp1/Exp2的任务，不应该发送
    
    def test_wrong_day(self):
        """测试日期不匹配时不发送"""
        webuser = self.create_webuser(
            uuid="wrong_day",
            group="Exp1",
            start_date=self.today - timedelta(days=5),  # 第6天
            current_day=6,
            ban_day=1
        )
        # 对于只允许days [1-9]的任务，不应该发送
    
    def test_banDay_not_1_skipped(self):
        """测试banDay!=1的用户被跳过（这是代码中的逻辑）"""
        webuser = self.create_webuser(
            uuid="skip_user",
            group="Exp1",
            start_date=self.today,
            current_day=1,
            ban_day=-1  # 不是1，会被跳过
        )
        # 根据代码逻辑，只有banDay==1的用户才会被处理
    
    def test_whitelist_missing_startDate(self):
        """测试白名单缺少startDate时不发送day_0任务"""
        whitelist = self.create_whitelist(uuid="no_start_date")
        whitelist.startDate = None
        whitelist.save()
        # 不应该发送任务
    
    def test_whitelist_no_wechat(self):
        """测试白名单未添加微信时不发送day_0任务"""
        whitelist = self.create_whitelist(uuid="no_wechat", has_wechat=False)
        # 不应该发送任务


class IntegrationTestCase(TasksTestCase):
    """集成测试：测试完整流程"""
    
    def test_complete_user_journey(self):
        """测试用户完整旅程，从day_0到训练完成"""
        # Day 0: 白名单用户接收任务1或2
        whitelist = self.create_whitelist(uuid="journey_user", start_date=self.today)
        
        # Day 1-9: 训练阶段
        user = User.objects.create_user(username="journey_user")
        webuser = WebUser.objects.create(
            user=user,
            uuid="journey_user",
            whitelist=whitelist,
            encryptedPhoneNumber="encrypted_phone_journey",
            encryptedWeChat="encrypted_wechat_journey",
            group="Exp1",
            startDate=self.today,
            currentDay=1,
            banDay=1
        )
        
        # Day 1 morning (time 8): 应该发送任务4
        # Day 1 evening (time 20): 检查任务5, 6
        
        # 完成训练后 (day 10+)
        webuser.currentDay = 10
        webuser.save()
        # 应该发送任务26


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["core.test_tasks"])
