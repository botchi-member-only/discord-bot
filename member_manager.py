import discord
from discord import app_commands
import json
import os
import requests

MEMBER_FILE = "Members.json"
REPO = "botchi-member-only/discord-bot"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


# ==========================
# データ読み書き
# ==========================

def load_member_data():
    if not os.path.exists(MEMBER_FILE):
        return {}
    with open(MEMBER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_member_data(data):
    with open(MEMBER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def trigger_member_update(data):
    url = f"https://api.github.com/repos/{REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    payload = {
        "event_type": "MemberUpdate",
        "client_payload": {
            "data": json.dumps(data, ensure_ascii=False)
        }
    }
    requests.post(url, headers=headers, json=payload)


# ==========================
# コマンド登録関数
# ==========================

def setup(tree: app_commands.CommandTree):

    def is_admin(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator


    @tree.command(name="addmember", description="メンバー登録（管理者専用）")
    @app_commands.describe(user="登録するユーザー", level="実力レベル")
    @app_commands.choices(level=[
        app_commands.Choice(name="A", value="A"),
        app_commands.Choice(name="A-", value="A-"),
        app_commands.Choice(name="B+", value="B+"),
        app_commands.Choice(name="B", value="B"),
    ])
    async def add_member(interaction: discord.Interaction, user: discord.Member, level: str):

        if not is_admin(interaction):
            await interaction.response.send_message("❌ 管理者のみ使用可能です。", ephemeral=True)
            return

        data = load_member_data()
        data[str(user.id)] = {
            "name": user.display_name,
            "level": level
        }

        save_member_data(data)
        trigger_member_update(data)

        await interaction.response.send_message(
            f"✅ {user.display_name} を レベル {level} で登録しました。"
        )


    @tree.command(name="removemember", description="メンバー削除（管理者専用）")
    async def remove_member(interaction: discord.Interaction, user: discord.Member):

        if not is_admin(interaction):
            await interaction.response.send_message("❌ 管理者のみ使用可能です。", ephemeral=True)
            return

        data = load_member_data()

        if str(user.id) not in data:
            await interaction.response.send_message("❌ 登録されていません。", ephemeral=True)
            return

        del data[str(user.id)]

        save_member_data(data)
        trigger_member_update(data)

        await interaction.response.send_message(
            f"🗑️ {user.display_name} を削除しました。"
        )


    @tree.command(name="memberlist", description="登録メンバー一覧")
    async def member_list(interaction: discord.Interaction):

        data = load_member_data()

        if not data:
            await interaction.response.send_message("登録メンバーはいません。")
            return

        embed = discord.Embed(title="📋 メンバー一覧", color=0x00ffcc)

        for info in data.values():
            embed.add_field(
                name=info["name"],
                value=f"レベル: {info['level']}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)
