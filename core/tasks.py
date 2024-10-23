import os
import django
import sys

sys.path.append(os.getcwd())
os.environ['DJANGO_SETTINGS_MODULE'] = 'CPTBackend.settings'
django.setup()

import json
from core.models import WebUser, Log, BannedLog, Whitelist
from datetime import datetime
from core.services import blued_msg
from core.utility import catch_exceptions

with open("core/scheduled_tasks.json") as f:
    tasks = json.load(f)

@catch_exceptions
def launch_tasks(time: int):
    print(f"Event triggered at {datetime.now()}, with time {time}.")
    log = Log.objects.create(
        user=None,
        log=f"Event triggered at {datetime.now()}, with time {time}."
    )
    log.save()

    sub_tasks = filter(lambda x: x["time"] == str(time), tasks)
    for sub_task in sub_tasks:
        if 'day_0' in sub_task['criteria']:
            for whitelist in Whitelist.objects.all():
                currentDay = (datetime.now().date() - whitelist.startDate).days + 1
                if currentDay != 0:
                    continue
                if whitelist.group not in sub_task['groups']:
                    continue
                if not whitelist.has_add_wechat:
                    continue
                res = blued_msg.send(whitelist.uuid, sub_task["id"])
                if res['code'] == 200:
                    log = Log.objects.create(
                        log=f"Message sent to {whitelist.uuid} on task {sub_task['id']} successfully."
                    )
                    log.save()
                else: 
                    log = Log.objects.create(
                        log=f"Message sent failed. Error message: " + res['msg']
                    )
                    log.save()
        else:
            for user in WebUser.objects.all():
                banLog = False
                # update user validity
                banReasons, banTags = user.validity_check()
                # check group
                if user.group not in sub_task['groups']:
                    continue
                currentDay = (datetime.now().date() - user.startDate).days + 1
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
                    if 'survey_not_done' in sub_task['criteria']:
                        if user.currentDay >= currentDay - 6:
                            continue
                    if 'has_unsent_quality_check_fail_msg' in sub_task['criteria']:
                        skip = True
                        for day in [1,4,5,6,8]:
                            if getattr(user, f'writing{day}QualityCheck') == "False" and not getattr(user, f'writing{day}QualityCheckNotified'):
                                skip = False
                                setattr(user, f'writing{day}QualityCheckNotified', True)
                                user.save()
                        if skip:
                            continue
                    if 'train_complete' in sub_task['criteria']:
                        if user.trainCompleteNotified or user.currentDay < 10:
                            continue
                        user.trainCompleteNotified = True
                        user.save()
                    if 'survey_complete' in sub_task['criteria']:
                        if user.surveyCompleteNotified or not (all([getattr(user, f"survey{day}IsValid") != "Null" for day in [23, 39, 99]]) and any([getattr(user, f"survey{day}IsValid") == "True" for day in [23, 39, 99]])):
                            continue
                        user.surveyCompleteNotified = True
                        user.save()
                            
                elif 'banned' in sub_task["criteria"] and banTags and not user.banNotified:
                    if not any([x in sub_task["criteria"] for x in banTags]):
                        continue
                    user.banNotified = True
                    user.save()
                    banLog = True
                
                else: 
                    continue
                
                res = blued_msg.send(user.uuid, sub_task["id"])
                if res['code'] == 200:
                    log = Log.objects.create(
                        user=user,
                        log=f"Message sent to {user.uuid} on task {sub_task['id']} successfully."
                    )
                    log.save()
                else: 
                    log = Log.objects.create(
                        user=user,
                        log=f"Message sent failed. Error message: " + res['msg']
                    )
                    log.save()
                    
                if banLog:
                        log = BannedLog.objects.create(
                            user=user,
                            log=f"{banReasons}"
                        )
                        log.save()
                    
@catch_exceptions
def test_tasks(time: int):
    print(f"Event triggered at {datetime.now()}, with time {time}.")
    res = blued_msg.send("wKLBbRvD", 1)
    user = WebUser.objects.filter(uuid="wKLBbRvD").first()
    if res['code'] == 200:
        log = Log.objects.create(
            user=user,
            log=f"Message sent to {user.uuid} on task 1 successfully."
        )
        log.save()
    else: 
        log = Log.objects.create(
            user=user,
            log=f"Message sent failed. Error message: " + res['msg']
        )
        log.save()
    

    
if __name__ == "__main__":
    launch_tasks(8)
    launch_tasks(20)
    
