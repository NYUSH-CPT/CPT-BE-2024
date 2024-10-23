from django.contrib import admin
from .models import WebUser, Whitelist, Log, BannedLog
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from typing import Dict
from django.utils import timezone

# Register your models here.
admin_fieldsets = [
    ("User Info and Access Status", {
        'fields': ('user', 'whitelist', 'uuid', 'sms', 'score', 'group', 'currentDay', 'startDate', 'banFlag', 'banDay', 'banReason', 'banReasonInternal', 'banNotified', 'trainCompleteNotified', 'surveyCompleteNotified')
    }),
    ("Writing  1", {
        'fields': ( 'writing1', 'writing1QualityCheck', 'writing1QualityCheckRA', 'writing1QualityCheckCS', 'writing1QualityCheckNotified')
    }),
    ("Writing  4", {
        'fields': ('writing4','writing4QualityCheck', 'writing4QualityCheckRA', 'writing4QualityCheckCS', 'writing4QualityCheckNotified', 'writing4Viewed')
    }),
    ("Writing  5", {
        'fields': ('writing5', 'writing5QualityCheck', 'writing5QualityCheckRA', 'writing5QualityCheckCS', 'writing5QualityCheckNotified', 'writing5Viewed')
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

ra_fieldsets = [
    ("User Info and Access Status", {
        'fields': ('uuid', 'whitelist', 'score', 'group', 'currentDay', 'startDate', 'banFlag', 'banDay', 'banReason', 'banReasonInternal')
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

cs_filesets = [
    ("User Info and Access Status", {
        'fields': ( 'uuid', 'group', 'currentDay', 'startDate')
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

        
class WebUserAdmin(admin.ModelAdmin):
    actions = [reset_game]
    list_display = ('uuid', 'banFlag', 'group', 'score', 'startDate', 'currentDay', 'writing4Viewed', 'writing5Viewed', 'feedback6Viewed', 'feedback8Viewed')
    exclude = ('phoneNumber', )
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.validity_check()
        
    def change_view(self, request: HttpRequest, object_id: str, form_url: str = "", extra_context: Dict[str, bool] | None = None) -> HttpResponse:
        self.readonly_fields = [
            'writing1QualityCheck', 'writing4QualityCheck', 'writing5QualityCheck', 'writing6QualityCheck', 'writing8QualityCheck', 
            'writing4Viewed', 'writing5Viewed', 'feedback6Viewed', 'feedback8Viewed', 
            'banReasonInternal', "gameBreakFlag", "gameFinished", 'banFlag', 'banDay',
        ]
        if request.user.is_superuser:
            self.fieldsets = admin_fieldsets
        else:
            gorup = list(request.user.groups.all())
            if len(gorup) > 0 and gorup[0].name == "RA":
                self.fieldsets = ra_fieldsets
                self.readonly_fields += [
                    'user', 'uuid', 'whitelist', 'sms', 'score', 'group', 'currentDay', 'startDate', 'banFlag', 'banDay', 'banReasonInternal', 'user'
                    "gameBreakFlag", "gameFinished", 
                    "gameData",
                    'writing1', 'writing4', 'writing5', 'writing6', 'writing8'
                ]
            elif len(gorup) > 0 and gorup[0].name == "CS":
                self.fieldsets = cs_filesets
                self.readonly_fields += [
                    'uuid', 'group', 'startDate', 'currentDay',
                    'writing1', 'writing4', 'writing5', 'writing6', 'writing8'
                    ]
            else:
                print("Error: user not in any group")
                self.fieldsets = [["",{'fields':[]}]]

        return super().change_view(request, object_id, form_url, extra_context)


    
class WhitelistAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'group', 'has_add_wechat', 'survey0', 'startDate')
    actions = [set_startDate_2, set_startDate_3, set_startDate_4]
    readonly_fields = ('uuid', 'group', 'survey0')
    exclude = ('phoneNumber', )
    fields = ('uuid',  'startDate', 'has_add_wechat', 'group', 'survey0')
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.assign_group()
    


admin.site.register(WebUser, WebUserAdmin)
admin.site.register(Whitelist, WhitelistAdmin)
admin.site.register(Log)
admin.site.register(BannedLog)