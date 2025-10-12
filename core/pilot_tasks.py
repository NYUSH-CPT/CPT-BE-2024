import json
from core.models import WebUser, Log, BannedLog, Whitelist
from datetime import datetime
from core.services import blued_msg

with open("core/pilot_scheduled_tasks.json") as f:
    tasks = json.load(f)
    
defer_fields = (
    "user",
    "sms",
    "encryptedPhoneNumber",
    "encryptedWeChat",
    "whitelist",
    "writing1", "writing4", "writing5", "writing6", "writing8",
    "writing4Viewed", "writing5Viewed",
    "feedback6", "feedback6Viewed",
    "feedback8", "feedback8Viewed",
    "game", "gameBreakFlag", "gameData",
)

def launch_tasks(time: int):
    # print(f"Event triggered at {datetime.now()}, with time {time}.")
    log = Log.objects.create(
        user=None,
        log=f"Event triggered at {datetime.now()}, with time {time}."
    )
    
    logs_to_create = []
    banlogs_to_create = []
    current_date = datetime.now().date()

    sub_tasks = filter(lambda x: x["time"] == str(time), tasks)
    for sub_task in sub_tasks:
        if 'day_0' in sub_task['criteria']:
            for whitelist in Whitelist.objects.iterator():
                if not whitelist.startDate or not whitelist.has_add_wechat:
                    continue
                currentDay = (current_date - whitelist.startDate).days + 1
                # print(whitelist.uuid, currentDay)
                if currentDay != 0:
                    continue
                res = blued_msg.send(whitelist.uuid, sub_task["id"])
                if res['code'] == 200:
                    logs_to_create.append(Log(
                        log=f"Message sent to {whitelist.uuid} on task {sub_task['id']} successfully."
                    ))
                else: 
                    logs_to_create.append(Log(
                        log=f"Message sent failed. Error message: " + res['msg']
                    ))
        else:
            for user in WebUser.objects.defer(*defer_fields).iterator():
                banLog = False
                # update user validity
                banReasons, banTags = user.validity_check()
                # check group
                if user.group not in sub_task['groups']:
                    continue
                currentDay = (current_date - user.startDate).days + 1
                # print(user.uuid, currentDay)
                if currentDay not in sub_task['days']:
                    continue
                # check criteria
                if 'not_banned' in sub_task['criteria'] and not banTags:
                    if 'task_not_done' in sub_task['criteria']:
                        if sub_task['days'] == 1 and user.group == 'Waitlist':
                            if user.currentDay >= 1.1:
                                continue
                        elif user.currentDay >= currentDay+1:
                            continue
                    # pilot-only
                    if 'survey_not_done' in sub_task['criteria']:
                        if user.currentDay >= 39:
                            continue
                    if 'has_unsent_quality_check_fail_msg' in sub_task['criteria']:
                        skip = True
                        for day in [1,4,5,6,8]:
                            if getattr(user, f'writing{day}QualityCheck') == "False" and not getattr(user, f'writing{day}QualityCheckNotified'):
                                skip = False
                                WebUser.objects.filter(uuid=user.uuid).update(**{f'writing{day}QualityCheckNotified': True})
                        if skip:
                            continue
                    if 'train_complete' in sub_task['criteria']:
                        if user.trainCompleteNotified or user.currentDay < 10:
                            continue
                        WebUser.objects.filter(uuid=user.uuid).update(trainCompleteNotified=True)
                    if 'survey_complete' in sub_task['criteria']:
                        if user.surveyCompleteNotified or not all([getattr(user, f"survey{day}IsValid") in ["False", "True"] for day in [23, 39, 99]]):
                            continue
                        WebUser.objects.filter(uuid=user.uuid).update(surveyCompleteNotified=True)
                            
                elif 'banned' in sub_task["criteria"] and banTags and not user.banNotified:
                    if 'survey_complete' in sub_task['criteria']:
                        if user.surveyCompleteNotified or not all([getattr(user, f"survey{day}IsValid") in ["False", "True"] for day in [23, 39, 99]]):
                            continue
                        WebUser.objects.filter(uuid=user.uuid).update(surveyCompleteNotified=True)
                        
                    if not any([x in sub_task["criteria"] for x in banTags]):
                        continue
                    WebUser.objects.filter(uuid=user.uuid).update(banNotified=True)
                    banLog = True
                
                else: 
                    continue
                
                # print(f"Sending message to {user.uuid} on task {sub_task['id']}...")
                res = blued_msg.send(user.uuid, sub_task["id"])
                if res['code'] == 200:
                    logs_to_create.append(Log(
                        user=user,
                        log=f"Message sent to {user.uuid} on task {sub_task['id']} successfully."
                    ))
                else: 
                    logs_to_create.append(Log(
                        user=user,
                        log=f"Message sent failed. Error message: " + res['msg']
                    ))
                    
                if banLog:
                    banlogs_to_create.append(BannedLog(
                            user=user,
                            log=f"{banReasons}"
                        ))
                        
    Log.objects.bulk_create(logs_to_create)
    BannedLog.objects.bulk_create(banlogs_to_create)
                    
def test_tasks(time: int):
    # print(f"Event triggered at {datetime.now()}, with time {time}.")
    res = blued_msg.send("wKLBbRvD", 1)
    user = WebUser.objects.filter(uuid="wKLBbRvD").first()
    if res['code'] == 200:
        log = Log.objects.create(
            user=user,
            log=f"Message sent to {user.uuid} on task 1 successfully."
        )
    else: 
        log = Log.objects.create(
            user=user,
            log=f"Message sent failed. Error message: " + res['msg']
        )

    
if __name__ == "__main__":
    launch_tasks(8)
    launch_tasks(20)
    
