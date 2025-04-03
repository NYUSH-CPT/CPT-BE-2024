from django.contrib import admin
from .models import WebUser, Whitelist, Log, BannedLog, LSUser
from django.utils import timezone
from core.utility import decrypt
import csv
from django.http import HttpResponse
import os.path as path

# Register your models here.
admin_fieldsets = [
    ("Contact Info", {
        'fields': ("phoneNumber", "WeChat")
    }),
    ("User Info and Access Status", {
        'fields': ('user', 'whitelist', 'uuid', 'sms', 'score', 'group', 'currentDay', 'startDate', 'banFlag', 'banDay', 'banReason', 'banNotified', 'trainCompleteNotified', 'surveyCompleteNotified')
    }),
    ("Writing  1", {
        'fields': ( 'writing1', 'writing1QualityCheck', 'writing1QualityCheckRA', 'writing1QualityCheckCS', 'writing1QualityCheckNotified')
    }),
    ("Writing  4", {
        'fields': ('writing4', 'writing4QualityCheck', 'writing4QualityCheckRA', 'writing4QualityCheckCS', 'writing4Viewed', 'writing4QualityCheckNotified')
    }),
    ("Writing  5", {
        'fields': ('writing5', 'writing5QualityCheck', 'writing5QualityCheckRA', 'writing5QualityCheckCS', 'writing5Viewed', 'writing5QualityCheckNotified')
    }),
    ("Writing  6", {
        'fields': ('writing6', 'writing6QualityCheck', 'writing6QualityCheckRA', 'writing6QualityCheckCS', 'writing6QualityCheckNotified', 'feedback6', 'feedback6Viewed')
    }),
    ("Writing  8", {    
        'fields': ('writing8', 'writing8QualityCheck', 'writing8QualityCheckRA', 'writing8QualityCheckCS', 'writing8QualityCheckNotified', 'feedback8', 'feedback8Viewed')
    }),
    ("Game",{
        'fields': ( "gameBreakFlag", "gameFinished", "gameData")
    }),
    ("Survey",{
        'fields': ( "survey1", "survey1IsValid", 
                    "survey23", "survey23IsValid", 
                    "survey39", "survey39IsValid", 
                    "survey99", "survey99IsValid")
    })
]

info_fieldsets = [
    ("Contact Info", {
        'fields': ("phoneNumber", "WeChat")
    }),
    ("User Info and Access Status", {
        'fields': ('uuid', 'whitelist', 'score', 'group', 'currentDay', 'startDate', 'banFlag', 'banDay', 'banReason')
    }),
    ("Writing  1", {
        'fields': ( 'writing1', 'writing1QualityCheck', 'writing1QualityCheckRA')
    }),
    ("Writing  4", {
        'fields': ('writing4','writing4QualityCheck', 'writing4QualityCheckRA', 'writing4Viewed')
    }),
    ("Writing  5", {
        'fields': ('writing5', 'writing5QualityCheck', 'writing5QualityCheckRA', 'writing5Viewed')
    }),
    ("Writing  6", {
        'fields': ('writing6', 'writing6QualityCheck', 'writing6QualityCheckRA', 'feedback6Viewed')
    }),
    ("Writing  8", {    
        'fields': ('writing8', 'writing8QualityCheck', 'writing8QualityCheckRA', 'feedback8Viewed')
    }),
    ("Game",{
        'fields': ( "gameBreakFlag", "gameFinished", "gameData")
    }),
    ("Survey",{
        'fields': ( "survey1", "survey1IsValid", 
                    "survey23", "survey23IsValid", 
                    "survey39", "survey39IsValid", 
                    "survey99", "survey99IsValid")
    })
]

ra_fieldsets = [
    ("User Info and Access Status", {
        'fields': ('uuid', 'whitelist', 'score', 'group', 'currentDay', 'startDate', 'banFlag', 'banDay', 'banReason')
    }),
    ("Writing  1", {
        'fields': ( 'writing1', 'writing1QualityCheck', 'writing1QualityCheckRA')
    }),
    ("Writing  4", {
        'fields': ('writing4','writing4QualityCheck', 'writing4QualityCheckRA', 'writing4Viewed')
    }),
    ("Writing  5", {
        'fields': ('writing5', 'writing5QualityCheck', 'writing5QualityCheckRA', 'writing5Viewed')
    }),
    ("Writing  6", {
        'fields': ('writing6', 'writing6QualityCheck', 'writing6QualityCheckRA', 'feedback6Viewed')
    }),
    ("Writing  8", {    
        'fields': ('writing8', 'writing8QualityCheck', 'writing8QualityCheckRA', 'feedback8Viewed')
    }),
    ("Game",{
        'fields': ( "gameBreakFlag", "gameFinished", "gameData")
    }),
    ("Survey",{
        'fields': ("survey1IsValid", 
                    "survey23IsValid", 
                    "survey39IsValid", 
                    "survey99IsValid")
    })
]

cs_fieldsets = [
    ("User Info and Access Status", {
        'fields': ('uuid', 'group', 'currentDay', 'startDate')
    }),
    ("Writing  1", {
        'fields': ( 'writing1', 'writing1QualityCheck', 'writing1QualityCheckCS')
    }),
    ("Writing  4", {
        'fields': ('writing4','writing4QualityCheck', 'writing4QualityCheckCS')
    }),
    ("Writing  5", {
        'fields': ('writing5', 'writing5QualityCheck', 'writing5QualityCheckCS')
    }),
    ("Writing  6", {
        'fields': ('writing6', 'writing6QualityCheck', 'writing6QualityCheckCS', 'feedback6')
    }),
    ("Writing  8", {    
        'fields': ('writing8', 'writing8QualityCheck', 'writing8QualityCheckCS', 'feedback8')
    })
]

ls_fieldset = [
    ("Contact Info", {
        'fields': ("phoneNumber", "QQ")
    })
]


@admin.action(description='Reset game')
def reset_game(modeladmin, request, queryset):
    for obj in queryset:
        obj.reset_game()
        
@admin.action(description="Set Whitelist Start Date to two days later")
def set_startDate_2(modeladmin, request, queryset):
    days_later = timezone.now() + timezone.timedelta(days=2)
    queryset.update(startDate=days_later)

               
@admin.action(description="Set Whitelist Start Date to three days later")
def set_startDate_3(modeladmin, request, queryset):
    days_later = timezone.now() + timezone.timedelta(days=3)
    queryset.update(startDate=days_later)
              
@admin.action(description="Set Whitelist Start Date to four days later")
def set_startDate_4(modeladmin, request, queryset):
    days_later = timezone.now() + timezone.timedelta(days=4)
    queryset.update(startDate=days_later)


def export_to_csv_func(csv_file, output_file):
    
    @admin.action(description="Export to CSV")
    def _export_to_csv(modeladmin, request, queryset):

        if not (request.user.is_superuser or request.user.groups.filter(name='LS').exists()):
            modeladmin.message_user(
                request, "You do not have permission to perform this action.", level='error')
            return

        # read fields for export
        fields, names = [], []
        with open(path.join(path.dirname(__file__), "csv_export", csv_file), 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip the first title line
            for row in reader:
                fields.append(row[0])
                names.append(row[1])

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{output_file}"'

        writer = csv.writer(response)
        writer.writerow(names)

        for obj in queryset:
            row = []
            for field in fields:
                if field in {"encryptedPhoneNumber", "encryptedWeChat", "encryptedQQ"}:
                    row.append(decrypt(getattr(obj, field)))
                else:
                    row.append(getattr(obj, field))
            writer.writerow(row)

        return response

    return _export_to_csv


class WebUserAdmin(admin.ModelAdmin):
    export_to_csv = export_to_csv_func(
        "web_user_export_fields.csv", "web_user.csv")
    actions = [reset_game, export_to_csv]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.validity_check()

    def phoneNumber(self, obj):
       return decrypt(obj.encryptedPhoneNumber)

    def WeChat(self, obj):
       return decrypt(obj.encryptedWeChat)

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return admin_fieldsets
        elif request.user.groups.filter(name="INFO").exists():
            return info_fieldsets
        elif request.user.groups.filter(name="RA").exists():
            return ra_fieldsets
        elif request.user.groups.filter(name="CS").exists():
            return cs_fieldsets
        else:
            return []

        return response

    def get_readonly_fields(self, request, obj=None):
        base_readonly_fields = [
            'uuid', 'group',
            'writing1', 'writing4', 'writing5', 'writing6', 'writing8',
            'writing1QualityCheck', 'writing4QualityCheck', 'writing5QualityCheck', 'writing6QualityCheck', 'writing8QualityCheck', 
            'writing4Viewed', 'writing5Viewed', 'feedback6Viewed', 'feedback8Viewed', 
            "gameBreakFlag", "gameFinished", 'banFlag', 'banDay', 'banReason'
        ]
        if request.user.is_superuser:
            return ["phoneNumber", "WeChat"]
        elif request.user.groups.filter(name="INFO").exists():
            return base_readonly_fields + [
                "phoneNumber", "WeChat",
                'user', 'whitelist', 'sms', 'score', 'banFlag', 'banDay', 'user'
                "gameBreakFlag", "gameFinished", "gameData",
                "survey1", "survey1IsValid", 
                "survey23", "survey23IsValid", 
                "survey39", "survey39IsValid", 
                "survey99", "survey99IsValid"
            ]
        elif request.user.groups.filter(name="RA").exists():
            return base_readonly_fields + [
                'user', 'whitelist', 'sms', 'score', 'banFlag', 'banDay', 'user'
                "gameBreakFlag", "gameFinished", "gameData",
                "survey1IsValid", "survey23IsValid", "survey39IsValid", "survey99IsValid"
            ]  
        elif request.user.groups.filter(name="CS").exists():
            return base_readonly_fields + [
                'startDate', 'currentDay'
            ]
        else:
            return []
        
    def get_list_display(self, request):
        if request.user.is_superuser:
            return ('uuid', 'banFlag', 'group', "phoneNumber", 'WeChat', 'score', 'startDate', 'currentDay')
        elif request.user.groups.filter(name="INFO").exists():
            return ('uuid', 'banFlag', 'group', "phoneNumber", 'WeChat', 'score', 'startDate', 'currentDay')
        elif request.user.groups.filter(name="RA").exists():
            return ('uuid', 'banFlag', 'group', 'score', 'startDate', 'currentDay')
        elif request.user.groups.filter(name="CS").exists():
            return ('uuid', 'group', 'startDate', 'currentDay')
        else:
            return []
       

class WhitelistAdmin(admin.ModelAdmin):
    export_to_csv = export_to_csv_func(
        "whitelist_export_fields.csv", "whitelist.csv")
    actions = [set_startDate_2, set_startDate_3,
               set_startDate_4, export_to_csv]
    exclude = ('encryptedPhoneNumber', 'encryptedWeChat')
    
    def phoneNumber(self, obj):
       return decrypt(obj.encryptedPhoneNumber)

    def WeChat(self, obj):
       return decrypt(obj.encryptedWeChat)
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.assign_group()

    def get_list_display(self, request):
        if request.user.is_superuser:
            return ('uuid', 'group', 'phoneNumber', 'WeChat', 'has_add_wechat', 'startDate', 'survey0')
        elif request.user.groups.filter(name="INFO").exists():
            return ('uuid', 'group', 'phoneNumber', 'WeChat', 'has_add_wechat', 'startDate', 'survey0')
        elif request.user.groups.filter(name="RA").exists():
            return ('uuid', 'group', 'has_add_wechat', 'startDate')
        else:
            return ()
        
    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ['phoneNumber', 'WeChat']
        elif request.user.groups.filter(name="INFO").exists():
            return ['phoneNumber', 'WeChat', 'uuid', 'group', 'survey0']
        elif request.user.groups.filter(name="RA").exists():
            return ['uuid', 'group']
        else:
            return []
        
    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return [
                ("Contact Info", {'fields': ('phoneNumber', 'WeChat')}),
                ("User Info", {"fields": ("uuid", "group", "has_add_wechat", "startDate", 'survey0')})]
        elif request.user.groups.filter(name="INFO").exists():
            return [
                ("Contact Info", {'fields': ('phoneNumber', 'WeChat')}),
                ("User Info", {"fields": ("uuid", "group", "has_add_wechat", "startDate", 'survey0')})]
        elif request.user.groups.filter(name="RA").exists():
            return [("User Info", {"fields": ("uuid", "group", "has_add_wechat", "startDate")})]
        else:
            return []
    

class LSUserAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'phoneNumber', 'qq', 'survey0')
    readonly_fields = ('uuid', 'survey0', 'phoneNumber', 'qq')
    export_to_csv = export_to_csv_func(
        "ls_user_export_fields.csv", "ls_user.csv")
    actions = [export_to_csv]
    
    def phoneNumber(self, obj):
       return decrypt(obj.encryptedPhoneNumber)

    def qq(self, obj):
       return decrypt(obj.encryptedQQ)


    def get_model_perms(self, request):
        if request.user.groups.filter(name='LS').exists() or request.user.is_superuser:
            return super().get_model_perms(request)
        return {}
    
    def get_fieldsets(self, request, obj = ...):
        if request.user.is_superuser or request.user.groups.filter(name="LS").exists():
            return [
                ("Contact Info", {'fields': ('phoneNumber', 'qq')}),
                ("User Info", {"fields": ("uuid", 'survey0')})]
        else:
            return []    

admin.site.register(WebUser, WebUserAdmin)
admin.site.register(Whitelist, WhitelistAdmin)
admin.site.register(LSUser, LSUserAdmin)
admin.site.register(Log)
admin.site.register(BannedLog)
