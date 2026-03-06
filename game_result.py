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

RANK_MULTIPLIER = {
    "A": 1.0,
    "A-": 1.05,
    "B+": 1.1,
    "B": 1.15
}

SCORE_TABLE = [10, 8, 6, 4, 2]

def get_member_rank(team_data, user_id):
    for m in team_data["members"]:
        if m["user_id"] == user_id:
            return m.get("rank", "A")
    return "A"

# ==========================
# コマンド登録
# ==========================

def setup(tree: app_commands.CommandTree):

    @tree.command(name="result", description="イベント結果を表示します")
    async def result(interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ実行できます。", ephemeral=True)
            return

        await interaction.response.defer()

        time_data = load_json(TIME_RECORD_FILE)
        game_state = load_json(GAME_STATE_FILE)

        records = time_data.get("records", [])
        courses = game_state.get("courses", [])
        teams = game_state.get("teams", {})

        team_scores = {team: 0 for team in teams}

        embed = discord.Embed(
            title="🏁 Botchi Club Event Result",
            color=0xffd700
        )

        embed.description = f"参加チーム: {len(teams)}\nコース数: {len(courses)}"

        for course in courses:

            course_id = course["id"]
            course_name = course["name"]

            results = []

            for team_name, team_data in teams.items():

                rec = next(
                    (r for r in records if r["course_id"] == course_id and r["team"] == team_name),
                    None
                )

                if rec:
                    sec = time_to_seconds(rec["time"])
                    user_id = rec["user_id"]
                    time_str = rec["time"]
                else:
                    sec = float("inf")
                    user_id = None
                    time_str = "---"

                results.append({
                    "team": team_name,
                    "user": user_id,
                    "time": time_str,
                    "sec": sec
                })

            results.sort(key=lambda x: x["sec"])

            text = ""

            for i, r in enumerate(results):

                if r["user"] is None:
                    base_score = 0
                    multiplier = 1
                else:
                    base_score = SCORE_TABLE[i] if i < len(SCORE_TABLE) else 0

                    rank = get_member_rank(teams[r["team"]], r["user"])
                    multiplier = RANK_MULTIPLIER.get(rank, 1)

                final_score = base_score * multiplier
                team_scores[r["team"]] += final_score

                if i == 0:
                    medal = "🥇"
                elif i == 1:
                    medal = "🥈"
                elif i == 2:
                    medal = "🥉"
                else:
                    medal = f"{i+1}位"

                runner = f"<@{r['user']}>" if r["user"] else "未提出"

                text += (
                    f"{medal} {r['team']}\n"
                    f"👤 {runner}\n"
                    f"⏱ {r['time']}\n"
                    f"🏆 +{final_score:.2f}pt\n\n"
                )

            embed.add_field(
                name=f"🏎 {course_name}",
                value=text,
                inline=False
            )

        # 総合順位
        sorted_scores = sorted(team_scores.items(), key=lambda x: x[1], reverse=True)

        total_text = "━━━━━━━━━━━━━━\n🏆 総合順位\n━━━━━━━━━━━━━━\n\n"

        for i, (team, score) in enumerate(sorted_scores):

            if i == 0:
                medal = "🥇"
            elif i == 1:
                medal = "🥈"
            elif i == 2:
                medal = "🥉"
            else:
                medal = f"{i+1}位"

            total_text += f"{medal} {team}　{score:.2f}pt\n"

        embed.add_field(
            name="総合結果",
            value=total_text,
            inline=False
        )
        game_state["result_locked"] = True

        with open(GAME_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(game_state, f, ensure_ascii=False, indent=2)
            
        await interaction.followup.send(embed=embed)
