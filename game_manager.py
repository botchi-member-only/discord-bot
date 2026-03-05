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
SUBMIT_FILE = "SubmitTimes.json"
RESULT_CHANNEL_ID = 1478572921461936231

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

def trigger_submit_update(data):
    url = f"https://api.github.com/repos/{REPO}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    payload = {
        "event_type": "SubmitTimeUpdate",
        "client_payload": {
            "data": json.dumps(data, ensure_ascii=False)
        }
    }
    requests.post(url, headers=headers, json=payload)

async def course_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    # スレッド以外では候補を出さない
    if not isinstance(interaction.channel, discord.Thread):
        return []

    thread_data = load_json(THREAD_FILE)

    if not thread_data.get("active"):
        return []

    courses = thread_data.get("courses", [])

    # 入力中の文字列でフィルタ
    filtered = [
        c for c in courses
        if current.lower() in c["name"].lower()
    ]

    # Discordは最大25件
    return [
        app_commands.Choice(
            name=f"{c['name']} | {c['machine_label']}",
            value=c["name"]
        )
        for c in filtered[:25]
    ]
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator


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

        from datetime import datetime

        thread_save_data = {
            "active": True,
            "created_at": datetime.now().isoformat(),
            "courses": [],
            "teams": {}
        }
        # ==========================
        # コース情報保存
        # ==========================

        for pair in course_machine_pairs:

            thread_save_data["courses"].append({
                "id": pair["course"]["id"],
                "name": pair["course"]["name"],
                "machine_label": pair["machine"]["label"]
            })

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
                "⏱️ タイム提出前に必ず確認を！\n\n"
                "## このチャンネルの使い方\n"
                "だれがどのコースを走るか決めよう！\n"
                "-# 名前の横にコース数も書いてあるのでチェック\n"
                "走行タイムを``/submittime``コマンドで送ろう！\n"
                "タイムを修正するときは``/submittime``タイムを削除するときは``/withdrawtime``だ\n"
                "-# 走るコースを変えるときは必ず``/withdrawtime``してくれ\n"
                "``/myteamstatus``で自分のチームの状況を確認できるぞ"
            )
            # ★ スレッドID保存
            thread_save_data["teams"][team["name"]] = {
                "thread_id": str(thread.id)
            }
        # ==========================
        # JSON保存 & GitHub反映
        # ==========================
        save_json(THREAD_FILE, thread_save_data)
        trigger_thread_update(thread_save_data)
        
    @tree.command(name="submittime", description="タイムを提出します")
    @app_commands.describe(
        course="コース名を選択",
        time="タイムを入力（例: 1:32.456）"
    )
    @app_commands.autocomplete(course=course_autocomplete)
    async def submit_time(
        interaction: discord.Interaction,
        course: str,
        time: str
    ):
        thread_data = load_json(THREAD_FILE)
        valid_thread_ids = [
            v["thread_id"]
            for v in thread_data.get("teams", {}).values()
        ]

        if str(interaction.channel.id) not in valid_thread_ids:
            await interaction.response.send_message(
                "❌ このスレッドでは使用できません。",
                ephemeral=True
            )
            return
        # ① スレッドチェック
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ このコマンドは戦略会議スレッド内でのみ使用できます。",
                ephemeral=True
            )
            return

        if not interaction.channel.name.endswith("戦略会議"):
            await interaction.response.send_message(
                "❌ このスレッドでは使用できません。",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        user_id = str(interaction.user.id)
        user_name = interaction.user.display_name
        thread_id = str(interaction.channel.id)

        data = load_json(SUBMIT_FILE)

        if thread_id not in data:
            data[thread_id] = {}

        if course not in data[thread_id]:
            data[thread_id][course] = []

        # 同一ユーザーが同一コース再提出 → 上書き
        data[thread_id][course] = [
            x for x in data[thread_id][course]
            if x["user_id"] != user_id
        ]

        data[thread_id][course].append({
            "user_id": user_id,
            "name": user_name,
            "time": time
        })

        save_json(SUBMIT_FILE, data)
        trigger_submit_update(data)

        # 結果チャンネルへ送信
        result_channel = interaction.client.get_channel(RESULT_CHANNEL_ID)

        if result_channel:
            await result_channel.send(
                f"🏁 **タイム提出**\n"
                f"👤 {user_name}\n"
                f"🗺️ {course}\n"
                f"⏱️ {time}"
            )

        await interaction.followup.send(
            f"✅ **タイムを提出しました**\n\n"
            f"🗺️ コース: {course}\n"
            f"⏱️ タイム: {time}\n\n"
            f"🎥 走行動画を運営へ提出してください。",
            ephemeral=False
        )
    @tree.command(name="withdrawtime", description="提出したタイムを撤回します")
    @app_commands.describe(
        course="撤回するコースを選択"
    )
    @app_commands.autocomplete(course=course_autocomplete)
    async def withdraw_time(
        interaction: discord.Interaction,
        course: str
    ):

        # スレッドチェック
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ このコマンドは戦略会議スレッド内でのみ使用できます。",
                ephemeral=True
            )
            return

        thread_data = load_json(THREAD_FILE)
        valid_thread_ids = [
            v["thread_id"]
            for v in thread_data.get("teams", {}).values()
        ]

        if str(interaction.channel.id) not in valid_thread_ids:
            await interaction.response.send_message(
                "❌ このスレッドでは使用できません。",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        thread_id = str(interaction.channel.id)

        data = load_json(SUBMIT_FILE)

        if thread_id not in data or course not in data[thread_id]:
            await interaction.followup.send(
                "❌ このコースに提出されたタイムは見つかりません。",
                ephemeral=True
            )
            return

        original_length = len(data[thread_id][course])

        # 実行者のデータ削除
        data[thread_id][course] = [
            x for x in data[thread_id][course]
            if x["user_id"] != user_id
        ]

        if len(data[thread_id][course]) == original_length:
            await interaction.followup.send(
                "❌ あなたはこのコースにタイムを提出していません。",
                ephemeral=True
            )
            return

        # コースが空になったら削除
        if not data[thread_id][course]:
            del data[thread_id][course]

        save_json(SUBMIT_FILE, data)
        trigger_submit_update(data)

        await interaction.followup.send(
            f"🗑️ **タイムを撤回しました**\n\n"
            f"🗺️ コース: {course}",
            ephemeral=False
        )
        
    @tree.command(name="timestatus", description="【管理者専用】各チームのタイム提出状況を表示します")
    @app_commands.describe(
        ephemeral="自分だけに表示するか（true / false）"
    )
    async def time_status(interaction: discord.Interaction, ephemeral: bool):
        # 管理者チェック
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ このコマンドは管理者のみ使用できます。",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=ephemeral)

        thread_data = load_json(THREAD_FILE)
        submit_data = load_json(SUBMIT_FILE)

        if not thread_data.get("active"):
            await interaction.followup.send("❌ 現在アクティブな試合がありません。", ephemeral=True)
            return

        embed = discord.Embed(
            title="📊 チーム別 タイム提出状況",
            color=0x2ecc71
        )

        courses = thread_data.get("courses", [])

        for team_name, team_info in thread_data.get("teams", {}).items():
            thread_id = team_info["thread_id"]
            team_submit = submit_data.get(thread_id, {})

            text = ""

            for c in courses:
                course_name = c["name"]

                if course_name in team_submit and team_submit[course_name]:
                    for entry in team_submit[course_name]:
                        user_id = entry["user_id"]
                        text += f"🗺️ {course_name}\n"
                        text += f"　👤 <@{user_id}>\n"
                        text += f"　⏱️ {entry['time']}\n"
                else:
                    text += f"🗺️ {course_name}\n　❌ 未提出\n"

                text += "\n"

            embed.add_field(
                name=f"🏎️ {team_name}",
                value=text if text else "データなし",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        
    @tree.command(name="myteamstatus", description="【チーム専用】自分のチームのタイム提出状況を表示します")
    @app_commands.describe(
        ephemeral="自分だけに表示するか（true / false）"
    )
    async def my_time_status(interaction: discord.Interaction, ephemeral: bool):

        # スレッド内チェック
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ このコマンドは戦略会議スレッド内でのみ使用できます。",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=ephemeral)

        user_id = str(interaction.user.id)
        thread_id = str(interaction.channel.id)

        thread_data = load_json(THREAD_FILE)
        submit_data = load_json(SUBMIT_FILE)

        if not thread_data.get("active"):
            await interaction.followup.send("❌ 現在アクティブな試合がありません。", ephemeral=True)
            return

        # このスレッドがどのチームか特定
        team_name = None
        for t_name, t_info in thread_data.get("teams", {}).items():
            if t_info["thread_id"] == thread_id:
                team_name = t_name
                break

        if team_name is None:
            await interaction.followup.send(
                "❌ このスレッドはチームスレッドではありません。",
                ephemeral=True
            )
            return

        courses = thread_data.get("courses", [])
        team_submit = submit_data.get(thread_id, {})

        embed = discord.Embed(
            title=f"📊 {team_name} タイム提出状況",
            color=0x3498db
        )

        text = ""
        for c in courses:
            course_name = c["name"]

            if course_name in team_submit and team_submit[course_name]:
                for entry in team_submit[course_name]:
                    uid = entry["user_id"]
                    text += f"🗺️ {course_name}\n"
                    text += f"　👤 <@{uid}>\n"
                    text += f"　⏱️ {entry['time']}\n"
            else:
                text += f"🗺️ {course_name}\n　❌ 未提出\n"

            text += "\n"
        embed.add_field(
            name="提出状況",
            value=text if text else "データなし",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @tree.command(name="edittime", description="【管理者専用】指定ユーザーのタイムを修正します")
    @app_commands.describe(
        user="修正するユーザー",
        course="コースを選択",
        time="新しいタイム（例: 1:32.456）"
    )
    @app_commands.autocomplete(course=course_autocomplete)
    async def edit_time(
        interaction: discord.Interaction,
        user: discord.User,
        course: str,
        time: str
    ):

        # 管理者チェック
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ このコマンドは管理者のみ使用できます。",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        target_user_id = str(user.id)
        data = load_json(SUBMIT_FILE)

        found = False
        found_thread = None

        # 全スレッドを探索
        for thread_id, thread_courses in data.items():
            if course not in thread_courses:
                continue

            for entry in thread_courses[course]:
                if entry["user_id"] == target_user_id:
                    entry["time"] = time
                    found = True
                    found_thread = thread_id
                    break

            if found:
                break

        if not found:
            await interaction.followup.send(
                "❌ 指定されたユーザーの該当コースのタイムが見つかりません。",
                ephemeral=True
            )
            return

        save_json(SUBMIT_FILE, data)
        trigger_submit_update(data)

        # 結果チャンネルへ送信
        result_channel = interaction.client.get_channel(RESULT_CHANNEL_ID)

        if result_channel:
            await result_channel.send(
                f"🏁 **タイム提出**\n"
                f"👤 {user_name}\n"
                f"🗺️ {course}\n"
                f"⏱️ {time}"
            )

        await interaction.followup.send(
            f"✏️ **タイムを修正しました**\n\n"
            f"👤 ユーザー: <@{target_user_id}>\n"
            f"🗺️ コース: {course}\n"
            f"⏱️ 新タイム: {time}",
            ephemeral=False
        )
