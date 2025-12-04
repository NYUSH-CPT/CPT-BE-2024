import json
from core.models import WebUser, Log, BannedLog
from datetime import datetime
from core.services import blued_msg

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
    log = Log(
        user=None,
        log=f"Event triggered at {datetime.now()}, with time {time}."
    )
    
    logs_to_create = [log]
    banlogs_to_create = []
    current_date = datetime.now().date()

    sub_tasks = filter(lambda x: x["time"] == str(time), tasks)
    for sub_task in sub_tasks:
        # Use iterator() to avoid loading all users into memory at once
        # Process users in batches to prevent memory issues
        batch_size = 100
        user_queryset = WebUser.objects.all().iterator(chunk_size=batch_size)
        
        for user in user_queryset:
            banLog = False
            # update user validity
            banTags = user.validity_check()
            # check group
            if user.group not in sub_task['groups']:
                continue
            currentDay = (current_date - user.startDate).days + 1
            if currentDay not in sub_task['days']:
                continue
            
            # check criteria
            if 'survey_not_done' in sub_task['criteria']:
                anchor = survey_anchor_for(currentDay)
                if anchor is None or user.currentDay != anchor:
                    continue
                
            if 'survey_complete' in sub_task['criteria']:
                if user.surveyCompleteNotified or not (all(getattr(user, f"survey{day}IsValid") != "Null" for day in [23, 39, 99]) and any(getattr(user, f"survey{day}IsValid") == "True" for day in [23, 39, 99])):
                    continue
                WebUser.objects.filter(uuid=user.uuid).update(surveyCompleteNotified=True)
                    
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
                            WebUser.objects.filter(uuid=user.uuid).update(**{f'writing{day}QualityCheckNotified': True})
                    if skip:
                        continue
                if 'train_complete' in sub_task['criteria']:
                    if user.trainCompleteNotified or user.currentDay < 10:
                        continue
                    WebUser.objects.filter(uuid=user.uuid).update(trainCompleteNotified=True)
                        
            if 'banned' in sub_task["criteria"]:
                if user.banNotified:
                    continue
                if not any(x in sub_task["criteria"] for x in banTags):
                    continue
                WebUser.objects.filter(uuid=user.uuid).update(banNotified=True)
                banLog = True
            
            res = blued_msg.send(user.uuid, sub_task["id"])
            if res['code'] == 200:
                logs_to_create.append(Log(
                    user=user,
                    log=f"Message sent to {user.uuid} on task {sub_task['id']} successfully."
                ))
            else: 
                logs_to_create.append(Log(
                    user=user,
                    log="Message sent failed. Error message: " + res['msg']
                ))
                
            if banLog:
                banlogs_to_create.append(BannedLog(
                        user=user,
                        log=f"{banTags}"
                    ))
            
            # Batch create logs periodically to avoid memory issues
            if len(logs_to_create) >= 500:
                Log.objects.bulk_create(logs_to_create)
                logs_to_create = []
            if len(banlogs_to_create) >= 500:
                BannedLog.objects.bulk_create(banlogs_to_create)
                banlogs_to_create = []
    
    # Create remaining logs
    if logs_to_create:
        Log.objects.bulk_create(logs_to_create)
    if banlogs_to_create:
        BannedLog.objects.bulk_create(banlogs_to_create)
                    
# def test_tasks(time: int):
#     # print(f"Event triggered at {datetime.now()}, with time {time}.")
#     res = blued_msg.send("wKLBbRvD", 1)
#     user = WebUser.objects.filter(uuid="wKLBbRvD").first()
#     if res['code'] == 200:
#         log = Log.objects.create(
#             user=user,
#             log=f"Message sent to {user.uuid} on task 1 successfully."
#         )
#         log.save()
#     else: 
#         log = Log.objects.create(
#             user=user,
#             log="Message sent failed. Error message: " + res['msg']
#         )
#         log.save()
    

    
if __name__ == "__main__":
    launch_tasks(8)
    launch_tasks(20)
    
