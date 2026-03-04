import discord
from discord import app_commands
import json
import os
import requests

MEMBER_FILE = "Members.json"
GAME_FILE = "GameParticipants.json"

REPO = "botchi-member-only/discord-bot"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

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

def trigger_game_update(data):
    url = f"https://api.github.com/repos/{REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    payload = {
        "event_type": "GameUpdate",
        "client_payload": {
            "data": json.dumps(data, ensure_ascii=False)
        }
    }
    requests.post(url, headers=headers, json=payload)


# ==========================
# コマンド登録
# ==========================

def setup(tree: app_commands.CommandTree):

    @tree.command(name="joingame", description="ゲームに参加します")
    async def join_game(interaction: discord.Interaction):

        user_id = str(interaction.user.id)

        members = load_json(MEMBER_FILE)

        if user_id not in members:
            await interaction.response.send_message(
                "❌ あなたはメンバー登録されていません。",
                ephemeral=True
            )
            return

        participants = load_json(GAME_FILE)

        if user_id in participants:
            await interaction.response.send_message(
                "⚠️ すでに参加しています。",
                ephemeral=True
            )
            return

        participants[user_id] = {
            "name": members[user_id]["name"],
            "level": members[user_id]["level"]
        }

        save_json(GAME_FILE, participants)
        trigger_game_update(participants)

        await interaction.response.send_message(
            f"✅ 参加しました！（レベル: {members[user_id]['level']}）"
        )


    @tree.command(name="leavegame", description="ゲーム参加を取り消します")
    async def leave_game(interaction: discord.Interaction):

        user_id = str(interaction.user.id)
        participants = load_json(GAME_FILE)

        if user_id not in participants:
            await interaction.response.send_message(
                "❌ 参加していません。",
                ephemeral=True
            )
            return

        del participants[user_id]

        save_json(GAME_FILE, participants)
        trigger_game_update(participants)

        await interaction.response.send_message("🗑️ 参加を取り消しました。")
    @tree.command(name="gamelist", description="現在の参加者一覧を表示します")
    async def game_list(interaction: discord.Interaction):

        participants = load_json(GAME_FILE)

        if not participants:
            await interaction.response.send_message("現在の参加者はいません。")
            return

        # レベル順に並び替え
        level_order = {"A": 0, "A-": 1, "B+": 2, "B": 3}

        sorted_participants = sorted(
            participants.values(),
            key=lambda x: level_order.get(x["level"], 99)
        )
        embed = discord.Embed(
            title="🎮 現在の参加者一覧",
            color=0x3498db
        )
        for p in sorted_participants:
            embed.add_field(
                name=p["name"],
                value=f"レベル: {p['level']}",
                inline=False
            )
        embed.set_footer(text=f"参加人数: {len(participants)}人")
        await interaction.response.send_message(embed=embed)
