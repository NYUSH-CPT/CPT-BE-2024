from rest_framework import serializers
from .models import WebUser, Screen

class WebUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebUser
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'context' in kwargs:
            if kwargs['context'].get('info'):
                info_fields = [
                    'uuid', 'group', 'currentDay', 'startDate', 'banFlag', 'banReason', 'banDay', 'feedback6', 'feedback8',
                    'feedback6RAApproved', 'feedback8RAApproved',
                    'writing4Viewed', 'writing5Viewed', 'feedback6Viewed', 'feedback8Viewed', 
                    'survey1', 'survey23', 'survey39', 'survey99',
                    'survey1IsValid', 'survey23IsValid', 'survey39IsValid', 'survey99IsValid',
                ]
                for field in set(self.fields) - set(info_fields):
                    self.fields.pop(field)

            if kwargs['context'].get('writing'):
                for field in set(self.fields) - set([kwargs['context']['field_name']]):
                    self.fields.pop(field)


class ScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Screen
        fields = '__all__'