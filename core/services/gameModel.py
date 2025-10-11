import json
import pickle
from typing import List, Optional
import sys

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse, JsonResponse

from core.models import WebUser

from . import blued_msg

sys.setrecursionlimit(10000)  # Set the recursion limit to a higher value
ThoughtDict = {"非黑即白": "表现为以极端的方式看待事物，不能或不愿看到灰色地带。",
               "以偏概全": "指将某一事件或者某一时间点作为唯一证据用于一个宽泛的结论。",
               "灾难化思维": "指对未来做出负面的、非理性的预判。",
               "过分自责": "指在解释自己所观察到的别人的行为时，较少关注情境的原因，而过多关注别人的特质和性格的原因。",
               "揣摩人心": "指在缺乏足够证据的情况下，解释别人的想法和信念。",
               "对号入座": "指随意地将外界对于某个群体的标签贴到自己身上,"
               }


class Node:
    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Optional['Node']:
        raise NotImplementedError()


class Response:
    def to_json(self):
        raise NotImplementedError()


class ClientTextResponse(Response):
    def __init__(self, text: str):
        self.text = text

    def to_json(self):
        return {
            'speaker': 'client',
            'text': self.text
        }


class UserTextResponse(Response):
    def __init__(self, text: str):
        self.text = text

    def to_json(self):
        return {
            'speaker': 'user',
            'text': self.text
        }


class SupervisorTextResponse(Response):
    def __init__(self, text: str):
        self.text = text

    def to_json(self):
        return {
            'speaker': 'supervisorText',
            'text': self.text
        }


class TransitionTextResponse(Response):
    def __init__(self, text: str):
        self.text = text

    def to_json(self):
        return {
            'speaker': 'transition',
            'text': self.text
        }


class QuestionResponse(Response):
    def __init__(self, text: str, choices: List[str], speaker: str):
        self.text = text
        self.choices = choices
        self.speaker = speaker

    def to_json(self):
        d = {i: self.choices[i] for i in range(len(self.choices))}
        return {
            'speaker': self.speaker,
            'text': self.text,
            'choices': json.dumps(d)
        }


class GameResponse(Response):

    def __init__(self, user: WebUser, name_list):
        self.responses = []
        self.user = user
        self.name_list = name_list
        self.scenario_true_id = 0
        self.scenario_display_id = 0

    def addResponse(self, reponse: Response):
        self.responses.append(reponse)

    def set_score(self, score: int):
        self.user.score = score

    def set_scenario_true_id(self, id: int):
        self.scenario_true_id = id

    def set_scenario_display_id(self, id: int):
        self.scenario_display_id = id

    def to_json(self):
        return {
            'responses': [r.to_json() for r in self.responses],
            'score': self.user.score,
            'scenario_true_id': self.scenario_true_id,
            'scenario_display_id': self.scenario_display_id,
            'name_list': self.name_list,
        }


class Question(Node):

    def __init__(self, question_text: str, choices: List[str], next_node: List[Node]):
        self.question_text = question_text
        self.choices = choices
        self.next_node = next_node

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Optional['Node']:
        user_choice = json.loads(request.body)['choice']

        if user_choice in self.choices:
            index = self.choices.index(user_choice)
            return self.next_node[index]

        game.addQuestion(self.question_text, self.choices)

        return WaitingForInput()


class Text(Node):

    def __init__(self, text: str, speaker: str, next_node: Node = None):
        self.text = text
        self.speaker = speaker
        self.next_node = next_node

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Node | None:
        if self.speaker == 'client':
            text_list = self.text.split('//')
            for text in text_list:
                game.addClientText(text)
        elif self.speaker == 'user':
            text_list = self.text.split('//')
            for text in text_list:
                game.addUserText(text)

        elif self.speaker == 'supervisor':
            game.addSupervisorText(self.text)
        elif self.speaker == 'transition':
            game.addTransitionText(self.text)

        if self.next_node is not None:
            return self.next_node
        else:
            return End()


class End(Node):
    pass


class WaitingForInput(Node):
    pass


class TypeChoiceQuestion(Node):
    def __init__(self, true_id: int, display_id: int, question_type: str, choices: List[str],
                 true_question_reply: dict[str:str],
                 false_question_reply: dict[str:str], order: int, next_node: Node = None):
        self.question_type = question_type
        self.choices = choices
        self.true_question_reply = true_question_reply
        self.false_question_reply = false_question_reply
        self.order = order
        self.next_node = next_node
        self.question_text = f"导师：第{self.order}种挑战方式是{self.question_type}。请选择以下运用该挑战方式的问题："
        self.true_id = true_id
        self.display_id = display_id

    def set_next_node(self, next_node: Node):
        self.next_node = next_node

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Optional['Node']:
        game.setTrueId(self.true_id)
        game.setDisplayId(self.display_id)
        user_choice = json.loads(request.body)['choice']

        if user_choice in self.true_question_reply.keys():
            game.add1000Score()
            true_reply = Text(self.true_question_reply[user_choice], 'client', self.next_node)
            true_question = Text(user_choice, 'user', true_reply)
            return true_question


        elif user_choice in self.false_question_reply.keys():
            game.subtract300Score()

            if (str(self.true_id) + '-' + str(self.order) + self.question_type + user_choice) not in game.user.gameData:
                game.user.gameData[str(self.true_id) + '-' + str(self.order) + self.question_type + user_choice] = 1
            else:
                game.user.gameData[str(self.true_id) + '-' + str(self.order) + self.question_type + user_choice] += 1
            game.user.save()

            false_reply = Text(self.false_question_reply[user_choice], 'supervisor', self)
            return false_reply

        game.addQuestion(self.question_text, self.choices)

        return WaitingForInput()


class ThoughtChoiceQuestion(Node):

    def __init__(self, true_id: int, display_id: int, question_text_input: str, choices: List[str],
                 type_choice_question: List[TypeChoiceQuestion],
                 alternative_thought: str, next_node: Node = None):
        self.question_text = f"导师：来访者说道：“{question_text_input}” 这是一种思维偏差，让我们试着帮助来访者来挑战并重塑它。这种想法表现出了哪一种思维偏差呢？"
        self.choices = choices  # choices[0] true, choices[1] false
        self.type_choice_question = type_choice_question
        self.alternative_thought = alternative_thought
        self.next_node = next_node
        self.true_id = true_id
        self.display_id = display_id

    def set_next_node(self, next_node: Node):
        self.next_node = next_node

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Optional['Node']:
        game.setTrueId(self.true_id)
        game.setDisplayId(self.display_id)
        user_choice = json.loads(request.body)['choice']

        if user_choice in self.choices:
            index = self.choices.index(user_choice)

            if index == 0:
                game.add1000Score()

                alternative_thought = Text(self.alternative_thought, 'client', self.next_node)
                for i in range(len(self.type_choice_question) - 1):
                    self.type_choice_question[i].set_next_node(self.type_choice_question[i + 1])
                self.type_choice_question[-1].set_next_node(alternative_thought)
                transition_content = Text(
                    f"导师：通常来说，有{len(self.type_choice_question)}个方法可以挑战“{self.choices[index]}”这一思维方式。",
                    'supervisor',
                    self.type_choice_question[0])
                correct_response = Text("非常好！现在我们来想想如何挑战这一思维偏差。", 'supervisor', transition_content)

                return correct_response
            elif index == 1:
                if (str(self.true_id) + '-' + self.question_text + user_choice) not in game.user.gameData:
                    game.user.gameData[str(self.true_id) + '-' + self.question_text + user_choice] = 1
                else:
                    game.user.gameData[str(self.true_id) + '-' + self.question_text + user_choice] += 1
                game.user.save()

                game.subtract300Score()

                incorrect_response = Text(
                    f"导师：不太对哦。再想想~ {self.choices[index]}:{ThoughtDict[self.choices[index]]}", 'supervisor',
                    self)
                return incorrect_response
            else:

                error_response = Text("输入错误，请重新输入", 'supervisor', self)

                return error_response

        game.addQuestion(self.question_text, self.choices)

        return WaitingForInput()


class RankingQuestion(Node):

    def __init__(self, true_id: int, display_id: int, thought_content: str, question_text: str, next_node: Node):
        self.question_text = question_text
        self.choices = ['1分', '2分', '3分', '4分', '5分']
        self.next_node = next_node
        self.true_id = true_id
        self.display_id = display_id
        self.thought_content = thought_content

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Optional['Node']:
        game.setTrueId(self.true_id)
        game.setDisplayId(self.display_id)
        user_choice = json.loads(request.body)['choice']

        if user_choice in self.choices:
            # save to database
            game.user.gameData[str(self.true_id) + '-' + self.thought_content] = user_choice
            game.user.save()
            return self.next_node

        game.addQuestion(self.question_text, self.choices)
        return WaitingForInput()


class TransitionQuestion(Node):

    def __init__(self, true_id: int, display_id: int, transition_text: str, next_node: Node):
        self.transition_text = transition_text
        self.choices = ['继续']
        self.next_node = next_node
        self.true_id = true_id
        self.display_id = display_id

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Optional['Node']:
        game.setTrueId(self.true_id)
        game.setDisplayId(self.display_id)
        user_choice = json.loads(request.body)['choice']
        if user_choice in self.choices:

            return self.next_node

        game.addQuestion(self.transition_text, self.choices)
        return WaitingForInput()


class Thought(Node):

    def __init__(self, true_id: int, display_id: int, thought_content: str, question_types: ThoughtChoiceQuestion,
                 alternative_thought: str, next_node: Node = None):
        self.true_id = true_id
        self.display_id = display_id
        self.thought_content = thought_content
        self.question_types = question_types
        self.next_node = next_node
        self.alternative_thought = alternative_thought

    def set_next_node(self, next_node: Node):
        self.next_node = next_node

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Node:
        # thought_choice_question = ThoughtChoiceQuestion(
        #     f"导师：来访者说道：“{self.thought_content}” 这是一种思维偏差，让我们试着帮助来访者来挑战并重塑它。这种想法表现出了哪一种思维偏差呢？",
        #     self.thought_choices, self.question_types, self.alternative_thought, self.next_node)

        game.setTrueId(self.true_id)
        game.setDisplayId(self.display_id)
        self.question_types.set_next_node(self.next_node)

        rank_question = RankingQuestion(self.true_id, self.display_id, self.thought_content,
                                        f"导师：来访者说道：{self.thought_content} 在日常生活中，你自己有出现这种想法吗？1分表示“从来没有”，5分表示“一直出现”。",
                                        self.question_types)
        client_thought_content = Text(self.thought_content, 'client', rank_question)

        return client_thought_content


class Scenario(Node):

    def __init__(self, name: str, true_id: int, display_id: int, start_sentence: str, end_sentence: str,
                 scenario_content: str,
                 thoughts: List[Thought],
                 next_node: Node):
        self.next_node = next_node
        self.start_sentence = start_sentence
        self.end_sentence = end_sentence
        self.thoughts = thoughts
        self.scenario_content = scenario_content
        self.display_id = display_id
        self.true_id = true_id
        self.name = name

    def set_next_node(self, next_node: Node):
        self.next_node = next_node

    def consume(self, game: 'MiniGame', request: WSGIRequest) -> Node:
        game.setTrueId(self.true_id)
        game.setDisplayId(self.display_id)
        for i in range(len(self.thoughts) - 1):
            self.thoughts[i].set_next_node(self.thoughts[i + 1])

        end_sentence = Text(self.end_sentence, 'client', self.next_node)
        self.thoughts[-1].set_next_node(end_sentence)
        scenario_content = Text(self.scenario_content, 'client', self.thoughts[0])
        # start_sentence = Text(self.start_sentence, 'supervisor',scenario_content)
        start_sentence = TransitionQuestion(self.true_id, self.display_id, self.start_sentence,
                                            scenario_content)

        return start_sentence

    def __str__(self):
        return f'网名: {self.name}, display_id: {self.display_id}'


class MiniGame(Node):
    start_sentence = "欢迎来到小游戏！在这个游戏里，您将扮演一名心理咨询专业的大一学生，在导师的带领下，为十六位性少数男性来访者解决他们的困扰。让我们开始吧!"

    def __init__(self, current_node: Node, user: WebUser, name_list: List[str]):
        self.current_node = current_node
        self.user = user
        self.name_list = name_list
        self.response = GameResponse(self.user, self.name_list)

    def add1000Score(self):
        self.user.score += 1000
        self.user.save()
        self.response.set_score(self.user.score)

    def subtract300Score(self):
        self.user.score -= 300
        self.user.save()
        self.response.set_score(self.user.score)

    def addClientText(self, text):
        self.response.addResponse(ClientTextResponse(text))

    def addUserText(self, text):
        self.response.addResponse(UserTextResponse(text))

    def addSupervisorText(self, text):
        self.response.addResponse(SupervisorTextResponse(text))

    def addTransitionText(self, text):
        self.response.addResponse(TransitionTextResponse(text))

    def addQuestion(self, text: str, choices: List[str]):
        self.response.addResponse(QuestionResponse(text, choices, 'supervisor'))

    def setDisplayId(self, display_id):
        self.response.set_scenario_display_id(display_id)

    def setTrueId(self, true_id):
        self.response.set_scenario_true_id(true_id)

    def handleRequest(self, request: WSGIRequest) -> HttpResponse:

        self.response = GameResponse(self.user, self.name_list)

        node = Node()

        while not isinstance(node, WaitingForInput):


            if isinstance(self.current_node,
                          TransitionQuestion) and self.user.group!="Waitlist" and self.current_node.display_id == 8 and self.user.gameBreakFlag == False:
                self.user.gameBreakFlag = True
                self.response.addResponse(
                    SupervisorTextResponse('今天辛苦啦，您的游戏进度已经保存。您可以在明天继续游戏。'))
                pickle_game = pickle.dumps(self)
                self.user.game = pickle_game
                self.user.currentDay = 3
                self.user.save()
                if self.user.group != "Waitlist" and self.user.score < 30600:
                    # Day2游戏低于总分30%
                    blued_msg.send(self.user.uuid, 7)
                break
            node = self.current_node.consume(self, request)
            request.body = b'{"choice":""}'
            if isinstance(node, End) :
                self.response.addResponse(SupervisorTextResponse('游戏结束'))
                self.user.gameFinished = True
                pickle_game = pickle.dumps(self)
                self.user.game = pickle_game
                if self.user.group!="Waitlist": 
                    self.user.currentDay = 4
                    banTags = self.user.validity_check()
                    if "game_score_low" in banTags:
                        # 游戏总得分低于60%
                        blued_msg.send(self.user.uuid, 18)
                self.user.save()
                
                break

            if not isinstance(node, WaitingForInput):
                self.current_node = node
        pickle_game = pickle.dumps(self)
        self.user.game = pickle_game
        self.user.save()
        return JsonResponse(self.response.to_json())