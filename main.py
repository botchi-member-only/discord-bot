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

from member_manager import setup as setup_member
setup_member(tree)
from game_manager import setup as setup_game
setup_game(tree)

# 日本時間（JST）
JST = timezone(timedelta(hours=9))

ALLOWED_GUILD_IDS = {1389253121649414239,742727484750954577}  # ✅ Botが所属できるサーバーIDをここに記入（複数対応可）

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

@client.event
async def on_guild_join(guild):
    if guild.id not in ALLOWED_GUILD_IDS:
        print(f"❌ 許可されていないサーバー ({guild.name}) に参加したため退出します。")
        try:
            await guild.leave()
            channel_id = '1389456562166436051'
            channel = client.get_channel(channel_id)
            await channel.send(f"❌ 許可されていないサーバー ({guild.name}) に参加したため退出します。")
        except Exception as e:
            print(f"⚠️ サーバーから退出できませんでした: {e}")
    else:
        print(f"✅ 許可されたサーバー ({guild.name}) に参加しました。")

#スラッシュコマンド
@tree.command(name='membercount', description='サーバーの人数を表示します') 
async def member_count(message):
    # message インスタンスから guild インスタンスを取得
    guild = message.guild 
    # ユーザとBOTを区別しない場合
    member_count = guild.member_count
    await message.response.send_message(f'今の人数は{member_count}です')
@tree.command(name='help', description='BOTの使い方') 
async def help_command(message):
    embed = discord.Embed( # Embedを定義する
                          title="Botの使い方",# タイトル
                          color=0xffffff, # フレーム色指定(今回は白)
                          description="このbotの使い方を説明します。"
                          )
    embed.set_author(name=client.user, # Botのユーザー名
                     url="https://botchi-member-only.github.io/botchi-resource/botchi-logo.png",
                     icon_url=client.user.avatar_url # Botのアイコンを設定してみる
                     )
    embed.add_field(name="/help",value="今表示しているものです。", inline=False) # フィールドを追加。
    embed.add_field(name="/translate",value="英語と日本語を翻訳します。", inline=False)
    embed.add_field(name="/auto_translate_mode",value="自動翻訳を開始します。", inline=False)
    await message.response.send_message(embed=embed) # embedの送信には、embed={定義したembed名}

@tree.command(name="translate", description="メッセージを翻訳します")
@app_commands.describe(
    message_id="翻訳したいメッセージのID（省略可）",
    direction="翻訳方向を選択（to_en: 日本語→English, to_ja: English→日本語）",
    ephemeral="実行者だけに表示するかどうか（true/false、省略可）"
)
@app_commands.choices(direction=[
    app_commands.Choice(name="自動/Auto",value="auto"),
    app_commands.Choice(name="日本語 → English", value="to_en"),
    app_commands.Choice(name="English → 日本語", value="to_ja")
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
        result = f"{translated}"
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
    channel_id = str(interaction.channel.id)
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
    # Bot自身のメッセージは翻訳しない
    if message.author.bot:
        return

    # ▼ 自動翻訳 ON/OFF の読み取り
    channel_id = str(message.channel.id)
    settings = load_auto_translate_settings()
    is_auto = settings.get(channel_id) == "on"
    if is_auto:
        text = message.content.strip()
        if not text:
            return
        # 言語判定
        try:
            detected = detect(text)
        except:
            return
        # 翻訳方向を決定
        if detected.startswith("ja"):
            src, dest, flag = "ja", "en", "🇯🇵 → 🇺🇸"
        else:
            src, dest, flag = "en", "ja", "🇺🇸 → 🇯🇵"
        # 翻訳
        try:
            translated = GoogleTranslator(source=src, target=dest).translate(text)
        except:
            return
        # 返信形式で送信
        await message.reply(f"{translated}", mention_author=False)
    if message.content == "こんにちは":
        await message.channel.send("こんにちは！")

                
TOKEN = os.getenv("DISCORD_TOKEN")
# Web サーバの立ち上げ
keep_alive()
client.run(TOKEN)
