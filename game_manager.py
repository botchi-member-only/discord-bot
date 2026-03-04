import discord
from discord import app_commands
import json
import os
import requests
import random
from datetime import datetime

MEMBER_FILE = "Members.json"
GAME_FILE = "GameParticipants.json"
COURSE_FILE = "Courses.json"
MACHINE_FILE = "MachineConditions.json"
THREAD_FILE = "GameThreads.json"

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

def trigger_thread_update(data):
    url = f"https://api.github.com/repos/{REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    payload = {
        "event_type": "ThreadUpdate",
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
    TEAM_NAMES = ["α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ"]

    RANK_VALUE = {
        "A": 4,
        "A-": 3,
        "B+": 2,
        "B": 1
    }

    @tree.command(name="gamestart", description="チームを生成してメンバーを振り分けます")
    @app_commands.describe(team_count="作成するチーム数")
    async def GameStart(interaction: discord.Interaction, team_count: int):

        await interaction.response.defer()

        # 参加者読み込み
        try:
            with open("GameParticipants.json", "r", encoding="utf-8") as f:
                participants = json.load(f)
        except:
            await interaction.followup.send("❌ 参加者データが読み込めません。")
            return

        if not participants:
            await interaction.followup.send("❌ 参加者がいません。")
            return

        if team_count <= 0:
            await interaction.followup.send("❌ チーム数は1以上にしてください。")
            return

        if team_count > len(participants):
            await interaction.followup.send("❌ チーム数が参加人数を超えています。")
            return

        # チーム初期化
        teams = []
        for i in range(team_count):
            teams.append({
                "name": f"{TEAM_NAMES[i]}チーム",
                "members": [],
                "total_power": 0
            })

        # 実力順ソート
        participants_list = [
            {"user_id": uid, **data}
            for uid, data in participants.items()
        ]
        # ★ まず全体をシャッフル（同レベル固定防止）
        random.shuffle(participants_list)
        # ★ その後ランク順ソート
        participants_list.sort(
            key=lambda x: RANK_VALUE.get(x.get("level"), 0),
            reverse=True
        )

        # 均等振り分け
        for p in participants_list:
            weakest_team = min(
                teams,
                key=lambda t: (t["total_power"], len(t["members"]))
            )

            weakest_team["members"].append({
            "user_id": p.get("user_id"),
            "display_name": p.get("name", "Unknown"),
            "rank": p.get("level", "?"),
            "courses": 1
            })
            weakest_team["total_power"] += RANK_VALUE.get(p.get("level"), 0)

        # コース再調整
        max_members = max(len(t["members"]) for t in teams)
        # ==========================
        # コース読み込み（ランダム抽選）
        # ==========================
        courses_data = load_json(COURSE_FILE)
        if not courses_data:
            await interaction.followup.send("❌ コースデータが存在しません。")
            return
        course_count = max_members

        if course_count > len(courses_data):
            await interaction.followup.send("❌ コース数が不足しています。")
            return
        # ★ 重複なしランダム抽選
        selected_courses = random.sample(courses_data, course_count)
        # ==========================
        # マシン条件読み込み
        # ==========================

        machine_data = load_json(MACHINE_FILE)

        if not machine_data:
            await interaction.followup.send("❌ マシン条件データが存在しません。")
            return
        course_count = max_members
        if course_count > len(courses_data):
            await interaction.followup.send("❌ コース数が不足しています。")
            return
        selected_courses = random.sample(courses_data, course_count)
        # ★ コースごとにマシン条件をランダム決定（重複OK）
        course_machine_pairs = []
        for course in selected_courses:
            machine = random.choice(machine_data)
            course_machine_pairs.append({
                "course": course,
                "machine": machine
            })

        for team in teams:
            diff = max_members - len(team["members"])
            if diff > 0:
                candidates = team["members"][:]
                random.shuffle(candidates)
                for i in range(min(diff, len(candidates))):
                    candidates[i]["courses"] = 2

        # embed作成
        embed = discord.Embed(
            title="🏁 チーム振り分け結果",
            color=0x00ffcc
        )

        for team in teams:
            text = ""
            for m in team["members"]:
                text += f"{m['display_name']} ({m['rank']}) - {m['courses']}コース\n"

            embed.add_field(
                name=team["name"],
                value=text if text else "メンバーなし",
                inline=False
            )

        await interaction.followup.send(embed=embed)
        # ==========================
        # コース発表Embed
        # ==========================
        course_embed = discord.Embed(
            title="🛣️ 今回の指定コース",
            description="各チームで走行担当を決めてください。",
            color=0xffcc00
        )
        course_text = ""
        for pair in course_machine_pairs:
            course_name = pair["course"]["name"]
            machine_label = pair["machine"]["label"]
            course_text += f"{course_name} | {machine_label}\n"
        course_embed.add_field(
            name="指定コース & マシン条件",
            value=course_text,
            inline=False
        )
        await interaction.followup.send(embed=course_embed)
        # ==========================
        # スレッド保存用データ
        # ==========================

        thread_save_data = {
            "active": True,
            "teams": {}
        }

        # ==========================
        # チーム戦略スレッド作成
        # ==========================

        for team in teams:

            thread = await interaction.channel.create_thread(
                name=f"🏎️ {team['name']} 戦略会議",
                type=discord.ChannelType.private_thread,
                invitable=False
            )

            # ★ 表示安定用
            await thread.send("🟢 スレッドを作成しました。")

            # メンバー招待
            for member in team["members"]:
                guild_member = interaction.guild.get_member(int(member["user_id"]))
                if guild_member:
                    try:
                        await thread.add_user(guild_member)
                    except:
                        pass

            # メンション文字列作成
            mentions = " ".join(
                f"<@{m['user_id']}>" for m in team["members"]
            )

            # 戦略開始メッセージ
            await thread.send(
                f"{mentions}\n\n"
                f"🏎️ **{team['name']} 戦略会議を開始します！**\n"
                "🛣️ 担当コースをここで決定してください。\n"
                "⏱️ タイム提出前に必ず確認を！"
            )
            # ★ スレッドID保存
            thread_save_data["teams"][team["name"]] = {
                "thread_id": str(thread.id)
            }
        # ==========================
        # JSON保存 & GitHub反映
        # ==========================
        save_json(THREAD_FILE, thread_save_data)
        trigger_thread_update(thread_save_data))
