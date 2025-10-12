# -*- coding: utf-8 -*-
import pickle
from rest_framework.response import Response
from rest_framework import status

from core.models import WebUser
from core.services.parser import get_scenario_list
from core.services.gameModel import MiniGame, Text



def initializeGame(user: WebUser) -> MiniGame:

    scenario_list = get_scenario_list()
    patient_names = []
    scenario_list[0].start_sentence = "你好，我是你这节实践课的导师。我是一名彩虹友善心理咨询师，取向为认知–行为疗法。很高兴认识你！我们来与第一位来访者连线吧！"
    for i in range(len(scenario_list) - 1):
        scenario_list[i].set_next_node(scenario_list[i + 1])

    start_sentence = Text(MiniGame.start_sentence, 'supervisor', scenario_list[0])

    for scenario in scenario_list:
        patient_names.append(scenario.name)
        
    game = MiniGame(start_sentence,user,patient_names)
    return game





def getNewGame(user: str) -> MiniGame|Response:
    try:
        webUser = WebUser.objects.get(user=user)
    except WebUser.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    if webUser.currentDay < 2:
        return Response({"error": f"Current progress has not reach day 2"}, status=status.HTTP_400_BAD_REQUEST)
    # check if game is initialized in web user
    if webUser.game is None:
        game = initializeGame(webUser)
        # use pickle serialization for game
        pickle_game = pickle.dumps(game)
        webUser.game = pickle_game
        webUser.save()
        webUser.validity_check()
        return game
    else:
        game = pickle.loads(webUser.game)
        game.user = webUser
        return game


