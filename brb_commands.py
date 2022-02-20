import asyncio
import logging
import requests

from requests.exceptions import HTTPError
from nextcord.ext import commands
from nextcord import Interaction
from nextcord import SlashOption
from typing import Final

bot = commands.Bot(command_prefix='$')

MAX_QUERY_LEN: Final = 512
SOLVED_AC_API_URL: Final = "https://solved.ac/api/v3/search/problem"


@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logging.info('------')


@bot.slash_command(name='brb-rand', description='기본 커맨드. 모든 참가자들이 안 푼 문제를 랜덤하게 골라 대결합니다.', force_global=True)
async def brb_rand(inter: Interaction, competitors: str = SlashOption(description='참가자들의 백준 아이디 (공백으로 구분)', required=True), options: str = SlashOption(description='solved.ac 검색 옵션 (예. tier:b5..g1)', required=False, default=''), tag_hint_minutes: int = SlashOption(description='알고리즘 분류를 공개할 시간 (0분이면 비공개, 기본값 30분 경과시)', required=False, default=30, min_value=0), battle_timeout: int = SlashOption(description='대전 자동 종료 시간 (0분이면 자동 종료 안함, 기본값 60분 경과시)', required=False, default=60, min_value=0), alert_minutes: int = SlashOption(description='추가 알림 시간 (기본값 꺼짐)', required=False, default=0, min_value=1)):

    competitors: list = competitors.split()

    # 쿼리 문자열 만들기
    options = 'solvable:1&' + options + '&' if options else 'solvable:1&'
    query_competitors_len = len(options)
    query_competitors = [options]
    # 참가자 추가
    for person in competitors:
        partial_query = f'~solved_by:{person}&'
        query_competitors_len += len(partial_query)
        query_competitors.append(partial_query)
    if query_competitors_len > MAX_QUERY_LEN:
        await inter.send('쿼리가 너무 길어 문제 검색이 불가능합니다!\n참가자나 옵션을 줄여주세요.')
        return

    query = ''.join(query_competitors)[:-1]

    # 문제를 검색
    chosen_problem = None
    try:
        chosen_problem = await search_problem(query)
    except HTTPError as e:
        await inter.send(f'문제 검색 중 오류가 발생했습니다. (HTTP {e.response.status_code})')
        return

    # 뽑은 문제로 대전 시작
    await initiate_battle(inter, chosen_problem, tag_hint_minutes,
                          battle_timeout, alert_minutes)


# solved.ac API에서 조건에 맞는 랜덤 문제를 뽑기
async def search_problem(query: str):
    chosen_problem = None
    logging.info(f'쿼리: {query}')
    query: dict = {'query': query, 'sort': 'random'}

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(
        None, requests.get, SOLVED_AC_API_URL, query)
    response = await future
    # HTTPError 예외
    response.raise_for_status()

    result = response.json()
    if result['count'] != 0:
        chosen_problem = result['items'][0]
    return chosen_problem


# 뽑은 문제로 대전 시작
async def initiate_battle(inter: Interaction, chosen_problem, tag_hint_minutes: int, battle_timeout: int, alert_minutes: int):
    if not chosen_problem:
        await inter.send('조건에 맞는 문제를 찾을 수 없습니다.')
        return
    else:
        await inter.send(f"{chosen_problem['problemId']}번: {chosen_problem['titleKo']}\nhttps://www.acmicpc.net/problem/{chosen_problem['problemId']}\n대전을 시작합니다! (아무때나 `stop`으로 중단)")
        timer_msg = await inter.channel.send(f'0분 경과' + (f' (남은 시간 {battle_timeout}분)' if battle_timeout != 0 else ''))

    # `stop` 입력 감지
    def stop_check(msg):
        return msg.content == 'stop' and msg.channel.id == inter.channel.id

    # 대전 타이머 처리
    elapsed = 0

    while battle_timeout == 0 or battle_timeout-elapsed > 0:
        try:
            await bot.wait_for('message', check=stop_check, timeout=60)
        except asyncio.TimeoutError:
            elapsed += 1
            await timer_msg.edit(content=f'{elapsed}분 경과' + (f' (남은 시간 {battle_timeout-elapsed}분)' if battle_timeout != 0 else ''))
            if elapsed == tag_hint_minutes:
                tags = [tag['displayNames'][0]['name']
                        for tag in chosen_problem['tags']]
                await inter.channel.send(f'{tag_hint_minutes}분 경과: 알고리즘 분류 힌트\n||'+', '.join(tags)+'||')
            if elapsed == alert_minutes:
                await inter.channel.send(f'{elapsed}분 경과!')
        else:
            break

    await inter.channel.send(f'대전이 종료되었습니다. (소요시간: {elapsed}분)')
