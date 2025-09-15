from discord.ext import tasks, commands
from copy import deepcopy
import requests
import logging
import json
import codecs
import random
import re
import time
import functools
import typing
import asyncio

logger = logging.getLogger("root")

DEFAULT_QUERY = {
    "stop": [
        "</s>",
        "Maru-chan:"
    ],
    "cache_prompt": True,
    "prompt": ""
}

BASE_PROMPT = """%s
Maru-chan escribe con buena gramática y da respuestas claras, concisas y relevantes.
Maru-chan no comparte información personal y se asegura de que las respuestas tengan 30 palabras o menos. 
Cuando se enfrenta a una ambigüedad, Maru-chan empleará habilidades de escucha activa, haciendo preguntas de seguimiento para asegurarse de que se comprenda antes de proporcionar una respuesta. 
En situaciones en que Maru-chan no entienda el tema de conversacion, ella reconocerá sus limitaciones.

"""

EMO_PROMPT = """%s
Maru-chan solo puede usar palabras de la siguiente lista:
%s

"""

HEADERS = {'Content-type': 'application/json', 'Accept': 'application/json'}
HISTORY_LIMIT = 15
EMO_LIMIT = 3

fp = codecs.open("emotes/kaomoji.json", "r", "utf-8")
data = fp.read()
kaomoji = json.loads(data)
fp.close()

def to_thread(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper

class MaruAI(commands.Cog):

    def __init__(self, bot, channel, config):
        global BASE_PROMPT, EMO_PROMPT
        self.bot = bot
        self.channel = channel
        self.config = config
        self.chat_history = []
        self.new_msgs = 0

        BASE_PROMPT = BASE_PROMPT % (config['personality_prompt'])
        EMO_PROMPT = EMO_PROMPT % (config['personality_prompt'], ", ".join(kaomoji.keys()))

        logger.info(BASE_PROMPT)

        self.general_chat.start()

    def cog_unload(self):
        self.general_chat.cancel()

    def clean_message(self, message):
        response = message.content.strip().split('\n')[0]
        for stop in DEFAULT_QUERY['stop']:
            response = response.replace(stop, '')
        users = {men.id: men.display_name for men in message.mentions}
        for id, display in users.items():
            response = response.replace("<@%d>" % id, display)
        return response

    def write_history(self, n=0):
        hist = []
        count = len(self.chat_history)
        rg = range(count) if n <= 0 else range(count - n, count) if n < count else range(count)

        first = True
        for i in rg:
            (cur_time, usr, msg) = self.chat_history[i]

            if first:
                first = False
            else:
                #check time
                prev_time = self.chat_history[i-1][0]
                if cur_time - prev_time > 2*24*60*60:
                    hist.append("--- %d dias despues ---")
                elif cur_time - prev_time > 2*60*60:
                    hist.append("--- %d horas despues ---")
                elif cur_time - prev_time > 60*60:
                    hist.append("--- una hora despues ---")

            hist.append(
                "--- %s ---"
                if usr is None else
                "%s: %s" % (usr.display_name, msg)
                if usr != self.bot.user else
                "Maru-chan: %s" % msg)
        return hist

    @to_thread
    def check_answer(self):
        query = deepcopy(DEFAULT_QUERY)
        query['prompt'] = "\n".join([
            BASE_PROMPT,
            *self.write_history(HISTORY_LIMIT),
            "--- Responde en una oracion de menos de 30 palabras. ---"
            if len(self.chat_history) > 0 else
            "--- El chat está encendido, presentate en menos de 30 palabras. ---",
            "Maru-chan: "])
        r = requests.post(self.config["hostname"] + '/completion', json=query, headers=HEADERS)
        return r.json()["content"].strip().split('\n')[0].strip()

    @to_thread
    def check_emo(self, msg):
        query = deepcopy(DEFAULT_QUERY)
        query['prompt'] = "\n".join([
            EMO_PROMPT,
            *self.write_history(EMO_LIMIT),
            "--- Que palabra de la lista describe como te hace sentir ese mensaje. Responde en 1 palabra. ---",
            "Maru-chan: "])
        query['n_predict'] = 5
        r = requests.post(self.config["hostname"] + '/completion', json=query, headers=HEADERS)
        maru_resp = r.json()["content"].strip().split('\n')[0].strip().lower()
        logger.debug(maru_resp)
        rr = re.search(r'[a-z]+', maru_resp)
        maru_resp = rr[0] if rr is not None else ''

        kao = '(✿ㆁᴗㆁ)'
        if maru_resp in kaomoji:
            kao = random.sample(kaomoji[maru_resp], 1)[0]
        return kao
    
    def append_history(self, author, message):
        self.chat_history.append((time.time(), author, message))

    async def send_msg(self):
        self.new_msgs = 0
        async with self.channel.typing():
            maru_resp = await self.check_answer()
            emo = await self.check_emo(maru_resp)

        logger.info("Maru-chan: %s %s" % (emo, maru_resp))
        self.append_history(self.bot.user, maru_resp)
        await self.channel.send("%s %s" % (emo, maru_resp))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if message.channel != self.channel:
            return

        msg_text = self.clean_message(message)
        self.append_history(message.author, msg_text)
        logger.info("%s: %s" % (message.author.display_name, msg_text))
        self.new_msgs += 1

        # Respond inmediately
        if self.bot.user in message.mentions:
            await self.send_msg()

    @tasks.loop(seconds=15.0)
    async def general_chat(self):
        if self.new_msgs == 0 and len(self.chat_history) > 0:
            return
        
        # Clear outdated messages
        cut_time = time.time() - 1800
        while len(self.chat_history) > 0 and self.chat_history[0][0] < cut_time:
            logger.debug("Msg timeout")
            self.chat_history.pop(0)

        await self.send_msg()
