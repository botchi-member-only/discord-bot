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
from langdetect import detect  # 言語判定ライブラリ

intents=discord.Intents.all()
intents.message_content = True
intents.members = True  # メンバー参加イベントを取得するために必要
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 日本時間（JST）
JST = timezone(timedelta(hours=9))

ALLOWED_GUILD_IDS = {742727484750954577,1389253121649414239}  # ✅ Botが所属できるサーバーIDをここに記入（複数対応可）

#save機能
AUTO_TRANSLATE_FILE = "AutoTranslateChannel.json"
REPO = "botchi-member-only/discord-bot"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # 安全な方法で読み込む

@client.event
async def on_ready():
    print('ログインしました')
 # アクティビティを設定
    activity = discord.Activity(name='Botchi™', type=discord.ActivityType.competing)
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

@tree.command(name="translate", description="メッセージを翻訳します")
@app_commands.describe(
    message_id="翻訳したいメッセージのID（省略可）",
    direction="翻訳方向を選択（to_en: 日本語→英語, to_ja: 英語→日本語）",
    ephemeral="実行者だけに表示するかどうか（true/false、省略可）"
)
@app_commands.choices(direction=[
    app_commands.Choice(name="自動auto",value="auto"),
    app_commands.Choice(name="日本語 → 英語", value="to_en"),
    app_commands.Choice(name="英語 → 日本語", value="to_ja")
])
async def translate(
    interaction: discord.Interaction,
    message_id: str = None,
    direction: str = "auto",
    ephemeral: bool = False
):
    await interaction.response.defer(thinking=True, ephemeral=ephemeral)
    message = None
    if message_id:
        # IDからメッセージ取得
        try:
            message = await interaction.channel.fetch_message(int(message_id))
        except:
            await interaction.followup.send("❌ 指定したメッセージIDのメッセージが見つかりませんでした。", ephemeral=ephemeral)
            return
    else:
        # 直近の「ユーザーが送った」メッセージを取得
        async for msg in interaction.channel.history(limit=10):
            if msg.content and not msg.author.bot:
                message = msg
                break
        if message is None:
            await interaction.followup.send("❌ 翻訳対象のメッセージが見つかりません。", ephemeral=ephemeral)
            return
    text = message.content.strip()
    if not text:
        await interaction.followup.send("❌ メッセージが空です。", ephemeral=ephemeral)
        return
        
    if direction == "auto":
        try:
            detected = detect(text)  # ja / en / etc...
        except:
            await interaction.followup.send("⚠️ 判別中にエラーが発生しました。", ephemeral=ephemeral)
            return
        if detected.startswith("ja"):
            direction = "to_en"
        else:
            direction = "to_ja"
    try:
        if direction == "to_en":
            src, dest, flag = "ja", "en", "🇯🇵 → 🇺🇸"
        else:
            src, dest, flag = "en", "ja", "🇺🇸 → 🇯🇵"
        translated = GoogleTranslator(source=src, target=dest).translate(text)
        result = f"{flag}\n{translated}"
    except Exception as e:
        await interaction.followup.send("⚠️ 翻訳中にエラーが発生しました:{e}", ephemeral=ephemeral)
        return
    await interaction.followup.send(result, ephemeral=ephemeral)

@tree.command(name="auto_translate_mode", description="自動翻訳モードをチャンネルごとにON/OFFします。")
@app_commands.describe(
    direction="ON / OFF を選択"
)
@app_commands.choices(direction=[
    app_commands.Choice(name="ON", value="on"),
    app_commands.Choice(name="OFF", value="off"),
])
async def AutoTranslateModeChange(interaction: discord.Interaction, direction: str):
    channel_id = str(interaction.channel_id)
    # 現在の設定をロード
    data = load_auto_translate_settings()
    # 設定を保存
    data[channel_id] = direction
    save_auto_translate_settings(data)
    trigger_github_action(data)
    mode_text = "ON" if direction == "on" else "OFF"
    await interaction.response.send_message(
        f"🌐 このチャンネルの自動翻訳モードを **{mode_text}** に切り替えました！"
    )
# ▼ JSON 読み書き関数 ▼
def load_auto_translate_settings():
    if not os.path.exists(AUTO_TRANSLATE_FILE):
        return {}
    with open(AUTO_TRANSLATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_auto_translate_settings(data):
    with open(AUTO_TRANSLATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def trigger_github_action(data):
    """GitHub Actionsに更新リクエストを送る"""
    url = f"https://api.github.com/repos/{REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    payload = {
        "event_type": "TranslateModeChange",
        "client_payload": {
            "data": json.dumps(data, ensure_ascii=False)
        }
    }
    r = requests.post(url, headers=headers, json=payload)
    print("GitHub Action Trigger:", r.status_code, r.text)


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    # ▼ 自動翻訳 ON/OFF の読み取り
    channel_id = str(message.channel.id)
    settings = load_auto_translate_settings()  # ← すでに定義済みの関数を使用
    is_auto = settings.get(channel_id) == "on"
    if is_auto:
        return
    text = message.content.strip()
    detected = detect(text)  # ja / en / etc...
    if detected.startswith("ja"):
         direction = "to_en"
    else:
         direction = "to_ja"
    try:
        if direction == "to_en":
            src, dest, flag = "ja", "en", "🇯🇵 → 🇺🇸"
        else:
            src, dest, flag = "en", "ja", "🇺🇸 → 🇯🇵"
            translated = GoogleTranslator(source=src, target=dest).translate(text)
    except Exception as e:
        return
    await message.reply(f"{translated}")
        
    if message.content == "こんにちは":
        await message.channel.send("こんにちは！")

                
TOKEN = os.getenv("DISCORD_TOKEN")
# Web サーバの立ち上げ
keep_alive()
client.run(TOKEN)
