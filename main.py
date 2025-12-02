import discord
import os
from keep_alive import keep_alive
from discord import app_commands
from discord.ext import commands, tasks
import re
import asyncio
import random
from datetime import datetime, timezone, timedelta
import time
import requests
import json
from urllib.parse import urlparse  # emoji
from deep_translator import GoogleTranslator

intents=discord.Intents.all()
intents.message_content = True
intents.members = True  # メンバー参加イベントを取得するために必要
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 日本時間（JST）
JST = timezone(timedelta(hours=9))

ALLOWED_GUILD_IDS = {742727484750954577,1389253121649414239}  # ✅ Botが所属できるサーバーIDをここに記入（複数対応可）

@client.event
async def on_ready():
    print('ログインしました')
 # アクティビティを設定
    activity = discord.Activity(name='疾風スピードスター', type=discord.ActivityType.competing)
    await client.change_presence(status=discord.Status.online, activity=activity)
    # スラッシュコマンドを同期
    await tree.sync()
    
#スラッシュコマンド
@tree.command(name='membercount', description='サーバーの人数を表示します') 
async def member_count(message):
    # message インスタンスから guild インスタンスを取得
    guild = message.guild 
    # ユーザとBOTを区別しない場合
    member_count = guild.member_count
    await message.response.send_message(f'今の人数は{member_count}です')
@tree.command(name='help', description='疾風の使い方') 
async def help_command(message):
    help_message = discord.Embed( # Embedを定義する
                          title="Botの使い方",# タイトル
                          color=0x00ff00, # フレーム色指定(今回は緑)
                          description="このbotの使い方を説明します。"
                          )
    help_message.add_field(name="/help",value="今表示しているものです。", inline=False) # フィールドを追加。
    help_message.add_field(name="/",value="開発中。", inline=False)
    help_message.add_field(name="/",value="開発中", inline=False)
    await message.response.send_message(embed=help_message) # embedの送信には、embed={定義したembed名}

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content == "こんにちは":
        await message.channel.send("こんにちは！")

                
TOKEN = os.getenv("DISCORD_TOKEN")
# Web サーバの立ち上げ
keep_alive()
client.run(TOKEN)
