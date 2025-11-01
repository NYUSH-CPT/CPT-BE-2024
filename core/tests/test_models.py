"""
Comprehensive test suite for core/models.py

Tests cover:
- Model methods (validity_check, update_quality_check, etc.)
- Model properties (banReasons)
- Model relationships and constraints
- Edge cases and boundary conditions
"""

from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date, timedelta, datetime
from django.utils import timezone

from core.models import WebUser, Whitelist, Log, BannedLog, LSUser, Screen


class BaseModelTestCase(TestCase):
    """Base test class with common setup utilities"""
    
    def setUp(self):
        self.today = date.today()
    
    def create_whitelist(self, uuid="test_uuid", has_wechat=True, start_date=None):
        """Helper to create a Whitelist entry"""
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
        """Helper to create a WebUser"""
        if start_date is None:
            start_date = self.today
        
        whitelist, _ = Whitelist.objects.get_or_create(
            uuid=uuid,
            defaults=dict(
                encryptedPhoneNumber=f"encrypted_phone_{uuid}",
                encryptedWeChat=f"encrypted_wechat_{uuid}",
                has_add_wechat=True,
                startDate=start_date,
            )
        )

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


class TestWebUserValidityCheck(BaseModelTestCase):
    """Tests for WebUser.validity_check() method"""
    
    def test_validity_check_banDay_equals_1_returns_empty(self):
        """Test validity_check returns empty set when banDay == 1"""
        webuser = self.create_webuser(uuid="banDay1", ban_day=1, survey1IsValid="False")
        
        ban_tags = webuser.validity_check()
        
        self.assertEqual(ban_tags, set())
        self.assertFalse(webuser.banFlag)  # Should not update banFlag
    
    def test_validity_check_pre_survey_invalid(self):
        """Test validity_check flags pre_survey_invalid"""
        webuser = self.create_webuser(uuid="pre_invalid", survey1IsValid="False")
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("pre_survey_invalid", ban_tags)
        self.assertTrue(webuser.banFlag)
        ban_reasons_tags = {entry["tag"] for entry in webuser.banReasons}
        self.assertIn("pre_survey_invalid", ban_reasons_tags)
    
    def test_validity_check_post_survey_invalid(self):
        """Test validity_check flags post_survey_invalid when all surveys invalid"""
        webuser = self.create_webuser(
            uuid="post_invalid",
            survey23IsValid="False",
            survey39IsValid="False",
            survey99IsValid="False"
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("post_survey_invalid", ban_tags)
        ban_reasons_tags = {entry["tag"] for entry in webuser.banReasons}
        self.assertIn("post_survey_invalid", ban_reasons_tags)
    
    def test_validity_check_post_survey_not_invalid_if_one_valid(self):
        """Test validity_check doesn't flag if at least one post survey is valid"""
        webuser = self.create_webuser(
            uuid="post_valid",
            survey23IsValid="False",
            survey39IsValid="True",  # At least one valid
            survey99IsValid="False"
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertNotIn("post_survey_invalid", ban_tags)
    
    def test_validity_check_quality_check_fail_day1(self):
        """Test validity_check flags quality_check_fail for day 1 writing"""
        webuser = self.create_webuser(
            uuid="quality_day1",
            group="Exp1",
            writing1QualityCheckRA="False",
            writing1QualityCheckCS="False"
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("quality_check_fail", ban_tags)
        ban_reasons_tags = {entry["tag"] for entry in webuser.banReasons}
        self.assertIn("quality_check_fail", ban_reasons_tags)
    
    def test_validity_check_quality_check_fail_days_4to8(self):
        """Test validity_check flags when 2+ writings from days 4-8 fail"""
        webuser = self.create_webuser(
            uuid="quality_4to8",
            group="Exp2",
            writing4QualityCheckRA="False",
            writing4QualityCheckCS="False",
            writing5QualityCheckRA="False",
            writing5QualityCheckCS="False"
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("quality_check_fail", ban_tags)
    
    def test_validity_check_quality_check_not_fail_one_invalid(self):
        """Test validity_check doesn't flag if only 1 writing from 4-8 fails"""
        webuser = self.create_webuser(
            uuid="quality_one_fail",
            group="Exp1",
            writing4QualityCheckRA="False",
            writing4QualityCheckCS="False",
            writing5QualityCheckRA="True",
            writing5QualityCheckCS="True"
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertNotIn("quality_check_fail", ban_tags)
    
    def test_validity_check_task_not_done(self):
        """Test validity_check flags task_not_done for overdue tasks"""
        # Create user with startDate 5 days ago, currentDay=3
        # Task should have ended: startDate + (3-1) + 2 days + 4 hours = 5 days ago + 2 + 4h
        # Which is 3 days + 4 hours ago, should be overdue
        start_date = self.today - timedelta(days=5)
        webuser = self.create_webuser(
            uuid="task_overdue",
            group="Exp1",
            start_date=start_date,
            current_day=3
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("task_not_done", ban_tags)
        self.assertTrue(webuser.banFlag)
        self.assertEqual(webuser.banDay, 3)
        self.assertEqual(webuser.currentDay, 23)  # Should transition to 23
    
    def test_validity_check_task_not_done_not_overdue(self):
        """Test validity_check doesn't flag if task is not overdue"""
        # Create user with startDate today, currentDay=1
        # Task end time: today + 0 + 2 days + 4 hours = 2 days + 4h from now
        # Should not be overdue
        webuser = self.create_webuser(
            uuid="task_not_overdue",
            group="Exp1",
            start_date=self.today,
            current_day=1
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertNotIn("task_not_done", ban_tags)
    
    def test_validity_check_task_not_done_only_for_exp_groups(self):
        """Test validity_check doesn't check task_not_done for Waitlist"""
        start_date = self.today - timedelta(days=5)
        webuser = self.create_webuser(
            uuid="waitlist_overdue",
            group="Waitlist",
            start_date=start_date,
            current_day=3
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertNotIn("task_not_done", ban_tags)
    
    def test_validity_check_game_score_low(self):
        """Test validity_check flags game_score_low"""
        webuser = self.create_webuser(
            uuid="game_low",
            group="Exp1",
            gameFinished=True,
            score=50000  # Below 61200 (60%)
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("game_score_low", ban_tags)
    
    def test_validity_check_game_score_not_low(self):
        """Test validity_check doesn't flag if score is sufficient"""
        webuser = self.create_webuser(
            uuid="game_ok",
            group="Exp1",
            gameFinished=True,
            score=70000  # Above 61200
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertNotIn("game_score_low", ban_tags)
    
    def test_validity_check_game_score_not_low_if_not_finished(self):
        """Test validity_check doesn't check score if game not finished"""
        webuser = self.create_webuser(
            uuid="game_not_finished",
            group="Exp1",
            gameFinished=False,
            score=10000  # Low but game not finished
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertNotIn("game_score_low", ban_tags)
    
    def test_validity_check_multiple_reasons(self):
        """Test validity_check can flag multiple ban reasons"""
        start_date = self.today - timedelta(days=5)
        webuser = self.create_webuser(
            uuid="multiple_reasons",
            group="Exp1",
            start_date=start_date,
            current_day=3,
            survey1IsValid="False",
            writing1QualityCheckRA="False",
            writing1QualityCheckCS="False",
            gameFinished=True,
            score=50000
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("pre_survey_invalid", ban_tags)
        self.assertIn("quality_check_fail", ban_tags)
        self.assertIn("task_not_done", ban_tags)
        self.assertIn("game_score_low", ban_tags)
        self.assertTrue(webuser.banFlag)
    
    def test_validity_check_doesnt_duplicate_reasons(self):
        """Test validity_check doesn't add duplicate ban reasons"""
        webuser = self.create_webuser(
            uuid="duplicate_reasons",
            survey1IsValid="False"
        )
        
        # First call
        ban_tags1 = webuser.validity_check()
        self.assertIn("pre_survey_invalid", ban_tags1)
        initial_count = len(webuser.banReasons)
        
        # Second call
        ban_tags2 = webuser.validity_check()
        self.assertIn("pre_survey_invalid", ban_tags2)
        
        # Should not add duplicate
        self.assertEqual(len(webuser.banReasons), initial_count)
    
    def test_validity_check_ban_day_transition(self):
        """Test validity_check transitions currentDay to 23 when banned during training"""
        start_date = self.today - timedelta(days=3)
        webuser = self.create_webuser(
            uuid="ban_transition",
            group="Exp1",
            start_date=start_date,
            current_day=5
        )
        webuser.writing1QualityCheckRA = "False"
        webuser.writing1QualityCheckCS = "False"
        webuser.save()
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("quality_check_fail", ban_tags)
        self.assertEqual(webuser.banDay, 5)
        self.assertEqual(webuser.currentDay, 23)  # Should transition to 23
    
    def test_validity_check_ban_day_no_transition_after_day9(self):
        """Test validity_check doesn't transition if banned after day 9"""
        webuser = self.create_webuser(
            uuid="ban_no_transition",
            group="Exp1",
            current_day=23,
            survey23IsValid="False",
            survey39IsValid="False",
            survey99IsValid="False"
        )
        
        ban_tags = webuser.validity_check()
        
        self.assertIn("post_survey_invalid", ban_tags)
        self.assertEqual(webuser.banDay, 23)
        self.assertEqual(webuser.currentDay, 23)  # Should not change


class TestWebUserUpdateQualityCheck(BaseModelTestCase):
    """Tests for WebUser.update_quality_check() method"""
    
    def test_update_quality_check_both_false(self):
        """Test update_quality_check sets False when both RA and CS are False"""
        webuser = self.create_webuser(uuid="quality_test")
        
        webuser.update_quality_check('writing1QualityCheck', "False", "False")
        webuser.save()
        
        self.assertEqual(webuser.writing1QualityCheck, "False")
    
    def test_update_quality_check_both_not_null(self):
        """Test update_quality_check sets True when both are not Null"""
        webuser = self.create_webuser(uuid="quality_test")
        
        webuser.update_quality_check('writing1QualityCheck', "True", "True")
        webuser.save()
        
        self.assertEqual(webuser.writing1QualityCheck, "True")
    
    def test_update_quality_check_one_null(self):
        """Test update_quality_check sets Null when one is Null"""
        webuser = self.create_webuser(uuid="quality_test")
        
        webuser.update_quality_check('writing1QualityCheck', "True", "Null")
        webuser.save()
        
        self.assertEqual(webuser.writing1QualityCheck, "Null")


class TestWebUserCountInvalidChecks(BaseModelTestCase):
    """Tests for WebUser.count_invalid_checks() method"""
    
    def test_count_invalid_checks_zero(self):
        """Test count_invalid_checks returns 0 when no invalid checks"""
        webuser = self.create_webuser(
            uuid="count_test",
            writing1QualityCheck="True",
            writing4QualityCheck="True"
        )
        
        count = webuser.count_invalid_checks([1, 4])
        
        self.assertEqual(count, 0)
    
    def test_count_invalid_checks_one(self):
        """Test count_invalid_checks returns 1 when one invalid"""
        webuser = self.create_webuser(
            uuid="count_test",
            writing1QualityCheck="False",
            writing4QualityCheck="True"
        )
        
        count = webuser.count_invalid_checks([1, 4])
        
        self.assertEqual(count, 1)
    
    def test_count_invalid_checks_multiple(self):
        """Test count_invalid_checks returns correct count for multiple"""
        webuser = self.create_webuser(
            uuid="count_test",
            writing4QualityCheck="False",
            writing5QualityCheck="False",
            writing6QualityCheck="True"
        )
        
        count = webuser.count_invalid_checks([4, 5, 6])
        
        self.assertEqual(count, 2)


class TestWebUserUpdateDateAfterSurveyDue(BaseModelTestCase):
    """Tests for WebUser.update_date_after_survey_due() method"""
    
    def test_update_date_after_survey_due_survey1_overdue(self):
        """Test update_date_after_survey_due marks survey1 as overdue"""
        # Survey 1 window: day 1, -1 days (meaning it must be done before day 1)
        # If currentDay <= 1 and we're past day 1 + (-1) = day 0, it's overdue
        start_date = self.today - timedelta(days=2)  # 2 days ago
        webuser = self.create_webuser(
            uuid="survey_overdue",
            start_date=start_date,
            current_day=1,
            survey1IsValid="Null"
        )
        
        webuser.update_date_after_survey_due()
        webuser.save()
        
        self.assertEqual(webuser.survey1IsValid, "False")
        self.assertEqual(webuser.survey1, "Overdue")
        self.assertEqual(webuser.currentDay, 1)  # Should not change for survey 1
    
    def test_update_date_after_survey_due_survey23_overdue(self):
        """Test update_date_after_survey_due marks survey23 as overdue and transitions"""
        # Survey 23 window: day 23, 6 days window (23-29)
        # If currentDay <= 23 and we're past day 23 + 6 = day 29, it's overdue
        start_date = self.today - timedelta(days=30)  # 30 days ago
        webuser = self.create_webuser(
            uuid="survey23_overdue",
            start_date=start_date,
            current_day=23,
            survey23IsValid="Null"
        )
        
        webuser.update_date_after_survey_due()
        webuser.save()
        
        self.assertEqual(webuser.survey23IsValid, "False")
        self.assertEqual(webuser.survey23, "Overdue")
        self.assertEqual(webuser.currentDay, 39)  # Should transition to 39


class TestWebUserBanReasons(BaseModelTestCase):
    """Tests for WebUser.banReasons property"""
    
    def test_ban_reasons_getter_empty(self):
        """Test banReasons getter returns empty list when empty"""
        webuser = self.create_webuser(uuid="ban_reasons_test")
        
        reasons = webuser.banReasons
        
        self.assertEqual(reasons, [])
    
    def test_ban_reasons_getter_parsed(self):
        """Test banReasons getter parses JSON correctly"""
        webuser = self.create_webuser(
            uuid="ban_reasons_test",
            banReasonsJson='[{"tag": "test", "label": "Test", "time": "2024-01-01"}]'
        )
        
        reasons = webuser.banReasons
        
        self.assertEqual(len(reasons), 1)
        self.assertEqual(reasons[0]["tag"], "test")
    
    def test_ban_reasons_setter(self):
        """Test banReasons setter stores JSON correctly"""
        webuser = self.create_webuser(uuid="ban_reasons_test")
        
        webuser.banReasons = [{"tag": "test", "label": "Test", "time": "2024-01-01"}]
        webuser.save()
        
        self.assertIn('"tag": "test"', webuser.banReasonsJson)
        reasons = webuser.banReasons
        self.assertEqual(reasons[0]["tag"], "test")
    
    def test_ban_reasons_invalid_json(self):
        """Test banReasons getter returns empty list on invalid JSON"""
        webuser = self.create_webuser(uuid="ban_reasons_test", banReasonsJson="invalid json")
        
        reasons = webuser.banReasons
        
        self.assertEqual(reasons, [])


class TestWebUserResetGame(BaseModelTestCase):
    """Tests for WebUser.reset_game() method"""
    
    def test_reset_game_clears_all_fields(self):
        """Test reset_game clears all game-related fields"""
        webuser = self.create_webuser(
            uuid="reset_game",
            game=b"test_game_data",
            gameBreakFlag=True,
            gameFinished=True,
            gameData={"score": 100},
            score=5000
        )
        
        webuser.reset_game()
        webuser.save()
        
        self.assertIsNone(webuser.game)
        self.assertFalse(webuser.gameBreakFlag)
        self.assertFalse(webuser.gameFinished)
        self.assertEqual(webuser.gameData, {})
        self.assertEqual(webuser.score, 0)


class TestWebUserStringRepresentation(BaseModelTestCase):
    """Tests for WebUser.__str__ method"""
    
    def test_webuser_str(self):
        """Test WebUser string representation"""
        webuser = self.create_webuser(
            uuid="str_test",
            group="Exp1",
            current_day=5
        )
        
        str_repr = str(webuser)
        
        self.assertIn("str_test", str_repr)
        self.assertIn("Exp1", str_repr)
        self.assertIn("currentDay", str_repr)


class TestWhitelistModel(BaseModelTestCase):
    """Tests for Whitelist model"""
    
    def test_whitelist_creation(self):
        """Test Whitelist can be created with required fields"""
        whitelist = Whitelist.objects.create(
            uuid="whitelist_test",
            encryptedPhoneNumber="enc_phone",
            encryptedWeChat="enc_wechat"
        )
        
        self.assertEqual(whitelist.uuid, "whitelist_test")
        self.assertEqual(str(whitelist), "whitelist_test")
    
    def test_whitelist_defaults(self):
        """Test Whitelist default values"""
        whitelist = Whitelist.objects.create(
            uuid="defaults_test",
            encryptedPhoneNumber="enc_phone",
            encryptedWeChat="enc_wechat"
        )
        
        self.assertFalse(whitelist.has_add_wechat)
        self.assertIsNone(whitelist.startDate)
        self.assertIsNone(whitelist.survey0)


class TestLogModel(BaseModelTestCase):
    """Tests for Log model"""
    
    def test_log_creation(self):
        """Test Log can be created"""
        webuser = self.create_webuser(uuid="log_test")
        
        log = Log.objects.create(
            user=webuser,
            log="Test log message"
        )
        
        self.assertEqual(log.user, webuser)
        self.assertEqual(log.log, "Test log message")
        self.assertIsNotNone(log.time)


class TestBannedLogModel(BaseModelTestCase):
    """Tests for BannedLog model"""
    
    def test_bannedlog_creation(self):
        """Test BannedLog can be created"""
        webuser = self.create_webuser(uuid="banlog_test")
        
        banlog = BannedLog.objects.create(
            user=webuser,
            log="Banned for quality check fail"
        )
        
        self.assertEqual(banlog.user, webuser)
        self.assertEqual(banlog.log, "Banned for quality check fail")
        self.assertIn("banlog_test", str(banlog))


class TestScreenModel(BaseModelTestCase):
    """Tests for Screen model"""
    
    def test_screen_creation(self):
        """Test Screen can be created"""
        screen = Screen.objects.create(
            uuid="screen_test",
            valid=True,
            eligible=True,
            service=False
        )
        
        self.assertEqual(screen.uuid, "screen_test")
        self.assertTrue(screen.valid)
        self.assertTrue(screen.eligible)
        self.assertFalse(screen.service)
        self.assertIn("screen_test", str(screen))
    
    def test_screen_defaults(self):
        """Test Screen default values"""
        screen = Screen.objects.create(uuid="defaults_test")
        
        self.assertFalse(screen.valid)
        self.assertFalse(screen.eligible)
        self.assertFalse(screen.service)
        self.assertFalse(screen.consent)
        self.assertFalse(screen.submitted)


class TestLSUserModel(BaseModelTestCase):
    """Tests for LSUser model"""
    
    def test_lsuser_creation(self):
        """Test LSUser can be created"""
        lsuser = LSUser.objects.create(
            uuid="lsuser_test",
            encryptedPhoneNumber="enc_phone",
            encryptedQQ="enc_qq"
        )
        
        self.assertEqual(lsuser.uuid, "lsuser_test")
        self.assertIn("lsuser_test", str(lsuser))


class TestModelRelationships(BaseModelTestCase):
    """Tests for model relationships"""
    
    def test_webuser_one_to_one_user(self):
        """Test WebUser has OneToOne relationship with User"""
        user = User.objects.create_user(username="relationship_test")
        whitelist = self.create_whitelist(uuid="relationship_test")
        webuser = WebUser.objects.create(
            user=user,
            uuid="relationship_test",
            whitelist=whitelist,
            encryptedPhoneNumber="enc_phone",
            encryptedWeChat="enc_wechat"
        )
        
        self.assertEqual(webuser.user, user)
        self.assertEqual(user.webuser, webuser)
    
    def test_webuser_one_to_one_whitelist(self):
        """Test WebUser has OneToOne relationship with Whitelist"""
        whitelist = self.create_whitelist(uuid="whitelist_rel")
        webuser = self.create_webuser(uuid="whitelist_rel")
        
        self.assertEqual(webuser.whitelist.id, whitelist.id)
        self.assertEqual(whitelist.webUser.id, webuser.id)
    
    def test_log_foreign_key_webuser(self):
        """Test Log has ForeignKey to WebUser"""
        webuser = self.create_webuser(uuid="log_rel")
        log = Log.objects.create(user=webuser, log="Test")
        
        self.assertEqual(log.user, webuser)
        self.assertIn(log, webuser.log_set.all())
    
    def test_bannedlog_foreign_key_webuser(self):
        """Test BannedLog has ForeignKey to WebUser"""
        webuser = self.create_webuser(uuid="banlog_rel")
        banlog = BannedLog.objects.create(user=webuser, log="Test")
        
        self.assertEqual(banlog.user, webuser)

