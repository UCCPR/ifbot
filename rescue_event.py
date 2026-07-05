"""
Raid 系统 - BOSS讨伐活动
功能：活动框架 + BOSS召唤 + 挑战/协助 + HS/RS计分 + 公共求援 + 救援币 + 兑换商店
      + 排名报酬 + 活动结算 + 历史记录 + 队伍锁定机制
数据存储：info/rescue_event.json / info/rescue_event_history.json
"""

import json
import os
import sys
import re
import random
import copy
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from team_system import build_vs_team_image as _build_vs_team_image


# ========== 路径 ==========
BASE_DIR = Path(__file__).parent
INFO_DIR = BASE_DIR / "info"
INFO_DIR.mkdir(exist_ok=True)

RESCUE_EVENT_FILE = INFO_DIR / "rescue_event.json"
RESCUE_EVENT_HISTORY_FILE = INFO_DIR / "rescue_event_history.json"


# ========== _qq() 模式 ==========
def _qq():
    """获取qq_bot_ws模块引用（优先__main__，避免模块双重加载）"""
    main = sys.modules.get('__main__')
    if main and hasattr(main, 'send_message'):
        return main


def _get_display_name(uid: str) -> str:
    """获取用户显示名（昵称优先，无昵称则截取ID前6位）"""
    try:
        qq = _qq()
        if hasattr(qq, 'get_nickname'):
            nick = qq.get_nickname(str(uid))
            if nick:
                return nick
    except Exception:
        pass
    uid_str = str(uid)
    return uid_str[:6] if len(uid_str) > 8 else uid_str


# ========== 安全JSON写入 ==========
def _atomic_json_save(file_path: Path, data: dict):
    """原子写入JSON：先写临时文件再rename，防止崩溃损坏数据"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(
            suffix='.json', prefix='tmp_', dir=str(file_path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, file_path)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise
    except Exception as e:
        _qq().log_error(f"rescue_event 原子写入失败 {file_path}: {e}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e2:
            _qq().log_error(f"rescue_event 降级写入也失败: {e2}")


# ========== Rank HP倍率表（普通BOSS）==========
RANK_HP_MULTIPLIER = {
    1: 1.0, 2: 1.2, 3: 1.4, 4: 1.6, 5: 1.8,
    6: 2.0, 7: 2.2, 8: 2.5, 9: 3.0,
}

# Rank解锁通过BOSS击杀机制（max_rank字段）实现
# 每个玩家有自己的 max_rank，初始为1，当召唤的Rank N BOSS被击杀时 max_rank 升为 N+1

# EX BOSS HP倍率固定4
EX_BOSS_HP_MULTIPLIER = 4

# 初始HP
BASE_HP = 5_000_000

# 每日挑战次数上限
DAILY_CHALLENGE_LIMIT = 5

# Raid槽位范围（预设7-11对应slot_7到slot_11）
RAID_SLOT_MIN = 7
RAID_SLOT_MAX = 11

# 公共求援列表上限
PUBLIC_BOARD_MAX = 20

# BOSS最大持有数
MAX_PERSONAL_BOSSES = 10


# ========== 兑换商店 ==========
EXCHANGE_SHOP = [
    {"key": "挑战券", "cost": 10, "ticket_type": "challenge", "amount": 1},
    {"key": "救援券", "cost": 10, "ticket_type": "rescue", "amount": 1},
    {"key": "EX券", "cost": 20, "ticket_type": "ex", "amount": 1},
    {"key": "呱太", "cost": 30, "type": "gacha", "amount": 5000},
    {"key": "蓝碎片", "cost": 20, "type": "blue_crystal", "amount": 150},
]


# ========== 排名报酬表 ==========
RANKING_REWARDS = [
    {"rank_min": 1, "rank_max": 1, "gacha": 50000, "blue_crystal": 1000, "rescue_coins": 50, "title": "冠军"},
    {"rank_min": 2, "rank_max": 3, "gacha": 30000, "blue_crystal": 500, "rescue_coins": 30, "title": "亚军"},
    {"rank_min": 4, "rank_max": 10, "gacha": 15000, "blue_crystal": 200, "rescue_coins": 15, "title": "精英"},
    {"rank_min": 11, "rank_max": 30, "gacha": 8000, "blue_crystal": 100, "rescue_coins": 8, "title": "强者"},
    {"rank_min": 31, "rank_max": 50, "gacha": 3000, "blue_crystal": 50, "rescue_coins": 3, "title": "勇敢"},
    {"rank_min": 51, "rank_max": 999, "gacha": 1000, "blue_crystal": 20, "rescue_coins": 1, "title": "参与"},
]


# ========== 数据加载/保存 ==========
def _create_default_event_data() -> dict:
    """创建默认的活动数据结构"""
    return {
        "active": False,
        "start_date": "",
        "end_date": "",
        "settled": False,
        "event_id": 0,
        "players": {},
        "public_board": [],
        "boss_fighting": {},
    }


def load_event_data() -> dict:
    """加载活动数据（文件不存在则创建默认）"""
    try:
        if RESCUE_EVENT_FILE.exists():
            with open(RESCUE_EVENT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            data = _create_default_event_data()
            _atomic_json_save(RESCUE_EVENT_FILE, data)
            _qq().log_info("rescue_event: 首次创建默认数据文件")
            return data
    except Exception as e:
        _qq().log_error(f"rescue_event load_event_data 异常: {e}")
        return _create_default_event_data()


def save_event_data(data: dict):
    """保存活动数据"""
    try:
        _atomic_json_save(RESCUE_EVENT_FILE, data)
    except Exception as e:
        _qq().log_error(f"rescue_event save_event_data 异常: {e}")


# ========== BOSS数据获取 ==========
def _get_boss_card_id() -> str:
    """从config读取普通BOSS的card_id：RAID_BOSS_CARD_ID > BOSS_CARD_ID > 默认"""
    try:
        qq = _qq()
        # 优先读取 RAID 专用配置
        raid_id = getattr(qq, 'RAID_BOSS_CARD_ID', None)
        if raid_id and str(raid_id).strip():
            return str(raid_id).strip()
        # fallback 到 BOSS战配置
        boss_id = getattr(qq, 'BOSS_CARD_ID', None)
        if boss_id and str(boss_id).strip():
            return str(boss_id).strip()
    except Exception:
        pass
    return '101630001'


def _get_ex_boss_card_id() -> str:
    """从config读取EX BOSS的card_id：RAID_EX_BOSS_CARD_ID > RAID_BOSS_CARD_ID > BOSS_CARD_ID > 默认"""
    try:
        qq = _qq()
        ex_id = getattr(qq, 'RAID_EX_BOSS_CARD_ID', None)
        if ex_id and str(ex_id).strip():
            return str(ex_id).strip()
    except Exception:
        pass
    return _get_boss_card_id()


def _get_boss_character(boss_card_id: str, battle_system=None):
    """通过战斗系统获取BOSS角色数据"""
    if battle_system is not None and hasattr(battle_system, 'get_character'):
        char = battle_system.get_character(boss_card_id)
        if char:
            return char
    return None


def _get_boss_name(boss_card_id: str, battle_system=None, default_name: str = "BOSS") -> str:
    """获取BOSS角色名称"""
    char = _get_boss_character(boss_card_id, battle_system)
    if char:
        name = char.get("name", "") if isinstance(char, dict) else getattr(char, "name", "")
        if name:
            return name
    return default_name


def _build_boss_extra_chars(boss_card_id: str, boss_name: str, boss_hp: int,
                            battle_system=None) -> dict:
    """构建BOSS角色额外数据（传给战斗系统），优先使用实际角色数据"""
    # 尝试从实际角色获取属性
    char = _get_boss_character(boss_card_id, battle_system)
    if char and isinstance(char, dict):
        attack = char.get("attack", char.get("phys_atk", 8000))
        defense = char.get("defense", char.get("phys_def", 5000))
        speed = char.get("dexterity", char.get("speed", 1200))
        attribute = char.get("element", char.get("attribute", "红"))
        attack_type = char.get("attack_type", "物理")
        side = char.get("side", "魔法")
    else:
        attack, defense, speed = 8000, 5000, 1200
        attribute, attack_type, side = "红", "物理", "魔法"

    return {
        boss_card_id: {
            "name": boss_name,
            "hp": boss_hp,
            "attack": attack,
            "defense": defense,
            "dexterity": speed,
            "element": attribute,
            "attack_type": attack_type,
            "side": side,
        }
    }


def _calc_boss_hp(rank: int, is_ex: bool = False) -> int:
    """计算BOSS的HP"""
    if is_ex:
        return int(BASE_HP * EX_BOSS_HP_MULTIPLIER)
    multiplier = RANK_HP_MULTIPLIER.get(rank, 1.0)
    return int(BASE_HP * multiplier)


def _calc_reward_pool(rank: int, is_ex: bool = False) -> int:
    """计算击杀奖励池（救援币）"""
    if is_ex:
        return 9 * 12  # 108
    return 9 * rank


def _get_reward_for_rank(rank_num: int) -> Optional[dict]:
    """根据排名获取报酬信息"""
    for r in RANKING_REWARDS:
        if r["rank_min"] <= rank_num <= r["rank_max"]:
            return r
    return None


# ========== 玩家数据辅助 ==========
def _get_player(data: dict, user_id: str) -> dict:
    """获取玩家数据（不存在则创建）"""
    uid = str(user_id)
    if uid not in data["players"]:
        data["players"][uid] = {
            "tickets": {"challenge": 10, "rescue": 10, "ex": 0},
            "rescue_coins": 0,
            "my_bosses": [],
            "daily_challenge_count": {},
            "daily_locked_teams": {},
            "team_hp_saved": {},
            "hs_today": 0,
            "hs_history": {},
            "rs": 0,
            "max_rank": 1,
        }
    # 向后兼容：确保所有字段存在
    p = data["players"][uid]
    p.setdefault("tickets", {"challenge": 0, "rescue": 0, "ex": 0})
    p.setdefault("rescue_coins", 0)
    p.setdefault("my_bosses", [])
    p.setdefault("daily_challenge_count", {})
    p.setdefault("daily_locked_teams", {})
    p.setdefault("team_hp_saved", {})
    p.setdefault("hs_today", 0)
    p.setdefault("hs_history", {})
    p.setdefault("rs", 0)
    p.setdefault("max_rank", 1)
    return p


# ========== 工具函数 ==========
def _today_str() -> str:
    """获取今天日期字符串 YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def _is_event_active(data: dict) -> bool:
    """检查活动是否在有效期内"""
    if not data.get("active", False):
        return False
    today = _today_str()
    start = data.get("start_date", "")
    end = data.get("end_date", "")
    if not start or not end:
        return False
    return start <= today <= end


def _is_admin(user_id: str) -> bool:
    """判断是否为管理员"""
    try:
        return str(user_id) == str(getattr(_qq(), 'ADMIN_QQ', ''))
    except Exception:
        return False


def _generate_boss_id() -> str:
    """生成唯一BOSS ID"""
    return f"rb_{uuid.uuid4().hex[:8]}"


def _is_past_end(data: dict) -> bool:
    """活动是否已过期（用于结算判断）"""
    end = data.get("end_date", "")
    if not end:
        return False
    return _today_str() > end


# ========== 降级战斗模拟 ==========
def _simulate_battle(player_team: dict, boss_hp: int) -> dict:
    """降级模式：当无战斗系统时模拟战斗（支持血量继承）"""
    battle_cards = player_team.get("battle_cards", [])
    saved_hp_data = player_team.get("_raid_saved_hp")

    card_count = sum(1 for c in battle_cards if c is not None)
    if card_count == 0:
        return {
            "damage_dealt": 0,
            "damage_percent": 0,
            "boss_killed": False,
            "boss_starting_hp": boss_hp,
            "boss_ending_hp": boss_hp,
            "rounds": 12,
            "player_survived": 0,
            "player_total": len(battle_cards),
            "log": [],
            "player_units": [],
            "enemy_units": [],
        }

    # 构建角色列表（含HP和存活状态）
    battle_position_map = [0, 2, 4, 5, 6, 7]  # 与build_battle_team一致
    units = []
    for i, c in enumerate(battle_cards):
        if c is None:
            continue
        if saved_hp_data:
            is_alive = i < len(saved_hp_data.get("alive", [])) and saved_hp_data["alive"][i]
            hp = saved_hp_data["hp"][i] if i < len(saved_hp_data.get("hp", [])) else 1000
        else:
            is_alive = True
            hp = 10000  # 默认HP（模拟用）
        pos = battle_position_map[i] if i < len(battle_position_map) else -1
        units.append({"index": i, "hp": hp, "max_hp": 10000, "alive": is_alive, "position": pos})

    # 模拟战斗：每个存活角色造成伤害，同时自己损失HP
    alive_units = [u for u in units if u["alive"]]
    damage_pct_per_unit = random.uniform(3.0, 7.0)
    total_pct = len(alive_units) * damage_pct_per_unit
    total_pct = min(total_pct, 100.0)
    damage_dealt = int(boss_hp * total_pct / 100)

    # 模拟角色HP损失（每个存活角色损失20-50%HP，有10%概率死亡）
    new_units = []
    for u in units:
        if not u["alive"]:
            new_units.append({"hp": 0, "alive": False, "max_hp": u.get("max_hp", 10000), "position": u.get("position", -1)})
            continue
        # HP损失 20-50%
        loss_pct = random.uniform(0.2, 0.5)
        new_hp = int(u["hp"] * (1 - loss_pct))
        new_hp = max(1, new_hp)  # 至少剩1HP
        # 10%概率死亡
        if random.random() < 0.1:
            new_units.append({"hp": 0, "alive": False, "max_hp": u.get("max_hp", 10000), "position": u.get("position", -1)})
        else:
            new_units.append({"hp": new_hp, "alive": True, "max_hp": u.get("max_hp", 10000), "position": u.get("position", -1)})

    alive_after = sum(1 for u in new_units if u["alive"])

    return {
        "damage_dealt": damage_dealt,
        "damage_percent": round(total_pct, 2),
        "boss_killed": total_pct >= 100,
        "boss_starting_hp": boss_hp,
        "boss_ending_hp": max(0, boss_hp - damage_dealt),
        "rounds": 12,
        "player_survived": alive_after,
        "player_total": card_count,
        "log": [],
        "player_units": new_units,
        "enemy_units": [],
    }


# ========== 队伍检查 ==========
def _check_raid_team(user_id: str, slot_key: str, player: dict) -> str:
    """检查Raid队伍是否可用
    返回 None 表示通过，否则返回错误信息字符串
    """
    # 检查是否已锁定
    if player.get("daily_locked_teams", {}).get(slot_key):
        return f"队伍{slot_key.replace('slot_', '')}今日已锁定（队伍全灭），请明日再战"

    # 检查每日使用次数
    daily_count = player.get("daily_challenge_count", {}).get(slot_key, 0)
    if daily_count >= DAILY_CHALLENGE_LIMIT:
        return f"队伍{slot_key.replace('slot_', '')}今日已使用{DAILY_CHALLENGE_LIMIT}次，已达上限"

    return None


def _get_active_slot_info(user_id: str) -> Optional[dict]:
    """获取玩家当前活跃槽位信息
    返回 {"slot": int, "slot_key": str, "team_data": dict, "presets_data": dict} 或 None
    """
    try:
        qq = _qq()
        # 通过 _qq() 间接调用 team_system
        team_system = getattr(qq, 'team_system', None)
        if team_system is None:
            try:
                import team_system as ts_mod
                team_system = ts_mod
            except ImportError:
                return None

        active_slot = team_system._get_active_slot(user_id)
        if active_slot < RAID_SLOT_MIN or active_slot > RAID_SLOT_MAX:
            return None

        # 从预设中加载该槽位的队伍，而不是当前编辑中的队伍
        presets_data = team_system.load_presets(user_id)
        presets = presets_data.get("presets", [])
        if active_slot - 1 >= len(presets) or presets[active_slot - 1] is None:
            return None

        team_data = presets[active_slot - 1]  # 使用预设中的队伍
        slot_key = f"slot_{active_slot}"
        return {
            "slot": active_slot,
            "slot_key": slot_key,
            "team_data": team_data,
            "presets_data": presets_data,
        }
    except Exception as e:
        _qq().log_error(f"rescue_event _get_active_slot_info 异常: {e}")
        return None


def _check_raid_slot_duplicate(user_id: str) -> Optional[str]:
    """检查raid槽位(7-11)的5支队伍之间是否有重复角色
    返回 None 表示无重复，否则返回错误信息
    """
    try:
        qq = _qq()
        team_system = getattr(qq, 'team_system', None)
        if team_system is None:
            try:
                import team_system as ts_mod
                team_system = ts_mod
            except ImportError:
                return None

        all_card_ids = []
        for slot_num in range(RAID_SLOT_MIN, RAID_SLOT_MAX + 1):
            presets_data = team_system.load_presets(user_id)
            presets = presets_data.get("presets", [])
            if slot_num - 1 < len(presets) and presets[slot_num - 1] is not None:
                preset = presets[slot_num - 1]
                battle_cards = preset.get("battle_cards", [])
                for cid in battle_cards:
                    if cid is not None:
                        all_card_ids.append((slot_num, str(cid)))

        seen = {}
        for slot_num, cid in all_card_ids:
            if cid in seen:
                return f"Raid队伍中角色 {cid} 在槽位{seen[cid]}和槽位{slot_num}重复，请修改队伍后挑战"
            seen[cid] = slot_num
        return None
    except Exception as e:
        _qq().log_error(f"rescue_event _check_raid_slot_duplicate 异常: {e}")
        return None


def _get_slot_team(user_id: str, slot_num: int) -> Optional[dict]:
    """获取指定槽位的队伍数据"""
    try:
        qq = _qq()
        team_system = getattr(qq, 'team_system', None)
        if team_system is None:
            try:
                import team_system as ts_mod
                team_system = ts_mod
            except ImportError:
                return None

        presets_data = team_system.load_presets(user_id)
        presets = presets_data.get("presets", [])
        if slot_num - 1 < len(presets) and presets[slot_num - 1] is not None:
            return presets[slot_num - 1]
        return None
    except Exception:
        return None


def _get_all_raid_slot_characters(user_id: str) -> List[str]:
    """获取用户所有raid槽位(7-11)的战斗卡card_id列表"""
    result = []
    for slot_num in range(RAID_SLOT_MIN, RAID_SLOT_MAX + 1):
        preset = _get_slot_team(user_id, slot_num)
        if preset:
            for cid in preset.get("battle_cards", []):
                if cid is not None:
                    result.append(str(cid))
    return result


# ========== BOSS信息获取 ==========
def _get_boss_display_info(boss: dict) -> str:
    """获取BOSS显示信息字符串"""
    rank = boss.get("rank", 1)
    is_ex = boss.get("boss_type") == "ex"
    hp = boss.get("current_hp", 0)
    max_hp = boss.get("max_hp", 1)
    hp_pct = hp / max_hp * 100 if max_hp > 0 else 0
    type_str = "[EX]" if is_ex else ""
    killed_str = " [已击败]" if boss.get("killed", False) else ""
    public_str = " [公开]" if boss.get("is_public", False) else ""
    return f"{type_str} Rank{rank} HP:{hp:,}/{max_hp:,}({hp_pct:.1f}%){killed_str}{public_str}"


# ========== 管理员命令 ==========

def cmd_raid_start(data: dict, days: int = 7) -> str:
    """管理员命令：开启Raid活动"""
    try:
        today = datetime.now()
        start = today.strftime("%Y-%m-%d")
        end = (today + timedelta(days=days)).strftime("%Y-%m-%d")

        data["active"] = True
        data["start_date"] = start
        data["end_date"] = end
        data["settled"] = False
        data["event_id"] = data.get("event_id", 0) + 1
        data["players"] = {}
        data["public_board"] = []
        data["boss_fighting"] = {}

        save_event_data(data)

        msg = (
            f"[RAID] Raid活动已开启！\n"
            f"活动期间：{start} ~ {end}\n"
            f"参与方式：\n"
            f"  raid召唤N - 消耗挑战券召唤Rank N BOSS\n"
            f"  raid召唤ex - 消耗EX券召唤EX BOSS\n"
            f"  raid挑战N - 用Raid队伍挑战个人BOSS\n"
            f"  raid协助N - 用Raid队伍协助公共BOSS\n"
            f"  raid兑换xx数量 - 兑换商店\n"
            f"\n"
            f"Raid队伍槽位：7-11（预设槽位）\n"
            f"每个队伍每日可挑战5次\n"
        )
        _qq().log_info(f"rescue_event: Raid活动已开启 {start}~{end}")
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_start 异常: {e}")
        return f"开启Raid活动失败: {e}"


def cmd_raid_stop(data: dict) -> str:
    """管理员命令：关闭Raid活动"""
    try:
        if not data.get("active", False):
            return "[RAID] 当前没有进行中的活动。"
        data["active"] = False
        save_event_data(data)
        _qq().log_info("rescue_event: Raid活动被管理员手动关闭")
        return "[RAID] 活动已手动关闭。感谢各位的参与！"
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_stop 异常: {e}")
        return f"关闭活动失败: {e}"


def cmd_raid_status(data: dict) -> str:
    """管理员命令：查看活动状态"""
    try:
        active = data.get("active", False)
        start = data.get("start_date", "未设置")
        end = data.get("end_date", "未设置")
        settled = data.get("settled", False)
        players = data.get("players", {})
        public_board = data.get("public_board", [])

        if not active and not settled:
            return "[RAID] 当前没有进行中的活动。"

        remaining = 0
        if end and end != "未设置":
            try:
                remaining = max(0, (datetime.strptime(end, '%Y-%m-%d') - datetime.now()).days + 1)
            except Exception:
                pass

        msg = "[RAID] 活动状态\n"
        msg += f"状态: {'进行中' if active else '已结束'}"
        if settled:
            msg += "（已结算）"
        msg += "\n"
        msg += f"活动期间：{start} ~ {end}\n"
        if active:
            msg += f"剩余天数：{remaining} 天\n"
        msg += f"参与玩家：{len(players)} 人\n"
        msg += f"公共求援列表：{len(public_board)} 条\n"

        # 各玩家简要信息
        if players:
            msg += "--- 玩家概览 ---\n"
            sorted_p = sorted(players.items(), key=lambda x: x[1].get("rs", 0), reverse=True)
            for uid, p in sorted_p[:20]:
                rs = p.get("rs", 0)
                hs_today = p.get("hs_today", 0)
                coins = p.get("rescue_coins", 0)
                boss_count = len(p.get("my_bosses", []))
                msg += f"  {_get_display_name(uid)} RS:{rs:.0f} 今日HS:{hs_today:,} 币:{coins} BOSS:{boss_count}\n"

        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_status 异常: {e}")
        return f"获取活动状态失败: {e}"


def cmd_raid_give_ticket(data: dict, admin_user_id: str, target_user_id: str,
                         ticket_type: str, amount: int) -> str:
    """管理员命令：发放票券"""
    try:
        ticket_names = {
            "challenge": "挑战券",
            "rescue": "救援券",
            "ex": "EX券",
        }
        type_display = ticket_names.get(ticket_type, ticket_type)
        if ticket_type not in ("challenge", "rescue", "ex"):
            return f"未知的票券类型: {ticket_type}，可选: challenge/rescue/ex"

        player = _get_player(data, target_user_id)
        player["tickets"][ticket_type] = player["tickets"].get(ticket_type, 0) + amount
        save_event_data(data)

        msg = (
            f"[RAID] 管理员发放票券\n"
            f"目标用户：{target_user_id}\n"
            f"票券类型：{type_display}\n"
            f"发放数量：{amount}\n"
            f"当前持有：{player['tickets'][ticket_type]}"
        )
        _qq().log_info(f"rescue_event: 管理员{admin_user_id}给{target_user_id}发放{amount}{type_display}")
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_give_ticket 异常: {e}")
        return f"发放票券失败: {e}"


def settle_event(data: dict) -> str:
    """活动结算：按RS排名发放最终奖励"""
    try:
        if data.get("settled", False):
            return "[RAID] 活动已经结算过了。"

        players = data.get("players", {})
        if not players:
            data["settled"] = True
            save_event_data(data)
            return "[RAID] 没有参与玩家，直接标记为已结算。"

        # 按RS排序
        sorted_players = sorted(
            players.items(),
            key=lambda x: x[1].get("rs", 0),
            reverse=True,
        )

        result_lines = ["[RAID] 活动结算完成！排名报酬已发放：\n"]

        for rank_idx, (uid, pdata) in enumerate(sorted_players, 1):
            reward = _get_reward_for_rank(rank_idx)
            if not reward:
                continue

            gacha_amount = reward.get("gacha", 0)
            blue_amount = reward.get("blue_crystal", 0)
            coin_amount = reward.get("rescue_coins", 0)

            # 发放奖励
            if gacha_amount > 0:
                try:
                    qq = _qq()
                    if hasattr(qq, 'add_gacha'):
                        qq.add_gacha(uid, gacha_amount)
                except Exception:
                    pass

            if blue_amount > 0:
                try:
                    qq = _qq()
                    if hasattr(qq, 'add_blue_crystal'):
                        qq.add_blue_crystal(uid, blue_amount)
                except Exception:
                    pass

            if coin_amount > 0:
                pdata["rescue_coins"] = pdata.get("rescue_coins", 0) + coin_amount

            result_lines.append(
                f"#{rank_idx} [{reward['title']}] {_get_display_name(uid)} "
                f"RS:{pdata.get('rs', 0):.0f} "
                f"呱太:+{gacha_amount} 蓝碎片:+{blue_amount} 救援币:+{coin_amount}"
            )

        data["settled"] = True
        # 活动结束后清除券和HS/RS，只留救援币
        for uid, pdata in players.items():
            pdata["tickets"] = {"challenge": 0, "rescue": 0, "ex": 0}
            pdata["hs_today"] = 0
            pdata["hs_history"] = {}
            pdata["rs"] = 0
            pdata["max_rank"] = 1
            pdata["daily_challenge_count"] = {}
            pdata["daily_locked_teams"] = {}
            pdata["team_hp_saved"] = {}
            pdata["my_bosses"] = []
        save_event_data(data)

        # 保存历史
        _save_history(data, sorted_players)

        msg = "\n".join(result_lines)
        _qq().log_info(f"rescue_event: Raid活动结算完成，{len(sorted_players)}名玩家")
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event settle_event 异常: {e}")
        return f"结算失败: {e}"


def _save_history(data: dict, sorted_players: list):
    """保存活动历史"""
    try:
        history = []
        if RESCUE_EVENT_HISTORY_FILE.exists():
            try:
                with open(RESCUE_EVENT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except Exception:
                history = []

        record = {
            "event_id": data.get("event_id", 0),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "settled_at": _today_str(),
            "player_count": len(data.get("players", {})),
            "rankings": [
                {
                    "rank": i,
                    "user_id": uid,
                    "rs": pdata.get("rs", 0),
                    "hs_best": max(pdata.get("hs_history", {}).values(), default=0),
                    "rescue_coins": pdata.get("rescue_coins", 0),
                }
                for i, (uid, pdata) in enumerate(sorted_players, 1)
            ],
        }
        history.append(record)

        with open(RESCUE_EVENT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _qq().log_error(f"rescue_event _save_history 异常: {e}")


# ========== 玩家命令 ==========

def cmd_raid_info(data: dict, user_id: str) -> str:
    """玩家命令：显示活动状态+个人数据"""
    try:
        if not _is_event_active(data):
            if data.get("settled", False):
                return "[RAID] 活动已结束并完成结算。\n请等待下次活动开启。"
            if data.get("start_date"):
                if _is_past_end(data):
                    return "[RAID] 活动已结束，等待管理员结算中。"
            return "[RAID] 当前没有进行中的活动。\n请等待下次活动开启。"

        start = data.get("start_date", "")
        end = data.get("end_date", "")
        today = _today_str()
        player = _get_player(data, user_id)

        remaining = 0
        try:
            remaining = max(0, (datetime.strptime(end, '%Y-%m-%d') - datetime.now()).days + 1)
        except Exception:
            pass

        msg = f"[RAID] 活动进行中 ({start} ~ {end})\n"
        msg += f"剩余 {remaining} 天\n"
        msg += f"--- 我的进度 ---\n"
        msg += f"今日HS: {player.get('hs_today', 0):,}\n"
        msg += f"累计RS: {player.get('rs', 0):.0f}\n"
        msg += f"救援币: {player.get('rescue_coins', 0)}\n"
        msg += f"--- 票券 ---\n"
        msg += f"挑战券: {player['tickets'].get('challenge', 0)} 张\n"
        msg += f"救援券: {player['tickets'].get('rescue', 0)} 张\n"
        msg += f"EX券: {player['tickets'].get('ex', 0)} 张\n"
        msg += f"--- Rank解锁状态 ---\n"
        max_rank = player.get("max_rank", 1)
        msg += f"  当前最高可召唤Rank: {max_rank}\n"
        for r in range(1, 10):
            unlocked = r <= max_rank
            status = "已解锁" if unlocked else "未解锁"
            msg += f"  Rank {r}: {status}\n"

        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_info 异常: {e}")
        return f"获取Raid信息失败: {e}"


def cmd_raid_summon(data: dict, user_id: str, rank_str: str) -> str:
    """玩家命令：召唤BOSS
    raid召唤N - 消耗1张挑战券，召唤Rank N普通BOSS
    raid召唤ex - 消耗1张EX券，召唤EX BOSS
    """
    try:
        if not _is_event_active(data):
            return "[RAID] 当前没有进行中的活动。"

        player = _get_player(data, user_id)
        uid = str(user_id)

        # 检查个人BOSS数量上限
        alive_bosses = [b for b in player.get("my_bosses", []) if not b.get("killed", False)]
        if len(alive_bosses) >= MAX_PERSONAL_BOSSES:
            return f"[RAID] 个人BOSS列表已满（{MAX_PERSONAL_BOSSES}个存活BOSS），请先击败现有BOSS。"

        rank_str = rank_str.strip().lower()

        if rank_str == "ex":
            # EX BOSS
            if player["tickets"].get("ex", 0) <= 0:
                return "[RAID] EX券不足！需要1张EX券才能召唤EX BOSS。"
            player["tickets"]["ex"] -= 1

            boss_card_id = _get_ex_boss_card_id()
            boss_rank = 12  # EX BOSS固定rank=12（用于奖励计算）
            boss_hp = _calc_boss_hp(1, is_ex=True)
            boss_type = "ex"
            # 获取实际角色名
            boss_name = _get_boss_name(boss_card_id, default_name="EX BOSS")
        else:
            # 普通BOSS
            try:
                rank_num = int(rank_str)
            except ValueError:
                return f"[RAID] 无效的Rank编号：{rank_str}。请输入1-9的数字，或'ex'召唤EX BOSS。"

            if rank_num < 1 or rank_num > 9:
                return "[RAID] Rank范围1-9，请输入有效数字。"

            # 检查Rank解锁
            max_rank = player.get("max_rank", 1)
            if rank_num > max_rank:
                return f"[RAID] Rank {rank_num} 尚未解锁！你需要先击杀 Rank {rank_num-1} 的BOSS。当前最高Rank: {max_rank}"

            if player["tickets"].get("challenge", 0) <= 0:
                return "[RAID] 挑战券不足！需要1张挑战券才能召唤BOSS。"
            player["tickets"]["challenge"] -= 1

            boss_card_id = _get_boss_card_id()
            boss_rank = rank_num
            boss_hp = _calc_boss_hp(rank_num, is_ex=False)
            boss_type = "normal"
            boss_name = _get_boss_name(boss_card_id, default_name="BOSS")

        boss_id = _generate_boss_id()
        new_boss = {
            "boss_id": boss_id,
            "boss_card_id": boss_card_id,
            "boss_name": boss_name,
            "boss_type": boss_type,
            "rank": boss_rank,
            "current_hp": boss_hp,
            "max_hp": boss_hp,
            "is_public": False,
            "damage_contributors": {},
            "locked": False,
            "killed": False,
        }
        player["my_bosses"].append(new_boss)
        save_event_data(data)

        type_str = "[EX]" if boss_type == "ex" else ""
        msg = (
            f"[RAID] 成功召唤 {type_str}{boss_name} (Rank {boss_rank})！\n"
            f"HP: {boss_hp:,}\n"
            f"击杀奖励池: {_calc_reward_pool(boss_rank, boss_type == 'ex')} 救援币\n"
            f"使用「raid挑战」或「raid列表」查看详情"
        )
        _qq().log_info(f"rescue_event: {uid} 召唤 {type_str} {boss_id}")
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_summon 异常: {e}")
        return f"召唤BOSS失败: {e}"


def cmd_raid_list(data: dict, user_id: str) -> str:
    """玩家命令：显示个人BOSS列表"""
    try:
        if not _is_event_active(data):
            return "[RAID] 当前没有进行中的活动。"

        player = _get_player(data, user_id)
        bosses = player.get("my_bosses", [])

        if not bosses:
            return "[RAID] 你还没有召唤任何BOSS。\n使用「raid召唤N」召唤BOSS（如 raid召唤1）。"

        msg = "[RAID] 个人BOSS列表\n"
        for i, boss in enumerate(bosses, 1):
            killed_str = " [已击败]" if boss.get("killed", False) else ""
            public_str = " [已求助]" if boss.get("is_public", False) else ""
            type_str = "[EX]" if boss.get("boss_type") == "ex" else ""
            rank = boss.get("rank", 1)
            hp = boss.get("current_hp", 0)
            max_hp = boss.get("max_hp", 1)
            hp_pct = hp / max_hp * 100 if max_hp > 0 else 0
            boss_name = boss.get("boss_name", "BOSS")
            contributors = boss.get("damage_contributors", {})
            contrib_str = f" {len(contributors)}人贡献" if contributors else ""
            msg += (
                f"{i}. {type_str}{boss_name} Rank{rank} HP:{hp:,}/{max_hp:,}({hp_pct:.1f}%)"
                f"{killed_str}{public_str}{contrib_str}\n"
            )

        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_list 异常: {e}")
        return f"获取BOSS列表失败: {e}"


def cmd_raid_public(data: dict, user_id: str) -> str:
    """玩家命令：显示公共求援列表"""
    try:
        if not _is_event_active(data):
            return "[RAID] 当前没有进行中的活动。"

        board = data.get("public_board", [])
        if not board:
            return "[RAID] 当前没有公共求援BOSS。"

        msg = "[RAID] 公共求援列表\n"
        for i, entry in enumerate(board, 1):
            requester = _get_display_name(entry.get("requester_id", "?"))
            boss_type = entry.get("boss_type", "normal")
            rank = entry.get("rank", 1)
            hp = entry.get("current_hp", 0)
            max_hp = entry.get("max_hp", 1)
            hp_pct = hp / max_hp * 100 if max_hp > 0 else 0
            contributors = entry.get("damage_contributors", {})
            type_str = "[EX]" if boss_type == "ex" else ""
            boss_name = entry.get("boss_name", "BOSS")
            contrib_str = f" {len(contributors)}人协助" if contributors else ""
            ts = entry.get("timestamp", "")
            msg += (
                f"{i}. {type_str}{boss_name} Rank{rank} HP:{hp:,}/{max_hp:,}({hp_pct:.1f}%)"
                f" 求助者:{requester}...{contrib_str} {ts}\n"
            )

        msg += f"\n使用「raid协助N」协助对应BOSS"
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_public 异常: {e}")
        return f"获取公共列表失败: {e}"


def cmd_raid_help_request(data: dict, user_id: str, index_str: str) -> str:
    """玩家命令：将个人列表第N个BOSS转移到公共求援列表"""
    try:
        if not _is_event_active(data):
            return "[RAID] 当前没有进行中的活动。"

        player = _get_player(data, user_id)
        bosses = player.get("my_bosses", [])

        try:
            idx = int(index_str) - 1
        except ValueError:
            return f"[RAID] 无效的编号：{index_str}。请输入BOSS在个人列表中的编号。"

        if idx < 0 or idx >= len(bosses):
            return f"[RAID] 无效的编号。你有 {len(bosses)} 个BOSS，请输入1-{len(bosses)}。"

        boss = bosses[idx]
        if boss.get("killed", False):
            return "[RAID] 该BOSS已被击败，无法求助。"
        if boss.get("is_public", False):
            return "[RAID] 该BOSS已经在公共求援列表中。"

        # 检查公共列表上限
        if len(data.get("public_board", [])) >= PUBLIC_BOARD_MAX:
            return f"[RAID] 公共求援列表已满（{PUBLIC_BOARD_MAX}条），请稍后再试。"

        # 转移到公共列表
        boss["is_public"] = True
        public_entry = {
            "requester_id": str(user_id),
            "owner_boss_index": idx,
            "boss_id": boss["boss_id"],
            "boss_card_id": boss.get("boss_card_id", ""),
            "boss_name": boss.get("boss_name", "BOSS"),
            "boss_type": boss["boss_type"],
            "rank": boss["rank"],
            "current_hp": boss["current_hp"],
            "max_hp": boss["max_hp"],
            "damage_contributors": dict(boss.get("damage_contributors", {})),
            "timestamp": datetime.now().strftime("%m-%d %H:%M"),
        }
        data["public_board"].append(public_entry)
        save_event_data(data)

        type_str = "[EX]" if boss.get("boss_type") == "ex" else ""
        rank = boss.get("rank", 1)
        msg = (
            f"[RAID] 已将 {type_str}Rank{rank} BOSS 发布到公共求援列表！\n"
            f"其他玩家可以通过「raid协助」来协助你击败这个BOSS。"
        )
        _qq().log_info(f"rescue_event: {user_id} 发布求助 {boss['boss_id']}")
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_help_request 异常: {e}")
        return f"发布求助失败: {e}"


def cmd_raid_challenge(data: dict, user_id: str, index_str: str,
                        battle_system=None) -> str:
    """玩家命令：用当前队伍挑战个人列表第N个BOSS"""
    try:
        # 获取角色列表（用于VS图）
        try:
            characters = _qq().get_characters()
        except Exception:
            characters = []

        if not _is_event_active(data):
            return "[RAID] 当前没有进行中的活动。"

        player = _get_player(data, user_id)
        uid = str(user_id)
        bosses = player.get("my_bosses", [])

        try:
            idx = int(index_str) - 1
        except ValueError:
            return f"[RAID] 无效的编号：{index_str}"

        if idx < 0 or idx >= len(bosses):
            return f"[RAID] 无效的编号。你有 {len(bosses)} 个BOSS，请输入1-{len(bosses)}。"

        boss = bosses[idx]
        if boss.get("killed", False):
            return "[RAID] 该BOSS已被击败。"

        # 检查BOSS是否被锁定（其他人正在挑战）
        boss_id = boss["boss_id"]
        if data.get("boss_fighting", {}).get(boss_id):
            fighting_uid = data["boss_fighting"][boss_id]
            return f"[RAID] 该BOSS正在被挑战中，请稍后再试。"

        # 获取当前活跃槽位
        slot_info = _get_active_slot_info(user_id)
        if slot_info is None:
            return "[RAID] 请先选择Raid队伍槽位（预设7-11）再挑战。\n使用队伍系统的预设槽位7-11。"

        slot_key = slot_info["slot_key"]
        slot_num = slot_info["slot"]
        team_data = slot_info["team_data"]

        # 检查队伍
        check_err = _check_raid_team(user_id, slot_key, player)
        if check_err:
            return f"[RAID] {check_err}"

        # 检查角色去重
        dup_err = _check_raid_slot_duplicate(user_id)
        if dup_err:
            return f"[RAID] {dup_err}"

        # 检查队伍是否有角色
        battle_cards = team_data.get("battle_cards", [])
        has_cards = any(c is not None for c in battle_cards)
        if not has_cards:
            return "[RAID] 当前队伍是空的！请先在配队系统中编队后再挑战。"

        # 锁定BOSS
        data.setdefault("boss_fighting", {})[boss_id] = uid

        # 获取BOSS数据
        boss_card_id = boss.get("boss_card_id", "") or (_get_ex_boss_card_id() if boss.get("boss_type") == "ex" else _get_boss_card_id())
        boss_hp = boss.get("current_hp", boss.get("max_hp", 0))
        boss_max_hp = boss.get("max_hp", boss_hp)
        is_ex = boss.get("boss_type") == "ex"
        boss_rank = boss.get("rank", 1)
        boss_name = boss.get("boss_name", _get_boss_name(boss_card_id, battle_system, "BOSS"))

        try:
            # 构建BOSS额外角色数据（使用实际角色属性）
            boss_extra = _build_boss_extra_chars(
                boss_card_id=boss_card_id,
                boss_name=boss_name,
                boss_hp=boss_hp,
                battle_system=battle_system,
            )

            # 恢复队伍血量（如果有保存）
            saved = player.get("team_hp_saved", {}).get(slot_key)
            player_initial_hp = None
            if saved:
                modified_team = copy.deepcopy(team_data)
                modified_team["_raid_saved_hp"] = saved
                team_data = modified_team
                # 构建player_initial_hp: {card_id: hp}（阵亡的角色HP设为0）
                bc = team_data.get("battle_cards", [])
                saved_hp = saved.get("hp", [])
                saved_alive = saved.get("alive", [])
                player_initial_hp = {}
                for i, cid in enumerate(bc):
                    if cid is not None:
                        cid_str = str(cid)
                        if i < len(saved_alive) and not saved_alive[i]:
                            player_initial_hp[cid_str] = 0  # 阵亡
                        elif i < len(saved_hp):
                            player_initial_hp[cid_str] = max(1, saved_hp[i])

            # 执行战斗
            if battle_system is not None:
                try:
                    result = battle_system.start_boss_battle(
                        player_team=team_data,
                        boss_card_id=boss_card_id,
                        initial_sp=300,
                        extra_characters=boss_extra,
                        player_initial_hp=player_initial_hp,
                        boss_hp_override=boss_hp,
                    )
                except Exception as e:
                    import traceback
                    _qq().log_error(f"rescue_event 战斗执行异常: {e}\n{traceback.format_exc()}")
                    result = _simulate_battle(team_data, boss_hp)
            else:
                result = _simulate_battle(team_data, boss_hp)

            # 计算伤害（cap到BOSS剩余HP，避免超额伤害）
            damage_dealt = result.get("damage_dealt", 0)
            # 超额伤害不计入：最多只能造成BOSS当前剩余HP的伤害
            damage_dealt = min(damage_dealt, boss_hp)  # boss_hp是战斗前BOSS的HP
            damage_pct = damage_dealt / boss_max_hp * 100 if boss_max_hp > 0 else 0

            # 记录伤害
            boss["damage_contributors"][uid] = boss["damage_contributors"].get(uid, 0) + damage_dealt
            boss["current_hp"] = max(0, boss["current_hp"] - damage_dealt)

            # 更新挑战次数
            player.setdefault("daily_challenge_count", {})[slot_key] = \
                player["daily_challenge_count"].get(slot_key, 0) + 1

            # 保存队伍剩余血量（按6个位置保存，与battle_cards索引对齐）
            player_units = result.get("player_units", [])
            if player_units:
                bc_count = len(team_data.get("battle_cards", []))
                hp_list = [0] * bc_count
                alive_list = [False] * bc_count
                maxhp_list = [10000] * bc_count
                for u in player_units:
                    if u.get("is_assist"):
                        continue
                    pos = u.get("position", -1)
                    pos_map = {0: 0, 2: 1, 4: 2, 5: 3, 6: 4, 7: 5}
                    bc_idx = pos_map.get(pos, -1)
                    if 0 <= bc_idx < bc_count:
                        hp_list[bc_idx] = u.get("hp", 0)
                        alive_list[bc_idx] = u.get("alive", True)
                        maxhp_list[bc_idx] = u.get("max_hp", 10000)
                player.setdefault("team_hp_saved", {})[slot_key] = {
                    "hp": hp_list,
                    "alive": alive_list,
                    "max_hp": maxhp_list,
                }

            # 检查队伍是否全灭
            player_survived = result.get("player_survived", 0)
            player_total = result.get("player_total", 1)
            all_dead = player_survived == 0

            # 检查使用次数
            current_count = player["daily_challenge_count"].get(slot_key, 0)
            count_maxed = current_count >= DAILY_CHALLENGE_LIMIT

            # 锁定队伍（全灭或达上限）
            if all_dead or count_maxed:
                player.setdefault("daily_locked_teams", {})[slot_key] = True

            # 检查BOSS是否被击杀
            boss_killed = boss["current_hp"] <= 0
            reward_msg = ""
            if boss_killed:
                boss["killed"] = True

                # 从个人BOSS列表移除
                my_bosses = player.get("my_bosses", [])
                player["my_bosses"] = [b for b in my_bosses if b.get("boss_id") != boss_id]

                # 从公共求援列表移除
                public_board = data.get("public_board", [])
                data["public_board"] = [e for e in public_board if e.get("boss_id") != boss_id]

                # 分配奖励
                reward_msg = _distribute_kill_rewards(data, player, boss, uid)

            # 更新HS（绝对伤害值）
            hs_today = player.get("hs_today", 0)
            if damage_dealt > hs_today:
                player["hs_today"] = damage_dealt

            # 解锁BOSS（在保存前清除）
            data.get("boss_fighting", {}).pop(boss_id, None)

            save_event_data(data)

            # 尝试生成VS图
            vs_img_path = None
            try:
                boss_team_data = {"battle_cards": [None, None, boss_card_id] + [None] * 3, "assist_cards": [None] * 6}
                vs_img_path = _build_vs_team_image(team_data, boss_team_data, characters)
            except Exception:
                vs_img_path = None

            # 构建结果消息
            type_str = "[EX] " if is_ex else ""
            msg = (
                f"[RAID] 挑战结果\n"
                f"BOSS: {type_str}{boss_name} (Rank {boss_rank})\n"
                f"伤害: {damage_dealt:,} ({damage_pct:.2f}%)\n"
                f"队伍存活: {player_survived}/{player_total}\n"
                f"BOSS剩余HP: {boss['current_hp']:,}/{boss_max_hp:,}\n"
                f"今日挑战次数: {current_count}/{DAILY_CHALLENGE_LIMIT}"
            )
            if all_dead:
                msg += "\n队伍全灭，该队伍今日已锁定。"
            if boss_killed:
                msg += f"\n*** BOSS已被击败！***\n{reward_msg}"

            if vs_img_path:
                msg += f"\n[RAID_VS_IMAGE]{vs_img_path}"

            _qq().log_info(
                f"rescue_event: {uid} 挑战个人BOSS {boss_id} "
                f"伤害{damage_pct:.2f}% 击杀={boss_killed}"
            )
            return msg

        except Exception as e:
            # 确保解锁BOSS
            data.get("boss_fighting", {}).pop(boss_id, None)
            raise

        finally:
            # 确保解锁BOSS
            data.get("boss_fighting", {}).pop(boss_id, None)

    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_challenge 异常: {e}")
        return f"挑战BOSS失败: {e}"


def cmd_raid_assist(data: dict, user_id: str, index_str: str,
                     battle_system=None) -> str:
    """玩家命令：用当前队伍挑战公共列表第N个BOSS"""
    try:
        # 获取角色列表（用于VS图）
        try:
            characters = _qq().get_characters()
        except Exception:
            characters = []

        if not _is_event_active(data):
            return "[RAID] 当前没有进行中的活动。"

        uid = str(user_id)
        board = data.get("public_board", [])

        try:
            idx = int(index_str) - 1
        except ValueError:
            return f"[RAID] 无效的编号：{index_str}"

        if idx < 0 or idx >= len(board):
            return f"[RAID] 无效的编号。公共列表有 {len(board)} 个BOSS，请输入1-{len(board)}。"

        entry = board[idx]
        if entry.get("killed", False):
            return "[RAID] 该BOSS已被击败。"

        boss_id = entry["boss_id"]

        # 不能协助自己的BOSS
        if entry.get("requester_id") == uid:
            return "[RAID] 不能协助自己发布的BOSS，请使用「raid挑战」。"

        # 检查BOSS是否被锁定
        if data.get("boss_fighting", {}).get(boss_id):
            return "[RAID] 该BOSS正在被其他人挑战中，请稍后再试。"

        # 获取当前活跃槽位
        player = _get_player(data, user_id)
        slot_info = _get_active_slot_info(user_id)
        if slot_info is None:
            return "[RAID] 请先选择Raid队伍槽位（预设7-11）再协助。"

        slot_key = slot_info["slot_key"]
        slot_num = slot_info["slot"]
        team_data = slot_info["team_data"]

        # 检查队伍
        check_err = _check_raid_team(user_id, slot_key, player)
        if check_err:
            return f"[RAID] {check_err}"

        # 检查角色去重
        dup_err = _check_raid_slot_duplicate(user_id)
        if dup_err:
            return f"[RAID] {dup_err}"

        # 检查队伍角色
        battle_cards = team_data.get("battle_cards", [])
        has_cards = any(c is not None for c in battle_cards)
        if not has_cards:
            return "[RAID] 当前队伍是空的！请先编队。"

        # 锁定BOSS
        data.setdefault("boss_fighting", {})[boss_id] = uid

        # 获取BOSS数据
        boss_card_id = entry.get("boss_card_id", "") or (_get_ex_boss_card_id() if entry.get("boss_type") == "ex" else _get_boss_card_id())
        boss_hp = entry.get("current_hp", entry.get("max_hp", 0))
        boss_max_hp = entry.get("max_hp", boss_hp)
        is_ex = entry.get("boss_type") == "ex"
        boss_rank = entry.get("rank", 1)
        boss_name = entry.get("boss_name", _get_boss_name(boss_card_id, battle_system, "BOSS"))

        try:
            boss_extra = _build_boss_extra_chars(
                boss_card_id=boss_card_id,
                boss_name=boss_name,
                boss_hp=boss_hp,
                battle_system=battle_system,
            )

            # 恢复队伍血量（如果有保存）
            saved = player.get("team_hp_saved", {}).get(slot_key)
            player_initial_hp = None
            if saved:
                modified_team = copy.deepcopy(team_data)
                modified_team["_raid_saved_hp"] = saved
                team_data = modified_team
                bc = team_data.get("battle_cards", [])
                saved_hp = saved.get("hp", [])
                saved_alive = saved.get("alive", [])
                player_initial_hp = {}
                for i, cid in enumerate(bc):
                    if cid is not None:
                        cid_str = str(cid)
                        if i < len(saved_alive) and not saved_alive[i]:
                            player_initial_hp[cid_str] = 0
                        elif i < len(saved_hp):
                            player_initial_hp[cid_str] = max(1, saved_hp[i])

            # 执行战斗
            if battle_system is not None:
                try:
                    result = battle_system.start_boss_battle(
                        player_team=team_data,
                        boss_card_id=boss_card_id,
                        initial_sp=300,
                        extra_characters=boss_extra,
                        player_initial_hp=player_initial_hp,
                        boss_hp_override=boss_hp,
                    )
                except Exception as e:
                    import traceback
                    _qq().log_error(f"rescue_event 协助战斗执行异常: {e}\n{traceback.format_exc()}")
                    result = _simulate_battle(team_data, boss_hp)
            else:
                result = _simulate_battle(team_data, boss_hp)

            # 超额伤害cap
            damage_dealt = result.get("damage_dealt", 0)
            damage_dealt = min(damage_dealt, boss_hp)
            damage_pct = damage_dealt / boss_max_hp * 100 if boss_max_hp > 0 else 0

            # 更新公共列表和拥有者的BOSS数据
            entry["damage_contributors"][uid] = entry["damage_contributors"].get(uid, 0) + damage_dealt
            entry["current_hp"] = max(0, entry["current_hp"] - damage_dealt)

            # 同步到拥有者的个人BOSS数据
            owner_id = entry.get("requester_id", "")
            owner_boss_idx = entry.get("owner_boss_index", -1)
            if owner_id and owner_id in data.get("players", {}):
                owner = data["players"][owner_id]
                if 0 <= owner_boss_idx < len(owner.get("my_bosses", [])):
                    owner_boss = owner["my_bosses"][owner_boss_idx]
                    owner_boss["damage_contributors"][uid] = \
                        owner_boss["damage_contributors"].get(uid, 0) + damage_dealt
                    owner_boss["current_hp"] = max(0, owner_boss["current_hp"] - damage_dealt)
                    if entry["current_hp"] <= 0:
                        owner_boss["killed"] = True

            # 更新挑战次数
            player.setdefault("daily_challenge_count", {})[slot_key] = \
                player["daily_challenge_count"].get(slot_key, 0) + 1

            # 保存队伍血量（按6个位置保存，与battle_cards索引对齐）
            player_units = result.get("player_units", [])
            if player_units:
                bc_count = len(team_data.get("battle_cards", []))
                hp_list = [0] * bc_count
                alive_list = [False] * bc_count
                maxhp_list = [10000] * bc_count
                for u in player_units:
                    if u.get("is_assist"):
                        continue
                    pos = u.get("position", -1)
                    pos_map = {0: 0, 2: 1, 4: 2, 5: 3, 6: 4, 7: 5}
                    bc_idx = pos_map.get(pos, -1)
                    if 0 <= bc_idx < bc_count:
                        hp_list[bc_idx] = u.get("hp", 0)
                        alive_list[bc_idx] = u.get("alive", True)
                        maxhp_list[bc_idx] = u.get("max_hp", 10000)
                player.setdefault("team_hp_saved", {})[slot_key] = {
                    "hp": hp_list,
                    "alive": alive_list,
                    "max_hp": maxhp_list,
                }

            # 队伍状态检查
            player_survived = result.get("player_survived", 0)
            player_total = result.get("player_total", 1)
            all_dead = player_survived == 0
            current_count = player["daily_challenge_count"].get(slot_key, 0)
            count_maxed = current_count >= DAILY_CHALLENGE_LIMIT

            if all_dead or count_maxed:
                player.setdefault("daily_locked_teams", {})[slot_key] = True

            # 检查击杀
            boss_killed = entry["current_hp"] <= 0
            reward_msg = ""
            if boss_killed:
                entry["killed"] = True

                # 从拥有者的个人BOSS列表移除
                if owner_id and owner_id in data.get("players", {}):
                    owner = data["players"][owner_id]
                    my_bosses = owner.get("my_bosses", [])
                    owner["my_bosses"] = [b for b in my_bosses if b.get("boss_id") != boss_id]

                # 从公共求援列表移除
                data["public_board"] = [e for e in data.get("public_board", []) if e.get("boss_id") != boss_id]

                # 分配奖励
                if owner_id and owner_id in data.get("players", {}):
                    owner = data["players"][owner_id]
                    if 0 <= owner_boss_idx < len(owner.get("my_bosses", [])):
                        owner_boss = owner["my_bosses"][owner_boss_idx]
                        reward_msg = _distribute_kill_rewards(data, owner, owner_boss, uid, is_assist=True)

            # 更新HS（绝对伤害值）
            hs_today = player.get("hs_today", 0)
            if damage_dealt > hs_today:
                player["hs_today"] = damage_dealt

            # 解锁BOSS（在保存前清除）
            data.get("boss_fighting", {}).pop(boss_id, None)

            save_event_data(data)

            # 尝试生成VS图
            vs_img_path = None
            try:
                boss_team_data = {"battle_cards": [None, None, boss_card_id] + [None] * 3, "assist_cards": [None] * 6}
                vs_img_path = _build_vs_team_image(team_data, boss_team_data, characters)
            except Exception:
                vs_img_path = None

            # 构建结果
            type_str = "[EX] " if is_ex else ""
            msg = (
                f"[RAID] 协助结果\n"
                f"BOSS: {type_str}{boss_name} (Rank {boss_rank})\n"
                f"伤害: {damage_dealt:,} ({damage_pct:.2f}%)\n"
                f"队伍存活: {player_survived}/{player_total}\n"
                f"BOSS剩余HP: {entry['current_hp']:,}/{boss_max_hp:,}\n"
                f"今日挑战次数: {current_count}/{DAILY_CHALLENGE_LIMIT}"
            )
            if all_dead:
                msg += "\n队伍全灭，该队伍今日已锁定。"
            if boss_killed:
                msg += f"\n*** BOSS已被击败！***\n{reward_msg}"

            if vs_img_path:
                msg += f"\n[RAID_VS_IMAGE]{vs_img_path}"

            _qq().log_info(
                f"rescue_event: {uid} 协助 {boss_id} "
                f"伤害{damage_pct:.2f}% 击杀={boss_killed}"
            )
            return msg

        except Exception as e:
            data.get("boss_fighting", {}).pop(boss_id, None)
            raise
        finally:
            data.get("boss_fighting", {}).pop(boss_id, None)

    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_assist 异常: {e}")
        return f"协助BOSS失败: {e}"


def _distribute_kill_rewards(data: dict, owner: dict, boss: dict,
                              killer_id: str = "", is_assist: bool = False) -> str:
    """分配击杀奖励（按伤害%比例分配救援币）"""
    try:
        boss_max_hp = boss.get("max_hp", 1)
        contributors = boss.get("damage_contributors", {})
        if not contributors:
            return ""

        # 计算总伤害
        total_damage = sum(contributors.values())
        if total_damage <= 0:
            return ""

        is_ex = boss.get("boss_type") == "ex"
        boss_rank = boss.get("rank", 1)
        total_reward = _calc_reward_pool(boss_rank, is_ex)

        lines = [f"--- 击杀奖励分配（总池: {total_reward} 救援币）---"]
        for cid, dmg in contributors.items():
            pct = dmg / boss_max_hp * 100
            reward = int(total_reward * pct / 100)
            if reward > 0:
                if cid in data.get("players", {}):
                    data["players"][cid]["rescue_coins"] = data["players"][cid].get("rescue_coins", 0) + reward
                lines.append(f"  {_get_display_name(cid)} 伤害{pct:.1f}% 获得{reward}救援币")

        # 从公共列表移除已击败的BOSS
        boss_id = boss.get("boss_id", "")
        data["public_board"] = [
            e for e in data.get("public_board", [])
            if e.get("boss_id") != boss_id
        ]

        # BOSS拥有者Rank升级：当玩家召唤的Rank N BOSS被击杀时，max_rank升为N+1
        rank_upgrade_msg = ""
        if not is_ex:
            boss_rank = boss.get("rank", 1)
            owner_max = owner.get("max_rank", 1)
            if boss_rank >= owner_max and owner_max < 9:
                owner["max_rank"] = owner_max + 1
                rank_upgrade_msg = f"\n[Rank解锁] BOSS拥有者现在可以召唤 Rank {owner_max + 1} 的BOSS了！"

        return "\n".join(lines) + rank_upgrade_msg
    except Exception as e:
        _qq().log_error(f"rescue_event _distribute_kill_rewards 异常: {e}")
        return "奖励分配出错"


def cmd_raid_ranking(data: dict, user_id: str, top_n: int = 10) -> str:
    """玩家命令：显示HS和RS排行榜"""
    try:
        players = data.get("players", {})
        if not players:
            return "[RAID] 还没有玩家参与。"

        uid = str(user_id)

        # RS排行
        sorted_by_rs = sorted(
            players.items(),
            key=lambda x: x[1].get("rs", 0),
            reverse=True,
        )

        # HS排行（今日）
        sorted_by_hs = sorted(
            players.items(),
            key=lambda x: x[1].get("hs_today", 0),
            reverse=True,
        )

        msg = "[RAID] 排行榜（前10名）\n"
        msg += "=== RS排行（累计）===\n"
        for i, (pid, pdata) in enumerate(sorted_by_rs[:top_n], 1):
            rs = pdata.get("rs", 0)
            is_me = " <- 你" if pid == uid else ""
            reward = _get_reward_for_rank(i)
            title = f"[{reward['title']}]" if reward else ""
            msg += f"#{i} {title}{_get_display_name(pid)} RS:{rs:.0f}{is_me}\n"

        msg += "\n=== 今日HS排行 ===\n"
        for i, (pid, pdata) in enumerate(sorted_by_hs[:top_n], 1):
            hs = pdata.get("hs_today", 0)
            is_me = " <- 你" if pid == uid else ""
            msg += f"#{i} {_get_display_name(pid)} HS:{hs:,}{is_me}\n"

        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_ranking 异常: {e}")
        return f"获取排行榜失败: {e}"


def cmd_raid_exchange(data: dict, user_id: str, key: str, amount: int) -> str:
    """玩家命令：兑换商店
    raid兑换挑战券3 - 兑换3张挑战券
    raid兑换呱太500 - 兑换500组呱太（每组5000）
    """
    try:
        player = _get_player(data, user_id)
        coins = player.get("rescue_coins", 0)

        # 查找商品
        shop_item = None
        for item in EXCHANGE_SHOP:
            if item["key"] == key:
                shop_item = item
                break

        if shop_item is None:
            # 显示商店
            available_keys = [item["key"] for item in EXCHANGE_SHOP]
            msg = f"[RAID] 未知商品: {key}\n可用商品: {', '.join(available_keys)}"
            return msg

        # 计算总花费
        total_cost = shop_item["cost"] * amount
        if coins < total_cost:
            return (
                f"[RAID] 救援币不足！\n"
                f"需要: {total_cost} 救援币（{shop_item['cost']} x {amount}）\n"
                f"当前: {coins} 救援币"
            )

        # 扣除救援币
        player["rescue_coins"] = coins - total_cost

        # 发放商品
        if shop_item.get("ticket_type"):
            # 票券类
            ticket_type = shop_item["ticket_type"]
            ticket_amount = shop_item["amount"] * amount
            player["tickets"][ticket_type] = player["tickets"].get(ticket_type, 0) + ticket_amount
            result_msg = f"获得 {ticket_amount} 张{shop_item['key']}"
        elif shop_item.get("type") == "gacha":
            # 呱太
            gacha_total = shop_item["amount"] * amount
            try:
                qq = _qq()
                if hasattr(qq, 'add_gacha'):
                    qq.add_gacha(str(user_id), gacha_total)
            except Exception:
                pass
            result_msg = f"获得 {gacha_total} 呱太"
        elif shop_item.get("type") == "blue_crystal":
            # 蓝碎片
            blue_total = shop_item["amount"] * amount
            try:
                qq = _qq()
                if hasattr(qq, 'add_blue_crystal'):
                    qq.add_blue_crystal(str(user_id), blue_total)
            except Exception:
                pass
            result_msg = f"获得 {blue_total} 蓝碎片"
        else:
            result_msg = f"获得 {key} x{amount}"

        save_event_data(data)

        msg = (
            f"[RAID] 兑换成功！\n"
            f"{result_msg}\n"
            f"消耗救援币: {total_cost}\n"
            f"剩余救援币: {player['rescue_coins']}"
        )
        _qq().log_info(f"rescue_event: {user_id} 兑换 {key}x{amount} 花费{total_cost}币")
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_exchange 异常: {e}")
        return f"兑换失败: {e}"


def cmd_raid_team(user_id: str) -> str:
    """玩家命令：显示队伍信息（标注raid槽位）"""
    try:
        qq = _qq()
        team_system = getattr(qq, 'team_system', None)
        if team_system is None:
            try:
                import team_system as ts_mod
                team_system = ts_mod
            except ImportError:
                return "[RAID] 队伍系统不可用。"

        presets_data = team_system.load_presets(str(user_id))
        presets = presets_data.get("presets", [])
        active_slot = presets_data.get("active_slot", 0)

        lines = ["[RAID] 队伍预设信息"]
        for i in range(len(presets)):
            slot_num = i + 1
            preset = presets[i]
            marker = " <- 当前" if slot_num == active_slot else ""
            raid_marker = " [Raid]" if RAID_SLOT_MIN <= slot_num <= RAID_SLOT_MAX else ""

            if preset is None:
                lines.append(f"  槽{slot_num}: 空{marker}{raid_marker}")
            else:
                b_count = sum(1 for c in preset.get("battle_cards", []) if c)
                a_count = sum(1 for c in preset.get("assist_cards", []) if c)
                lines.append(f"  槽{slot_num}: 战斗{b_count}+支援{a_count}{marker}{raid_marker}")

        lines.append(f"\nRaid队伍使用槽位 7-11")
        lines.append(f"选择槽位后使用「raid挑战」或「raid协助」")
        return "\n".join(lines)
    except Exception as e:
        _qq().log_error(f"rescue_event cmd_raid_team 异常: {e}")
        return f"获取队伍信息失败: {e}"


# ========== 每日重置 ==========
def daily_raid_reset(data: dict) -> str:
    """每日raid重置：发券、解锁队伍、重置挑战次数（由qq_bot_ws在12点调用）"""
    try:
        today = _today_str()
        extra_msg = ""

        # 检查活动是否到期，自动结算
        if data.get("active", False) and _is_past_end(data) and not data.get("settled", False):
            settle_result = settle_event(data)
            extra_msg = f"\n{settle_result}"

        # 只在活动进行中（或未结算）时才发券和重置
        if data.get("active", False):
            for uid, player in data.get("players", {}).items():
                # 发10张挑战券+10张救援券
                player.setdefault("tickets", {})
                player["tickets"]["challenge"] = player["tickets"].get("challenge", 0) + 10
                player["tickets"]["rescue"] = player["tickets"].get("rescue", 0) + 10
                # 重置每日挑战次数
                player["daily_challenge_count"] = {}
                # 解锁所有队伍
                player["daily_locked_teams"] = {}
                # 清除保存的队伍血量（新的一天重新开始）
                player["team_hp_saved"] = {}
                # 更新RS（把昨日HS加到RS）
                if player.get("hs_today", 0) > 0:
                    player["rs"] = player.get("rs", 0) + player["hs_today"]
                    player.setdefault("hs_history", {})[today] = player["hs_today"]
                player["hs_today"] = 0
            save_event_data(data)
            _qq().log_info(f"rescue_event: 每日raid重置完成 {today}")

        result = f"[RAID] 每日重置完成"
        if extra_msg:
            result += extra_msg
        return result
    except Exception as e:
        _qq().log_error(f"rescue_event daily_raid_reset 异常: {e}")
        return f"每日重置失败: {e}"


# ========== 命令路由 ==========

def handle_admin_command(data, user_id: str, message: str) -> Optional[str]:
    """管理员命令路由入口"""
    try:
        if not _is_admin(user_id):
            return None

        msg = message.strip()
        if not msg.startswith("raid"):
            return None

        # 去掉 "raid" 前缀
        rest = msg[4:].strip() if len(msg) > 4 else ""

        # 首次调用时 data 可能为 None
        if data is None:
            data = load_event_data()

        # 管理员命令列表
        if rest == "开启" or rest.startswith("开启"):
            # raid开启 或 raid开启7
            days = 7
            parts = rest.split()
            if len(parts) > 1:
                try:
                    days = int(parts[1])
                    days = max(1, min(30, days))
                except ValueError:
                    days = 7
            return cmd_raid_start(data, days)

        elif rest == "关闭":
            return cmd_raid_stop(data)

        elif rest == "状态":
            return cmd_raid_status(data)

        elif rest == "结算":
            return settle_event(data)

        elif rest.startswith("发券"):
            # raid发券 用户ID 类型 数量
            # 支持格式: raid发券 user1 challenge 10 / raid发券 user1 挑战券 10
            parts = rest.split()
            if len(parts) >= 4:
                target_uid = parts[1]
                ticket_type = parts[2]
                amount = parts[3]
            else:
                # 尝试正则匹配: 发券(用户ID)(类型关键词)(数字)
                ticket_map = {'挑战券': 'challenge', '救援券': 'rescue', 'EX券': 'ex',
                              'ex': 'ex', 'challenge': 'challenge', 'rescue': 'rescue'}
                give_match = re.search(r'发券\s*(\S+?)\s*(challenge|rescue|ex|挑战券|救援券|EX券)\s*(\d+)', message)
                if not give_match:
                    # 无空格: 发券user1挑战券10 → 需要更灵活的匹配
                    give_match = re.search(r'发券(\S+?)(?:挑战券|challenge)(\d+)', message)
                    if give_match:
                        target_uid = give_match.group(1)
                        ticket_type = 'challenge'
                        amount = give_match.group(2)
                    else:
                        give_match = re.search(r'发券(\S+?)(?:救援券|rescue)(\d+)', message)
                        if give_match:
                            target_uid = give_match.group(1)
                            ticket_type = 'rescue'
                            amount = give_match.group(2)
                        else:
                            give_match = re.search(r'发券(\S+?)(?:EX券|ex)(\d+)', message)
                            if give_match:
                                target_uid = give_match.group(1)
                                ticket_type = 'ex'
                                amount = give_match.group(2)
                if not give_match and len(parts) < 4:
                    return (
                        "[RAID] 发券格式: raid发券 用户ID 类型 数量\n"
                        f"类型: challenge(挑战券) / rescue(救援券) / ex(EX券)\n"
                        f"示例: raid发券 123456 challenge 5"
                    )
            # 标准化类型名
            ticket_type_map = {'挑战券': 'challenge', '救援券': 'rescue', 'EX券': 'ex',
                               'challenge': 'challenge', 'rescue': 'rescue', 'ex': 'ex'}
            ticket_type = ticket_type_map.get(ticket_type, ticket_type)
            try:
                amount = int(amount)
                amount = max(1, min(999, amount))
            except (ValueError, UnboundLocalError):
                return "[RAID] 数量必须是数字。"
            return cmd_raid_give_ticket(data, user_id, target_uid, ticket_type, amount)

        return None  # 不是管理员命令，交给玩家命令处理

    except Exception as e:
        _qq().log_error(f"rescue_event handle_admin_command 异常: {e}")
        return f"管理员命令处理失败: {e}"


def handle_player_command(data, user_id: str, message: str,
                            battle_system=None) -> Optional[str]:
    """玩家命令路由入口"""
    try:
        msg = message.strip()
        if not msg.startswith("raid"):
            return None

        # 去掉 "raid" 前缀
        rest = msg[4:].strip() if len(msg) > 4 else ""

        # 首次调用时 data 可能为 None
        if data is None:
            data = load_event_data()

        # 空命令 -> 显示信息
        if rest == "":
            return cmd_raid_info(data, user_id)

        # raid召唤N 或 raid召唤ex
        if rest.startswith("召唤"):
            rank_str = rest[2:].strip()
            if not rank_str:
                return "[RAID] 用法: raid召唤N（N=1-9）或 raid召唤ex"
            return cmd_raid_summon(data, user_id, rank_str)

        # raid列表
        elif rest == "列表":
            return cmd_raid_list(data, user_id)

        # raid公告
        elif rest == "公告":
            return cmd_raid_public(data, user_id)

        # raid求助N
        elif rest.startswith("求助"):
            idx_str = rest[2:].strip()
            if not idx_str:
                return "[RAID] 用法: raid求助N（N为个人BOSS列表编号）"
            return cmd_raid_help_request(data, user_id, idx_str)

        # raid挑战N
        elif rest.startswith("挑战"):
            idx_str = rest[2:].strip()
            if not idx_str:
                return "[RAID] 用法: raid挑战N（N为个人BOSS列表编号）"
            return cmd_raid_challenge(data, user_id, idx_str, battle_system)

        # raid协助N
        elif rest.startswith("协助"):
            idx_str = rest[2:].strip()
            if not idx_str:
                return "[RAID] 用法: raid协助N（N为公共求援列表编号）"
            return cmd_raid_assist(data, user_id, idx_str, battle_system)

        # raid排行
        elif rest == "排行":
            return cmd_raid_ranking(data, user_id)

        # raid帮助
        elif rest == "帮助" or rest == "help":
            return _show_raid_help()

        # raid兑换
        elif rest.startswith("兑换"):
            exchange_str = rest[2:].strip()
            if not exchange_str:
                # 显示商店
                return _show_exchange_shop(data, user_id)
            # 解析: raid兑换挑战券3 或 raid兑换呱太500
            result = _parse_exchange(exchange_str)
            if result is None:
                return (
                    f"[RAID] 兑换格式: raid兑换商品名数量\n"
                    f"示例: raid兑换挑战券3 / raid兑换呱太500 / raid兑换蓝碎片2\n"
                    f"可用商品: {', '.join(item['key'] for item in EXCHANGE_SHOP)}"
                )
            key, amount = result
            return cmd_raid_exchange(data, user_id, key, amount)

        # raid队伍
        elif rest == "队伍":
            return cmd_raid_team(user_id)

        return None

    except Exception as e:
        _qq().log_error(f"rescue_event handle_player_command 异常: {e}")
        return f"命令处理失败: {e}"


def _show_raid_help() -> str:
    """显示RAID帮助信息"""
    return (
        "[RAID] 帮助\n"
        "=== 玩家命令 ===\n"
        "raid - 查看活动状态和个人进度\n"
        "raid召唤N - 召唤Rank N普通BOSS（消耗挑战券，需解锁）\n"
        "raid召唤ex - 召唤EX BOSS（消耗EX券）\n"
        "raid列表 - 查看个人BOSS列表\n"
        "raid公告 - 查看公共求援列表\n"
        "raid求助N - 将个人BOSS转到公共求援列表\n"
        "raid挑战N - 挑战个人BOSS（需raid队槽位7-11）\n"
        "raid协助N - 协助公共BOSS\n"
        "raid排行 - 查看HS/RS排行榜\n"
        "raid兑换xx数量 - 兑换商店（如raid兑换挑战券3）\n"
        "raid帮助 - 显示本帮助\n\n"
        "=== 队伍系统 ===\n"
        "队伍槽位7-11为RAID专用槽位\n"
        "RAID队每天每队最多5次挑战（跨BOSS共享）\n"
        "队伍血量跨局继承，每日结算刷新\n"
        "5支RAID队之间不能使用重复角色\n\n"
        "=== 奖励规则 ===\n"
        "Rank N击杀奖励池: 9*N 救援币（EX=108币）\n"
        "按伤害百分比分配，只有击杀时才发放\n"
        "HS = 今日单局最高绝对伤害\n"
        "RS = 周期内每日HS累计"
    )


def _show_exchange_shop(data: dict, user_id: str) -> str:
    """显示兑换商店"""
    try:
        player = _get_player(data, user_id)
        coins = player.get("rescue_coins", 0)
        msg = "[RAID] 兑换商店\n"
        msg += f"当前救援币: {coins}\n"
        msg += "--- 商品列表 ---\n"
        for i, item in enumerate(EXCHANGE_SHOP):
            can_afford = "O" if coins >= item["cost"] else "X"
            msg += f"{item['key']} — {item['cost']}币/个 [{can_afford}]\n"
        msg += (
            f"\n用法: raid兑换商品名数量\n"
            f"示例: raid兑换挑战券3（3张挑战券=花费30币）\n"
            f"      raid兑换呱太500（500组x5000=花费15000币）"
        )
        return msg
    except Exception as e:
        _qq().log_error(f"rescue_event _show_exchange_shop 异常: {e}")
        return f"获取商店信息失败: {e}"


def _parse_exchange(text: str) -> Optional[tuple]:
    """解析兑换命令文本
    raid兑换挑战券3 -> ("挑战券", 3)
    raid兑换呱太500 -> ("呱太", 500)
    返回 (key, amount) 或 None
    """
    # 尝试从末尾提取数字
    match = re.match(r'^(.+?)(\d+)$', text.strip())
    if not match:
        return None

    key = match.group(1)
    try:
        amount = int(match.group(2))
    except ValueError:
        return None

    if amount <= 0:
        return None

    # 验证商品是否存在
    for item in EXCHANGE_SHOP:
        if item["key"] == key:
            return (key, amount)

    return None
