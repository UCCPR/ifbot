"""
排行榜系统
"""
import json, os, random, re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from battle_system import format_battle_result, format_boss_result
from json_store import atomic_write_json, read_json, synchronized
from team_system import (
    get_defense_team, get_defense_team_info,
    build_vs_team_image, build_team_image,
    build_3star_cards_image, set_team_card, auto_save_preset,
    clear_team_card, clear_all_team, load_preset, load_presets,
    save_presets, list_presets_info, get_user_3star_cards,
    get_defense_slot, set_defense_slot, auto_build_team,
)

BASE_DIR = Path(__file__).parent
INFO_DIR = BASE_DIR / "info"
BACKUP_DIR = INFO_DIR / "backup"
BACKUP_DIR.mkdir(exist_ok=True)


def _atomic_json_save(file_path, data):
    """兼容旧调用点，实际写入由统一存储模块负责。"""
    atomic_write_json(file_path, data)

def _qq():
    """获取qq_bot_ws模块引用（优先__main__，避免模块双重加载）"""
    import sys
    if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'BOX_SESSIONS'):
        return sys.modules['__main__']
    import qq_bot_ws
    return qq_bot_ws

# ========== 排行榜系统 ==========
RANKING_FILE = INFO_DIR / "ranking.json"
RANKING_REWARDS_FILE = INFO_DIR / "ranking_rewards.json"
# 排行榜每日结算奖励: 第1名45000呱太, 第2名35000呱太, 第3名25000呱太
RANKING_REWARDS = {1: 45000, 2: 35000, 3: 25000}

@synchronized("ranking", lambda *args, **kwargs: "global")
def init_ranking():
    """初始化排行榜（如果文件不存在）"""
    if not RANKING_FILE.exists():
        _qq().log_info("排行榜文件不存在，开始初始化...")
        # 初始排行榜：10个AI队伍
        ranking = []
        for i in range(10):
            ai_team = _qq().generate_ai_team(difficulty=i + 1 if i < 5 else 5)  # 排名越高AI越强
            # 防御：如果 AI 队伍生成为空（角色数据未就绪），重试一次
            if not ai_team.get("battle_cards") and not ai_team.get("assist_cards"):
                _qq().log_error(f"AI队伍{i+1} 生成为空，重试...")
                ai_team = _qq().generate_ai_team(difficulty=i + 1 if i < 5 else 5)
            # 仍然为空则跳过这个位置
            if not ai_team.get("battle_cards") and not ai_team.get("assist_cards"):
                _qq().log_error(f"AI队伍{i+1} 仍然为空，使用空队伍占位")

            # 设置一个不满编的队伍（前几个位置为空）
            empty_positions = i // 3  # 越靠前的AI队伍越完整
            for pos in range(empty_positions):
                if pos < len(ai_team["battle_cards"]):
                    ai_team["battle_cards"][pos] = None
                if pos < len(ai_team["assist_cards"]):
                    ai_team["assist_cards"][pos] = None

            ranking.append({
                "rank": i + 1,
                "is_ai": True,
                "user_id": f"AI_{i + 1}",
                "nickname": f"AI队伍{i + 1}",
                "team": ai_team,
                "wins": 0,
                "losses": 0
            })

        _atomic_json_save(RANKING_FILE, ranking)
        _qq().log_info(f"排行榜初始化完成: {len(ranking)} 个AI队伍")

def load_ranking():
    """加载排行榜数据"""
    init_ranking()
    return read_json(RANKING_FILE, list)

def save_ranking(ranking):
    """保存排行榜数据（写入前自动备份到 backup/ 目录）"""
    # 写前备份：保留最近 7 天的备份
    if RANKING_FILE.exists():
        try:
            backup_dir = BACKUP_DIR / "rankings"
            backup_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.now().strftime("%Y-%m-%d")
            backup_path = backup_dir / f"ranking_{today}.json"
            if not backup_path.exists():
                import shutil
                shutil.copy2(RANKING_FILE, backup_path)
                # 清理 7 天前的旧备份
                cutoff = datetime.now().timestamp() - 7 * 86400
                for old in backup_dir.glob("ranking_*.json"):
                    if old.stat().st_mtime < cutoff:
                        old.unlink()
        except Exception as e:
            _qq().log_error(f"排行榜备份失败: {e}")
    _atomic_json_save(RANKING_FILE, ranking)

def load_ranking_rewards() -> dict:
    """加载排行榜奖励记录"""
    return read_json(
        RANKING_REWARDS_FILE,
        lambda: {"last_settlement_date": "", "players": {}},
    )

def save_ranking_rewards(data: dict):
    """保存排行榜奖励记录"""
    _atomic_json_save(RANKING_REWARDS_FILE, data)

def get_player_ranking(user_id: str):
    """获取玩家的排名（如果不在排行榜中返回11）"""
    ranking = load_ranking()
    for entry in ranking:
        if not entry["is_ai"] and entry["user_id"] == user_id:
            return entry["rank"]
    return 11

def get_player_entry(user_id: str):
    """获取玩家的排行榜entry（如果不在排行榜中返回None）"""
    ranking = load_ranking()
    for entry in ranking:
        if not entry["is_ai"] and entry["user_id"] == user_id:
            return entry
    return None

@synchronized("ranking", lambda *args, **kwargs: "global")
def settle_ranking_rewards() -> dict | None:
    """每日12:00结算排行榜前三名奖励（每天最多一次）"""
    try:
        rewards_data = load_ranking_rewards()
        if not isinstance(rewards_data, dict):
            _qq().log_error(f"排行榜结算: rewards_data 类型异常 {type(rewards_data)}, 重置")
            rewards_data = {"last_settlement_date": "", "players": {}}

        today = datetime.now().strftime("%Y-%m-%d")

        # 今天已结算 → 跳过
        if rewards_data.get("last_settlement_date") == today:
            return None

        # 还没到12:00 → 跳过
        now = datetime.now()
        if now.hour < 12:
            return None

        # 读取排行榜
        ranking = load_ranking()
        if not ranking or not isinstance(ranking, list):
            return None

        # 结算前三名中的真人玩家
        settlement = {"date": today, "rewards": []}
        players = rewards_data.setdefault("players", {})
        if not isinstance(players, dict):
            players = {}
            rewards_data["players"] = players

        for entry in ranking[:3]:
            if not isinstance(entry, dict):
                continue
            rank = entry.get("rank")
            if not isinstance(rank, int) or rank not in RANKING_REWARDS:
                continue
            if entry.get("is_ai", False):
                continue  # AI 不发奖

            user_id = str(entry.get("user_id", ""))
            if not user_id:
                continue
            amount = RANKING_REWARDS[rank]
            _qq().add_gacha(user_id, amount)

            # 更新获奖次数
            player_stats = players.setdefault(user_id, {"first": 0, "second": 0, "third": 0})
            if not isinstance(player_stats, dict):
                player_stats = {"first": 0, "second": 0, "third": 0}
                players[user_id] = player_stats
            rank_key = {1: "first", 2: "second", 3: "third"}[rank]
            player_stats[rank_key] = player_stats.get(rank_key, 0) + 1

            settlement["rewards"].append({
                "rank": rank,
                "user_id": user_id,
                "nickname": _qq().get_nickname(user_id),
                "amount": amount
            })

        # 无论有没有真人获奖，都标记今天已结算
        rewards_data["last_settlement_date"] = today
        save_ranking_rewards(rewards_data)

        if settlement["rewards"]:
            _qq().log_info(f"排行榜结算完成: {today}, 获奖 {len(settlement['rewards'])} 人")
        return settlement

    except Exception as e:
        import traceback
        _qq().log_error(f"排行榜结算异常: {e}\n{traceback.format_exc()}")
        return None

@synchronized("ranking", lambda *args, **kwargs: "global")
def add_player_to_ranking(user_id: str, nickname: str, team: dict, rank: int):
    """将玩家添加到排行榜（替换该位置的AI）"""
    ranking = load_ranking()

    # 检查是否已存在
    for entry in ranking:
        if not entry["is_ai"] and entry["user_id"] == user_id:
            return entry

    # 移除该排名的AI条目，为新玩家腾位置
    ranking = [e for e in ranking if not (e["rank"] == rank and e["is_ai"])]

    # 添加新玩家
    new_entry = {
        "rank": rank,
        "is_ai": False,
        "user_id": user_id,
        "nickname": nickname,
        "team": team,
        "wins": 0,
        "losses": 0
    }
    ranking.append(new_entry)

    # 重新排序
    ranking.sort(key=lambda x: x["rank"])
    for i, entry in enumerate(ranking[:10], 1):
        entry["rank"] = i

    # 确保没有超过10条
    for entry in ranking[10:]:
        if not entry["is_ai"]:
            entry["rank"] = 11

    save_ranking(ranking)
    return new_entry

@synchronized("ranking", lambda *args, **kwargs: "global")
def update_ranking_after_battle(winner_id: str, loser_id: str, is_winner_ai: bool, is_loser_ai: bool, winner_team: dict = None, winner_nickname: str = None):
    """战斗结束后更新排行榜"""
    ranking = load_ranking()
    
    # 找到获胜者和失败者
    winner_entry = None
    loser_entry = None
    
    for entry in ranking:
        if entry["is_ai"] and is_winner_ai and entry["user_id"] == winner_id:
            winner_entry = entry
        elif not entry["is_ai"] and not is_winner_ai and entry["user_id"] == winner_id:
            winner_entry = entry
        
        if entry["is_ai"] and is_loser_ai and entry["user_id"] == loser_id:
            loser_entry = entry
        elif not entry["is_ai"] and not is_loser_ai and entry["user_id"] == loser_id:
            loser_entry = entry
    
    # 如果玩家首次进入排行榜（winner_entry为None）
    if not is_winner_ai and winner_entry is None and loser_entry is not None:
        # 添加玩家到排行榜（替换该位置AI）
        add_player_to_ranking(winner_id, winner_nickname or _qq().get_nickname(winner_id), winner_team, loser_entry["rank"])
        ranking = load_ranking()
        # 重新找到winner_entry（reload后的新对象）
        for entry in ranking:
            if not entry["is_ai"] and entry["user_id"] == winner_id:
                winner_entry = entry
                break
    
    if winner_entry and loser_entry:
        # 增加胜负记录
        winner_entry["wins"] += 1
        loser_entry["losses"] += 1

        # 更新人类玩家的存储队伍为当前队伍
        if not is_winner_ai and winner_team:
            winner_entry["team"] = winner_team
        if not is_loser_ai:
            loser_team = _qq().load_team_data(loser_id)
            if loser_team and loser_team.get("battle_cards"):
                loser_entry["team"] = loser_team
        
        # 如果玩家击败了AI或排名更高的玩家，交换位置
        if winner_entry["rank"] > loser_entry["rank"]:
            # 交换排名
            winner_entry["rank"], loser_entry["rank"] = loser_entry["rank"], winner_entry["rank"]
            
            # 重新排序
            ranking.sort(key=lambda x: x["rank"])
            
            # 调整排名序号
            for i, entry in enumerate(ranking[:10], 1):
                entry["rank"] = i
            
            # 将超出前10的设为11
            for entry in ranking[10:]:
                if not entry["is_ai"]:
                    entry["rank"] = 11
    
    save_ranking(ranking)

def _get_ranking_text(user_id: str) -> str:
    """获取排行榜文本（可嵌入其他消息）"""
    ranking = load_ranking()
    lines = ["🏆 排行榜 TOP 10 🏆"]
    for i, entry in enumerate(ranking[:10], 1):
        if entry["is_ai"]:
            lines.append(f"第{i}名: 🤖 {entry['nickname']} (AI)")
        else:
            # 玩家昵称实时从 nicknames.json 读取，保证改名后同步
            nick = _qq().get_nickname(entry['user_id'])
            lines.append(f"第{i}名: 👤 {nick} (玩家)")
    player_rank = get_player_ranking(user_id)
    if player_rank > 10:
        lines.append(f"\n你的排名: 第{player_rank}名 (未进入前10)")
        lines.append(f"可挑战排名: 第8-10名")
    else:
        lines.append(f"\n你的排名: 第{player_rank}名")
        min_challenge = max(1, player_rank - 3)
        if min_challenge < player_rank:
            lines.append(f"可挑战排名: 第{min_challenge}-{player_rank-1}名")
        else:
            lines.append("你已是第1名，无法被挑战")
    return "\n".join(lines)

def show_ranking(user_id: str, group_id):
    """显示排行榜（独立消息）"""
    reply = _get_ranking_text(user_id)
    if group_id and user_id:
        reply = f"<@{user_id}>\n{reply}"
    _qq().send_message(reply, user_id, group_id)
    return _qq().jsonify({"status": "success", "message": "显示排行榜"})

@synchronized("ranking", lambda *args, **kwargs: "global")
def challenge_player(user_id: str, group_id, target_openid: str):
    """@玩家 挑战：根据 openid 查找排名并发起挑战"""
    ranking = load_ranking()
    target_rank = None
    target_nick = ""
    for entry in ranking:
        if entry.get("user_id") == target_openid:
            target_rank = entry["rank"]
            target_nick = _qq().get_nickname(target_openid)
            break
    if target_rank is None:
        reply = f"该玩家不在排行榜中！（需先打过一次战斗才能上榜）"
        if group_id and user_id:
            reply = f"<@{user_id}> {reply}"
        _qq().send_message(reply, user_id, group_id)
        return
    _qq().log_info(f"@挑战: {user_id} -> {target_openid} (排名{target_rank} {target_nick})")
    return challenge_rank(user_id, group_id, target_rank)

@synchronized("ranking", lambda *args, **kwargs: "global")
def challenge_rank(user_id: str, group_id, target_rank: int):
    """挑战指定排名的玩家/AI"""
    try:
        _qq().log_info(f"开始挑战: user_id={user_id}, target_rank={target_rank}")
        
        ranking = load_ranking()
        _qq().log_info(f"排行榜加载完成，共{len(ranking)}个条目")
        
        if target_rank is None:
            _qq().send_message("请指定挑战排名！格式: 挑战 1~10", user_id, group_id)
            return _qq().jsonify({"status": "error"})
        if target_rank < 1 or target_rank > 10:
            reply = "无效的排名！请挑战1-10名之间的对手"
            if group_id and user_id:
                reply = f"<@{user_id}> {reply}"
            _qq().send_message(reply, user_id, group_id)
            return _qq().jsonify({"status": "error", "message": "无效的排名"})
        
        player_rank = get_player_ranking(user_id)
        _qq().log_info(f"玩家排名: {player_rank}")
        
        # 检查是否可以挑战
        if player_rank <= 10:
            min_challenge_rank = max(1, player_rank - 3)
            if target_rank < min_challenge_rank or target_rank >= player_rank:
                reply = f"只能挑战排名比你高且不超过3位的对手！\n你的排名: 第{player_rank}名\n可挑战排名: 第{min_challenge_rank}-{player_rank-1}名"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": "无法挑战该排名"})
        else:
            if target_rank < 8:
                reply = f"你还未进入排行榜，只能挑战第8-10名！\n你的排名: 第{player_rank}名"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": "无法挑战该排名"})
        
        target_entry = None
        for entry in ranking:
            if entry["rank"] == target_rank:
                target_entry = entry
                break
        
        if not target_entry:
            reply = "未找到该排名的对手！"
            if group_id and user_id:
                reply = f"<@{user_id}> {reply}"
            _qq().send_message(reply, user_id, group_id)
            return _qq().jsonify({"status": "error", "message": "未找到对手"})
        
        _qq().log_info(f"目标对手: {target_entry['nickname']}, is_ai={target_entry['is_ai']}")
        
        # 获取玩家队伍 + 活跃预设
        player_team_data = _qq().get_user_team(user_id)
        active_slot = 0
        try:
            pdata = load_presets(user_id)
            active_slot = pdata.get("active_slot", 0)
        except Exception:
            pass
        _qq().log_info(f"玩家队伍数据类型: {type(player_team_data)}")
        
        if player_team_data:
            _qq().log_info(f"玩家队伍 battle_cards: {player_team_data.get('battle_cards')}")
        
        if not player_team_data or not player_team_data.get("battle_cards"):
            reply = "请先配置队伍！使用【队伍】命令"
            if group_id and user_id:
                reply = f"<@{user_id}> {reply}"
            _qq().send_message(reply, user_id, group_id)
            return _qq().jsonify({"status": "error", "message": "未配置队伍"})
        
        # 获取敌方队伍（人类玩家用防守队，AI用存储队伍）
        if target_entry["is_ai"]:
            enemy_team = target_entry["team"]
        else:
            # 对手使用防守队迎战
            enemy_team = get_defense_team(target_entry["user_id"])
            enemy_battle_cards = enemy_team.get("battle_cards", [])
            if not any(enemy_battle_cards):
                reply = "对手还没有配置防守队，暂时无法挑战！"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": "对手防守队为空"})
        _qq().log_info(f"敌方队伍类型: {type(enemy_team)}")
        if enemy_team:
            _qq().log_info(f"敌方队伍 battle_cards: {enemy_team.get('battle_cards')}")
        
        # 开始战斗
        enemy_name = target_entry["nickname"] if target_entry["is_ai"] else _qq().get_nickname(target_entry["user_id"])
        
        # 生成双方VS配队图
        vs_img = None
        try:
            characters = _qq().get_characters_dict()
            vs_img = build_vs_team_image(player_team_data, enemy_team, characters)
            if not vs_img:
                # 如果无法生成图片，显示文字信息
                enemy_battle_cards = enemy_team.get("battle_cards", [])
                enemy_assist_cards = enemy_team.get("assist_cards", [])
                characters = _qq().get_characters()
                char_dict = {c["card_id"]: c for c in characters}
                
                enemy_team_display = f"👥 {enemy_name} 的队伍:\n"
                for i in range(6):
                    battle_name = "空"
                    assist_name = "空"
                    
                    if i < len(enemy_battle_cards) and enemy_battle_cards[i]:
                        card_info = char_dict.get(str(enemy_battle_cards[i]))
                        if card_info:
                            battle_name = card_info.get("name", str(enemy_battle_cards[i]))
                        else:
                            battle_name = str(enemy_battle_cards[i])
                    
                    if i < len(enemy_assist_cards) and enemy_assist_cards[i]:
                        card_info = char_dict.get(str(enemy_assist_cards[i]))
                        if card_info:
                            assist_name = card_info.get("name", str(enemy_assist_cards[i]))
                        else:
                            assist_name = str(enemy_assist_cards[i])
                    
                    enemy_team_display += f" 位置{i+1}: {battle_name} + {assist_name}\n"
                
                _qq().send_message(enemy_team_display.strip(), user_id, group_id)
        except Exception as e:
            _qq().log_error(f"生成敌方配队图片失败: {e}")

        # 执行战斗（挑战上限15回合）
        _qq().log_info("开始执行战斗...")
        result = _qq().BATTLE_INSTANCE.start_battle(player_team_data, enemy_team, challenger="player",
                                              extra_characters={**_qq().get_characters_dict(), **_qq().BATTLE_CHARACTERS},
                                              max_rounds=15)
        _qq().log_info(f"战斗结束: winner={result.get('winner')}, rounds={result.get('rounds')}")

        # 保存战斗日志（滚动保留最近3次）
        _qq().save_rolling_battle_log(user_id, result)

        winner = result["winner"]
        player_nickname = _qq().get_nickname(str(user_id))

        if winner == "player":
            update_ranking_after_battle(user_id, target_entry["user_id"], False, target_entry["is_ai"], player_team_data, player_nickname)
        else:
            update_ranking_after_battle(target_entry["user_id"], user_id, target_entry["is_ai"], False)

        rounds = result["rounds"]
        if winner == "player":
            new_rank = get_player_ranking(user_id)
            result_text = f"🏆 胜利！你击败了 {enemy_name}！\n🎉 你的新排名: 第{new_rank}名"
        else:
            result_text = f"💀 失败... 你被 {enemy_name} 击败了..."

        player_alive = sum(1 for u in result["player_units"] if u["alive"] and not u["is_assist"])
        enemy_alive = sum(1 for u in result["enemy_units"] if u["alive"] and not u["is_assist"])
        result_text += f"\n📊 我方存活 {player_alive}/6, 敌方存活 {enemy_alive}/6"
        if active_slot > 0:
            result_text += f"\n📋 使用预设: 槽{active_slot}"
        result_text += "\n💡 输入「战斗日志」查看详细记录，输入「战斗GIF」生成动画"
        result_text += "\n\n" + _get_ranking_text(user_id)

        # VS图 + 结果文字合并为一条消息
        at_message = _qq()._at_user(user_id, group_id)
        full_text = f"⚔️ VS {enemy_name}（排名第{target_rank}）\n{result_text}"
        if vs_img and os.path.exists(vs_img):
            _qq().send_message_with_image(group_id or user_id, at_message + full_text, vs_img)
        else:
            _qq().send_message(at_message + full_text, user_id, group_id)
        
    except Exception as e:
        import traceback
        _qq().log_error(f"挑战失败: {e}\n{traceback.format_exc()}")
        reply = f"挑战失败: {str(e)}"
        if group_id and user_id:
            reply = f"<@{user_id}> {reply}"
        _qq().send_message(reply, user_id, group_id)
        return _qq().jsonify({"status": "error", "message": f"挑战失败: {str(e)}"})


def _list_cached_gifs(user_id: str, group_id):
    """列出用户缓存的最近1个GIF下载链接"""
    # GIF缓存放在static_images下，直接用图片服务器提供下载
    cache_dir = BASE_DIR / "static_images" / "gifs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(cache_dir.glob(f"{user_id}_*.gif"), key=os.path.getmtime, reverse=True)
    if not files:
        _qq().send_message("你还没有生成过GIF", user_id, group_id)
        return _qq().jsonify({"status": "empty"})
    host = _qq().IMAGE_HOST or "localhost"
    scheme = "https" if "trycloudflare" in host else "http"
    port = "" if "trycloudflare" in host else ":18080"
    msg = f"最近生成的GIF:\n"
    for f in files[:1]:
        ts = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%m-%d %H:%M")
        size_kb = os.path.getsize(f) // 1024
        url = f"{scheme}://{host}{port}/gifs/{f.name}"
        msg += f"  {ts} {size_kb}KB\n  {url}\n"
    _qq().send_message(msg, user_id, group_id)
    return _qq().jsonify({"status": "success"})


def handle_battle_log(user_id: str, group_id, gen_gif: bool = False):
    """显示最近一场战斗的详细日志，可选生成GIF"""
    try:
        log_path = INFO_DIR / f"battle_{user_id}.json"
        if not log_path.exists():
            reply = "你还没有进行过战斗！"
            if group_id and user_id:
                reply = f"<@{user_id}> {reply}"
            _qq().send_message(reply, user_id, group_id)
            return _qq().jsonify({"status": "error", "message": "没有战斗日志"})

        with open(log_path, "r", encoding="utf-8") as f:
            all_logs = json.load(f)
        if not isinstance(all_logs, list) or not all_logs:
            reply = "你还没有进行过战斗！"
            if group_id and user_id:
                reply = f"<@{user_id}> {reply}"
            _qq().send_message(reply, user_id, group_id)
            return _qq().jsonify({"status": "error", "message": "没有战斗日志"})

        # 读取最近一次战斗日志
        result = all_logs[-1]

        # 格式化战斗日志文本（先定义，GIF可能用到）
        if "boss_name" in result:
            log_text = format_boss_result(result, include_log=True)
        else:
            log_text = format_battle_result(result)

        # 生成GIF（缓存到本地，同用户3分钟冷却）
        if gen_gif and _qq().BATTLE_SYSTEM_LOADED:
            last_gif = _qq()._GIF_COOLDOWN.get(user_id, 0)
            now = datetime.now().timestamp()
            if now - last_gif < 180:
                _qq().send_message(f"GIF生成冷却中，请{int(180 - (now - last_gif))}秒后再试", user_id, group_id)
                return _qq().jsonify({"status": "cooldown"})
            try:
                import time as _time
                started_at = _time.perf_counter()
                _qq().send_message("正在生成战斗GIF，请稍候…\n详细文字战报可另输入「战斗日志」。", user_id, group_id)
                # 用战斗日志哈希做缓存key，相同战斗直接复用
                import hashlib
                cache_key = hashlib.md5(json.dumps(result.get('log', [])[:500]).encode()).hexdigest()[:12]
                cache_dir = BASE_DIR / "static_images" / "gifs"
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_file = cache_dir / f"{user_id}_{cache_key}.gif"

                send_ok = False
                if cache_file.exists():
                    _qq().log_info(f"GIF缓存命中: {cache_file.name}")
                    with open(cache_file, 'rb') as f:
                        send_qq_gif = _qq().send_qq_gif
                        send_ok = send_qq_gif(group_id, BytesIO(f.read()), content="")
                else:
                    from gif_renderer import battle_to_gif_bytes
                    gif_buffer = battle_to_gif_bytes(result, frame_duration=1200)
                    if gif_buffer:
                        gif_bytes = gif_buffer.getvalue()
                        with open(cache_file, 'wb') as f:
                            f.write(gif_bytes)
                        gif_buffer.seek(0)
                        send_ok = _qq().send_qq_gif(group_id, gif_buffer, content="")
                        elapsed = _time.perf_counter() - started_at
                        _qq().log_info(
                            f"GIF生成+发送: {elapsed:.2f}s, {len(gif_bytes) / 1024:.1f}KB, send_ok={send_ok}"
                        )
                    else:
                        _qq().send_message("GIF生成失败", user_id, group_id)

                # 每用户只保留当前缓存。旧逻辑在新文件写入前清理，实际可能留下2个。
                for old_file in cache_dir.glob(f"{user_id}_*.gif"):
                    if old_file != cache_file:
                        try:
                            old_file.unlink()
                        except OSError:
                            pass

                if cache_file.exists() and not send_ok:
                    host = _qq()._IMAGE_HOST_CACHE.get("value") or _qq().IMAGE_HOST or "localhost"
                    scheme = "https" if "trycloudflare" in host else "http"
                    port = "" if "trycloudflare" in host else ":18080"
                    url = f"{scheme}://{host}{port}/gifs/{cache_file.name}"
                    _qq().send_message(f"GIF直接发送失败，请使用下载链接:\n{url}", user_id, group_id)

                if cache_file.exists():
                    _qq()._GIF_COOLDOWN[user_id] = now
            except Exception as gif_err:
                _qq().log_error(f"战斗GIF生成失败: {gif_err}")
        import re
        log_text = re.sub(r'\n{3,}', '\n\n', log_text)

        # 如果已经发送了GIF（含文字），不再重复发文字
        if not gen_gif:
            at_message = _qq()._at_user(user_id, group_id)
            if len(log_text) > 4000:
                log_text = log_text[:4000] + "\n... (日志过长已截断)"
            _qq().send_message(at_message + log_text, user_id, group_id)
        # GIF命令只发生成提示 + GIF，不再附加4000字战报，减少同一 msg_id 的多次被动回复。

        return _qq().jsonify({"status": "success", "message": "显示战斗日志"})

    except Exception as e:
        _qq().log_error(f"获取战斗日志失败: {e}")
        reply = f"获取战斗日志失败: {str(e)}"
        if group_id and user_id:
            reply = f"<@{user_id}> {reply}"
        _qq().send_message(reply, user_id, group_id)
        return _qq().jsonify({"status": "error", "message": str(e)})  # jsonify 返回 None，避免 tuple


def handle_team(user_id: str, group_id, raw_message: str):
    """处理配队相关命令"""
    try:
        characters = _qq().get_characters_dict()
        
        # 解析命令
        # 队伍 - 显示当前队伍（只显示图片）
        # 队伍 我的卡 - 显示三星卡图（50张，可翻页，无文字卡名）
        # 队伍 我的卡 红/绿/蓝/黄/紫/超红/超绿... - 按颜色筛选三星卡
        # 队伍 我的卡 B/A - 按战斗/支援类型筛选三星卡
        # 队伍 我的卡 下一页/上一页 - 翻页查看三星卡（保持筛选）
        # 队伍 设置 位置 序号(1-50) - 根据当前页序号设置卡牌
        # 队伍 设置 战斗位/支援位 位置 序号 - 手动指定类型
        # 队伍 清除 位置 - 清除该位置的战斗卡和支援卡
        # 队伍 清空 - 清空所有队伍配置
        # 队伍 自动配队 - AI自动配队（B+A同色同攻击类型，FES优先）
        # 队伍 切换 N - 加载预设N (1-6)，设为活跃槽位，后续编辑自动保存到此槽
        # 队伍 预设 - 查看所有预设摘要
        # 防守队 - 查看当前防守队（被挑战时使用）
        # 防守队 设置 N - 设置防守队为预设槽位N（1-6）
        
        # 获取用户当前查看的页码（从session或默认第1页）
        team_session_file = INFO_DIR / f"team_session_{user_id}.json"
        current_page = 1
        if team_session_file.exists():
            try:
                with open(team_session_file, "r", encoding="utf-8") as f:
                    session_data = json.load(f)
                    current_page = session_data.get("cards_page", 1)
            except:
                current_page = 1
        
        # 自动配队命令
        if '自动配队' in raw_message or '自动' in raw_message:
            result = auto_build_team(user_id, characters)

            if not result["success"]:
                reply = result["message"]
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": result["message"]})

            # 只发队伍图片 + 简短提示
            team_data = _qq().load_team_data(user_id)
            img_path = build_team_image(team_data, characters)
            if img_path and os.path.exists(img_path):
                try:
                    at = _qq()._at_user(user_id, group_id)
                    _qq().send_message_with_image(group_id or user_id, f"{at}🤖 自动配队完成", img_path)
                    if os.path.exists(img_path):
                        os.remove(img_path)
                except Exception as e:
                    _qq().log_error(f"配队图片处理失败: {e}")
                    at = _qq()._at_user(user_id, group_id)
                    _qq().send_message(f"{at}🤖 自动配队完成", group_id or user_id)
            else:
                at = _qq()._at_user(user_id, group_id)
                _qq().send_message(f"{at}🤖 自动配队完成", group_id or user_id)
            return _qq().jsonify({"status": "success"})
        
        if '我的卡' in raw_message:
            import re

            # --- 解析筛选条件（颜色/B/A）---
            # 从session恢复上次的筛选条件（翻页时保持筛选）
            last_filter_color = None
            last_filter_type = None
            if team_session_file.exists():
                try:
                    with open(team_session_file, "r", encoding="utf-8") as f:
                        sd = json.load(f)
                    last_filter_color = sd.get("filter_color")
                    last_filter_type = sd.get("filter_type")
                except:
                    pass

            filter_color = last_filter_color
            filter_type = last_filter_type

            # 检查是否指定了新的筛选条件
            BASE_COLORS = ["红", "绿", "蓝", "黄", "紫"]
            SUPER_COLORS = ["超红", "超绿", "超蓝", "超黄", "超紫"]
            ALL_COLORS = SUPER_COLORS + BASE_COLORS  # 超X优先匹配
            after_mycard = raw_message.split('我的卡', 1)[-1] if '我的卡' in raw_message else ''
            after_stripped = after_mycard.strip()

            # 检测翻页/页码关键词
            is_pagination = ('下一页' in after_mycard or '上一页' in after_mycard or
                             bool(re.search(r'(第)?\d+(页)?', after_mycard)))

            # 检测筛选关键词（含超属性）
            has_color_filter = any(cn in after_mycard for cn in ALL_COLORS)
            has_type_filter = (bool(re.search(r'(?<![a-zA-Z])[Bb](?![a-zA-Z])', after_mycard)) or
                               bool(re.search(r'(?<![a-zA-Z])[Aa](?![a-zA-Z])', after_mycard)))

            # 颜色筛选（超X优先，避免"超红"被"红"误匹配）
            for cn in ALL_COLORS:
                if cn in after_mycard:
                    filter_color = cn
                    break

            # 类型筛选：匹配独立B/A（不与其他字母粘连）
            if re.search(r'(?<![a-zA-Z])[Bb](?![a-zA-Z])', after_mycard):
                filter_type = "battle"
            elif re.search(r'(?<![a-zA-Z])[Aa](?![a-zA-Z])', after_mycard):
                filter_type = "assist"

            # 纯「队伍 我的卡」（无筛选无翻页）→ 清空筛选显示全部
            if not after_stripped:
                filter_color = None
                filter_type = None
            elif not has_color_filter and not has_type_filter and not is_pagination:
                # 有其他文字但无筛选无翻页 → 也清空筛选
                filter_color = None
                filter_type = None

            # 如果指定了筛选但和session不同，重置页码到第1页
            if filter_color != last_filter_color or filter_type != last_filter_type:
                current_page = 1

            # --- 获取筛选后的总数和总页数 ---
            user_cards = get_user_3star_cards(user_id, characters,
                                               filter_color=filter_color,
                                               filter_type=filter_type)
            total_pages = max(1, (len(user_cards) + 50 - 1) // 50)

            # --- 处理翻页 ---
            # 检查是否跳转到指定页码（如"队伍 我的卡 第3页"或"队伍 我的卡 3"）
            page_match = re.search(r'我的卡\s+(第)?(\d+)(页)?', raw_message)
            if page_match:
                target_page = int(page_match.group(2))
                current_page = max(1, min(target_page, total_pages))
            elif '下一页' in raw_message:
                current_page += 1
                if current_page > total_pages:
                    current_page = total_pages
            elif '上一页' in raw_message:
                current_page -= 1
                if current_page < 1:
                    current_page = 1

            # 确保页码在有效范围内
            current_page = max(1, min(current_page, total_pages))

            # 保存当前页码和筛选条件
            _atomic_json_save(team_session_file, {
                "cards_page": current_page,
                "filter_color": filter_color,
                "filter_type": filter_type,
            })

            # 显示用户拥有的三星卡（50张一页，只显示图片，无文字卡名）
            img_path, current_cards, total_pages = build_3star_cards_image(
                user_id, characters, current_page, 50,
                filter_color=filter_color, filter_type=filter_type)

            if not current_cards:
                # 有筛选条件时给更友好的提示
                filter_desc = ""
                if filter_color and filter_type:
                    type_label = "B" if filter_type == "battle" else "A"
                    filter_desc = f"{filter_color}色{type_label}卡"
                elif filter_color:
                    filter_desc = f"{filter_color}色卡"
                elif filter_type:
                    type_label = "B" if filter_type == "battle" else "A"
                    filter_desc = f"{type_label}卡"
                filter_desc = filter_desc.replace("黄色", "黄") if filter_desc else ""
                if filter_desc:
                    reply = f"你没有{filter_desc}~ 输入「队伍 我的卡」查看全部三星卡"
                else:
                    reply = "你还没有三星卡~"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "success", "message": "没有三星卡"})

            # 构建筛选标签
            filter_label = ""
            if filter_color and filter_type:
                type_label = "B" if filter_type == "battle" else "A"
                filter_label = f"【{filter_color}色{type_label}卡】"
            elif filter_color:
                filter_label = f"【{filter_color}色卡】"
            elif filter_type:
                type_label = "B" if filter_type == "battle" else "A"
                filter_label = f"【{type_label}卡】"

            filter_label = filter_label.replace("黄色", "黄") if filter_label else ""

            # 构建翻页提示（带上筛选条件）
            filter_suffix = ""
            if filter_color:
                filter_suffix += filter_color
            if filter_type:
                type_label = "B" if filter_type == "battle" else "A"
                filter_suffix += type_label

            # 构建消息（只有图片和页码提示）
            page_info = f"{filter_label} 第{current_page}/{total_pages}页"
            if total_pages > 1:
                nav_cmd = f"队伍 我的卡 {filter_suffix}" if filter_suffix else "队伍 我的卡"
                if current_page < total_pages:
                    page_info += f" | 输入「{nav_cmd} 下一页」查看下一页"
                if current_page > 1:
                    page_info += f" | 输入「{nav_cmd} 上一页」查看上一页"
                page_info += f" | 输入「{nav_cmd} 页码」跳转到指定页"
            page_info += " | 输入「队伍 我的卡」查看全部"

            # 使用提示（根据当前页实际卡牌数量）
            current_page_size = len(current_cards)
            usage_hint = (f"设置: 队伍 设置 位置 序号(1-{current_page_size}) | "
                          f"切换预设: 队伍 切换 1~6")

            if img_path and os.path.exists(img_path):
                # 发送文字提示 + 图片
                if group_id and user_id:
                    at_message = f"<@{user_id}> "
                else:
                    at_message = ""
                _qq().send_message_with_image(group_id or user_id, f"{at_message}{page_info}\n{usage_hint}", str(img_path))

                if os.path.exists(img_path):
                    os.remove(img_path)
            else:
                reply = f"{page_info}\n{usage_hint}"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)

            return _qq().jsonify({"status": "success", "message": "显示三星卡", "page": current_page, "total_pages": total_pages})
        
        elif '设置' in raw_message:
            # 设置队伍卡牌
            import re

            # 读取当前session的筛选条件（确保设置时序号与显示一致）
            _set_filter_color = None
            _set_filter_type = None
            if team_session_file.exists():
                try:
                    with open(team_session_file, "r", encoding="utf-8") as f:
                        _sd = json.load(f)
                    _set_filter_color = _sd.get("filter_color")
                    _set_filter_type = _sd.get("filter_type")
                except:
                    pass

            # 匹配格式1: 队伍 设置 位置 序号（使用当前页的序号1-50）
            match_simple = re.search(r'设置\s+(\d+)\s+(\d+)', raw_message)
            # 匹配格式2: 队伍 设置 战斗位/支援位 位置 序号
            match_full = re.search(r'设置\s+(战斗位|支援位)\s+(\d+)\s+(\d+)', raw_message)

            if match_simple and not match_full:
                # 简化格式：使用序号选择卡牌
                position = int(match_simple.group(1))
                card_index = int(match_simple.group(2))  # 序号1-50

                if position < 1 or position > 6:
                    reply = "队伍位置必须在1-6之间！"
                else:
                    # 获取当前页的卡牌列表（使用session中的筛选条件）
                    img_path, current_cards, total_pages = build_3star_cards_image(
                        user_id, characters, current_page, 50,
                        filter_color=_set_filter_color, filter_type=_set_filter_type)
                    
                    if card_index < 1:
                        reply = "序号必须大于0！"
                    elif card_index > len(current_cards):
                        reply = f"当前页只有{len(current_cards)}张卡，序号{card_index}无效！"
                    else:
                        card_info = current_cards[card_index - 1]
                        card_id = card_info.get("card_id")
                        card_type = card_info.get("type", "battle")
                        
                        success = set_team_card(user_id, position, card_id, card_type)
                        type_text = "战斗位" if card_type == "battle" else "支援位"
                        if success:
                            auto_save_preset(user_id)
                            reply = f"成功设置{type_text}{position}！"
                        elif success == -1:
                            reply = "设置失败！RAID队伍(7-11)不能使用重复角色~"
                        else:
                            # 检查是否因为重复导致失败
                            team_data = _qq().load_team_data(user_id)
                            all_cards = (team_data.get("battle_cards", []) +
                                        team_data.get("assist_cards", []))
                            already_used = any(
                                c and str(c) == str(card_id)
                                for i, c in enumerate(all_cards)
                                if not (i == position - 1 and card_type == "battle") and
                                   not (i == position + 5 and card_type == "assist")
                            )
                            if already_used:
                                reply = "设置失败！该卡牌已在队伍的其他位置使用，不能重复选择同一张卡~"
                            else:
                                reply = "设置失败！"
                            
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "success" if '成功' in reply else "error", "message": reply})
            
            elif match_full:
                # 完整格式：手动指定类型
                card_type = "battle" if match_full.group(1) == "战斗位" else "assist"
                position = int(match_full.group(2))
                card_index = int(match_full.group(3))  # 序号1-10
                
                if position < 1 or position > 6:
                    reply = "队伍位置必须在1-6之间！"
                elif card_index < 1 or card_index > 10:
                    reply = "序号必须在1-10之间！"
                else:
                    # 获取当前页的卡牌列表（使用session中的筛选条件）
                    img_path, current_cards, total_pages = build_3star_cards_image(
                        user_id, characters, current_page, 10,
                        filter_color=_set_filter_color, filter_type=_set_filter_type)
                    
                    if card_index > len(current_cards):
                        reply = f"当前页只有{len(current_cards)}张卡，序号{card_index}无效！"
                    else:
                        card_info = current_cards[card_index - 1]
                        card_id = card_info.get("card_id")
                        
                        success = set_team_card(user_id, position, card_id, card_type)
                        if success:
                            auto_save_preset(user_id)
                            reply = f"成功设置{match_full.group(1)}{position}！"
                        elif success == -1:
                            reply = "设置失败！RAID队伍(7-11)不能使用重复角色~"
                        else:
                            # 检查是否因为重复导致失败
                            team_data = _qq().load_team_data(user_id)
                            all_cards = (team_data.get("battle_cards", []) +
                                        team_data.get("assist_cards", []))
                            already_used = any(
                                c and str(c) == str(card_id)
                                for i, c in enumerate(all_cards)
                                if not (i == position - 1 and card_type == "battle") and
                                   not (i == position + 5 and card_type == "assist")
                            )
                            if already_used:
                                reply = "设置失败！该卡牌已在队伍的其他位置使用，不能重复选择同一张卡~"
                            else:
                                reply = "设置失败！"
                
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "success" if success else "error", "message": reply})
            
            else:
                reply = "格式错误！正确格式：队伍 设置 位置 序号(1-10)"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": "格式错误"})
        
        elif '清除' in raw_message:
            # 清除指定位置的卡牌
            import re
            match = re.search(r'清除\s+(\d+)', raw_message)
            
            if match:
                position = int(match.group(1))
                
                if position < 1 or position > 6:
                    reply = "位置必须在1-6之间！"
                else:
                    # 清除战斗位和支援位的对应位置
                    clear_team_card(user_id, position, "battle")
                    clear_team_card(user_id, position, "assist")
                    reply = f"成功清除位置{position}的战斗卡和支援卡！"
                
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "success", "message": reply})
            
            else:
                reply = "格式错误！正确格式：队伍 清除 位置"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": "格式错误"})
        
        elif '清空' in raw_message:
            # 清空整个队伍
            clear_all_team(user_id)
            reply = "已清空所有队伍配置！"
            if group_id and user_id:
                reply = f"<@{user_id}> {reply}"
            _qq().send_message(reply, user_id, group_id)
            return _qq().jsonify({"status": "success", "message": "队伍已清空"})

        elif '切换' in raw_message:
            # 切换预设: 队伍 切换 N
            import re
            m = re.search(r'切换\s*(\d)', raw_message)
            if m:
                slot = int(m.group(1))
                if load_preset(user_id, slot):
                    team_data = _qq().load_team_data(user_id)
                    img_path = build_team_image(team_data, characters)
                    if img_path and os.path.exists(img_path):
                        _qq().send_message_with_image(group_id or user_id, f"<@{user_id}> 已切换到预设{slot}！" if group_id and user_id else f"已切换到预设{slot}！", str(img_path))
                        os.remove(img_path)
                    else:
                        _qq().send_message(f"<@{user_id}> 已切换到预设{slot}！" if group_id and user_id else f"已切换到预设{slot}！", group_id or user_id)
                    return _qq().jsonify({"status": "success"})
                else:
                    # 预设为空 → 自动配队并保存到此槽位
                    result = auto_build_team(user_id, characters)
                    if result["success"] and result["team"]:
                        _qq().save_team_data(user_id, result["team"])
                        presets_data = load_presets(user_id)
                        presets_data["presets"][slot - 1] = {
                            "battle_cards": list(result["team"].get("battle_cards", [])),
                            "assist_cards": list(result["team"].get("assist_cards", []))
                        }
                        presets_data["active_slot"] = slot
                        save_presets(user_id, presets_data)
                        reply = f"预设{slot}自动配队完成！"
                        img_path = build_team_image(result["team"], characters)
                        prefix = _qq()._at_user(user_id, group_id)
                        if img_path and os.path.exists(img_path):
                            _qq().send_message_with_image(group_id or user_id, f"{prefix}预设{slot}为空，正在自动配队...\n{reply}", str(img_path))
                            os.remove(img_path)
                        else:
                            _qq().send_message(f"{prefix}预设{slot}为空，正在自动配队...\n{reply}", group_id or user_id)
                    else:
                        reply = f"预设{slot}为空，正在自动配队...\n{result.get('message', '自动配队失败，请先抽卡！')}"
                        if group_id and user_id:
                            reply = f"<@{user_id}> {reply}"
                        _qq().send_message(reply, group_id or user_id)
            else:
                reply = "格式：队伍 切换 1~6"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, group_id or user_id)
            return _qq().jsonify({"status": "success"})

        elif '预设' in raw_message:
            # 查看所有预设
            info = list_presets_info(user_id, characters)
            reply = info
            if group_id and user_id:
                reply = f"<@{user_id}>\n{reply}"
            _qq().send_message(reply, user_id, group_id)
            return _qq().jsonify({"status": "success", "message": "显示预设列表"})

        else:
            # 显示当前队伍（只显示图片，不显示文字信息）
            team_data = _qq().load_team_data(user_id)
            
            # 生成队伍图片
            img_path = build_team_image(team_data, characters)

            if img_path and os.path.exists(img_path):
                hints = "队伍 预设 | 队伍 切换 1~6 | 队伍 我的卡 | 队伍 自动配队"
                _qq().send_image_from_path(group_id or user_id, str(img_path), content=hints)
            else:
                reply = "队伍配置为空！"
                if group_id and user_id:
                    reply = f"<@{user_id}> {reply}"
                _qq().send_message(reply, group_id or user_id)
            
            return _qq().jsonify({"status": "success", "message": "显示队伍"})
    
    except Exception as e:
        _qq().log_error(f"配队处理失败: {e}")
        return _qq().jsonify({"status": "error", "message": str(e)})  # jsonify 返回 None，避免 tuple


def handle_defense_team(user_id: str, group_id, raw_message: str):
    """处理防守队命令"""
    try:
        characters = _qq().get_characters_dict()
        import re

        # 设置防守队槽位: 防守队 设置 N 或 防守队 N
        set_match = re.search(r'设置\s*(\d)', raw_message)
        if not set_match:
            set_match = re.search(r'防守队\s+(\d)', raw_message)

        if set_match:
            slot = int(set_match.group(1))
            if slot < 1 or slot > 6:
                reply = f"<@{user_id}> 防守队槽位必须在1-6之间！" if group_id else "防守队槽位必须在1-6之间！"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": "无效的槽位"})

            # 检查预设槽位是否有队伍
            presets_data = load_presets(user_id)
            preset = presets_data["presets"][slot - 1]
            if preset is None or not any(preset.get("battle_cards", [])):
                reply = f"<@{user_id}> 预设槽位{slot}为空！请先使用「队伍 切换 {slot}」配置该预设的队伍。" if group_id else f"预设槽位{slot}为空！请先使用「队伍 切换 {slot}」配置该预设的队伍。"
                _qq().send_message(reply, user_id, group_id)
                return _qq().jsonify({"status": "error", "message": "预设为空"})

            set_defense_slot(user_id, slot)
            reply = f"<@{user_id}> 🛡️ 防守队已设置为「预设槽位{slot}」！被挑战时将使用该队伍迎战。" if group_id else f"🛡️ 防守队已设置为「预设槽位{slot}」！被挑战时将使用该队伍迎战。"
            _qq().send_message(reply, user_id, group_id)
            _qq().log_info(f"防守队 [{user_id}]: 设置为预设槽位{slot}")
            return _qq().jsonify({"status": "success", "message": f"防守队设置为槽位{slot}"})

        # 查看当前防守队 — 生成配队图片
        defense_team = get_defense_team(user_id)
        defense_slot = get_defense_slot(user_id)

        at_message = _qq()._at_user(user_id, group_id)

        # 生成防守队配队图片
        img_path = build_team_image(defense_team, characters)
        if img_path and os.path.exists(img_path):
            _qq().send_message_with_image(group_id or user_id, f"{at_message}🛡️ 防守队 (预设槽{defense_slot})", str(img_path))
        else:
            info = get_defense_team_info(user_id, characters)
            _qq().send_message(f"{at_message}{info}", group_id or user_id)

        return _qq().jsonify({"status": "success", "message": "显示防守队"})

    except Exception as e:
        _qq().log_error(f"防守队处理失败: {e}")
        return _qq().jsonify({"status": "error", "message": str(e)})  # jsonify 返回 None，避免 tuple


def handle_help(user_id: str, group_id, raw_message: str = ""):
    """分章节帮助系统
    帮助          → 显示帮助总览（章节列表）
    帮助 抽卡     → 抽卡相关帮助
    帮助 战斗     → 战斗相关帮助
    帮助 队伍     → 配队相关帮助
    帮助 经济     → 货币/经济帮助
    """
    import re

    # 解析章节参数
    chapter = ""
    for kw in ["抽卡", "gacha", "战斗", "对战", "battle", "队伍", "配队",
               "team", "经济", "economy", "货币", "其他", "other"]:
        if kw in raw_message:
            chapter = kw
            break

    if chapter in ("抽卡", "gacha"):
        help_text = _help_gacha()
    elif chapter in ("战斗", "对战", "battle"):
        help_text = _help_battle()
    elif chapter in ("队伍", "配队", "team"):
        help_text = _help_team()
    elif chapter in ("经济", "economy", "货币"):
        help_text = _help_economy()
    elif chapter in ("其他", "other"):
        help_text = _help_other()
    else:
        help_text = _help_overview()

    at = _qq()._at_user(user_id, group_id)
    _qq().send_message(at + help_text, user_id, group_id)
    _qq().log_info(f"帮助 [{user_id}]: 章节={chapter or '总览'}")
    return _qq().jsonify({"status": "success", "chapter": chapter or "overview"})
