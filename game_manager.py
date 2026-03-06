import discord
from discord import app_commands
import json
import os
import re
import requests
from datetime import datetime

GAMESTATE_FILE = "GameState.json"
TIMERECORD_FILE = "TimeRecords.json"

REPO = "botchi-member-only/discord-bot"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

RESULT_CHANNEL_ID = 1478572921461936231  # 送信先チャンネル

# ==========================
# 共通関数
# ==========================

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def trigger_time_record_update(data):
    url = f"https://api.github.com/repos/{REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    payload = {
        "event_type": "TimeRecordUpdate",
        "client_payload": {
            "data": json.dumps(data, ensure_ascii=False)
        }
    }
    requests.post(url, headers=headers, json=payload)

# ==========================
# コース choice 動的生成
# ==========================

async def get_course_choices(interaction: discord.Interaction, current: str):

    state = load_json(GAMESTATE_FILE)
    courses = state.get("courses", [])

    choices = []

    for c in courses:
        name = f"{c['name']} | {c['machine_label']}"

        if current.lower() in name.lower():
            choices.append(
                app_commands.Choice(
                    name=name,
                    value=str(c["id"])
                )
            )

    return choices[:25]

# ==========================
# setup
# ==========================

def setup(tree: app_commands.CommandTree):

    @tree.command(name="submittime", description="走行タイムを送信します")
    @app_commands.describe(
        course="走行したコース",
        time="タイム (例: 1:23.456)"
    )
    async def submit_time(
        interaction: discord.Interaction,
        course: str,
        time: str
    ):
        # 実行者のみ表示
        await interaction.response.defer(ephemeral=True)

        # フォーマットチェック
        if not re.match(r"^\d+:\d{2}\.\d{3}$", time):
            await interaction.followup.send(
                "❌ タイム形式が正しくありません。例: `1:23.456`",
                ephemeral=True
            )
            return

        state = load_json(GAMESTATE_FILE)
        if not state.get("active"):
            await interaction.followup.send("❌ ゲームは開始されていません。", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        team_name = None

        # チーム検索
        for tname, team in state["teams"].items():
            for m in team["members"]:
                if m["user_id"] == user_id:
                    team_name = tname
                    break

        if team_name is None:
            await interaction.followup.send("❌ あなたは今回のゲームに参加していません。", ephemeral=True)
            return

        # コース検索
        selected_course = None
        for c in state["courses"]:
            if str(c["id"]) == course:
                selected_course = c
                break

        if not selected_course:
            await interaction.followup.send("❌ 無効なコースです。", ephemeral=True)
            return

        # 保存データ読み込み
        records = load_json(TIMERECORD_FILE)
        if "records" not in records:
            records["records"] = []

        for r in records["records"]:
            if (
                r["team"] == team_name and
                r["course_id"] == selected_course["id"] and
                r["user_id"] != user_id
            ):
                await interaction.followup.send(
                    "❌ 同じチームの他メンバーが既にこのコースを提出しています。",
                    ephemeral=True
                )
                return

        # ==========================
        # 自分の同一コース記録があれば削除（上書き処理）
        # ==========================
        records["records"] = [
            r for r in records["records"]
            if not (
                r["team"] == team_name and
                r["course_id"] == selected_course["id"] and
                r["user_id"] == user_id
            )
        ]

        record = {
            "team": team_name,
            "user_id": user_id,
            "user_name": interaction.user.display_name,
            "course_id": selected_course["id"],
            "course_name": selected_course["name"],
            "time": time,
            "submitted_at": datetime.now().isoformat()
        }

        records["records"].append(record)

        save_json(TIMERECORD_FILE, records)
        trigger_time_record_update(records)

        # 結果チャンネルへ送信
        channel = interaction.client.get_channel(RESULT_CHANNEL_ID)
        if channel:
            await channel.send(
                f"⏱️ **タイム提出**\n"
                f"チーム: {team_name}\n"
                f"ユーザー: {interaction.user.display_name}\n"
                f"コース: {selected_course['name']}\n"
                f"タイム: `{time}`"
            )

        await interaction.followup.send(
            f"✅ タイムを記録しました。\n"
            f"{selected_course['name']} : `{time}`",
            ephemeral=True
        )

    @tree.command(name="withdrawtime", description="提出したタイムを撤回します")
    @app_commands.describe(course="コース")
    async def withdraw_time(interaction: discord.Interaction, course: str):

        user_id = str(interaction.user.id)
        course_id = int(course)

        data = load_json(TIMERECORD_FILE)
        records = data.get("records", [])

        new_records = []
        removed = None

        for r in records:
            if r["user_id"] == user_id and r["course_id"] == course_id:
                removed = r
                continue
            new_records.append(r)

        if removed is None:
            await interaction.response.send_message(
                "❌ このコースの提出タイムは見つかりません。",
                ephemeral=True
            )
            return

        data["records"] = new_records

        save_json(TIMERECORD_FILE, data)
        trigger_time_record_update(data)

        # 通知チャンネル
        channel = interaction.client.get_channel(RESULT_CHANNEL_ID)

        if channel:
            await channel.send(
                f"🗑️ **タイム撤回**\n"
                f"チーム: {removed['team']}\n"
                f"プレイヤー: {interaction.user.mention}\n"
                f"コース: {removed['course_name']}"
            )

        await interaction.response.send_message(
            f"🗑️ **タイムを撤回しました**\n"
            f"{removed['course_name']}",
            ephemeral=True
        )

    # 動的 choices 登録
    @submit_time.autocomplete("course")
    @withdraw_time.autocomplete("course")
    async def course_autocomplete(interaction: discord.Interaction, current: str):
        return await get_course_choices(interaction, current)
