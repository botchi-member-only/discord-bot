import discord
from discord import app_commands
import json
import os
import requests
import random
from datetime import datetime

TIME_RECORD_FILE = "TimeRecords.json"
GAME_STATE_FILE = "GameState.json"

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def time_to_seconds(t):
    # "1:23.456" → 秒
    m, s = t.split(":")
    return int(m) * 60 + float(s)


# ==========================
# コマンド登録
# ==========================

def setup(tree: app_commands.CommandTree):

    @tree.command(name="result", description="イベント結果を表示します")
async def result(interaction: discord.Interaction):

    # 管理者チェック
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 管理者のみ実行できます。", ephemeral=True)
        return

    await interaction.response.defer()

    time_data = load_json(TIME_RECORD_FILE)
    game_state = load_json(GAME_STATE_FILE)

    records = time_data.get("records", [])
    courses = game_state.get("courses", [])
    teams = game_state.get("teams", {})

    score_table = [10, 8, 6, 4, 2]
    team_scores = {team: 0 for team in teams}

    embed = discord.Embed(
        title="🏁 イベント結果",
        color=0xffd700
    )

    for course in courses:

        course_id = course["id"]
        course_name = course["name"]

        course_results = []

        # 各チームのタイム取得
        for team_name, team_data in teams.items():

            team_records = [
                r for r in records
                if r["course_id"] == course_id and r["team"] == team_name
            ]

            if team_records:
                r = team_records[0]
                time_str = r["time"]
                sec = time_to_seconds(time_str)
                user_id = r["user_id"]
            else:
                time_str = "未提出"
                sec = float("inf")
                user_id = None

            course_results.append({
                "team": team_name,
                "user_id": user_id,
                "time": time_str,
                "sec": sec
            })

        # タイム順ソート
        course_results.sort(key=lambda x: x["sec"])

        text = ""

        for i, r in enumerate(course_results):

            if r["time"] == "未提出":
                point = 0
            else:
                point = score_table[i] if i < len(score_table) else 0

            team_scores[r["team"]] += point

            runner = f"<@{r['user_id']}>" if r["user_id"] else "未提出"

            text += (
                f"{i+1}位 | {r['team']}\n"
                f"走者: {runner}\n"
                f"タイム: {r['time']}\n"
                f"獲得ポイント: {point}\n\n"
            )

        embed.add_field(
            name=f"🏎 {course_name}",
            value=text,
            inline=False
        )

    # 合計スコア
    score_text = ""

    sorted_scores = sorted(
        team_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    for rank, (team, score) in enumerate(sorted_scores, start=1):
        score_text += f"{rank}位 | {team} : {score}点\n"

    embed.add_field(
        name="🏆 チーム合計スコア",
        value=score_text,
        inline=False
    )

    await interaction.followup.send(embed=embed)
