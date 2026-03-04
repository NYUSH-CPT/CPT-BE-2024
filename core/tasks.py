import json
from core.models import WebUser, Log, BannedLog
from datetime import datetime
from core.services import blued_msg
from django.utils import timezone
import traceback

with open("core/prod_scheduled_tasks.json") as f:
    tasks = json.load(f)
    
defer_fields = (
    "user",
    "encryptedPhoneNumber",
    "encryptedWeChat",
    "whitelist",
    "writing1", "writing4", "writing5", "writing6", "writing8",
    "writing4Viewed", "writing5Viewed",
    "feedback6", "feedback6Viewed",
    "feedback8", "feedback8Viewed",
    "game", "gameBreakFlag", "gameData",
)

SURVEY_ANCHORS = [23, 39, 99]
WINDOW_LEN = 6 

def survey_anchor_for(day: int) -> int | None:
    for a in SURVEY_ANCHORS:
        if a <= day <= a + WINDOW_LEN:
            return a
    return None


def launch_tasks(time: int):
    run_ts = timezone.localtime()
    print(f"[CRON] start launch_tasks time={time} at={run_ts}", flush=True)

    log = Log(
        user=None,
        log=f"Event triggered at {timezone.localtime()}, with time {time}."
    )
    
    logs_to_create = [log]
    banlogs_to_create = []
    current_date = datetime.now().date()

    sub_tasks = [t for t in tasks if t["time"] == str(time)]

    try:
        user_queryset = (
            WebUser.objects
            .filter(currentDay__lt=100)
            .defer(*defer_fields)
            .iterator(chunk_size=200)
        )
    except Exception as e:
        print(f"[FATAL] build queryset failed: {e}", flush=True)
        traceback.print_exc()
        return


    user_count = 0
    matched_count = 0
    send_ok = 0
    send_fail = 0
    vc_fail = 0
    db_fail = 0
    
    try:
        for user in user_queryset:
            user_count += 1

            try:
                banTags = user.validity_check()
            except Exception as e:
                vc_fail += 1
                print(f"[ERROR] validity_check uuid={getattr(user, 'uuid', None)} err={e}", flush=True)
                traceback.print_exc()
                continue
            
            for sub_task in sub_tasks:
                try: 
                    if user.group not in sub_task['groups']:
                        continue
                    
                    banLog = False
                    currentDay = (current_date - user.startDate).days + 1
                    
                    if currentDay not in sub_task['days']:
                        continue
                    # check criteria
                    if 'survey_not_done' in sub_task['criteria']:
                        anchor = survey_anchor_for(currentDay)
                        if anchor is None or user.currentDay != anchor:
                            continue
                        
                    needs_set_survey_complete = False
                    needs_set_train_complete = False
                    needs_set_ban_notified = False
                    needs_set_qc_notified_days = []
                
                    if 'survey_complete' in sub_task['criteria']:
                        if user.surveyCompleteNotified or not (all(getattr(user, f"survey{day}IsValid") != "Null" for day in [23, 39, 99]) and any(getattr(user, f"survey{day}IsValid") == "True" for day in [23, 39, 99])):
                            continue
                        needs_set_survey_complete = True
                            
                    if 'not_banned' in sub_task['criteria']:
                        if user.banFlag:
                            continue
                        if 'task_not_done' in sub_task['criteria']:
                            if user.currentDay >= currentDay+1:
                                continue
                        if 'has_unsent_quality_check_fail_msg' in sub_task['criteria']:
                            skip = True
                            for day in [1,4,5,6,8]:
                                if getattr(user, f'writing{day}QualityCheck') == "False" and not getattr(user, f'writing{day}QualityCheckNotified'):
                                    skip = False
                                    needs_set_qc_notified_days.append(day)
                            if skip:
                                continue
                        if 'train_complete' in sub_task['criteria']:
                            if user.trainCompleteNotified or user.currentDay < 10:
                                continue
                            needs_set_train_complete = True
                                
                    if 'banned' in sub_task["criteria"]:
                        if user.banNotified:
                            continue
                        if not any(x in sub_task["criteria"] for x in banTags):
                            continue
                        needs_set_ban_notified = True
                        banLog = True
                    
                    matched_count += 1
                    
                    try:
                        res = blued_msg.send(user.uuid, sub_task["id"])
                    except Exception as e:
                        send_fail += 1
                        print(f"[ERROR] send exception uuid={user.uuid} task={sub_task.get('id')} err={e}", flush=True)
                        traceback.print_exc()
                        continue
                    if res.get("code") == 200:
                        send_ok += 1

                        updates = {}
                        if needs_set_survey_complete:
                            updates["surveyCompleteNotified"] = True
                        if needs_set_train_complete:
                            updates["trainCompleteNotified"] = True
                        if needs_set_ban_notified:
                            updates["banNotified"] = True
                        for day in needs_set_qc_notified_days:
                            updates[f"writing{day}QualityCheckNotified"] = True

                        if updates:
                            WebUser.objects.filter(uuid=user.uuid).update(**updates)

                        logs_to_create.append(Log(user=user, log=f"Message sent to {user.uuid} on task {sub_task['id']} successfully."))
                    else:
                        send_fail += 1
                        msg = res.get("msg", "")
                        print(f"[SEND FAIL] uuid={user.uuid} task={sub_task.get('id')} msg={msg}", flush=True)
                        logs_to_create.append(Log(user=user, log="Message sent failed. Error message: " + msg))

                    if banLog:
                        banlogs_to_create.append(BannedLog(user=user, log=f"{banTags}"))
                
                except Exception as e:
                    print(f"[ERROR] sub_task loop crashed uuid={getattr(user,'uuid',None)} task={sub_task.get('id')} err={e}", flush=True)
                    traceback.print_exc()
                    continue
                
        if logs_to_create:
            try:
                Log.objects.bulk_create(logs_to_create)
            except Exception as e:
                db_fail += 1
                print(f"[ERROR] final bulk_create Log failed err={e}", flush=True)
                traceback.print_exc()
        if banlogs_to_create:
            try:
                BannedLog.objects.bulk_create(banlogs_to_create)
            except Exception as e:
                db_fail += 1
                print(f"[ERROR] final bulk_create BannedLog failed err={e}", flush=True)
                traceback.print_exc()
        
    except Exception as e:
        print(f"[FATAL] launch_tasks crashed err={e}", flush=True)
        traceback.print_exc()

    print(
        f"[CRON END] time={time} scanned={user_count} matched={matched_count} "
        f"send_ok={send_ok} send_fail={send_fail} vc_fail={vc_fail} db_fail={db_fail} at={timezone.localtime()}",
        flush=True
    )