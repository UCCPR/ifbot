"""
魔法禁书目录幻想收束 - 战斗系统
基于model文件夹战斗模拟器的核心逻辑重构

核心伤害公式：
攻击面板 = (B卡攻击 + A卡攻击) * (同色 ? 1.05 : 1)
攻击 = 攻击面板 * (1 + 攻击倍率) + 附加攻击
伤害 = 攻击^2 / (攻击 + 防御)

属性克制：
红克绿、绿克蓝、蓝克红（循环）
黄紫互相克制
克制倍率：1.5，被克制：0.6
超属性对非超属性：额外1.2倍率
"""

import os
import json
import random
import math
import copy
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


# ========== 日志模块 ==========
BASE_DIR = Path(__file__).parent
INFO_DIR = BASE_DIR / "info"
INFO_DIR.mkdir(exist_ok=True)


def log_info(message: str):
    """记录普通信息"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = INFO_DIR / "battle_info.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [INFO] {message}\n")


def log_battle(message: str):
    """记录战斗日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = INFO_DIR / "battle_log.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [BATTLE] {message}\n")


def log_error(message: str):
    """记录错误信息"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = INFO_DIR / "battle_error.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [ERROR] {message}\n")


# ========== 战斗参数配置（基于params.yaml） ==========
class BattleParams:
    """战斗参数配置"""

    # 攻击潜能加成
    ATTACK_POTENTIAL = {
        "攻击中": 3,
        "单攻击中": 5,
        "攻击大": 8,
        "队长中": 4,
        "队长大": 8
    }

    # 攻击buff（倍率, 附加）
    ATTACK_BUFF = {
        "小": [0.2, 1],
        "中": [0.3, 2],
        "大": [0.5, 3],
        "特大": [0.8, 4]
    }
    ATTACK_BUFF_LIMIT = [1.0, False]  # 上限倍率，是否严格上限

    # 潜能倍率
    POTENTIAL_MULTIPLIER = {
        "方向中": 0.1,
        "方向大": 0.15,
        "解析小": 0.1,
        "解析中": 0.15
    }

    # 必杀基础倍率
    ULTIMATE_BASE_MULTIPLIER = {
        "小": 1.2,
        "中": 1.5,
        "大": 1.7,
        "特大": 2.0,
        "极大": 2.3,
        "超特大": 2.5,
        "技能小": 0.8,
        "技能中": 1.0,
        "技能大": 1.2
    }

    # 威力上升幅度
    POWER_UP_RATE = {
        "无": 0,
        "中": 0.05,
        "大": 0.1,
        "非常大": 0.15
    }

    # 其他倍率加成
    OTHER_MULTIPLIER = {
        "无": 0,
        "中": 0.2,
        "大": 0.4,
        "非常大": 0.6
    }

    # 必杀威力buff（倍率, 附加）
    ULTIMATE_POWER_BUFF = {
        "小": [0.35, 1],
        "中": [0.5, 2],
        "大": [0.75, 3]
    }
    ULTIMATE_POWER_BUFF_LIMIT = [1.5, False]

    # 必杀附加攻击
    ULTIMATE_EXTRA_ATTACK = {
        "中": 4,
        "大": 6,
        "特大": 8,
        "极大": 8,
        "超特大": 10,
        "技能小": 2,
        "技能中": 4,
        "技能大": 6
    }

    # 防御buff（倍率, 附加）
    DEFENSE_BUFF = {
        "小": [0.4, 1],
        "中": [0.6, 2],
        "大": [0.8, 3]
    }
    DEFENSE_BUFF_LIMIT = [1.0, True]  # 严格上限

    # 暴伤buff（倍率, 附加）
    CRIT_DAMAGE_BUFF = {
        "小": [0.25, 1],
        "中": [0.4, 2],
        "大": [0.65, 3]
    }
    CRIT_DAMAGE_BUFF_LIMIT = [1.0, True]

    # 暴击防御buff（倍率, 附加）
    CRIT_DEFENSE_BUFF = {
        "小": [0.25, 1],
        "中": [0.35, 2]
    }
    CRIT_DEFENSE_BUFF_LIMIT = [1.0, True]

    # 颜色耐性buff（倍率, 附加）
    COLOR_RESIST_BUFF = {
        "小": [0.15, 1],
        "中": [0.25, 2],
        "大": [0.4, 3]
    }
    COLOR_RESIST_BUFF_LIMIT = [0.55, False]

    # 必杀耐性buff（倍率, 附加）
    ULTIMATE_RESIST_BUFF = {
        "小": [0.25, 1],
        "中": [0.35, 2],
        "大": [0.5, 3]
    }
    ULTIMATE_RESIST_BUFF_LIMIT = [0.5, False]

    # 颜色威力buff（倍率, 附加）
    COLOR_POWER_BUFF = {
        "小": [0.15, 1],
        "中": [0.25, 2]
    }

    # SP潜能
    SP_POTENTIAL = {
        "SP小": 0.15,
        "单SP小": 0.2
    }

    # SP获得buff
    SP_GAIN_BUFF = {
        "小": 0.25,
        "中": 0.5,
        "大": 0.75,
        "特大": 1.0
    }

    # SP固定值
    SP_FIXED = {
        "中": 5,
        "大": 10
    }

    # 攻击SP（固定SP, 比例SP）
    ATTACK_SP = {
        1: [1, 5],
        2: [1, 3.5],
        3: [1, 2.5]
    }


# ========== 属性克制配置 ==========
# 克制列表：红克绿、绿克蓝、蓝克红、黄紫互克
COUNT_COLOR_LIST = ['红绿', '绿蓝', '蓝红', '黄紫', '紫黄']

# 属性别名映射（统一使用日文原名）
ATTRIBUTE_ALIASES = {
    "赤": "红",
    "緑": "绿",
    "青": "蓝",
    "红": "红",
    "绿": "绿",
    "蓝": "蓝",
    "黄": "黄",
    "紫": "紫"
}


# ========== 战斗配置 ==========
TOTAL_BATTLE_POSITIONS = 6   # 总战斗位数量
TOTAL_ASSIST_POSITIONS = 6   # 总支援位数量
BATTLE_POSITIONS_ON_FIELD = 5  # 场上战斗位总列数（5列）
INITIAL_DEPLOY_COUNT = 3       # 初始上场人数（只占0/2/4列）
MAX_BATTLE_ROUNDS = 12  # 最大战斗回合数
# 初始上场位置（0-based：只占 0,2,4，1和3用于换位后空位）
INITIAL_FIELD_POSITIONS = [0, 2, 4]
# 换位可用位置（5列均可）
ALL_FIELD_COLS = [0, 1, 2, 3, 4]  # 换位可用全部5列

# SP配置
SP_PER_ATTACK = 15  # 攻击获得SP
SP_PER_DAMAGED = 10  # 被攻击获得SP
SP_MAX = 300  # SP上限（一队共用）
ULT_COST = 100  # 必杀技消耗SP

# 同色增益
SAME_COLOR_BONUS = 1.05  # B卡A卡同色时增益5%


# ========== buff/debuff关键词列表 ==========
ALL_TIME_LIST = [
    # 长串复合条件（必须在短串前）
    '敌方行动结束且我方一对角色HP少于一半时',
    # 自身以外（必须在自身前）
    '自身以外的我方退场时', '自身以外的我方必杀时', '自身以外的我方技能时',
    # 自身对敌方（必须在敌方对/自身对前）
    '我方一对角色使敌方退场时', '我方一对角色对敌方暴击时',
    '自身对敌方造成伤害时', '自身对敌方暴击时',
    '敌方对我方角色暴击时',
    # 自身/我方一对角色 + 动作
    '我方一对角色受到伤害时', '我方一对角色退场时',
    '我方一对角色必杀时', '我方一对角色技能时',
    '自身受到伤害时', '自身使敌方退场时',
    '自身从a卡以外被弱体时',
    # 基础触发时机
    '敌方行动开始时', '行动开始时',
    '替补入场时',
    '自身技能时', '自身必杀时',
    '自身退场时',
    # 敌方动作触发
    '敌方必杀时', '敌方技能时',
    # HP/SP触发
    'HP低于50%时', 'HP低于30%时', '敌方SP满时', '击破时'
]

ALL_AREA_LIST = [
    '我方全体', '自身(?!以外)', '自身以外的我方全体', '敌全体',
    '我方一对角色', '该敌方角色',
    '同色我方全体', '同色敌全体',
    '(红|绿|蓝|黄|紫)色敌全体',
    '范围内', '三方向', '正面', '左侧', '右侧', '[前左右]+',
    '同色与有利色敌全体', '(同色|有利色)敌全体', '..侧敌全体',
    '(.色与)?.色敌全体',
    '同色我方', '(.色与)?.色我方全体',
    '自身与两邻', '自身', '两邻'
]

ALL_BUFF_LIST = [
    '盾', '矢量操作', '强制咏唱待机', '全能神', '嘲讽', '强耐', '弱耐',
    r'不屈(?:\([^()]*\))?',
    '预测不能', '天罚', r'(?:攻击|攻撃)方向\+.',
    '必暴', '贯通', r'HP回复\(.+?\)', r'物攻提升\(.+?\)', r'异攻提升\(.+?\)', r'物防提升\(.+?\)',
    r'异防提升\(.+?\)', r'暴击防御提升\(.+?\)',
    r'暴击率提升\(.+?\)', r'回避率提升\(.+?\)', r'暴伤提升\(.+?\)',
    r'必杀威力提升\(.+?\)', r'技能威力提升\(.+?\)',
    r'SP获得量提升\(.+?\)', r'[^【]*减伤\(.+?\)', r'对.色威力提升\(.+?\)',
    # 各类“耐性”增益（抗性）：抵抗对应减益
    r'(?:a卡封印|必杀封印|感电|移动不能)耐性'
]

ALL_DEBUFF_LIST = [
    '强化妨害', '攻击提升妨害', 'HP回复妨害', '弱体化解除妨害',
    r'弱体状态解除', r'弱体化解除(?!妨害)',
    r'强化(?:状态)?解除(?:\(.+?\))?',
    r'(?:物攻|异攻|攻击)下降解除',
    r'持续被害\(.+?\)', '感电', '气绝', '移动不能', '制御不能', 'a卡封印', '出血',
    r'(?:攻击|攻撃)方向\-.', '技能封印', '必杀封印',
    r'物攻下降\(.+?\)', r'异攻下降\(.+?\)', r'物防下降\(.+?\)',
    r'异防下降\(.+?\)', r'必杀威力下降\(.+?\)', r'技能威力下降\(.+?\)',
    r'暴击率下降\(.+?\)', r'回避率下降\(.+?\)', r'暴击防御下降\(.+?\)',
    r'暴伤下降\(.+?\)', r'对.色威力下降\(.+?\)',
    r'SP获得量下降\(.+?\)', r'SP获得量下降',
    r'技能/必杀耐性下降\(.+?\)', r'.色耐性下降\(.+?\)'
]

ALL_ATTACK_LIST = [
    '((对(魔法|科学)|自身HP最大时|自身HP少于一半时|强化数|弱体数|自身HP[多少])(非常)?(大)?上升)?(?:必暴)?(超?特?大|中|小)威力(物理|异能)攻击'
]

ALL_SP_LIST = [
    'SP([0-9]+)上升', '根据(..侧|.色)数量SP(大)?上升'
]


# ========== 数据结构 ==========
@dataclass
class BuffEffect:
    """buff效果"""
    name: str  # buff名称
    magnitude: str  # 幅度（小/中/大/特大）
    level: int = 1  # 等级
    duration: int = 0  # 持续回合（0表示永久或本次行动）
    source: str = ""  # 来源（b卡/a卡）
    expire_half: Optional[int] = None  # 过期半回合序号（None=永不过期）；= 施加时的 _half_turn_count + duration*2
    applied_half_turn: int = -1  # 施加时的 _half_turn_count；每半回合结算时若 == 当前半回合序号则跳过（忽略本半回合新增）
    charges: int = 0  # 多层护盾的剩余层数（外的御供：免疫伤害次数；默认0=非多层）

    def get_multiplier(self) -> float:
        """获取倍率"""
        params = BattleParams
        buff_maps = {
            "攻击": params.ATTACK_BUFF,
            "防御": params.DEFENSE_BUFF,
            "暴伤": params.CRIT_DAMAGE_BUFF,
            "暴击防御": params.CRIT_DEFENSE_BUFF,
            "颜色耐性": params.COLOR_RESIST_BUFF,
            "必杀耐性": params.ULTIMATE_RESIST_BUFF,
            "颜色威力": params.COLOR_POWER_BUFF,
            "必杀威力": params.ULTIMATE_POWER_BUFF,
            "技能威力": params.ULTIMATE_POWER_BUFF,  # 复用必杀威力的倍率表
            "减伤": params.COLOR_RESIST_BUFF,        # 复用颜色耐性的倍率表
        }
        if self.name in buff_maps:
            values = buff_maps[self.name].get(self.magnitude, [0, 0])
            return values[0] + values[1] * (self.level - 1)
        return 0

    def get_extra(self) -> int:
        """获取附加数值"""
        params = BattleParams
        buff_maps = {
            "攻击": params.ATTACK_BUFF,
            "防御": params.DEFENSE_BUFF,
            "暴伤": params.CRIT_DAMAGE_BUFF,
            "暴击防御": params.CRIT_DEFENSE_BUFF,
            "颜色耐性": params.COLOR_RESIST_BUFF,
            "必杀耐性": params.ULTIMATE_RESIST_BUFF,
            "颜色威力": params.COLOR_POWER_BUFF,
            "必杀威力": params.ULTIMATE_POWER_BUFF,
            "技能威力": params.ULTIMATE_POWER_BUFF,
            "减伤": params.COLOR_RESIST_BUFF,
        }
        if self.name in buff_maps:
            values = buff_maps[self.name].get(self.magnitude, [0, 0])
            return int(values[1] * (self.level - 1))
        return 0


@dataclass
class Skill:
    """技能"""
    name: str
    description: str  # 技能描述文本
    sp_cost: int = 30
    cooldown: int = 2
    power_rank: str = "中"  # 威力等级（小/中/大/特大/极大/超特大）
    is_skill: bool = True  # True=技能，False=必杀
    area: str = "正面"  # 作用范围
    effects: List[str] = field(default_factory=list)  # 效果列表
    power_up_type: str = "无"  # 威力上升类型（强化数/弱体数/其他）
    power_up_rate: str = "无"  # 威力上升幅度
    limit_break_1: bool = False  # 限界1发动


@dataclass
class AssistEffect:
    """支援卡效果"""
    trigger_count: int = 100  # 触发次数（默认无限）
    trigger_time: str = "行动开始时"  # 触发时机
    area: str = "自身"  # 作用范围
    effects: List[str] = field(default_factory=list)  # 效果列表
    duration: int = 0  # 持续回合数
    current_count: int = 0  # 当前触发计数
    current_cd: int = 0  # 当前冷却（初始为0）
    cd: int = 0  # 冷却回合（触发后需等待的回合数）

    def is_ready(self) -> bool:
        """检查是否可以触发"""
        return self.current_cd <= 0 and self.trigger_count > self.current_count


@dataclass
class Passive:
    """潜能：3星激活passive1，5星激活passive2"""
    name: str  # 潜能名称
    activation_star: int = 3  # 激活所需星级（3=被动1, 5=被动2）

    # 固定数值加成（直接加在基础属性上）
    HP_BONUS = {"小": 500, "中": 1000, "大": 2000, "特大": 3000}
    ATK_BONUS = {"小": 200, "中": 500, "大": 1000, "特大": 1500}
    DEF_BONUS = {"小": 150, "中": 350, "大": 700, "特大": 1000}
    SPD_BONUS = {"小": 100, "中": 250, "大": 500, "特大": 800}

    def get_hp_bonus(self) -> int:
        if self.name.startswith("HP"):
            mag = self.name[2:]  # "HP中" → "中"
            return self.HP_BONUS.get(mag, 0)
        return 0

    def get_attack_bonus(self) -> int:
        if self.name.startswith("攻击") or self.name.startswith("单攻击"):
            mag = self.name.replace("单", "")[2:]  # "单攻击中" → "中"
            return self.ATK_BONUS.get(mag, 0)
        return 0

    def get_defense_bonus(self) -> int:
        if "防" in self.name and "向上" in self.name:
            for mag in ["特大", "大", "中", "小"]:
                if mag in self.name:
                    return self.DEF_BONUS.get(mag, 0)
        return 0

    def get_speed_bonus(self) -> int:
        if "集中力" in self.name or "速度" in self.name:
            for mag in ["特大", "大", "中", "小"]:
                if mag in self.name:
                    return self.SPD_BONUS.get(mag, 0)
        return 0

    def get_multiplier(self) -> float:
        """获取倍率加成（方向/解析类）"""
        params = BattleParams
        if self.name in params.POTENTIAL_MULTIPLIER:
            return params.POTENTIAL_MULTIPLIER[self.name]
        return 0


@dataclass
class Character:
    """角色数据"""
    card_id: str
    name: str
    hp: int
    attack: int
    defense: int
    speed: int
    attribute: str  # 红/绿/蓝/黄/紫（可能带超属性前缀）
    attack_type: str  # 物理/异能
    attack_directions: int = 1  # 攻击方向数 1~3
    side: str = "科学"  # 阵营（科学/魔法/其他）

    # 技能（战斗卡）
    skill: Optional[Skill] = None  # 技能1（普通技能）
    skill2: Optional[Skill] = None  # 技能2（双人卡第二个普通技能，普通卡为None）
    ultimate: Optional[Skill] = None  # 必杀技（双人卡=skill3，普通卡=skill2）

    # 支援效果（支援卡）
    assist_effect1: Optional[AssistEffect] = None
    assist_effect2: Optional[AssistEffect] = None

    # 潜能
    passives: List[Passive] = field(default_factory=list)

    # 星级
    stars: int = 3

    # 是否支援卡
    is_assist: bool = False


@dataclass
class BattleUnit:
    """战斗单位"""
    character: Character
    position: int  # 在配队中的位置 0-5
    is_assist: bool = False

    # 当前状态
    current_hp: int = 0
    max_hp: int = 0
    skill_cooldown: int = 0
    skill2_cooldown: int = 0  # 双人卡第二技能冷却
    ult_cooldown: int = 0
    assist_skill1_cd: int = 0
    assist_skill2_cd: int = 0

    # 状态
    alive: bool = True
    is_broken: bool = False

    # buff列表
    buffs: List[BuffEffect] = field(default_factory=list)
    debuffs: List[BuffEffect] = field(default_factory=list)

    # 关联的支援单位
    assist_unit: Optional['BattleUnit'] = None

    # 连携：carrying = 本单位携带的友方(A)；carried_by = 携带本单位的友方(B)
    carrying: Optional['BattleUnit'] = None
    carried_by: Optional['BattleUnit'] = None

    # 用于追踪非A卡来源的debuff（触发"自身从a卡以外被弱体时"）
    _got_debuff_non_assist: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        if self.current_hp == 0:
            self.current_hp = self.character.hp
        if self.max_hp == 0:
            self.max_hp = self.character.hp

    def get_buff_multiplier(self, buff_name: str) -> Tuple[float, int]:
        """获取指定buff的总倍率和附加"""
        total_mult = 0
        total_extra = 0

        # 获取上限
        params = BattleParams
        limit_maps = {
            "攻击": params.ATTACK_BUFF_LIMIT,
            "防御": params.DEFENSE_BUFF_LIMIT,
            "暴伤": params.CRIT_DAMAGE_BUFF_LIMIT,
            "暴击防御": params.CRIT_DEFENSE_BUFF_LIMIT,
            "颜色耐性": params.COLOR_RESIST_BUFF_LIMIT,
            "必杀耐性": params.ULTIMATE_RESIST_BUFF_LIMIT,
            "颜色威力": params.COLOR_POWER_BUFF,
            "必杀威力": params.ULTIMATE_POWER_BUFF_LIMIT,
            "技能威力": [0.5, False],
            "减伤": [0.55, False],
        }

        limit_mult = 1e5
        strict_limit = False
        if buff_name in limit_maps:
            limit_config = limit_maps[buff_name]
            if isinstance(limit_config, list) and len(limit_config) >= 2:
                limit_mult = limit_config[0]
                strict_limit = limit_config[1]

        for buff in self.buffs:
            if buff.name == buff_name:
                if total_mult < limit_mult or (not strict_limit and total_mult <= limit_mult):
                    total_mult += buff.get_multiplier()
                    total_extra += buff.get_extra()

        if strict_limit and total_mult > limit_mult:
            total_mult = limit_mult

        return total_mult, total_extra

    def get_debuff_multiplier(self, debuff_name: str) -> Tuple[float, int]:
        """获取指定debuff的总倍率和附加"""
        total_mult = 0
        total_extra = 0

        for debuff in self.debuffs:
            if debuff.name == debuff_name:
                total_mult += debuff.get_multiplier()
                total_extra += debuff.get_extra()

        return total_mult, total_extra


# ========== 战斗系统核心 ==========
class BattleSystem:
    """回合制战斗系统"""

    def __init__(self, characters_data: List[dict]):
        """
        初始化战斗系统
        :param characters_data: 角色数据列表（从Excel读取）
        """
        self.characters = {}
        self._load_characters(characters_data)
        # 用于攻击函数与half_turn通信本次攻击的暴击状态（敌方对我方角色暴击时）
        self._last_attack_had_crit = False
        # 半回合计数器：每个半回合（玩家/敌方）开始时 +1，用于状态按"半回合"对称计时
        self._half_turn_count = 0
        # BattleSystem is shared by the bot adapters.  A battle mutates the
        # counters above and temporarily adjusts boss character data, so two
        # battles must not execute on the same instance at the same time.
        self._battle_lock = threading.RLock()

    def _get_arrow_by_position(self, position: int, side: str) -> str:
        """根据位置获取箭头符号"""
        # 玩家方箭头
        player_arrows = ['↙', '←', '↓', '→', '↘']
        # 敌方箭头（镜像）
        enemy_arrows = ['↖', '←', '↑', '→', '↗']

        if 0 <= position < 5:
            return player_arrows[position] if side == 'P' else enemy_arrows[position]
        return ''

    def _normalize_attribute(self, attr: str) -> str:
        """标准化属性名称"""
        if not attr:
            return "红"

        attr = attr.strip()

        # 处理超属性
        if attr.startswith("超"):
            base_attr = attr[1:]
            return f"超{ATTRIBUTE_ALIASES.get(base_attr, base_attr)}"

        return ATTRIBUTE_ALIASES.get(attr, attr)

    def _extract_outside_offering(self, text: str) -> List[str]:
        """从 'N次【外的御供】' 抽取归一化 token '外的御供(N)'（N=免疫伤害次数）。"""
        return [f"外的御供({m.group(1)})" for m in re.finditer(r'(\d+)次【外的御供】', text)]

    def _parse_skill_text(self, text: str, is_ultimate: bool = False) -> Optional[Skill]:
        """解析技能文本"""
        if not text:
            return None

        skill = Skill(
            name="技能" if not is_ultimate else "必杀技",
            description=text,
            is_skill=not is_ultimate
        )

        # 解析威力等级
        power_match = re.search(r'(超?特?大|中|小)威力', text)
        if power_match:
            rank = power_match.group(1)
            if is_ultimate:
                skill.power_rank = rank
            else:
                skill.power_rank = "技能" + rank

        # 解析威力上升
        power_up_match = re.search(r'(强化数|弱体数)(非常)?(大)?上升', text)
        if power_up_match:
            skill.power_up_type = power_up_match.group(1)
            rate = power_up_match.group(2) or power_up_match.group(3) or ""
            skill.power_up_rate = rate if rate else "中"

        # 解析其他倍率加成
        other_match = re.search(r'(自身HP最大时|自身HP少于一半时)(非常)?(大)?上升', text)
        if other_match:
            rate = other_match.group(2) or other_match.group(3) or ""
            skill.power_up_rate = rate if rate else "中"

        # 解析作用范围
        area_patterns = ['自身与两邻', '自身与右邻', '自身与左邻',
                        '范围内', '三方向', '正面', '敌全体', '左侧', '右侧', '前右', '前左',
                        '自身']
        for area in area_patterns:
            if area in text:
                skill.area = area
                break

        # 解析效果
        effects = []
        for pattern in ALL_BUFF_LIST + ALL_DEBUFF_LIST + ALL_ATTACK_LIST:
            matches = re.findall(pattern, text)
            effects.extend(matches)
        # 外的御供：N次【外的御供】 → 外的御供(N)
        effects.extend(self._extract_outside_offering(text))
        skill.effects = effects

        return skill

    def _parse_assist_text(self, text: str, cd: int = 0) -> Optional[AssistEffect]:
        """解析支援卡技能文本
        格式: [条件] [对象] [效果列表] X回合 (Y次)
        例: 行动开始时我方全体【物攻提升(中)】1回合(1次)
        例: 自身技能时,【物防提升(小)】,【SP获得量提升(小)】2回合
        """
        if not text:
            return None

        effect = AssistEffect()
        effect.cd = cd

        # 解析最大触发次数: (X次)
        count_match = re.search(r'\((\d+)次\)', text)
        if count_match:
            effect.trigger_count = int(count_match.group(1))

        # 解析触发时机 — 长串优先（避免"行动开始时"误匹配"敌方行动开始时"）
        time_exact = [
            # 长串复合条件（必须在短串前）
            '敌方行动结束且我方一对角色HP少于一半时',
            # 自身以外（必须在自身前，避免"自身以外的我方技能时"被"自身技能时"误匹配）
            '自身以外的我方退场时', '自身以外的我方必杀时', '自身以外的我方技能时',
            # 我方一对角色 + 使敌方退场/暴击（必须在"自身对敌方*"前）
            '我方一对角色使敌方退场时', '我方一对角色对敌方暴击时',
            # 自身对敌方（4字长串）
            '自身对敌方造成伤害时', '自身对敌方暴击时',
            # 敌方对我方角色暴击（必须在"自身对敌方暴击时"前，因为包含"对.*暴击时"）
            '敌方对我方角色暴击时',
            # 我方一对角色 + 受伤/退场/必杀/技能
            '我方一对角色受到伤害时', '我方一对角色退场时',
            '我方一对角色必杀时', '我方一对角色技能时',
            # 自身新条件
            '自身受到伤害时', '自身使敌方退场时',
            '自身从a卡以外被弱体时',
            # 基础触发时机
            '敌方行动开始时', '行动开始时',
            '替补入场时',
            '自身技能时', '自身必杀时',
            '自身退场时',
            # 敌方动作触发
            '敌方必杀时', '敌方技能时',
            # HP/SP触发
            'HP低于50%时', 'HP低于30%时', '敌方SP满时', '击破时'
        ]
        for t in time_exact:
            if t in text:
                effect.trigger_time = t
                break

        # 解析作用范围 — 按优先级，先匹配更具体的
        area_exact = [
            '自身以外的我方全体', '我方一对角色', '我方全体',
            '同色我方全体', '同色敌全体', '同色我方', '同色',
            '该敌方角色', '敌全体',
            '自身与两邻', '两邻', '自身',
        ]
        for a in area_exact:
            if a in text:
                effect.area = a
                break

        # 解析特殊颜色目标: X色敌全体
        color_area_match = re.search(r'(红|绿|蓝|黄|紫)色敌全体', text)
        if color_area_match:
            effect.area = color_area_match.group(0)

        # 解析效果 — 提取【】内容 + 无括号效果（使用完整匹配文本）
        effect_list = []
        # 提取所有【效果名(幅度)】格式（保留完整文本如"物攻提升(中)"）
        bracket_effects = re.findall(r'【(.+?)】', text)
        effect_list.extend(bracket_effects)
        # 提取无括号效果: HP回复(X), SP15上升, 弱体状态解除等（使用finditer获取完整匹配）
        for pattern in ALL_BUFF_LIST + ALL_DEBUFF_LIST + ALL_SP_LIST:
            for m in re.finditer(pattern, text):
                effect_list.append(m.group(0))  # 完整匹配文本
        # 外的御供：N次【外的御供】 → 外的御供(N)（去掉无次数的裸 token）
        offering = self._extract_outside_offering(text)
        if offering:
            effect_list = [e for e in effect_list if e != '外的御供']
            effect_list.extend(offering)
        # 去重保持顺序
        seen = set()
        effect.effects = []
        for e in effect_list:
            if e not in seen:
                seen.add(e)
                effect.effects.append(e)

        # 解析持续回合数
        dur_match = re.search(r'(\d+)回合', text)
        if dur_match:
            effect.duration = int(dur_match.group(1))
        else:
            effect.duration = 0  # 瞬时效果

        return effect

    def _parse_passive_text(self, text: str, activation_star: int, attack_type: str, enemy_side: str) -> List[Passive]:
        """解析潜能文本。activation_star: 3=被动1, 5=被动2"""
        if not text:
            return []
        passives = []
        parts = text.strip().split('+')

        for part in parts:
            part = part.strip()

            # HP向上
            m = re.search(r'HP向上\((.+?)\)', part)
            if m:
                passives.append(Passive(name="HP" + m.group(1), activation_star=activation_star))
                continue

            # 物防向上 / 异防向上
            m = re.search(r'(物防|异防)向上\((.+?)\)', part)
            if m:
                passives.append(Passive(name=m.group(1) + "向上" + m.group(2), activation_star=activation_star))
                continue

            # 物攻向上/异攻向上 (保留旧格式兼容)
            m = re.fullmatch(r'(.)攻向上(?:\((.+?)\))?', part)
            if m and m.group(1) == attack_type[0]:
                magnitude = m.group(2) if m.group(2) else "中"
                passive_name = "攻击" + magnitude
                if len(parts) == 1:
                    passive_name = "单" + passive_name
                passives.append(Passive(name=passive_name, activation_star=activation_star))
                continue

            # 集中力向上
            m = re.search(r'集中力向上\((.+?)\)', part)
            if m:
                passives.append(Passive(name="集中力" + m.group(1), activation_star=activation_star))
                continue

            # 速度向上
            m = re.search(r'速度向上\((.+?)\)', part)
            if m:
                passives.append(Passive(name="速度" + m.group(1), activation_star=activation_star))
                continue

            # 方向攻击强化
            m = re.fullmatch(r'(.+)方向攻击强化(?:\((.+?)\))?', part)
            if m:
                magnitude = m.group(2) if m.group(2) else "中"
                passives.append(Passive(name="方向" + magnitude, activation_star=activation_star))
                continue

            # 科学支援/魔法支援：XXXX
            m = re.match(r'(科学|魔法)支援[：:]\s*(.+)', part)
            if m:
                # 支援类被动：解析支援效果文本中的buff词条
                sub_text = m.group(2)
                sub_passives = self._parse_passive_text(sub_text, activation_star, attack_type, enemy_side)
                passives.extend(sub_passives)
                continue

            # SP获得量向上
            m = re.fullmatch(r'SP获得量向上(?:\((.+?)\))?', part)
            if m:
                magnitude = m.group(1) if m.group(1) else "小"
                sp_name = "SP" + magnitude
                if len(parts) == 2:
                    sp_name = "单" + sp_name
                passives.append(Passive(name=sp_name, activation_star=activation_star))
                continue

            # 解析
            m = re.fullmatch(r'(..)解析\\((.)\\)', part)
            if m:
                if (m.group(1), enemy_side) in [('构造', '科学'), ('术式', '魔法')]:
                    passives.append(Passive(name="解析" + m.group(2), activation_star=activation_star))
                continue

        return passives

    def _load_characters(self, characters_data: List[dict]):
        """加载角色数据"""
        for char_data in characters_data:
            try:
                # 标准化属性
                attribute = self._normalize_attribute(char_data.get("attribute", "红"))

                # 解析技能（兼容两种数据格式）
                # 格式1: skill1.description, skill2.description（嵌套字典）
                # 格式2: skill1_description, skill2_description（扁平字段）
                skill1_data = char_data.get("skill1", {})
                skill2_data = char_data.get("skill2", {})

                if isinstance(skill1_data, dict):
                    skill_text1 = skill1_data.get("description", "")
                else:
                    skill_text1 = char_data.get("skill1_description", "")

                if isinstance(skill2_data, dict):
                    skill_text2 = skill2_data.get("description", "")
                else:
                    skill_text2 = char_data.get("skill2_description", "")

                skill = self._parse_skill_text(skill_text1, is_ultimate=False)
                skill2 = None
                ultimate = None

                # 双人卡：有skill3时，skill1+skill2为普通技能，skill3为必杀技
                # 普通卡：skill1为普通技能，skill2为必杀技
                skill3_data = char_data.get("skill3", {}) if isinstance(skill1_data, dict) else {}
                skill_text3 = ""
                if isinstance(skill3_data, dict):
                    skill_text3 = skill3_data.get("description", "")
                else:
                    skill_text3 = char_data.get("skill3_description", "")

                if skill_text3 and skill_text3.strip():
                    # 双人卡：skill2作为第二个普通技能，skill3作为必杀技
                    skill2 = self._parse_skill_text(skill_text2, is_ultimate=False)
                    ultimate = self._parse_skill_text(skill_text3, is_ultimate=True)
                else:
                    # 普通卡：skill2作为必杀技
                    ultimate = self._parse_skill_text(skill_text2, is_ultimate=True)

                # 解析支援效果
                assist_effect1 = None
                assist_effect2 = None

                if char_data.get("type") == "assist":
                    # 从skill数据中提取CD值（Excel CD1/CD2列）
                    sk1_cd = skill1_data.get("cd", 0) if isinstance(skill1_data, dict) else 0
                    sk2_cd = skill2_data.get("cd", 0) if isinstance(skill2_data, dict) else 0
                    assist_effect1 = self._parse_assist_text(skill_text1, int(sk1_cd) if sk1_cd else 0)
                    assist_effect2 = self._parse_assist_text(skill_text2, int(sk2_cd) if sk2_cd else 0)

                # 解析潜能（passive1=3星激活, passive2=5星激活）
                passives = []
                passive_text1 = char_data.get("passive1", "") or char_data.get("passive1_text", "")
                passive_text2 = char_data.get("passive2", "") or char_data.get("passive2_text", "")
                level = char_data.get("level", 1)
                attack_type = char_data.get("attack_type", "物理")
                side = char_data.get("side", "科学")

                passives.extend(self._parse_passive_text(passive_text1, 3, attack_type, side))
                if passive_text2:
                    passives.extend(self._parse_passive_text(passive_text2, 5, attack_type, side))

                # 创建角色
                character = Character(
                    card_id=str(char_data.get("card_id", "")),
                    name=char_data.get("name", "未知角色"),
                    hp=char_data.get("hp", 1000),
                    attack=char_data.get("attack", 100),
                    defense=char_data.get("defense", 50),
                    speed=char_data.get("dexterity", 1000),  # 器用=速度
                    attribute=attribute,
                    attack_type=char_data.get("attack_type", "物理"),
                    attack_directions=char_data.get("attack_directions", [0]) if isinstance(char_data.get("attack_directions"), list) else [0],
                    side=char_data.get("side", "科学"),
                    skill=skill,
                    skill2=skill2,
                    ultimate=ultimate,
                    assist_effect1=assist_effect1,
                    assist_effect2=assist_effect2,
                    passives=passives,
                    stars=char_data.get("stars", 3),
                    is_assist=char_data.get("type") == "assist"
                )

                self.characters[character.card_id] = character

            except Exception as e:
                log_error(f"加载角色数据失败: {e}")
                continue

    def _get_fallback_character(self, card_id: str) -> 'Character':
        """卡牌不在数据库时返回默认占位角色"""
        return Character(
            card_id=str(card_id), name=f'未知({str(card_id)[:6]})',
            hp=10000, attack=3000, defense=2000, speed=1000,
            attribute='红', attack_type='物理', attack_directions=[0], side='科学',
            skill=None, ultimate=None, assist_effect1=None, assist_effect2=None, passives=[]
        )

    # 卡牌信息.xlsx -> cards_completed.xlsx ID映射（仅3张不一致）
    CARD_ID_MAP = {'780030000':'180030001','780130000':'180130001','700230001':'100235001'}

    def get_character(self, card_id: str) -> Optional[Character]:
        """获取角色（含旧→新ID映射）"""
        cid = str(card_id)
        char = self.characters.get(cid)
        if not char and cid in self.CARD_ID_MAP:
            char = self.characters.get(self.CARD_ID_MAP[cid])
        return char

    def create_battle_unit(self, card_id: str, position: int, is_assist: bool = False, extra_characters: dict = None) -> Optional[BattleUnit]:
        """创建战斗单位（找不到角色时用默认占位）"""
        character = self.get_character(card_id)

        # 如果在战斗系统中找不到角色，尝试从extra_characters查找
        if not character and extra_characters:
            char_data = extra_characters.get(str(card_id))
            if char_data:
                card_type = char_data.get("type", "battle")
                is_assist_card = card_type == "assist"

                assist_effect1 = None
                assist_effect2 = None

                # 如果是A卡，解析A卡效果
                if is_assist_card:
                    skill_text1 = char_data.get("skill1", {}).get("description", "")
                    skill_cd1 = char_data.get("skill1", {}).get("cd", 0)
                    skill_text2 = char_data.get("skill2", {}).get("description", "")
                    skill_cd2 = char_data.get("skill2", {}).get("cd", 0)

                    assist_effect1 = self._parse_assist_text(skill_text1, skill_cd1)
                    assist_effect2 = self._parse_assist_text(skill_text2, skill_cd2)

                # 从extra_characters创建一个简化的战斗角色
                character = Character(
                    card_id=str(card_id),
                    name=char_data.get("name", f'未知({str(card_id)[:6]})'),
                    hp=char_data.get("hp", 10000),
                    attack=char_data.get("attack", 3000),
                    defense=char_data.get("defense", 2000),
                    speed=char_data.get("speed", 1000) if char_data.get("speed") else 500,
                    attribute=char_data.get("element", char_data.get("attribute", "红")),
                    attack_type=char_data.get("attack_type", "物理"),
                    attack_directions=char_data.get("attack_directions", [0]) if isinstance(char_data.get("attack_directions"), list) else [0],
                    side=char_data.get("side", "科学"),
                    skill=None,
                    ultimate=None,
                    assist_effect1=assist_effect1,
                    assist_effect2=assist_effect2,
                    passives=[],
                    is_assist=is_assist_card
                )

        if not character:
            log_error(f"找不到角色: {card_id}，使用默认占位")
            character = self._get_fallback_character(card_id)

        character_copy = copy.deepcopy(character)

        return BattleUnit(
            character=character_copy,
            position=position,
            is_assist=is_assist
        )

    def build_battle_team(self, team_data: dict, extra_characters: dict = None, player_card_stars: dict = None) -> List[BattleUnit]:
        """构建战斗队伍"""
        units = []

        battle_cards = team_data.get("battle_cards", [])
        assist_cards = team_data.get("assist_cards", [])

        if not isinstance(battle_cards, list):
            battle_cards = []
        if not isinstance(assist_cards, list):
            assist_cards = []

        # 初始战斗位置映射：0→0, 1→2, 2→4（初始上场占这3个位置）, 3→5(替补), 4→6(替补), 5→7(替补)
        # 场上位置0-4都是战斗位置，位置1和3初始为空，可通过换位使用
        battle_position_map = [0, 2, 4, 5, 6, 7]

        # 创建战斗单位
        for i in range(TOTAL_BATTLE_POSITIONS):
            card_id = battle_cards[i] if i < len(battle_cards) else None
            if card_id:
                unit = self.create_battle_unit(card_id, battle_position_map[i], False, extra_characters)
                if unit:
                    units.append(unit)

        # 创建支援单位（位置映射与战斗单位一致）
        for i in range(TOTAL_ASSIST_POSITIONS):
            card_id = assist_cards[i] if i < len(assist_cards) else None
            if card_id:
                unit = self.create_battle_unit(card_id, battle_position_map[i], True, extra_characters)
                if unit:
                    units.append(unit)

        # 关联支援单位并计算属性
        for battle_unit in units:
            if not battle_unit.is_assist:
                for assist_unit in units:
                    if assist_unit.is_assist and assist_unit.position == battle_unit.position:
                        battle_unit.assist_unit = assist_unit

                        # B+A属性相加
                        total_attack = battle_unit.character.attack + assist_unit.character.attack
                        total_defense = battle_unit.character.defense + assist_unit.character.defense

                        # 同色增益
                        battle_base_attr = self._get_base_attribute(battle_unit.character.attribute)
                        assist_base_attr = self._get_base_attribute(assist_unit.character.attribute)

                        if battle_base_attr == assist_base_attr:
                            total_attack = int(total_attack * SAME_COLOR_BONUS)
                            total_defense = int(total_defense * SAME_COLOR_BONUS)

                        battle_unit.character.attack = total_attack
                        battle_unit.character.defense = total_defense

                        # 速度 = B器用 + A器用（同色增益）
                        total_speed = battle_unit.character.speed + assist_unit.character.speed
                        if battle_base_attr == assist_base_attr:
                            total_speed = int(total_speed * SAME_COLOR_BONUS)
                        battle_unit.character.speed = total_speed

                        # HP相加
                        total_hp = battle_unit.character.hp + assist_unit.character.hp
                        if battle_base_attr == assist_base_attr:
                            total_hp = int(total_hp * SAME_COLOR_BONUS)

                        battle_unit.max_hp = total_hp
                        battle_unit.current_hp = total_hp

                        # 合并潜能
                        battle_unit.character.passives.extend(assist_unit.character.passives)

                        break

        # 应用已激活的潜能到基础属性（根据玩家星级过滤）
        if player_card_stars:
            for battle_unit in units:
                if not battle_unit.is_assist:
                    cid = str(battle_unit.character.card_id)
                    star_level = player_card_stars.get(cid, 3)  # 默认3星
                    self._apply_passive_stats(battle_unit, star_level)

        return units

    def _apply_passive_stats(self, unit: 'BattleUnit', star_level: int):
        """根据星级激活潜能并预加到角色基础属性上，保存原始值供恢复"""
        c = unit.character
        if not hasattr(c, '_passive_originals'):
            c._passive_originals = {}  # 保存原始属性值

        hp_bonus = 0; atk_bonus = 0; def_bonus = 0; spd_bonus = 0

        for p in c.passives:
            if star_level < p.activation_star:
                continue  # 星级不足，潜能未激活
            hp_bonus += p.get_hp_bonus()
            atk_bonus += p.get_attack_bonus()
            def_bonus += p.get_defense_bonus()
            spd_bonus += p.get_speed_bonus()

        # 保存原始值（仅首次）
        if 'hp' not in c._passive_originals:
            c._passive_originals['hp'] = c.hp
            c._passive_originals['attack'] = c.attack
            c._passive_originals['defense'] = c.defense
            c._passive_originals['speed'] = c.speed

        # 应用加成
        c.hp += hp_bonus
        c.attack += atk_bonus
        c.defense += def_bonus
        c.speed += spd_bonus
        unit.max_hp += hp_bonus
        unit.current_hp += hp_bonus

    def _restore_passive_stats(self, unit: 'BattleUnit'):
        """恢复被潜能修改的基础属性"""
        c = unit.character
        originals = getattr(c, '_passive_originals', None)
        if originals:
            hp_delta = c.hp - originals['hp']
            c.hp = originals['hp']
            c.attack = originals['attack']
            c.defense = originals['defense']
            c.speed = originals['speed']
            unit.max_hp -= hp_delta
            unit.current_hp = min(unit.current_hp, unit.max_hp)

    def _get_base_attribute(self, attr: str) -> str:
        """获取基础属性（去除超属性前缀）"""
        base_attrs = ["红", "绿", "蓝", "黄", "紫"]
        for base in base_attrs:
            if base in attr:
                return base
        return attr

    def _is_super_attribute(self, attr: str) -> bool:
        """检查是否是超属性"""
        return attr.startswith("超")

    def _get_attribute_multiplier(self, attacker_attr: str, defender_attr: str) -> float:
        """获取属性克制倍率"""
        attacker_base = self._get_base_attribute(attacker_attr)
        defender_base = self._get_base_attribute(defender_attr)

        # 检查克制关系
        if attacker_base + defender_base in COUNT_COLOR_LIST:
            multiplier = 1.5  # 克制
        elif defender_base + attacker_base in COUNT_COLOR_LIST:
            multiplier = 0.6  # 被克制
        else:
            multiplier = 1.0

        # 超属性加成
        attacker_super = self._is_super_attribute(attacker_attr)
        defender_super = self._is_super_attribute(defender_attr)

        if attacker_super and not defender_super:
            multiplier *= 1.2

        return multiplier

    def _calculate_attack_panel(self, unit: BattleUnit) -> int:
        """计算攻击面板"""
        base_attack = unit.character.attack

        # 潜能攻击加成
        potential_attack = 0
        for passive in unit.character.passives:
            potential_attack += passive.get_attack_bonus()

        attack_panel = base_attack + potential_attack

        return int(attack_panel)

    def _calculate_buffed_attack(self, unit: BattleUnit, attack_panel: int) -> Tuple[int, int]:
        """计算buff后的攻击值"""
        # 攻击buff
        attack_mult, attack_extra = unit.get_buff_multiplier("攻击")

        # 潜能倍率
        potential_mult = 1.0
        for passive in unit.character.passives:
            potential_mult += passive.get_multiplier()

        # 计算攻击
        attack = int(attack_panel * (1 + attack_mult) + attack_extra)
        attack = int(attack * potential_mult)

        return attack, attack_extra

    def _calculate_defense(self, defender: BattleUnit) -> int:
        """计算防御值"""
        base_defense = defender.character.defense

        # 防御debuff（降低敌方防御）
        def_debuff_mult, def_debuff_extra = defender.get_debuff_multiplier("防御")

        # 防御 = max(防御 * (1 - debuff倍率) - debuff附加, 0)
        defense = max(int(base_defense * (1 - def_debuff_mult) - def_debuff_extra), 0)

        return defense

    def calculate_damage(self, attacker: BattleUnit, defender: BattleUnit,
                         attack_type: str = "normal", power_rank: str = "中",
                         power_up_count: int = 0,
                         attacker_attribute_override: Optional[str] = None) -> Tuple[int, bool, str, float, float]:
        """
        计算伤害（基于calc_dmg.py的核心公式）

        :return: (伤害值, 是否暴击, 伤害类型描述, 属性倍率, 伤害/面板比率)
        """
        params = BattleParams

        # 1. 计算攻击面板
        attack_panel = self._calculate_attack_panel(attacker)

        # 2. 计算buff后的攻击
        attack, attack_extra = self._calculate_buffed_attack(attacker, attack_panel)

        # 3. 必杀/技能倍率
        if attack_type == "ultimate":
            base_mult = params.ULTIMATE_BASE_MULTIPLIER.get(power_rank, 2.0)
            extra_attack = params.ULTIMATE_EXTRA_ATTACK.get(power_rank, 0)

            # 威力上升
            power_up_mult = params.POWER_UP_RATE.get(attacker.character.ultimate.power_up_rate if attacker.character.ultimate else "无", 0)
            power_up_mult += power_up_count * power_up_mult

            # 必杀威力buff
            ult_power_mult, ult_power_extra = attacker.get_buff_multiplier("必杀威力")

            attack += extra_attack + ult_power_extra
            attack = int(attack * (base_mult + power_up_mult + ult_power_mult))

        elif attack_type == "skill":
            base_mult = params.ULTIMATE_BASE_MULTIPLIER.get(power_rank, 1.0)
            extra_attack = params.ULTIMATE_EXTRA_ATTACK.get(power_rank, 0)

            # 技能威力buff
            skill_mult, skill_extra = attacker.get_buff_multiplier("技能威力")
            attack += extra_attack + skill_extra
            attack = int(attack * (base_mult + skill_mult))

        # 4. 计算防御
        defense = self._calculate_defense(defender)

        # 5. 核心伤害公式：伤害 = 攻击^2 / (攻击 + 防御)
        damage = int(attack ** 2 / max(attack + defense, 1))

        # 6. 属性克制（连携：被携带单位A的攻击伤害使用携带者B的属性）
        eff_attr = attacker_attribute_override if attacker_attribute_override else attacker.character.attribute
        attr_mult = self._get_attribute_multiplier(eff_attr, defender.character.attribute)
        damage = int(damage * attr_mult)

        # 7. 暴击（基础5%，暴击率buff加成，必暴则100%）
        crit_rate = 0.05
        crit_rate_map = {'小': 0.05, '中': 0.10, '大': 0.15, '特大': 0.20}
        for b in attacker.buffs:
            if b.name == '暴击率':
                crit_rate += crit_rate_map.get(b.magnitude, 0.10)
        for d in attacker.debuffs:
            if d.name == '暴击率':
                crit_rate -= crit_rate_map.get(d.magnitude, 0.10)
        crit_rate = max(0, min(1, crit_rate))
        is_crit = random.random() < crit_rate
        if not is_crit:
            for b in list(attacker.buffs):
                if b.name == '必暴':
                    is_crit = True
                    attacker.buffs.remove(b)
                    break
        if is_crit:
            crit_mult, crit_extra = attacker.get_buff_multiplier("暴伤")
            crit_mult -= attacker.get_debuff_multiplier("暴伤")[0]  # 暴伤下降 减成
            crit_def_mult, crit_def_extra = attacker.get_buff_multiplier("暴击防御")

            # 暴击伤害 = 伤害 * (1.5 + 暴伤倍率 + 暴击防御倍率) + 附加伤害
            damage = int(damage * (1.5 + crit_mult + crit_def_mult) + crit_extra + crit_def_extra)

        # 8. 颜色耐性/必杀耐性/颜色威力
        color_resist_mult, color_resist_extra = defender.get_buff_multiplier("颜色耐性")
        ult_resist_mult, ult_resist_extra = defender.get_buff_multiplier("必杀耐性")
        color_power_mult, color_power_extra = attacker.get_buff_multiplier("颜色威力")
        color_power_mult -= attacker.get_debuff_multiplier("颜色威力")[0]  # 对X色威力下降 减成

        if attack_type == "ultimate":
            damage = int(damage * (1 + color_resist_mult + ult_resist_mult + color_power_mult) +
                        color_resist_extra + ult_resist_extra + color_power_extra)

        # 9. 限界1发动
        if attack_type == "ultimate" and attacker.character.ultimate and attacker.character.ultimate.limit_break_1:
            damage = int(damage * 1.1)

        # 10. 减伤buff
        dmg_reduce_mult, dmg_reduce_extra = defender.get_buff_multiplier("减伤")
        damage = int(damage * max(0, 1 - dmg_reduce_mult) - dmg_reduce_extra)

        # 伤害类型描述
        damage_type = "普通攻击"
        if attack_type == "skill":
            damage_type = "技能"
        elif attack_type == "ultimate":
            damage_type = "必杀技"

        if is_crit:
            damage_type += " 暴击！"

        if attr_mult > 1.0:
            damage_type += " 属性克制！"
        elif attr_mult < 1.0:
            damage_type += " 属性被克制"

        # 伤害/面板比率 (2位小数四舍五入)
        ratio = round(damage / attack_panel, 2) if attack_panel > 0 else 0.0

        return max(1, damage), is_crit, damage_type, attr_mult, ratio

    def get_on_field_units(self, units: List[BattleUnit]) -> List[BattleUnit]:
        """获取场上战斗单位"""
        alive_battle_units = [u for u in units if not u.is_assist and u.alive]
        alive_battle_units.sort(key=lambda x: x.position)
        return alive_battle_units[:BATTLE_POSITIONS_ON_FIELD]

    def get_targets_in_direction(self, attacker: BattleUnit, enemies: List[BattleUnit], area: str = "正面") -> List[BattleUnit]:
        """敌全体=全打, 三方向=用箭头, 范围内=前N个"""
        if not enemies: return []
        if "敌全体" in area: return [e for e in enemies if e.alive]
        dire_raw = attacker.character.attack_directions
        if isinstance(dire_raw, list): offsets = list(dire_raw)
        else: offsets = {1:[0],2:[-1,0],3:[-1,0,1]}.get(dire_raw,[0])
        for b in attacker.buffs:
            if b.name=="攻击方向+" and len(offsets)<3:
                for o in [-1,0,1]:
                    if o not in offsets: offsets.append(o); break
        for d in attacker.debuffs:
            if d.name=="攻击方向-" and len(offsets)>1: offsets=offsets[:-1]
        pos = attacker.position % 5
        cols = {pos+off for off in offsets if 0<=pos+off<5}
        if not cols: return []
        targets = [e for e in enemies if e.alive and e.position < 5 and (e.position%5) in cols
                   and getattr(e, 'carried_by', None) is None]  # 连携中被携带单位不可被直接选中
        # 嘲讽机制：如果目标方有带嘲讽的单位且攻击者在可攻击范围内，强制只攻击嘲讽单位
        taunters = [t for t in targets if any(b.name == '嘲讽' for b in t.buffs)]
        if taunters:
            targets = taunters
        if "范围内" in area: return targets[:len(offsets)]
        return targets
    def _get_sp_rate(self, unit: 'BattleUnit') -> float:
        """获取SP获得倍率（SP获得量提升buff）"""
        rate = 1.0
        rate_map = {'小': 0.25, '中': 0.50, '大': 0.75, '特大': 1.0}
        for b in unit.buffs:
            if b.name == 'SP获得量':
                rate += rate_map.get(b.magnitude, 0.50)
        return rate

    def add_sp(self, side_sp: int, sp_amount: int) -> int:
        """增加阵营SP，返回新的SP值"""
        new_sp = min(SP_MAX, side_sp + sp_amount)
        return new_sp

    def use_sp(self, side_sp: int, sp_amount: int) -> Tuple[bool, int]:
        """消耗阵营SP，返回(是否成功, 剩余SP)"""
        if side_sp >= sp_amount:
            return True, side_sp - sp_amount
        return False, side_sp

    # 特殊buff（不叠加，覆盖刷新duration）
    SPECIAL_BUFFS = {'必暴','集中','盾','贯通','强耐','弱耐','感电','气绝','制御不能',
                     '技能封印','必杀封印','a卡封印','持续被害',
                     '攻击方向+','攻击方向-','移动不能','强化妨害','HP回复妨害'}

    def _apply_buff(self, target, name, magnitude='中', source='', duration=0):
        """应用buff: 特殊buff覆盖刷新, 强化妨害阻止"""
        if name in self.SPECIAL_BUFFS:
            for e in target.buffs:
                if e.name == name:
                    e.duration = max(e.duration, duration); e.magnitude = magnitude
                    e.expire_half = None if e.duration <= 0 else self._half_turn_count + e.duration * 2; e.applied_half_turn = self._half_turn_count
                    return
            for e in target.debuffs:
                if e.name == name:
                    e.duration = max(e.duration, duration); e.magnitude = magnitude
                    e.expire_half = None if e.duration <= 0 else self._half_turn_count + e.duration * 2; e.applied_half_turn = self._half_turn_count
                    return
        if any(d.name == '强化妨害' for d in target.debuffs): return
        if name == '攻击' and any(d.name == '攻击提升妨害' for d in target.debuffs): return
        eh = None if duration <= 0 else self._half_turn_count + duration * 2
        target.buffs.append(BuffEffect(name=name, magnitude=magnitude, source=source, duration=duration, expire_half=eh, applied_half_turn=self._half_turn_count))

    def _apply_debuff(self, target, name, magnitude='中', source='', duration=0, mirror=True):
        """应用debuff: 特殊buff覆盖刷新, 弱耐阻止"""
        if name in self.SPECIAL_BUFFS:
            for e in target.debuffs:
                if e.name == name:
                    e.duration = max(e.duration, duration); e.magnitude = magnitude
                    e.expire_half = None if e.duration <= 0 else self._half_turn_count + e.duration * 2; e.applied_half_turn = self._half_turn_count
                    return
            for e in target.buffs:
                if e.name == name:
                    e.duration = max(e.duration, duration); e.magnitude = magnitude
                    e.expire_half = None if e.duration <= 0 else self._half_turn_count + e.duration * 2; e.applied_half_turn = self._half_turn_count
                    return
        if any(b.name == '弱耐' for b in target.buffs): return
        # 追踪非A卡来源的debuff（用于"自身从a卡以外被弱体时"触发）
        if source != 'a卡':
            target._got_debuff_non_assist = True
        eh = None if duration <= 0 else self._half_turn_count + duration * 2
        target.debuffs.append(BuffEffect(name=name, magnitude=magnitude, source=source, duration=duration, expire_half=eh, applied_half_turn=self._half_turn_count))
        # 连携镜像：受到攻击类状态时，同列连携伙伴也获得相同状态（仅一层，不递归）
        if mirror and source in ('技能', '必杀', '天罚', '普攻', 'normal'):
            partner = getattr(target, 'carrying', None) or getattr(target, 'carried_by', None)
            if partner is not None and partner.alive:
                self._apply_debuff(partner, name, magnitude, source, duration, mirror=False)

    def _check_tenacity(self, target: 'BattleUnit') -> bool:
        """不屈: 免疫一次致命伤害, 小/中/大控制回血量"""
        for b in list(target.buffs):
            if b.name == '不屈':
                target.buffs.remove(b)
                heal_pct = {'小': 0.15, '中': 0.30, '大': 0.50}.get(b.magnitude, 0.30)
                target.current_hp = max(int(target.max_hp * heal_pct), 1)
                target.alive = True
                if target.assist_unit: target.assist_unit.alive = True
                return True
        return False

    def _apply_outside_offering(self, target: 'BattleUnit', charges: int, duration: int = 0) -> None:
        """外的御供: 多层免伤护盾。charges=免疫伤害次数；duration 与同类 buff 一致（0=常驻至战斗结束）。"""
        if charges <= 0:
            charges = 1
        for b in target.buffs:
            if b.name == '外的御供':
                b.charges = max(b.charges, charges)
                if duration > 0:
                    b.duration = max(b.duration, duration)
                    b.expire_half = None if b.duration <= 0 else self._half_turn_count + b.duration * 2
                    b.applied_half_turn = self._half_turn_count
                return
        eh = None if duration <= 0 else self._half_turn_count + duration * 2
        target.buffs.append(BuffEffect(
            name='外的御供', magnitude=str(charges), source='', duration=duration,
            expire_half=eh, applied_half_turn=self._half_turn_count, charges=charges))

    def _apply_outside_offering_on_hit(self, target: 'BattleUnit', results: List[str], target_name: str) -> bool:
        """外的御供 受击结算：获得1回合攻击上升(大)（刷新不叠加）；若仍有层数则免疫本次伤害。返回True=本次免疫。"""
        offering = next((b for b in target.buffs if b.name == '外的御供'), None)
        if offering is None:
            return False
        # 受击获得攻击上升(大) 1回合（先移除旧的同类，避免叠加）
        target.buffs = [b for b in target.buffs if not (b.name == '攻击' and b.source == '外的御供')]
        self._apply_buff(target, "攻击", "大", "外的御供", 1)
        if offering.charges > 0:
            offering.charges -= 1
            results.append(f"{target_name} (外的御供免疫伤害！剩余{offering.charges}层) [{offering.magnitude}]")
            return True
        return False

    def _dissolve_combo(self, unit: 'BattleUnit') -> None:
        """解除 unit 参与的连携：清空双方 carrying/carried_by（幂等）"""
        a = getattr(unit, 'carrying', None)
        b = getattr(unit, 'carried_by', None)
        if a is not None:
            a.carried_by = None
            unit.carrying = None
        if b is not None:
            b.carrying = None
            unit.carried_by = None

    def _tick_expiry(self, units):
        """每个半回合开始时结算状态过期（基于半回合序号，上下半回合对称）。

        状态在施加时记录 expire_half = 当时的 _half_turn_count + duration*2，
        applied_half_turn = 当时的 _half_turn_count。
        当 _half_turn_count >= expire_half 时移除；但显式跳过 applied_half_turn
        等于当前半回合序号的状态——即「忽略本半回合新增的状态」，无论 tick 时机如何
        都不会误伤本半回合刚施加的 BUFF/DEBUFF。
        由于按「半回合」而非「回合」计，1回合状态都恰好存活 2 个半回合
        （含施加半回合的剩余部分），从而消除「上半回合施加比下半回合多存活约一个
        半回合」的不对称。expire_half 为 None 表示永不过期（duration<=0）。
        """
        expired = False
        ht = self._half_turn_count
        for u in units:
            for b in list(u.buffs):
                if (b.expire_half is not None and b.applied_half_turn != ht
                        and ht >= b.expire_half):
                    u.buffs.remove(b)
                    expired = True
            for d in list(u.debuffs):
                if (d.expire_half is not None and d.applied_half_turn != ht
                        and ht >= d.expire_half):
                    u.debuffs.remove(d)
                    expired = True
        return expired

    def _find_combo_partner(self, unit: 'BattleUnit', allies: List['BattleUnit'], enemies: List['BattleUnit'], claimed: set = None) -> Optional['BattleUnit']:
        """为 unit(作为A) 寻找可连携的友方 B：B 携带 unit，返回 B 或 None。

        连携是“不得已”的最后手段：仅当 A 自身【无法攻击到任何敌人】
        （普通攻击方向内没有可击目标）时才考虑连携；只要 A 自己能打到敌人，
        就老老实实普攻，绝不主动连携。存在可攻击的友方 B 时，
        优先选择对主目标属性克制更优、攻击力更高的 B；claimed 中的 B 已被本轮
        其他 A 认领，跳过它们以让更多 A 能连携。"""
        if getattr(unit, 'carried_by', None) or getattr(unit, 'carrying', None):
            return None
        # 关键：A 自己能打到敌人 → 不连携（宁可普攻）
        if self.get_targets_in_direction(unit, enemies):
            return None
        # A 打不到敌人：寻找能打到敌人、且尚未参与连携的友方 B
        primary = next((e for e in enemies if e.alive and e.position < 5), None)
        best = None
        best_score = -1.0
        for b in allies:
            if b is unit or not b.alive:
                continue
            if getattr(b, 'carried_by', None) or getattr(b, 'carrying', None):
                continue  # B 已参与连携
            if claimed and id(b) in claimed:
                continue  # B 本轮已被其他 A 认领
            if not self.get_targets_in_direction(b, enemies):
                continue  # B 自己也打不到敌人，带 A 没意义
            # 评分：属性克制优先，其次攻击力
            score = 0.0
            if primary is not None:
                score += self._get_attribute_multiplier(b.character.attribute, primary.character.attribute)
            score += min(b.character.attack / 2000.0, 1.0)
            if score > best_score:
                best = b
                best_score = score
        return best

    def _has_pierce(self, attacker: 'BattleUnit') -> bool:
        """检查攻击方是否有贯通（穿透盾）"""
        return any(b.name == '贯通' for b in attacker.buffs)

    def _check_shield(self, target: 'BattleUnit', attacker: 'BattleUnit') -> bool:
        """盾: 抵挡一次非贯通伤害, 返回True表示伤害被盾抵挡"""
        if self._has_pierce(attacker):
            return False  # 贯通穿透盾
        for b in list(target.buffs):
            if b.name == '盾':
                target.buffs.remove(b)
                return True
        return False

    def _check_dodge(self, target: 'BattleUnit', attacker: 'BattleUnit') -> bool:
        """回避判定：返回True=回避成功。预测不能可无视回避"""
        if any(b.name == '预测不能' for b in attacker.buffs):
            return False
        dodge_rate = 0.0
        rate_map = {'小': 0.10, '中': 0.15, '大': 0.25, '特大': 0.35}
        for b in target.buffs:
            if b.name == '回避率':
                dodge_rate += rate_map.get(b.magnitude, 0.15)
        for d in target.debuffs:
            if d.name == '回避率':
                dodge_rate -= rate_map.get(d.magnitude, 0.15)
        dodge_rate = max(0, min(0.5, dodge_rate))
        return random.random() < dodge_rate

    def _handle_counter_effects(self, target: 'BattleUnit', attacker: 'BattleUnit',
                                 damage: int) -> Tuple[int, List[str], bool]:
        """
        处理反击/反射/天罚效果。
        返回 (实际对目标造成的伤害, 日志, 攻击者是否死亡)

        天罚:     格挡全部伤害 + 眩晕攻击者（消耗）
        矢量操作:  反射物理伤害
        强制咏唱待机: 反射异能伤害
        全能神:   反射物理+异能双重伤害
        """
        results = []
        actual_damage = damage
        attacker_died = False

        # 天罚: 格挡伤害 + 眩晕攻击者（优先，消耗后不再检查其他反射）
        for b in list(target.buffs):
            if b.name == '天罚':
                actual_damage = 0
                target.buffs.remove(b)
                self._apply_debuff(attacker, '气绝', '中', '天罚')
                results.append(f"⚡天罚发动！{target.character.name}抵挡{damage}伤害，{attacker.character.name}被眩晕！")
                return actual_damage, results, False

        # 反射效果（不格挡伤害，额外对攻击者造成反射伤害）
        atk_type = attacker.character.attack_type
        for b in list(target.buffs):
            reflect_dmg = 0
            reflect_label = ""

            if b.name == '矢量操作' and atk_type == '物理':
                reflect_dmg = damage
                reflect_label = "物理"
            elif b.name == '强制咏唱待机' and atk_type == '异能':
                reflect_dmg = damage
                reflect_label = "异能"
            elif b.name == '全能神':
                reflect_dmg = damage * 2
                reflect_label = "物理+异能"

            if reflect_dmg > 0:
                results.append(f"↩{b.name}反射！{attacker.character.name}受到{reflect_dmg}{reflect_label}伤害")
                attacker.current_hp -= reflect_dmg
                if attacker.current_hp <= 0:
                    if not self._check_tenacity(attacker):
                        attacker.current_hp = 0
                        attacker.alive = False
                        if attacker.assist_unit:
                            attacker.assist_unit.alive = False
                        results.append(f"{attacker.character.name}被反射伤害击破！")
                        attacker_died = True
                        break  # 攻击者死亡，停止检查

        return actual_damage, results, attacker_died

    def execute_normal_attack(self, attacker: BattleUnit, enemies: List[BattleUnit],
                              allies: List[BattleUnit] = None,
                              attacker_attribute_override: Optional[str] = None) -> Tuple[List[str], int, int]:
        """执行普通攻击，返回(战斗日志, 攻击方获得SP, 防守方获得SP)
        attacker_attribute_override: 连携时由被携带单位(A)调用，传入携带者(B)的属性
        """
        results = []
        targets = self.get_targets_in_direction(attacker, enemies)

        if not targets:
            return results, 15, 0  # 无目标: 攻击方获15, 防守方获0

        damage_results = []
        defender_sp = 0
        assist_sp = 0
        has_crit_this_attack = False
        has_damage_this_attack = False
        for target in targets:
            # 回避判定
            if self._check_dodge(target, attacker):
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                self._last_damage_info[side][target.character.name] = {
                    "dodged": True, "blocked": False, "reflected": False,
                    "absorbed": False, "reduced": False, "tenacious": False
                }
                results.append(f"{attacker.character.name} -> {target.character.name} (回避！)")
                defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))
                continue

            damage, is_crit, damage_type, attr_mult, ratio = self.calculate_damage(
                attacker, target, "normal", attacker_attribute_override=attacker_attribute_override)
            target_name = f"({ratio:.2f}){attacker.character.name} -> {target.character.name}"

            defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))

            # 天罚/反射判定
            damage, reflect_logs, attacker_died = self._handle_counter_effects(target, attacker, damage)
            results.extend(reflect_logs)

            # 记录受击状态
            hit_status = {"blocked": False, "reflected": False, "absorbed": False, "reduced": False, "dodged": False, "tenacious": False}

            # 检查是否有反射效果
            if len(reflect_logs) > 0 and "反射" in reflect_logs[-1]:
                hit_status["reflected"] = True

            # 盾判定：抵挡一次非贯通伤害
            if self._check_shield(target, attacker):
                hit_status["blocked"] = True
                # 判断目标是玩家还是敌方：攻击方在allies中说明是玩家攻击，目标是敌方
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                self._last_damage_info[side][target.character.name] = hit_status
                results.append(f"{target_name} ({damage}伤害，盾抵挡！) [{damage_type}]")
                continue

            # 外的御供: 受击获得攻击上升(大)，有层数则免疫本次伤害
            if self._apply_outside_offering_on_hit(target, results, target_name):
                hit_status["blocked"] = True
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                self._last_damage_info[side][target.character.name] = hit_status
                continue

            # 检查减伤
            dmg_reduce_mult, _ = target.get_buff_multiplier("减伤")
            if dmg_reduce_mult > 0:
                hit_status["reduced"] = True

            # 记录受击状态
            side = "player" if id(target) in self._player_unit_ids else "enemy"
            self._last_damage_info[side][target.character.name] = hit_status

            _tgt_hp_before = target.current_hp
            target.current_hp -= damage
            has_damage_this_attack = True

            # 连携伤害联动：携带者(B=target)受击时，被携带的A受到同等(实际)伤害
            if getattr(target, 'carrying', None) and target.carrying.alive:
                linked = target.carrying
                lost = _tgt_hp_before - max(target.current_hp, 0)  # B 本回合实际损失(上限为B剩余HP)
                linked.current_hp -= lost
                if linked.current_hp <= 0:
                    linked.current_hp = 0
                    linked.alive = False
                    if linked.assist_unit:
                        linked.assist_unit.alive = False
                    self._dissolve_combo(linked)  # A阵亡 → 解除连携，B存活
                    results.append(f"{linked.character.name} (连携联动, {lost}伤害, 击破！)")
                else:
                    results.append(f"{linked.character.name} (连携联动, {lost}伤害)")
            if is_crit:
                has_crit_this_attack = True

            # B类: 自身受到伤害时 + A类(pair): 我方一对角色受到伤害时
            if allies:
                sp, a_logs = self.trigger_assist_effects(target, enemies, allies, '自身受到伤害时')
                assist_sp += sp; results.extend(a_logs)
                sp, a_logs = self.trigger_assist_effects(target, enemies, allies, '我方一对角色受到伤害时')
                assist_sp += sp; results.extend(a_logs)

            if target.current_hp <= 0:
                if self._check_tenacity(target):
                    side = "player" if id(target) in self._player_unit_ids else "enemy"
                    self._last_damage_info[side][target.character.name] = {
                        "tenacious": True, "blocked": False, "dodged": False,
                        "reflected": False, "absorbed": False, "reduced": False
                    }
                    results.append(f"{target_name} ({damage}伤害，不屈！HP={target.current_hp}) [{damage_type}]")
                else:
                    target.current_hp = 0; target.alive = False
                    if target.position >= 0: target._last_valid_position = target.position
                    if target.assist_unit: target.assist_unit.alive = False
                    if getattr(target, 'carrying', None):
                        self._dissolve_combo(target)  # B(携带者)阵亡 → 解除连携，A存活
                    results.append(f"{target_name} ({damage}伤害，击破！) [{damage_type}]")
                    # B类: 自身使敌方退场时 + A类(pair): 我方一对角色使敌方退场时
                    if allies:
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身使敌方退场时')
                        assist_sp += sp; results.extend(a_logs)
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '击破时')
                        assist_sp += sp; results.extend(a_logs)
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色使敌方退场时')
                        assist_sp += sp; results.extend(a_logs)
            else:
                results.append(f"{target_name} ({damage}伤害) [{damage_type}]")

        # ===== P5: 被攻击时触发 =====
        if allies and has_damage_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身对敌方造成伤害时')
            assist_sp += sp; results.extend(a_logs)
        if allies and has_crit_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)

        attacker_sp = int(SP_PER_ATTACK * self._get_sp_rate(attacker)) + assist_sp

        # 连携：携带者(B)普攻时，被携带A用B的属性协同攻击（A其余属性仍按A自身）
        carried = getattr(attacker, 'carrying', None)
        if carried and carried.alive:
            a_results, a_sp, a_def = self.execute_normal_attack(
                carried, enemies, allies, attacker_attribute_override=attacker.character.attribute)
            results.extend([f'  [连携] {carried.character.name} 协同攻击'] + a_results)
            attacker_sp += a_sp
            defender_sp += a_def

        self._last_attack_had_crit = has_crit_this_attack

        return results, attacker_sp, defender_sp

    def execute_skill_attack(self, attacker: BattleUnit, enemies: List[BattleUnit],
                            can_use_skill: bool = True, skill_sp: int = 30,
                            allies: List[BattleUnit] = None) -> Tuple[List[str], int, int, int]:
        """执行技能攻击，返回(战斗日志, 消耗的SP, 攻击方获得SP, 防守方获得SP)"""
        results = []

        if not attacker.character.skill:
            r, atk_sp, def_sp = self.execute_normal_attack(attacker, enemies, allies)
            return r, 0, atk_sp, def_sp

        if not can_use_skill:
            r, atk_sp, def_sp = self.execute_normal_attack(attacker, enemies, allies)
            return r, 0, atk_sp, def_sp

        if attacker.skill_cooldown > 0:
            r, atk_sp, def_sp = self.execute_normal_attack(attacker, enemies, allies)
            return r, 0, atk_sp, def_sp

        targets = self.get_targets_in_direction(attacker, enemies, attacker.character.skill.area)

        if not targets:
            return results, 0, 15, 0  # 无目标: 不扣SP, 攻击方获15, 防守方获0

        defender_sp = 0
        assist_sp = 0
        has_crit_this_attack = False
        has_damage_this_attack = False
        for target in targets:
            # 回避判定
            if self._check_dodge(target, attacker):
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                self._last_damage_info[side][target.character.name] = {
                    "dodged": True, "blocked": False, "reflected": False,
                    "absorbed": False, "reduced": False, "tenacious": False
                }
                results.append(f"{attacker.character.name} -> {target.character.name} (回避！)")
                defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))
                continue

            damage, is_crit, damage_type, attr_mult, ratio = self.calculate_damage(
                attacker, target, "skill", attacker.character.skill.power_rank
            )
            target_name = f"({ratio:.2f}){attacker.character.name} -> {target.character.name}"
            defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))

            # 天罚/反射判定
            damage, reflect_logs, attacker_died = self._handle_counter_effects(target, attacker, damage)
            results.extend(reflect_logs)

            # 盾判定：抵挡一次非贯通伤害
            if self._check_shield(target, attacker):
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                hit_status = {"blocked": True, "dodged": False, "reflected": False,
                              "absorbed": False, "reduced": False, "tenacious": False}
                if len(reflect_logs) > 0 and "反射" in reflect_logs[-1]:
                    hit_status["reflected"] = True
                self._last_damage_info[side][target.character.name] = hit_status
                results.append(f"{target_name} ({damage}伤害，盾抵挡！) [{damage_type}]")
                continue

            # 外的御供: 受击获得攻击上升(大)，有层数则免疫本次伤害
            if self._apply_outside_offering_on_hit(target, results, target_name):
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                hit_status = {"blocked": True, "dodged": False, "reflected": False,
                              "absorbed": False, "reduced": False, "tenacious": False}
                self._last_damage_info[side][target.character.name] = hit_status
                continue

            # 记录受击状态（减伤）
            side = "player" if id(target) in self._player_unit_ids else "enemy"
            hit_status = {"blocked": False, "dodged": False, "reflected": False,
                          "absorbed": False, "reduced": False, "tenacious": False}
            if len(reflect_logs) > 0 and "反射" in reflect_logs[-1]:
                hit_status["reflected"] = True
            dmg_reduce_mult, _ = target.get_buff_multiplier("减伤")
            if dmg_reduce_mult > 0:
                hit_status["reduced"] = True
            self._last_damage_info[side][target.character.name] = hit_status

            _tgt_hp_before = target.current_hp
            target.current_hp -= damage
            has_damage_this_attack = True

            # 连携伤害联动：携带者(B=target)受击时，被携带的A受到同等(实际)伤害
            if getattr(target, 'carrying', None) and target.carrying.alive:
                linked = target.carrying
                lost = _tgt_hp_before - max(target.current_hp, 0)  # B 本回合实际损失(上限为B剩余HP)
                linked.current_hp -= lost
                if linked.current_hp <= 0:
                    linked.current_hp = 0
                    linked.alive = False
                    if linked.assist_unit:
                        linked.assist_unit.alive = False
                    self._dissolve_combo(linked)  # A阵亡 → 解除连携，B存活
                    results.append(f"{linked.character.name} (连携联动, {lost}伤害, 击破！)")
                else:
                    results.append(f"{linked.character.name} (连携联动, {lost}伤害)")
            if is_crit:
                has_crit_this_attack = True

            # B类: 自身受到伤害时 + A类(pair): 我方一对角色受到伤害时
            if allies:
                sp, a_logs = self.trigger_assist_effects(target, enemies, allies, '自身受到伤害时')
                assist_sp += sp; results.extend(a_logs)
                sp, a_logs = self.trigger_assist_effects(target, enemies, allies, '我方一对角色受到伤害时')
                assist_sp += sp; results.extend(a_logs)

            if target.current_hp <= 0:
                if self._check_tenacity(target):
                    self._last_damage_info[side][target.character.name] = {
                        "tenacious": True, "blocked": False, "dodged": False,
                        "reflected": False, "absorbed": False, "reduced": False
                    }
                    results.append(f"{target_name} ({damage}伤害，不屈！HP={target.current_hp}) [{damage_type}]")
                else:
                    target.current_hp = 0; target.alive = False
                    if target.assist_unit: target.assist_unit.alive = False
                    if target.position >= 0: target._last_valid_position = target.position
                    results.append(f"{target_name} ({damage}伤害，击破！) [{damage_type}]")
                    # B类: 自身使敌方退场时 + A类(pair): 我方一对角色使敌方退场时
                    if allies:
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身使敌方退场时')
                        assist_sp += sp; results.extend(a_logs)
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '击破时')
                        assist_sp += sp; results.extend(a_logs)
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色使敌方退场时')
                        assist_sp += sp; results.extend(a_logs)
            else:
                results.append(f"{target_name} ({damage}伤害) [{damage_type}]")
        attacker.skill_cooldown = attacker.character.skill.cooldown

        # 应用技能增益效果
        if allies:
            buff_results = self._apply_skill_effect(attacker, attacker.character.skill, allies, enemies)
            results.extend(buff_results)

        # ===== P5: 被攻击时触发 + 技能时 =====
        if allies and has_damage_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身对敌方造成伤害时')
            assist_sp += sp; results.extend(a_logs)
        if allies and has_crit_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)
        if allies:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身技能时')
            assist_sp += sp; results.extend(a_logs)
            # A类(pair): 我方一对角色技能时（同自身技能时语义）
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色技能时')
            assist_sp += sp; results.extend(a_logs)

        attacker_sp = int(SP_PER_ATTACK * self._get_sp_rate(attacker)) + assist_sp

        self._last_attack_had_crit = has_crit_this_attack

        return results, 30, attacker_sp, defender_sp

    def execute_ultimate_attack(self, attacker: BattleUnit, enemies: List[BattleUnit],
                               can_use_ultimate: bool = True,
                               allies: List[BattleUnit] = None) -> Tuple[List[str], int, int, int]:
        """执行必杀技，返回(战斗日志, 消耗的SP, 攻击方获得SP, 防守方获得SP)"""
        results = []

        if not attacker.character.ultimate:
            r, used, atk_sp, def_sp = self.execute_skill_attack(attacker, enemies, can_use_ultimate, SP_MAX, allies)
            return r, used, atk_sp, def_sp

        if not can_use_ultimate:
            r, used, atk_sp, def_sp = self.execute_skill_attack(attacker, enemies, True, 30, allies)
            return r, used, atk_sp, def_sp

        ultimate = attacker.character.ultimate
        targets = self.get_targets_in_direction(attacker, enemies, ultimate.area)

        if not targets:
            return results, 0, 15, 0  # 无目标: 不扣SP, 攻击方获15, 防守方获0

        # 计算威力上升数量（强化数/弱体数）
        power_up_count = 0
        if ultimate.power_up_type == "强化数":
            power_up_count = len(attacker.buffs)
        elif ultimate.power_up_type == "弱体数":
            power_up_count = len(attacker.debuffs)

        damage_results = []
        defender_sp = 0
        assist_sp = 0
        has_crit_this_attack = False
        has_damage_this_attack = False
        for target in targets:
            # 回避判定
            if self._check_dodge(target, attacker):
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                self._last_damage_info[side][target.character.name] = {
                    "dodged": True, "blocked": False, "reflected": False,
                    "absorbed": False, "reduced": False, "tenacious": False
                }
                results.append(f"{attacker.character.name} -> {target.character.name} (回避！)")
                defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))
                continue

            damage, is_crit, damage_type, attr_mult, ratio = self.calculate_damage(
                attacker, target, "ultimate", ultimate.power_rank, power_up_count
            )
            target_name = f"({ratio:.2f}){attacker.character.name} -> {target.character.name}"
            defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))

            # 天罚/反射判定
            damage, reflect_logs, attacker_died = self._handle_counter_effects(target, attacker, damage)
            results.extend(reflect_logs)

            # 盾判定：抵挡一次非贯通伤害
            if self._check_shield(target, attacker):
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                hit_status = {"blocked": True, "dodged": False, "reflected": False,
                              "absorbed": False, "reduced": False, "tenacious": False}
                if len(reflect_logs) > 0 and "反射" in reflect_logs[-1]:
                    hit_status["reflected"] = True
                self._last_damage_info[side][target.character.name] = hit_status
                results.append(f"{target_name} ({damage}伤害，盾抵挡！) [{damage_type}]")
                continue

            # 外的御供: 受击获得攻击上升(大)，有层数则免疫本次伤害
            if self._apply_outside_offering_on_hit(target, results, target_name):
                side = "player" if id(target) in self._player_unit_ids else "enemy"
                hit_status = {"blocked": True, "dodged": False, "reflected": False,
                              "absorbed": False, "reduced": False, "tenacious": False}
                self._last_damage_info[side][target.character.name] = hit_status
                continue

            # 记录受击状态（减伤）
            side = "player" if id(target) in self._player_unit_ids else "enemy"
            hit_status = {"blocked": False, "dodged": False, "reflected": False,
                          "absorbed": False, "reduced": False, "tenacious": False}
            if len(reflect_logs) > 0 and "反射" in reflect_logs[-1]:
                hit_status["reflected"] = True
            dmg_reduce_mult, _ = target.get_buff_multiplier("减伤")
            if dmg_reduce_mult > 0:
                hit_status["reduced"] = True
            self._last_damage_info[side][target.character.name] = hit_status

            _tgt_hp_before = target.current_hp
            target.current_hp -= damage
            has_damage_this_attack = True

            # 连携伤害联动：携带者(B=target)受击时，被携带的A受到同等(实际)伤害
            if getattr(target, 'carrying', None) and target.carrying.alive:
                linked = target.carrying
                lost = _tgt_hp_before - max(target.current_hp, 0)  # B 本回合实际损失(上限为B剩余HP)
                linked.current_hp -= lost
                if linked.current_hp <= 0:
                    linked.current_hp = 0
                    linked.alive = False
                    if linked.assist_unit:
                        linked.assist_unit.alive = False
                    self._dissolve_combo(linked)  # A阵亡 → 解除连携，B存活
                    results.append(f"{linked.character.name} (连携联动, {lost}伤害, 击破！)")
                else:
                    results.append(f"{linked.character.name} (连携联动, {lost}伤害)")
            if is_crit:
                has_crit_this_attack = True

            # B类: 自身受到伤害时 + A类(pair): 我方一对角色受到伤害时
            if allies:
                sp, a_logs = self.trigger_assist_effects(target, enemies, allies, '自身受到伤害时')
                assist_sp += sp; results.extend(a_logs)
                sp, a_logs = self.trigger_assist_effects(target, enemies, allies, '我方一对角色受到伤害时')
                assist_sp += sp; results.extend(a_logs)

            if target.current_hp <= 0:
                if self._check_tenacity(target):
                    self._last_damage_info[side][target.character.name] = {
                        "tenacious": True, "blocked": False, "dodged": False,
                        "reflected": False, "absorbed": False, "reduced": False
                    }
                    results.append(f"{target_name} ({damage}伤害，不屈！HP={target.current_hp}) [{damage_type}]")
                else:
                    target.current_hp = 0; target.alive = False
                    if target.assist_unit: target.assist_unit.alive = False
                    if target.position >= 0: target._last_valid_position = target.position
                    results.append(f"{target_name} ({damage}伤害，击破！) [{damage_type}]")
                    # B类: 自身使敌方退场时 + A类(pair): 我方一对角色使敌方退场时
                    if allies:
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身使敌方退场时')
                        assist_sp += sp; results.extend(a_logs)
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '击破时')
                        assist_sp += sp; results.extend(a_logs)
                        sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色使敌方退场时')
                        assist_sp += sp; results.extend(a_logs)
            else:
                results.append(f"{target_name} ({damage}伤害) [{damage_type}]")

        # 应用技能增益效果
        if allies:
            buff_results = self._apply_skill_effect(attacker, ultimate, allies, enemies)
            results.extend(buff_results)

        # ===== P5: 被攻击时触发 + 必杀时 =====
        if allies and has_damage_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身对敌方造成伤害时')
            assist_sp += sp; results.extend(a_logs)
        if allies and has_crit_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)
        if allies:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '自身必杀时')
            assist_sp += sp; results.extend(a_logs)
            # A类(pair): 我方一对角色必杀时（同自身必杀时语义）
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '我方一对角色必杀时')
            assist_sp += sp; results.extend(a_logs)

        attacker_sp = int(SP_PER_ATTACK * self._get_sp_rate(attacker)) + assist_sp

        self._last_attack_had_crit = has_crit_this_attack

        return results, 100, attacker_sp, defender_sp

    def trigger_assist_effects(self, unit: BattleUnit, allies: List[BattleUnit],
                               enemies: List[BattleUnit], trigger_type: str = "行动开始时") -> Tuple[int, List[str]]:
        """触发支援卡效果，返回(SP变化量, 日志列表)"""
        total_sp_gained = 0
        raw_logs = []
        cd_logs = []

        if not unit.assist_unit:
            return 0, []

        # a卡封印: 阻止支援卡效果触发
        if any(d.name == 'a卡封印' for d in unit.debuffs):
            return 0, []

        assist_char = unit.assist_unit.character

        # 检查效果1
        if assist_char.assist_effect1 and assist_char.assist_effect1.is_ready():
            if assist_char.assist_effect1.trigger_time == trigger_type:
                sp, logs = self._apply_assist_effect(unit, assist_char.assist_effect1, allies, enemies)
                total_sp_gained += sp
                raw_logs.extend(logs)
                assist_char.assist_effect1.current_count += 1
                assist_char.assist_effect1.current_cd = assist_char.assist_effect1.cd  # 触发后设置冷却
                if assist_char.assist_effect1.cd > 0:
                    cd_logs.append(f"  [A卡CD] {assist_char.name} 效果1进入冷却({assist_char.assist_effect1.cd}回合)")

        # 检查效果2
        if assist_char.assist_effect2 and assist_char.assist_effect2.is_ready():
            if assist_char.assist_effect2.trigger_time == trigger_type:
                sp, logs = self._apply_assist_effect(unit, assist_char.assist_effect2, allies, enemies)
                total_sp_gained += sp
                raw_logs.extend(logs)
                assist_char.assist_effect2.current_count += 1
                assist_char.assist_effect2.current_cd = assist_char.assist_effect2.cd  # 触发后设置冷却
                if assist_char.assist_effect2.cd > 0:
                    cd_logs.append(f"  [A卡CD] {assist_char.name} 效果2进入冷却({assist_char.assist_effect2.cd}回合)")

        # 合并同角色BUFF为一行: "角色名 BUFF1, BUFF2, ... [A]"
        import re as _re
        consolidated = {}
        for log_line in raw_logs:
            m = _re.match(r'^(.+?) (.+?) \[A\]$', log_line)
            if m:
                name = m.group(1)
                effect = m.group(2)
                if name not in consolidated:
                    consolidated[name] = []
                consolidated[name].append(effect)
            else:
                # 非标准格式，保留原样
                consolidated.setdefault('__raw__', []).append(log_line)

        all_logs = []
        for name, effects in consolidated.items():
            if name == '__raw__':
                all_logs.extend(effects)
            else:
                all_logs.append(f"{name} {', '.join(effects)} [A]")
        all_logs.extend(cd_logs)

        return total_sp_gained, all_logs

    def _apply_assist_effect(self, source_unit: BattleUnit, effect: AssistEffect,
                            allies: List[BattleUnit], enemies: List[BattleUnit]) -> Tuple[int, List[str]]:
        """应用支援卡效果，返回(SP变化量, 日志列表)"""
        sp_gained = 0
        logs = []

        # 确定目标
        targets = []
        area = effect.area

        if "自身以外" in area:
            targets = [u for u in allies if not u.is_assist and u.alive and u != source_unit]
        elif "我方一对角色" in area:
            # 自身 + 相邻1格的友方（5列布局中相邻即±1，按位置排序确保确定性）
            targets = [source_unit]
            sorted_allies = sorted([a for a in allies if a != source_unit and not a.is_assist and a.alive],
                                    key=lambda x: x.position)
            for ally in sorted_allies:
                if abs((ally.position % 5) - (source_unit.position % 5)) == 1:
                    targets.append(ally)
                    break
        elif "我方全体" in area:
            targets = [u for u in allies if not u.is_assist and u.alive and u.position < 5]
        elif "敌全体" in area:
            targets = [e for e in enemies if not e.is_assist and e.alive and e.position < 5]
        elif "色敌全体" in area:
            # X色敌全体
            color_match = re.match(r'(红|绿|蓝|黄|紫)色敌全体', area)
            if color_match:
                target_color = color_match.group(1)
                targets = [e for e in enemies if not e.is_assist and e.alive and e.position < 5 and
                          self._get_base_attribute(e.character.attribute) == target_color]
        elif "该敌方角色" in area:
            # 攻击目标方向的第一个敌人
            dir_targets = self.get_targets_in_direction(source_unit, enemies)
            targets = dir_targets[:1] if dir_targets else []
        elif "同色" in area:
            source_attr = self._get_base_attribute(source_unit.character.attribute)
            if "我方" in area:
                targets = [u for u in allies if not u.is_assist and u.alive and u.position < 5 and
                          self._get_base_attribute(u.character.attribute) == source_attr]
            else:
                targets = [e for e in enemies if not e.is_assist and e.alive and e.position < 5 and
                          self._get_base_attribute(e.character.attribute) == source_attr]
        else:
            targets = [source_unit]

        # 应用效果（使用解析出的持续回合数）
        dur = effect.duration if effect.duration > 0 else 0
        for effect_text in (effect.effects or []):
            if not isinstance(effect_text, str): continue

            # === buff类 ===
            # 物攻/异攻 统一映射为"攻击"buff
            m = re.match(r'(物|异)攻提升\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "攻击", m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} {m.group(1)}攻提升({m.group(2)}) [A]")

            # 物防/异防 统一映射为"防御"buff
            m = re.match(r'(物|异)防提升\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "防御", m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} {m.group(1)}防提升({m.group(2)}) [A]")

            # 暴伤buff
            m = re.match(r'暴伤提升\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "暴伤", m.group(1), "a卡", dur)
                        logs.append(f"{target.character.name} 暴伤提升({m.group(1)}) [A]")

            # 必杀/技能威力buff
            m = re.match(r'(必杀|技能)威力提升\((.+?)\)', effect_text)
            if m:
                buf_name = m.group(1) + "威力"
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, buf_name, m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} {buf_name}提升({m.group(2)}) [A]")

            # 暴击率 / 回避率 / 暴击防御buff
            for rate_type in ['暴击率', '回避率', '暴击防御']:
                m = re.match(fr'{rate_type}提升\((.+?)\)', effect_text)
                if m:
                    buf_name = rate_type
                    for target in targets:
                        if target in allies:
                            self._apply_buff(target, buf_name, m.group(1), "a卡", dur)
                            logs.append(f"{target.character.name} {buf_name}提升({m.group(1)}) [A]")

            # SP获得量buff
            m = re.match(r'SP获得量提升\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "SP获得量", m.group(1), "a卡", dur)
                        logs.append(f"{target.character.name} SP获得量提升({m.group(1)}) [A]")

            # 外的御供（多层免伤护盾 + 受击攻击上升大）
            m = re.match(r'外的御供\((.+?)\)', effect_text)
            if m:
                try:
                    charges = int(m.group(1))
                except ValueError:
                    charges = 1
                for target in targets:
                    if target in allies:
                        self._apply_outside_offering(target, charges, dur)
                        logs.append(f"{target.character.name} 外的御供({charges}) [A]")

            # 减伤buff
            m = re.match(r'[^【]*减伤\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "减伤", m.group(1), "a卡", dur)
                        logs.append(f"{target.character.name} 减伤({m.group(1)}) [A]")

            # 对X色威力提升
            m = re.match(r'对(红|绿|蓝|黄|紫)色威力提升\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "颜色威力", m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} 颜色威力提升({m.group(2)}) [A]")

            # X色减伤
            m = re.match(r'(红|绿|蓝|黄|紫)色减伤\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "减伤", m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} 减伤({m.group(2)}) [A]")

            # 特殊buff（无幅度，默认"中"）
            for sp_buf in ['盾', '贯通', '强耐', '弱耐']:
                if sp_buf in effect_text and not re.search(rf'{sp_buf}\(.+?\)', effect_text):
                    for target in targets:
                        if target in allies:
                            self._apply_buff(target, sp_buf, "中", "a卡", dur)
                            logs.append(f"{target.character.name} 获得{sp_buf} [A]")

            # 不屈
            m = re.match(r'不屈(?:\((.+?)\))?', effect_text)
            if m:
                for target in targets:
                    if target in allies:
                        mag = m.group(1) or "中"
                        self._apply_buff(target, "不屈", mag, "a卡", dur)
                        logs.append(f"{target.character.name} 获得不屈({mag}) [A]")

            # 必暴
            if '必暴' in effect_text:
                for target in targets:
                    if target in allies:
                        self._apply_buff(target, "必暴", "中", "a卡", dur)
                        logs.append(f"{target.character.name} 获得必暴 [A]")

            # === debuff类（施加给敌方）===
            # 物攻/异攻 下降 → 统一映射为"攻击"debuff
            m = re.match(r'(物|异)攻下降\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in enemies:
                        self._apply_debuff(target, "攻击", m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} {m.group(1)}攻下降({m.group(2)}) [A]")

            # 物防/异防 下降 → 统一映射为"防御"debuff
            m = re.match(r'(物|异)防下降\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in enemies:
                        self._apply_debuff(target, "防御", m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} {m.group(1)}防下降({m.group(2)}) [A]")

            # 暴击率/回避率下降
            for rate_type in ['暴击率', '回避率']:
                m = re.match(fr'{rate_type}下降\((.+?)\)', effect_text)
                if m:
                    for target in targets:
                        if target in enemies:
                            self._apply_debuff(target, rate_type, m.group(1), "a卡", dur)
                            logs.append(f"{target.character.name} {rate_type}下降({m.group(1)}) [A]")

            # 颜色耐性下降
            m = re.match(r'(红|绿|蓝|黄|紫)色耐性下降\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in enemies:
                        self._apply_debuff(target, "颜色耐性", m.group(2), "a卡", dur)
                        logs.append(f"{target.character.name} 颜色耐性下降({m.group(2)}) [A]")

            # SP获得量下降
            m = re.match(r'SP获得量下降\((.+?)\)', effect_text)
            if m:
                for target in targets:
                    if target in enemies:
                        self._apply_debuff(target, "SP获得量", m.group(1), "a卡", dur)
                        logs.append(f"{target.character.name} SP获得量下降({m.group(1)}) [A]")

            # 特殊debuff（无幅度）
            for sp_deb in ['感电', '气绝', '移动不能', '制御不能', 'a卡封印',
                          '技能封印', '必杀封印', '强化妨害', '攻击提升妨害',
                          'HP回复妨害', '弱体化解除妨害']:
                if sp_deb in effect_text:
                    for target in targets:
                        if target in enemies:
                            self._apply_debuff(target, sp_deb, "中", "a卡", dur)
                            logs.append(f"{target.character.name} {sp_deb} [A]")

            # === 状态解除 ===
            for clr_type, clr_target in [('弱体状态解除', 'debuff'), ('强化状态解除', 'buff')]:
                if clr_type in effect_text:
                    if clr_target == 'debuff':
                        clear_targets = [t for t in targets if t in allies]
                        for t in clear_targets:
                            removed = [d.name for d in list(t.debuffs)
                                      if d.name not in ('弱体化解除妨害',)]
                            for d_name in removed:
                                t.debuffs = [d for d in t.debuffs if d.name != d_name]
                            if removed:
                                logs.append(f"{t.character.name} 弱体状态解除: {', '.join(removed)} [A]")
                    else:
                        clear_targets = [t for t in targets if t in enemies]
                        for t in clear_targets:
                            removed = [b.name for b in list(t.buffs)]
                            for b_name in removed:
                                t.buffs = [b for b in t.buffs if b.name != b_name]
                            if removed:
                                logs.append(f"{t.character.name} 强化状态解除: {', '.join(removed)} [A]")

            # === HP回复 ===
            m = re.match(r'HP回复\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                heal_pcts = {'小': 0.15, '中': 0.30, '大': 0.50}
                heal_pct = heal_pcts.get(magnitude, 0.20)
                for t in targets:
                    if t in allies and t.alive:
                        if any(d.name == 'HP回复妨害' for d in t.debuffs):
                            continue
                        heal_amount = max(1, int(t.max_hp * heal_pct))
                        t.current_hp = min(t.max_hp, t.current_hp + heal_amount)
                        logs.append(f"{t.character.name} HP回复+{heal_amount} [A]")

            # === 技能CD减少 ===
            m = re.match(r'技能CD减(\d+)', effect_text)
            if m:
                cd_reduce = int(m.group(1))
                for t in targets:
                    if t in allies and t.alive:
                        t.skill_cooldown = max(0, t.skill_cooldown - cd_reduce)
                        logs.append(f"{t.character.name} 技能CD-{cd_reduce} [A]")

            # 必杀CD减少 (スキル,必杀CD减X = both)
            m = re.match(r'.*必杀CD减(\d+)', effect_text)
            if m:
                cd_reduce = int(m.group(1))
                for t in targets:
                    if t in allies and t.alive:
                        t.ult_cooldown = max(0, t.ult_cooldown - cd_reduce)
                        logs.append(f"{t.character.name} 必杀CD-{cd_reduce} [A]")

            # === SP获得 ===
            # SP固定上升
            m = re.match(r'SP(\d+)上升', effect_text)
            if m:
                sp_gained += int(m.group(1))
                logs.append(f"SP+{m.group(1)} [A]")

            # 根据X侧/Y色数量SP上升
            m = re.match(r'根据(..侧|.色)数量SP(大)?上升', effect_text)
            if m:
                condition = m.group(1)
                sp_base = 10 if m.group(2) == "大" else 5
                count = 0
                for ally in allies:
                    if ally.is_assist or not ally.alive:
                        continue
                    if condition.endswith("侧"):
                        if condition == "前侧" and ally.position % 5 == 0:
                            count += 1
                        elif condition == "后侧" and ally.position % 5 == BATTLE_POSITIONS_ON_FIELD - 1:
                            count += 1
                    else:
                        if self._get_base_attribute(ally.character.attribute) == condition:
                            count += 1
                sp_gained += sp_base * count

        return sp_gained, logs

    def _get_adjacent_allies(self, allies: List[BattleUnit], attacker: BattleUnit,
                              right: bool = False, left: bool = False, both: bool = False) -> List[BattleUnit]:
        """返回 [施法者] + 指定方向的相邻友军（按 position±1，限制在 0..4 部署列）。

        用于支持「自身与右邻 / 自身与左邻 / 自身与两邻」这类带邻接范围的效果。
        """
        result = [attacker]
        deltas = []
        if both:
            deltas = [-1, 1]
        elif right:
            deltas = [1]
        elif left:
            deltas = [-1]
        for d in deltas:
            pos = attacker.position + d
            if 0 <= pos < 5:
                nb = next((u for u in allies
                           if u.alive and not u.is_assist and u.position == pos and u is not attacker), None)
                if nb:
                    result.append(nb)
        return result

    def _skill_debuff_targets(self, attacker: BattleUnit, skill: Skill,
                             enemies: List[BattleUnit]) -> List[BattleUnit]:
        """技能减益的施加目标（敌方），按 skill.area 选敌（与 A 卡效果一致）"""
        area = skill.area if skill else "正面"
        if "敌全体" in area:
            return [e for e in enemies if e.alive and not e.is_assist and e.position < 5]
        m = re.match(r'(红|绿|蓝|黄|紫)色敌全体', area)
        if m:
            col = m.group(1)
            return [e for e in enemies if e.alive and not e.is_assist and e.position < 5
                    and self._get_base_attribute(e.character.attribute) == col]
        # 方向性减益：攻击者方向上的敌人
        targets = self.get_targets_in_direction(attacker, enemies, area if area != "正面" else "正面")
        if targets:
            return targets
        return [e for e in enemies if e.alive and not e.is_assist and e.position < 5]

    def _apply_skill_effect(self, attacker: BattleUnit, skill: Skill,
                           allies: List[BattleUnit], enemies: List[BattleUnit]) -> List[str]:
        """应用技能效果，返回增益日志"""
        results = []

        # 确定目标
        targets = []
        is_ally_target = False

        if "我方全体" in skill.area:
            targets = [u for u in allies if not u.is_assist and u.alive and u.position < 5]
            is_ally_target = True
        elif "自身与两邻" in skill.area:
            targets = self._get_adjacent_allies(allies, attacker, both=True)
            is_ally_target = True
        elif "自身与右邻" in skill.area:
            targets = self._get_adjacent_allies(allies, attacker, right=True)
            is_ally_target = True
        elif "自身与左邻" in skill.area:
            targets = self._get_adjacent_allies(allies, attacker, left=True)
            is_ally_target = True
        elif "自身" in skill.area or "正面" in skill.area or "左侧" in skill.area or "右侧" in skill.area:
            targets = [attacker]
            is_ally_target = True
        elif "同色" in skill.area:
            source_attr = self._get_base_attribute(attacker.character.attribute)
            targets = [u for u in allies if not u.is_assist and u.alive and
                      self._get_base_attribute(u.character.attribute) == source_attr]
            is_ally_target = True
        else:
            # 默认对敌人
            targets = [attacker]  # 攻击者自身

        # 应用效果
        for effect_text in (skill.effects or []):
            if not isinstance(effect_text, str): continue
            # 攻击buff
            m = re.match(r'物攻提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    self._apply_buff(target, "攻击", magnitude, "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} {effect_text}")

            # 防御buff
            m = re.match(r'物防提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    self._apply_buff(target, "防御", magnitude, "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} {effect_text}")

            # 暴伤buff
            m = re.match(r'暴伤提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    self._apply_buff(target, "暴伤", magnitude, "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} {effect_text}")

            # 必杀威力buff
            m = re.match(r'必杀威力提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    self._apply_buff(target, "必杀威力", magnitude, "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} {effect_text}")

            # 技能威力buff
            m = re.match(r'技能威力提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_buff(t, "技能威力", magnitude, "技能")
                results.append(f"{attacker.character.name} 对 {'、'.join([t.character.name for t in buff_targets])} {effect_text}")

            # 暴击率buff
            m = re.match(r'暴击率提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_buff(t, "暴击率", magnitude, "技能")
                results.append(f"{attacker.character.name} 对 {'、'.join([t.character.name for t in buff_targets])} {effect_text}")

            # 回避率buff
            m = re.match(r'回避率提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_buff(t, "回避率", magnitude, "技能")
                results.append(f"{attacker.character.name} 对 {'、'.join([t.character.name for t in buff_targets])} {effect_text}")

            # SP获得量buff
            m = re.match(r'SP获得量提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_buff(t, "SP获得量", magnitude, "技能")
                results.append(f"{attacker.character.name} 对 {'、'.join([t.character.name for t in buff_targets])} {effect_text}")

            # 减伤buff
            m = re.match(r'[^【]*减伤\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_buff(t, "减伤", magnitude, "技能")
                results.append(f"{attacker.character.name} 对 {'、'.join([t.character.name for t in buff_targets])} {effect_text}")

            # 耐性增益（抵抗对应减益）：a卡封印/必杀封印/感电/移动不能 耐性
            m = re.match(r'(?:a卡封印|必杀封印|感电|移动不能)耐性', effect_text)
            if m:
                buff_name = m.group(0)
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_buff(t, buff_name, "中", "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} 【{buff_name}】")

            # 攻击方向+（增益，兼容 攻击/攻撃 两种写法）
            m = re.match(r'(?:攻击|攻撃)方向\+(.)', effect_text)
            if m:
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_buff(t, "攻击方向+", m.group(1), "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} 攻击方向+{m.group(1)}")

            # 盾
            if '盾' in effect_text and not re.match(r'.+\(.+\)', effect_text):
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    self._apply_buff(target, "盾", "中", "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} 【盾】")

            # 外的御供（多层免伤护盾 + 受击攻击上升大）
            m = re.match(r'外的御供\((.+?)\)', effect_text)
            if m:
                try:
                    charges = int(m.group(1))
                except ValueError:
                    charges = 1
                buff_targets = targets if is_ally_target else [attacker]
                for t in buff_targets:
                    self._apply_outside_offering(t, charges)
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} 【外的御供({charges})】")

            # 贯通
            if '贯通' in effect_text and not re.match(r'.+\(.+\)', effect_text):
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    self._apply_buff(target, "贯通", "中", "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} 【贯通】")

            # 不屈
            m = re.match(r'不屈(?:\((.+?)\))?', effect_text)
            if m:
                magnitude = m.group(1) or "中"
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    self._apply_buff(target, "不屈", magnitude, "技能")
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} 【不屈】({magnitude})")

            # HP回复
            m = re.match(r'HP回复\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                heal_pcts = {'小': 0.15, '中': 0.30, '大': 0.50}
                heal_pct = heal_pcts.get(magnitude, 0.20)
                if is_ally_target:
                    heal_targets = targets
                else:
                    heal_targets = [attacker]
                for t in heal_targets:
                    if any(d.name == 'HP回复妨害' for d in t.debuffs):
                        results.append(f"{t.character.name} HP回复被妨害！")
                        continue
                    heal_amount = max(1, int(t.max_hp * heal_pct))
                    t.current_hp = min(t.max_hp, t.current_hp + heal_amount)
                    results.append(f"{t.character.name} HP回复+{heal_amount}")

            # 强化解除 / 强化状态解除: 消除敌方buff（强耐可阻挡）
            if re.search(r'强化(?:状态)?解除', effect_text):
                unremovable = {'弱耐', '强耐', '盾', '不屈', '天罚', '矢量操作', '强制咏唱待机', '全能神', '贯通'}
                for enemy in enemies:
                    if enemy.alive:
                        blocked = False
                        for b in list(enemy.buffs):
                            if b.name == '强耐':
                                enemy.buffs.remove(b)
                                blocked = True
                                results.append(f"{enemy.character.name} 强耐抵抗了强化解除！")
                                break
                        if not blocked:
                            removed = []
                            for b in list(enemy.buffs):
                                if b.name not in unremovable:
                                    enemy.buffs.remove(b)
                                    removed.append(b.name)
                            if removed:
                                results.append(f"{enemy.character.name} 强化解除: {', '.join(removed)}")

            # 弱体状态解除 / 弱体化解除: 解除我方减益（弱体化解除妨害可阻挡；按 skill.area 选目标）
            if re.match(r'弱体(?:状态解除|化解除)(?!妨害)', effect_text):
                cleanse_allies = targets if is_ally_target else [attacker]
                for ally in cleanse_allies:
                    if ally.alive and not ally.is_assist:
                        blocked = False
                        for d in list(ally.debuffs):
                            if d.name == '弱体化解除妨害':
                                ally.debuffs.remove(d)
                                blocked = True
                                results.append(f"{ally.character.name} 弱体化解除妨害抵抗了弱体化解除！")
                                break
                        if not blocked:
                            removed = []
                            for d in list(ally.debuffs):
                                if d.name != '弱体化解除妨害':
                                    ally.debuffs.remove(d)
                                    removed.append(d.name)
                            if removed:
                                results.append(f"{ally.character.name} 弱体状态解除: {', '.join(removed)}")
                continue

            # 下降解除(净化): 解除我方对应减益（攻击类；映射与 物/异攻下降→"攻击" 对称）
            m = re.match(r'(?:物攻|异攻|攻击)下降解除', effect_text)
            if m:
                cleanse_targets = targets if is_ally_target else [attacker]
                for t in cleanse_targets:
                    if t.alive:
                        removed = [d.name for d in list(t.debuffs) if d.name == '攻击']
                        for d in list(t.debuffs):
                            if d.name == '攻击':
                                t.debuffs.remove(d)
                        if removed:
                            results.append(f"{t.character.name} 攻击下降解除: {', '.join(removed)}")
                continue

            # ===== debuff类（施加给敌方）=====
            # 此前 B 卡技能里的减益被解析进 effects 却从未施加（_apply_skill_effect 只有增益分支）。
            # 此处补全：按 skill.area 选敌方目标，复用与 A 卡效果一致的命名映射。
            if any(k in effect_text for k in ('下降', '感电', '気绝', '气绝', '封印', '耐性',
                                              '妨害', '持续被害', '出血', '移動不能', '移动不能',
                                              '制御不能', '攻击方向', '攻撃方向')):
                debuff_targets = self._skill_debuff_targets(attacker, skill, enemies)
                if debuff_targets:
                    names = '、'.join([t.character.name for t in debuff_targets])
                    # 物攻/异攻 下降 → 统一映射为"攻击"debuff
                    m = re.match(r'(物|异)攻下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "攻击", m.group(2), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 物防/异防 下降 → 统一映射为"防御"debuff
                    m = re.match(r'(物|异)防下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "防御", m.group(2), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 暴击率/回避率/暴击防御/暴伤 下降
                    for rate_type in ['暴击率', '回避率', '暴击防御', '暴伤']:
                        m = re.match(fr'{rate_type}下降\((.+?)\)', effect_text)
                        if m:
                            for t in debuff_targets:
                                self._apply_debuff(t, rate_type, m.group(1), "技能")
                            results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 对X色威力下降 → 颜色威力 debuff（与"对X色威力提升"buff 对称）
                    m = re.match(r'对(.色)威力下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "颜色威力", m.group(2), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 必杀威力下降
                    m = re.match(r'必杀威力下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "必杀威力", m.group(1), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 技能威力下降（与 技能威力提升 增益对称）
                    m = re.match(r'技能威力下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "技能威力", m.group(1), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 颜色耐性下降 / X色耐性下降
                    m = re.match(r'.色耐性下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "颜色耐性", m.group(1), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # SP获得量下降
                    m = re.match(r'SP获得量下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "SP获得量", m.group(1), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 技能/必杀耐性下降 → 必杀耐性
                    m = re.match(r'技能/必杀耐性下降\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "必杀耐性", m.group(1), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 持续被害（DoT）
                    m = re.match(r'持续被害\((.+?)\)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "持续被害", m.group(1), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 出血（DoT，无幅度，默认中）
                    if '出血' in effect_text and not re.match(r'.+\(.+\)', effect_text):
                        for t in debuff_targets:
                            self._apply_debuff(t, "出血", "中", "技能")
                        results.append(f"{attacker.character.name} 对 {names} 出血")
                    # 攻击方向-（兼容 攻击/攻撃 两种写法）
                    m = re.match(r'(?:攻击|攻撃)方向\-(.)', effect_text)
                    if m:
                        for t in debuff_targets:
                            self._apply_debuff(t, "攻击方向-", m.group(1), "技能")
                        results.append(f"{attacker.character.name} 对 {names} {effect_text}")
                    # 特殊减益（无幅度，默认"中"）
                    # 抗性映射：拥有对应“耐性”增益的单位可抵抗该减益
                    RESIST_MAP = {'感电': '感电耐性', '移动不能': '移动不能耐性',
                                  'a卡封印': 'a卡封印耐性', '必杀封印': '必杀封印耐性'}
                    for sp in ['感电', '気绝', '气绝', '移动不能', '制御不能', 'a卡封印',
                               '技能封印', '必杀封印', '强化妨害', '攻击提升妨害',
                               'HP回复妨害', '弱体化解除妨害']:
                        if sp in effect_text and not re.match(r'.+\(.+\)', effect_text):
                            for t in debuff_targets:
                                resist_buff = RESIST_MAP.get(sp)
                                if resist_buff and any(b.name == resist_buff for b in t.buffs):
                                    results.append(f"{t.character.name} {resist_buff}抵抗了{sp}！")
                                    continue
                                self._apply_debuff(t, sp, "中", "技能")
                            results.append(f"{attacker.character.name} 对 {names} {sp}")

        return results

    def _estimate_damage(self, attacker: BattleUnit, defender: BattleUnit,
                         attack_type: str = "normal", power_rank: str = "中") -> int:
        """预估伤害（不应用随机暴击，取平均值）"""
        params = BattleParams

        # 1. 计算攻击面板
        attack_panel = self._calculate_attack_panel(attacker)

        # 2. 计算buff后的攻击
        attack, attack_extra = self._calculate_buffed_attack(attacker, attack_panel)

        # 3. 必杀/技能倍率
        if attack_type == "ultimate":
            base_mult = params.ULTIMATE_BASE_MULTIPLIER.get(power_rank, 2.0)
            extra_attack = params.ULTIMATE_EXTRA_ATTACK.get(power_rank, 0)
            ult_power_mult, ult_power_extra = attacker.get_buff_multiplier("必杀威力")
            attack += extra_attack + ult_power_extra
            attack = int(attack * (base_mult + ult_power_mult))
        elif attack_type == "skill":
            base_mult = params.ULTIMATE_BASE_MULTIPLIER.get(power_rank, 1.0)
            extra_attack = params.ULTIMATE_EXTRA_ATTACK.get(power_rank, 0)
            attack += extra_attack
            attack = int(attack * base_mult)

        # 4. 计算防御
        defense = self._calculate_defense(defender)

        # 5. 核心伤害公式
        damage = int(attack ** 2 / (attack + defense))

        # 6. 属性克制
        attr_mult = self._get_attribute_multiplier(attacker.character.attribute, defender.character.attribute)
        damage = int(damage * attr_mult)

        # 7. 颜色耐性/必杀耐性（必杀技时）
        if attack_type == "ultimate":
            color_resist_mult, _ = defender.get_buff_multiplier("颜色耐性")
            ult_resist_mult, _ = defender.get_buff_multiplier("必杀耐性")
            color_power_mult, _ = attacker.get_buff_multiplier("颜色威力")
            damage = int(damage * (1 + color_resist_mult + ult_resist_mult + color_power_mult))

        return max(1, damage)

    def _can_one_shot_kill(self, attacker: BattleUnit, enemies: List[BattleUnit],
                           attack_type: str = "normal") -> bool:
        """判断是否可以一击必杀任意敌人"""
        power_rank = "中"
        if attack_type == "ultimate" and attacker.character.ultimate:
            power_rank = attacker.character.ultimate.power_rank
        elif attack_type == "skill" and attacker.character.skill:
            power_rank = attacker.character.skill.power_rank

        targets = self.get_targets_in_direction(attacker, enemies)
        for target in targets:
            if target.alive:
                estimated_damage = self._estimate_damage(attacker, target, attack_type, power_rank)
                if estimated_damage >= target.current_hp:
                    return True
        return False

    def ai_choose_action(self, unit: BattleUnit, enemies: List[BattleUnit], side_sp: int) -> str:
        """AI选择行动

        优先级：大招 > 技能 > 普攻
        但如果可以一击必杀，可以跳过优先级

        :param unit: 当前行动单位
        :param enemies: 敌方单位列表
        :param side_sp: 阵营SP（共用）
        :return: 行动类型 "ultimate"/"skill"/"normal"
        """
        # 1. 大招就绪且可以一击必杀 -> 大招
        if side_sp >= ULT_COST and self._can_one_shot_kill(unit, enemies, "ultimate"):
            return "ultimate"

        # 2. 技能就绪且可以一击必杀 -> 技能
        if unit.skill_cooldown == 0 and side_sp >= 30 and self._can_one_shot_kill(unit, enemies, "skill"):
            return "skill"

        # 3. 正常优先级：大招 > 技能 > 普攻
        if side_sp >= ULT_COST:
            return "ultimate"
        if unit.skill_cooldown == 0 and side_sp >= 30:
            return "skill"
        return "normal"

    def start_battle(self, player_team: dict, enemy_team: dict, challenger: str = "player", initial_player_sp: int = 0, extra_characters: dict = None, max_rounds: int = 12, player_hp_override: dict = None, player_card_stars: dict = None) -> dict:
        """Run one battle exclusively on this shared engine instance."""
        with self._battle_lock:
            return self._start_battle_unlocked(
                player_team,
                enemy_team,
                challenger=challenger,
                initial_player_sp=initial_player_sp,
                extra_characters=extra_characters,
                max_rounds=max_rounds,
                player_hp_override=player_hp_override,
                player_card_stars=player_card_stars,
            )

    def _start_battle_unlocked(self, player_team: dict, enemy_team: dict, challenger: str = "player", initial_player_sp: int = 0, extra_characters: dict = None, max_rounds: int = 12, player_hp_override: dict = None, player_card_stars: dict = None) -> dict:
        """开始战斗
        :param player_hp_override: 玩家角色HP覆盖 {card_id: hp}，用于RAID血量继承
        :param player_card_stars: 玩家卡牌星级 {card_id: star_level}，用于激活潜能(3★→被动1, 5★→被动2)
        """
        log_battle("=" * 50)
        log_battle("战斗开始！")

        # 重置半回合计数器（状态计时用）
        self._half_turn_count = 0

        player_units = self.build_battle_team(player_team, extra_characters, player_card_stars)
        enemy_units = self.build_battle_team(enemy_team, extra_characters)

        # 应用玩家HP覆盖（在build_battle_team之后，B+A属性合并后）
        if player_hp_override:
            for u in player_units:
                if u.is_assist:
                    continue
                cid = str(u.character.card_id)
                if cid in player_hp_override:
                    override_hp = player_hp_override[cid]
                    if override_hp <= 0:
                        # HP=0表示阵亡
                        u.current_hp = 0
                        u.max_hp = max(u.max_hp, 1)
                        u.alive = False
                    else:
                        u.current_hp = override_hp
                        u.max_hp = max(u.max_hp, override_hp)

        # 给角色名加位置箭头: 友方5列, 敌方5列
        p_arrows = {0:'↙', 1:'←', 2:'↓', 3:'→', 4:'↘'}
        e_arrows = {0:'↖', 1:'←', 2:'↑', 3:'→', 4:'↗'}

        # 阵营SP池（共用SP）
        player_sp = initial_player_sp
        enemy_sp = 0

        battle_log = []
        parsable_battle_log = []
        _last_state_hash = [0]  # mutable to allow modification in _log closure

        # GIF v2 使用稳定单位 ID + 事件前/后快照，不再依赖角色名字猜测状态。
        _unit_runtime_ids = {}
        for idx, unit in enumerate(u for u in player_units if not u.is_assist):
            _unit_runtime_ids[id(unit)] = f"P{idx}"
        for idx, unit in enumerate(u for u in enemy_units if not u.is_assist):
            _unit_runtime_ids[id(unit)] = f"E{idx}"
        _last_event_snapshot = [None]

        def _snapshot_unit(unit, side):
            return {
                "unit_id": _unit_runtime_ids.get(id(unit), f"{side}?"),
                "side": side,
                "name": unit.character.name,
                "card_id": unit.character.card_id,
                "stars": unit.character.stars,
                "attack_directions": unit.character.attack_directions,
                "position": unit.position,
                "alive": unit.alive,
                "hp": unit.current_hp,
                "max_hp": unit.max_hp,
                "is_broken": getattr(unit, "is_broken", False),
                "buffs": [
                    {"name": b.name, "magnitude": b.magnitude,
                     "charges": getattr(b, "charges", 0)} for b in unit.buffs
                ],
                "debuffs": [
                    {"name": d.name, "magnitude": d.magnitude,
                     "charges": getattr(d, "charges", 0)} for d in unit.debuffs
                ],
                "carrying_id": _unit_runtime_ids.get(id(unit.carrying)) if unit.carrying else None,
                "carried_by_id": _unit_runtime_ids.get(id(unit.carried_by)) if unit.carried_by else None,
            }

        def _capture_visual_state():
            return {
                "player_sp": player_sp,
                "enemy_sp": enemy_sp,
                "half_turn": self._half_turn_count,
                "player_units": [
                    _snapshot_unit(u, "P") for u in player_units if not u.is_assist
                ],
                "enemy_units": [
                    _snapshot_unit(u, "E") for u in enemy_units if not u.is_assist
                ],
            }

        def _state_hash():
            """计算当前所有单位状态的哈希（用于去重）"""
            parts = [f"SP:{player_sp}:{enemy_sp}"]
            for u in player_units + enemy_units:
                if not u.is_assist and u.position >= 0 and u.position < 5:
                    parts.append(f"{u.character.name}:{u.position}:{u.current_hp}:{u.alive}:{getattr(u, 'is_broken', False)}")
                    parts.append("B:" + ",".join(
                        f"{b.name}:{b.magnitude}:{getattr(b, 'charges', 0)}"
                        for b in sorted(u.buffs, key=lambda x: x.name)))
                    parts.append("D:" + ",".join(
                        f"{d.name}:{d.magnitude}:{getattr(d, 'charges', 0)}"
                        for d in sorted(u.debuffs, key=lambda x: x.name)))
                    parts.append(
                        f"C:{_unit_runtime_ids.get(id(u.carrying)) if u.carrying else ''}:"
                        f"{_unit_runtime_ids.get(id(u.carried_by)) if u.carried_by else ''}"
                    )
            return hash("|".join(parts))

        # 在记录战斗日志前添加位置箭头（确保箭头与实际位置一致）
        p_arrows = ['↙', '←', '↓', '→', '↘']
        e_arrows = ['↖', '←', '↑', '→', '↗']

        for u in player_units:
            if not u.is_assist and u.position >= 0 and u.position < 5:
                # 避免重复添加箭头
                if '[' not in u.character.name or ']' not in u.character.name:
                    u.character.name = f'{u.character.name}[{p_arrows[u.position]}]'

        for u in enemy_units:
            if not u.is_assist and u.position >= 0 and u.position < 5:
                # 避免重复添加箭头
                if '[' not in u.character.name or ']' not in u.character.name:
                    u.character.name = f'{u.character.name}[{e_arrows[u.position]}]'

        # 跟踪上一个状态的HP值，用于计算HP变化
        last_player_hp = {u.character.name: u.current_hp for u in player_units if not u.is_assist}
        last_enemy_hp = {u.character.name: u.current_hp for u in enemy_units if not u.is_assist}

        # 跟踪伤害事件信息（使用实例变量，以便在其他方法中访问）
        self._last_damage_info = {"player": {}, "enemy": {}}
        # 记录玩家单位ID集合，用于攻击方法中判断目标所属阵营
        self._player_unit_ids = {id(u) for u in player_units if not u.is_assist}

        # 这些事件类型始终记录（不受去重影响）
        _MANDATORY_TYPES = {'round_start', 'sp_info', 'turn_switch', 'attack',
                            'enter', 'swap', 'battle_end', 'retreat', 'hp_threshold'}

        def _log(text, parsable=None, force=False):
            nonlocal last_player_hp, last_enemy_hp
            """同时记录文本日志和可解析日志。强制帧(攻击/回合/切换等)跳过状态去重"""
            # 判断是否为强制帧
            is_mandatory = force or (
                isinstance(parsable, dict) and parsable.get('type') in _MANDATORY_TYPES)
            # 状态去重：如果当前状态和上次一样且非强制帧，只写文本不写结构化
            cur_hash = _state_hash()
            state_changed = cur_hash != _last_state_hash[0]
            if not is_mandatory and not state_changed and parsable_battle_log:
                # 状态没变，只追加文本日志
                if isinstance(text, list):
                    battle_log.extend(text)
                elif text:
                    battle_log.append(text)
                return
            # 计算当前HP变化
            current_player_hp = {u.character.name: u.current_hp for u in player_units if not u.is_assist}
            current_enemy_hp = {u.character.name: u.current_hp for u in enemy_units if not u.is_assist}

            def calc_hp_change(name, current_hp, last_hp_dict):
                if name in last_hp_dict:
                    delta = current_hp - last_hp_dict[name]
                    if delta != 0:
                        return delta
                return 0

            def get_hit_status(name, side):
                """获取受击状态（回避、抵挡、反射、不屈、特殊BUFF）"""
                status = ""
                damage_info = self._last_damage_info.get(side, {}).get(name, {})
                if damage_info.get("dodged", False):
                    status += "回避"
                if damage_info.get("blocked", False):
                    status += "抵挡"
                if damage_info.get("reflected", False):
                    status += "反射"
                if damage_info.get("absorbed", False):
                    status += "吸收"
                if damage_info.get("reduced", False):
                    status += "减伤"
                if damage_info.get("tenacious", False):
                    status += "不屈"
                return status

            if isinstance(text, list):
                for t in text:
                    battle_log.append(t)
                    if parsable:
                        if isinstance(parsable, list) and len(parsable) > 0:
                            entry = parsable.pop(0)
                        else:
                            entry = {"type": "text", "content": t}
                    else:
                        entry = {"type": "text", "content": t}

                    entry["player_positions"] = [
                        {"name": u.character.name, "position": u.position, "alive": u.alive, "hp": u.current_hp, "max_hp": u.max_hp,
                         "hp_change": calc_hp_change(u.character.name, u.current_hp, last_player_hp),
                         "hit_status": get_hit_status(u.character.name, "player"),
                         "buffs": [{"name": b.name, "magnitude": b.magnitude} for b in u.buffs],
                         "debuffs": [{"name": d.name, "magnitude": d.magnitude} for d in u.debuffs]}
                        for u in player_units if not u.is_assist
                    ]
                    entry["enemy_positions"] = [
                        {"name": u.character.name, "position": u.position, "alive": u.alive, "hp": u.current_hp, "max_hp": u.max_hp,
                         "hp_change": calc_hp_change(u.character.name, u.current_hp, last_enemy_hp),
                         "hit_status": get_hit_status(u.character.name, "enemy"),
                         "buffs": [{"name": b.name, "magnitude": b.magnitude} for b in u.buffs],
                         "debuffs": [{"name": d.name, "magnitude": d.magnitude} for d in u.debuffs]}
                        for u in enemy_units if not u.is_assist
                    ]
                    current_snapshot = _capture_visual_state()
                    entry["schema_version"] = 2
                    entry["before_state"] = _last_event_snapshot[0] or current_snapshot
                    entry["after_state"] = current_snapshot
                    _last_event_snapshot[0] = current_snapshot
                    parsable_battle_log.append(entry)
            else:
                battle_log.append(text)
                if parsable:
                    entry = parsable
                else:
                    entry = {"type": "text", "content": text}

                entry["player_positions"] = [
                    {"name": u.character.name, "position": u.position, "alive": u.alive, "hp": u.current_hp, "max_hp": u.max_hp,
                     "hp_change": calc_hp_change(u.character.name, u.current_hp, last_player_hp),
                     "hit_status": get_hit_status(u.character.name, "player"),
                     "buffs": [{"name": b.name, "magnitude": b.magnitude} for b in u.buffs],
                     "debuffs": [{"name": d.name, "magnitude": d.magnitude} for d in u.debuffs]}
                    for u in player_units if not u.is_assist
                ]
                entry["enemy_positions"] = [
                    {"name": u.character.name, "position": u.position, "alive": u.alive, "hp": u.current_hp, "max_hp": u.max_hp,
                     "hp_change": calc_hp_change(u.character.name, u.current_hp, last_enemy_hp),
                     "hit_status": get_hit_status(u.character.name, "enemy"),
                     "buffs": [{"name": b.name, "magnitude": b.magnitude} for b in u.buffs],
                     "debuffs": [{"name": d.name, "magnitude": d.magnitude} for d in u.debuffs]}
                    for u in enemy_units if not u.is_assist
                ]
                current_snapshot = _capture_visual_state()
                entry["schema_version"] = 2
                entry["before_state"] = _last_event_snapshot[0] or current_snapshot
                entry["after_state"] = current_snapshot
                _last_event_snapshot[0] = current_snapshot
                parsable_battle_log.append(entry)

            # 更新上一个状态的HP值
            last_player_hp = current_player_hp
            last_enemy_hp = current_enemy_hp
            # 更新状态哈希（去重用）
            _last_state_hash[0] = cur_hash
            # 重置伤害信息
            self._last_damage_info = {"player": {}, "enemy": {}}

        # ===== P1: 开场被动 — 初始上场3人占0/2/4，替补放在替补队列 =====
        player_alive_all = [u for u in player_units if not u.is_assist and u.alive]
        enemy_alive_all = [u for u in enemy_units if not u.is_assist and u.alive]

        # 场上位置只使用0-4，替补角色位置设为-1表示在替补队列
        for i, u in enumerate(player_alive_all):
            if i < 3:
                u.position = INITIAL_FIELD_POSITIONS[i]
            else:
                u.position = -1  # 替补队列
        for i, u in enumerate(enemy_alive_all):
            if i < 3:
                u.position = INITIAL_FIELD_POSITIONS[i]
            else:
                u.position = -1  # 替补队列

        # 位置确定后再加箭头（确保箭头与实际位置一致）
        for u in player_units:
            if not u.is_assist:
                if u.position >= 0:
                    u.character.name = f'{u.character.name}[{p_arrows[u.position]}]'
        for u in enemy_units:
            if not u.is_assist:
                if u.position >= 0:
                    u.character.name = f'{u.character.name}[{e_arrows[u.position]}]'

        player_starters = player_alive_all[:INITIAL_DEPLOY_COUNT]
        enemy_starters = enemy_alive_all[:INITIAL_DEPLOY_COUNT]

        # 作为第一个事件的 before_state：已完成初始布阵，但尚未触发开场 A 卡/被动。
        _last_event_snapshot[0] = _capture_visual_state()

        p1_fired = False
        p1_last_text = ''
        for unit in player_starters:
            sp_gained, logs = self.trigger_assist_effects(unit, player_starters, enemy_starters, '行动开始时')
            player_sp = self.add_sp(player_sp, sp_gained)
            battle_log.extend(logs)
            if logs: p1_fired = True; p1_last_text = logs[-1]
        for unit in enemy_starters:
            sp_gained, logs = self.trigger_assist_effects(unit, enemy_starters, player_starters, '行动开始时')
            enemy_sp = self.add_sp(enemy_sp, sp_gained)
            battle_log.extend(logs)
            if logs: p1_fired = True; p1_last_text = logs[-1]
        if p1_fired:
            _log(p1_last_text, {"type": "assist_trigger", "phase": "P1"})

        # 跨回合记录：上回合未被继承的死单位位置，供下回合P2使用
        _pending_dead_positions = {'P': [], 'E': []}

        for round_num in range(1, max_rounds + 1):
            round_title = f"\n{'='*50}\n第 {round_num} 回合\n{'='*50}"
            _log(round_title, {"type": "round_start", "round": round_num})
            round_log = []

            # ===== P1: 波次/回合开始 — CD递减 + 回合开始触发 =====
            for unit in player_units + enemy_units:
                if unit.skill_cooldown > 0: unit.skill_cooldown -= 1
                if unit.skill2_cooldown > 0: unit.skill2_cooldown -= 1
                if unit.ult_cooldown > 0: unit.ult_cooldown -= 1
                if unit.assist_skill1_cd > 0: unit.assist_skill1_cd -= 1
                if unit.assist_skill2_cd > 0: unit.assist_skill2_cd -= 1
                # A卡效果冷却递减
                if unit.assist_unit:
                    ae1 = unit.assist_unit.character.assist_effect1
                    ae2 = unit.assist_unit.character.assist_effect2
                    if ae1 and ae1.current_cd > 0:
                        ae1.current_cd -= 1
                    if ae2 and ae2.current_cd > 0:
                        ae2.current_cd -= 1

            # 检查胜负（全部6个战斗单位阵亡才结束）
            player_alive_all = [u for u in player_units if not u.is_assist and u.alive]
            enemy_alive_all = [u for u in enemy_units if not u.is_assist and u.alive]

            if len(player_alive_all) == 0:
                _log("玩家队伍全灭！", {"type": "battle_end", "winner": "enemy", "reason": "player_dead"})
                _log("敌方胜利！", {"type": "battle_end", "winner": "enemy", "reason": "player_dead"})
                return self._create_result("enemy", round_num, battle_log, parsable_battle_log, player_units, enemy_units)

            if len(enemy_alive_all) == 0:
                _log("敌方全灭！", {"type": "battle_end", "winner": "player", "reason": "enemy_dead"})
                _log("玩家队伍胜利！", {"type": "battle_end", "winner": "player", "reason": "enemy_dead"})
                return self._create_result("player", round_num, battle_log, parsable_battle_log, player_units, enemy_units)

            # 刷新场上单位（初始3人已在P1分配0/2/4列，之后保持位置）
            player_on_field = [u for u in player_alive_all if not u.is_assist and u.alive and u.position >= 0][:INITIAL_DEPLOY_COUNT]
            player_on_field.sort(key=lambda x: x.position)
            enemy_on_field = [u for u in enemy_alive_all if not u.is_assist and u.alive and u.position >= 0][:INITIAL_DEPLOY_COUNT]
            enemy_on_field.sort(key=lambda x: x.position)

            # ===== 半回合处理 =====
            # 优先级: P2替补→P3行动开始→P4攻击→P5被攻击→P6 HP阈值→P7 SP满→P8 Break
            def half_turn(side_units, side_enemies, all_units, side_sp, tag, round_log, defender_sp=300):
                """执行半回合，返回(攻击方新SP, 防守方获得SP)"""
                defender_sp_total = 0  # 防守方本回合被攻击获得的SP

                # ===== P2: 替补入场（继承阵亡单位的位置）=====
                # 从替补队列中获取可用替补（position=-1表示在替补队列）
                alive_bench = sorted([u for u in all_units if not u.is_assist and u.alive and u.position == -1], key=lambda x: x.character.name)
                needed = max(0, INITIAL_DEPLOY_COUNT - len(side_units))
                # 找出阵亡单位的位置（含上回合未继承的 + 本回合新增的）
                dead_positions = list(_pending_dead_positions[tag])
                _pending_dead_positions[tag] = []
                for u in all_units:
                    if not u.is_assist and not u.alive:
                        pos = u.position
                        if pos >= 0 and pos < 5 and pos not in dead_positions:
                            dead_positions.append(pos)
                dead_positions.sort()
                # 限制替补数量不超过可用死亡位置
                needed = min(needed, len(dead_positions))
                # 记录被替补继承的位置
                inherited_positions = set()
                for i, u in enumerate(alive_bench[:needed]):
                    # 替补继承阵亡位置（按原顺序分配）
                    if i < len(dead_positions):
                        u.position = dead_positions[i]
                        inherited_positions.add(dead_positions[i])
                    side_units.append(u)
                    # 记录替补位置信息到日志（避免重复箭头）
                    dir_map = {'P': {0:'↙',1:'←',2:'↓',3:'→',4:'↘'}, 'E': {0:'↖',1:'←',2:'↑',3:'→',4:'↗'}}
                    arrow = dir_map.get(tag, {}).get(u.position, '?')
                    base_name = re.sub(r'\[[↙←↓→↘↖↑↗]\]$', '', u.character.name)
                    u.character.name = f'{base_name}[{arrow}]'
                    _log(f'  [上场] [{tag}] {base_name}[{arrow}]', {
                        "type": "enter",
                        "side": tag,
                        "name": base_name,
                        "arrow": arrow,
                        "position": u.position
                    })
                    sp_gained, e_logs = self.trigger_assist_effects(u, side_units, side_enemies, '替补入场时')
                    side_sp = self.add_sp(side_sp, sp_gained)
                    round_log.extend(e_logs)
                    if e_logs:
                        _log(e_logs[-1], {"type": "assist_trigger", "trigger_type": "替补入场时"})
                side_units.sort(key=lambda x: x.position)
                # 未被继承的死位置留到下回合，所有死单位清出场外
                for pos in dead_positions:
                    if pos not in inherited_positions:
                        if pos not in _pending_dead_positions[tag]:
                            _pending_dead_positions[tag].append(pos)
                _pending_dead_positions[tag].sort()
                for u in all_units:
                    if not u.is_assist and not u.alive and u.position >= 0:
                        u.position = -1
                if not side_units: return side_sp, 0

                # 2. 换位优化（移动不能的单位跳过）
                mobile_units = [u for u in side_units if not any(d.name == '移动不能' for d in u.debuffs)]
                immobile_units = [u for u in side_units if u not in mobile_units]
                if len(mobile_units) == 1 and len(side_units) == 1:
                    u = mobile_units[0]
                    best_col, best_cnt = u.position % 5, len(self.get_targets_in_direction(u, side_enemies))
                    for col in ALL_FIELD_COLS:
                        u.position = col
                        cnt = len(self.get_targets_in_direction(u, side_enemies))
                        if cnt > best_cnt: best_cnt, best_col = cnt, col
                    if u.position % 5 != best_col:
                        u.position = best_col
                        for ac in all_units:
                            if ac.is_assist and ac.position%5 == (best_col+3)%5: ac.position = best_col
                        dir_map = {'P': {0:'↙',1:'←',2:'↓',3:'→',4:'↘'}, 'E': {0:'↖',1:'←',2:'↑',3:'→',4:'↗'}}
                        arrow = dir_map.get(tag, {}).get(best_col, '?')
                        base_name = re.sub(r'\[[↙←↓→↘↖↑↗]\]$', '', u.character.name)
                        _log(f'  [换位] [{tag}] {u.character.name} -> {arrow}', {
                            "type": "swap",
                            "side": tag,
                            "name": base_name,
                            "old_arrow": dir_map.get(tag, {}).get(u.position % 5, '?'),
                            "new_arrow": arrow,
                            "old_position": u.position % 5,
                            "new_position": best_col
                        })
                        u.character.name = f'{base_name}[{arrow}]'
                elif len(mobile_units) >= 2:
                    from itertools import permutations
                    # 只排列可移动单位，不可移动单位保持原位
                    fixed_positions = {u.position % 5 for u in immobile_units}
                    best_total = sum(len(self.get_targets_in_direction(u, side_enemies)) for u in side_units)
                    best_assign = [(u, u.position) for u in mobile_units]
                    available_cols = [c for c in ALL_FIELD_COLS if c not in fixed_positions]
                    if len(available_cols) >= len(mobile_units):
                        for perm in permutations(mobile_units):
                            saved = [(u, u.position) for u in mobile_units]
                            for i, u in enumerate(perm): u.position = available_cols[i]
                            total = sum(len(self.get_targets_in_direction(u, side_enemies)) for u in side_units)
                            if total > best_total:
                                best_total, best_assign = total, [(u, u.position) for u in perm]
                            for u, pos in saved: u.position = pos
                    if best_total > sum(len(self.get_targets_in_direction(u, side_enemies)) for u in side_units):
                        for unit, new_pos in best_assign:
                            old_pos = unit.position
                            if old_pos == new_pos: continue
                            for other in side_units:
                                if other.position == new_pos: other.position, unit.position = old_pos, new_pos; break
                            else: unit.position = new_pos
                            for ac in all_units:
                                if ac.is_assist:
                                    if ac.position == old_pos: ac.position = new_pos
                                    elif ac.position == new_pos: ac.position = old_pos
                            dir_map = {'P': {0:'↙',1:'←',2:'↓',3:'→',4:'↘'}, 'E': {0:'↖',1:'←',2:'↑',3:'→',4:'↗'}}
                            arrow = dir_map.get(tag, {0:'_',1:'_',2:'_',3:'_',4:'_'}).get(new_pos%5, '?')
                            old_arrow = dir_map.get(tag, {}).get(old_pos % 5, '?')
                            base_name = re.sub(r'\[[↙←↓→↘↖↑↗]\]$', '', unit.character.name)
                            _log(f'  [换位] [{tag}] {unit.character.name} -> {arrow}', {
                                "type": "swap",
                                "side": tag,
                                "name": base_name,
                                "old_arrow": old_arrow,
                                "new_arrow": arrow,
                                "old_position": old_pos % 5,
                                "new_position": new_pos % 5
                            })
                            unit.character.name = f'{base_name}[{arrow}]'
                if immobile_units:
                    for u in immobile_units:
                        round_log.append(f'  [移动不能] [{tag}] {u.character.name} 无法换位')

                # ===== 换位后：连携形成（A 移动到可命中友方 B 同列）=====
                # 规则（与换位同阶段）：仅对“自身攻击方向打不到任何敌人”且非移动不能、
                # 未参与连携的单位，将其移动到某可命中敌人的友方 B 同列，由 B 在行动中
                # 携带其协同攻击（A 不单独行动）。1对1（claimed 防多A抢同一B）。
                claimed_partners = set()
                for unit in sorted([u for u in side_units if u.alive], key=lambda x: x.character.speed, reverse=True):
                    if getattr(unit, 'carried_by', None) or getattr(unit, 'carrying', None):
                        continue
                    if any(d.name == '移动不能' for d in unit.debuffs):
                        continue
                    if self.get_targets_in_direction(unit, side_enemies):
                        continue  # A 自己能打到敌人，不连携
                    partner = self._find_combo_partner(unit, side_units, side_enemies, claimed_partners)
                    if partner and id(partner) not in claimed_partners:
                        claimed_partners.add(id(partner))
                        unit.position = partner.position
                        unit.carried_by = partner
                        partner.carrying = unit
                        dir_map = {'P': {0:'↙',1:'←',2:'↓',3:'→',4:'↘'}, 'E': {0:'↖',1:'←',2:'↑',3:'→',4:'↗'}}
                        arrow = dir_map.get(tag, {}).get(partner.position % 5, '?')
                        base_name = re.sub(r'\[[↙←↓→↘↖↑↗]\]$', '', unit.character.name)
                        unit.character.name = f'{base_name}[{arrow}]'
                        round_log.append(f'  [连携] {unit.character.name} 移动到 {partner.character.name} 同列，形成连携')
                        _log(f'  [连携] {unit.character.name}→{partner.character.name}', {"type": "combo_form"})

                # ===== P3: 行动开始时触发 =====
                # A卡效果 + 被动效果在此阶段触发
                for unit in list(side_units):
                    if unit.alive and unit.assist_unit:
                        assist_char = unit.assist_unit.character
                        # 检查是否有即将触发的效果
                        will_trigger = False
                        if assist_char.assist_effect1 and assist_char.assist_effect1.is_ready():
                            if assist_char.assist_effect1.trigger_time == '行动开始时':
                                will_trigger = True
                        if assist_char.assist_effect2 and assist_char.assist_effect2.is_ready():
                            if assist_char.assist_effect2.trigger_time == '行动开始时':
                                will_trigger = True

                        if will_trigger:
                            # 记录A卡效果触发前的状态
                            _log(f'  [A卡准备] {assist_char.name} 即将触发效果', {
                                "type": "assist_prepare",
                                "source_unit": unit.character.name,
                                "source_position": unit.position,
                                "assist_name": assist_char.name,
                                "trigger_type": "行动开始时"
                            })

                for unit in list(side_units):
                    if unit.alive:
                        sp_gained, a_logs = self.trigger_assist_effects(unit, side_units, side_enemies, '行动开始时')
                        side_sp = self.add_sp(side_sp, sp_gained)
                        round_log.extend(a_logs)

                        # 如果有A卡效果触发，记录触发后的状态
                        if a_logs and unit.assist_unit:
                            assist_char = unit.assist_unit.character
                            # 解析日志中的效果信息
                            effects_info = []
                            for log_line in a_logs:
                                if '[A]' in log_line:
                                    effects_info.append(log_line)
                            if effects_info:
                                _log(f'  [A卡触发] {assist_char.name}', {
                                    "type": "assist_trigger",
                                    "source_unit": unit.character.name,
                                    "source_position": unit.position,
                                    "assist_name": assist_char.name,
                                    "effects": effects_info,
                                    "trigger_type": "行动开始时"
                                })

                # DoT (between P3 and P4)
                dot_fired = False
                dot_pcts = {'小': 0.03, '中': 0.05, '大': 0.08}
                # DoT前HP快照（用于DoT后P6检查）
                dot_hp_before = {}
                for u in list(side_units):
                    if u.alive:
                        dot_hp_before[id(u)] = u.current_hp
                for unit in list(side_units):
                    if unit.alive:
                        for d in list(unit.debuffs):
                            if d.name in ('持续被害', '出血'):
                                dot_pct = dot_pcts.get(d.magnitude, 0.05)
                                dot_dmg = max(1, int(unit.max_hp * dot_pct))
                                unit.current_hp -= dot_dmg
                                dot_fired = True
                                round_log.append(f'  [持续被害] {unit.character.name} -{dot_dmg}HP')
                                if unit.current_hp <= 0:
                                    if not self._check_tenacity(unit):
                                        unit.current_hp = 0
                                        unit.alive = False
                                        if unit.position >= 0: unit._last_valid_position = unit.position
                                        if unit.assist_unit:
                                            unit.assist_unit.alive = False
                                        # 保存原始位置，避免退场A卡触发时position已被清空
                                        _dead_pos_backup = unit.position
                                        round_log.append(f'  [持续被害] {unit.character.name} 被DoT击破！')
                                        # P10: 自身退场时触发
                                        sp_gained, r_logs = self.trigger_assist_effects(unit, side_units, side_enemies, '自身退场时')
                                        side_sp = self.add_sp(side_sp, sp_gained)
                                        round_log.extend(r_logs)
                                        # A类(pair): 我方一对角色退场时
                                        sp_gained, r_logs = self.trigger_assist_effects(unit, side_units, side_enemies, '我方一对角色退场时')
                                        side_sp = self.add_sp(side_sp, sp_gained)
                                        round_log.extend(r_logs)
                                        # D类: 自身以外的我方退场时
                                        for other in side_units:
                                            if other is unit or other.is_assist or not other.alive:
                                                continue
                                            sp, logs = self.trigger_assist_effects(other, side_units, side_enemies, '自身以外的我方退场时')
                                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                                break  # 每种持续被害只触发一次
                # DoT处理后记录状态变化
                if dot_fired:
                    _log(round_log[-1] if round_log else '', {"type": "dot_damage"})

                # DoT后P6 HP阈值检查
                if dot_fired:
                    for u in list(side_units):
                        if not u.alive or id(u) not in dot_hp_before: continue
                        hp_pct = u.current_hp / u.max_hp if u.max_hp > 0 else 0
                        hp_before_pct = dot_hp_before[id(u)] / u.max_hp if u.max_hp > 0 else 0
                        if hp_pct < 0.5 and hp_before_pct >= 0.5:
                            round_log.append(f'  [HP阈值] {u.character.name} HP低于50%')
                            sp_gained, hp_logs = self.trigger_assist_effects(u, side_units, side_enemies, 'HP低于50%时')
                            side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(hp_logs)
                        if hp_pct < 0.3 and hp_before_pct >= 0.3:
                            round_log.append(f'  [HP阈值] {u.character.name} HP低于30%')
                            sp_gained, hp_logs = self.trigger_assist_effects(u, side_units, side_enemies, 'HP低于30%时')
                            side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(hp_logs)

                # ===== P4: 攻击决策 =====
                planned = {}
                sp = side_sp

                # ===== P7: 敌方SP满时触发 (在攻击方行动前，防御方SP满时触发) =====
                p7_fired = False
                if defender_sp >= SP_MAX:
                    for opp_unit in side_enemies:
                        if opp_unit.alive and not opp_unit.is_assist:
                            sp_gained, p7_logs = self.trigger_assist_effects(
                                opp_unit, side_enemies, side_units, '敌方SP满时')
                            side_sp = self.add_sp(side_sp, sp_gained)
                            round_log.extend(p7_logs)
                            if p7_logs: p7_fired = True
                if p7_fired:
                    _log(round_log[-1] if round_log else '', {"type": "trigger", "trigger_type": "P7"})

                # P4: 智能SP分配（两阶段：先标记候选，再按优先级分配）
                action_candidates = []
                for unit in sorted([u for u in side_units if u.alive], key=lambda x: x.character.speed, reverse=True):
                    # 连携：被携带单位(A)不单独行动
                    if getattr(unit, 'carried_by', None):
                        continue
                    has_ult = bool(unit.character.ultimate) if hasattr(unit.character, 'ultimate') else False
                    has_skill = bool(unit.character.skill) if hasattr(unit.character, 'skill') else False
                    has_skill2 = bool(unit.character.skill2) if hasattr(unit.character, 'skill2') else False
                    sealed_skill = any(d.name == '技能封印' for d in unit.debuffs)
                    sealed_ult = any(d.name == '必杀封印' for d in unit.debuffs)
                    has_targets = bool(self.get_targets_in_direction(unit, side_enemies))

                    # 检查是否有"自身技能时"或"自身必杀时"A卡效果 → 提高优先级
                    has_skill_trigger = False
                    has_ult_trigger = False
                    if unit.assist_unit:
                        for eff in [unit.assist_unit.character.assist_effect1, unit.assist_unit.character.assist_effect2]:
                            if eff and eff.is_ready():
                                tt = eff.trigger_time
                                if tt in ('自身技能时',): has_skill_trigger = True
                                if tt in ('自身必杀时',): has_ult_trigger = True

                    priority = unit.character.speed  # 基础优先级=速度
                    if has_ult_trigger: priority += 10000  # 有必杀触发A卡 → 最高优先
                    if has_skill_trigger: priority += 5000  # 有技能触发A卡 → 高优先

                    want_ult = has_targets and unit.ult_cooldown == 0 and not sealed_ult and has_ult
                    want_skill = has_targets and unit.skill_cooldown == 0 and not sealed_skill and has_skill

                    # 连携：携带者(B)只能普攻
                    if getattr(unit, 'carrying', None):
                        want_ult = want_skill = False

                    # 必杀优先（SP>=100时释放）；SP不足时SP分配阶段自动降级为技能→普攻
                    if want_ult:
                        action_candidates.append((priority, 'ultimate', unit, ULT_COST))
                    elif want_skill:
                        action_candidates.append((priority, 'skill', unit, 0))
                    else:
                        # 连携已在换位阶段形成（half_turn 换位优化后）；此处兜底为普攻
                        action_candidates.append((priority, 'normal', unit, 0))

                # 按优先级降序分配SP
                action_candidates.sort(key=lambda x: x[0], reverse=True)
                for priority, action, unit, cost in action_candidates:
                    if action == 'ultimate' and sp < cost:
                        # 必杀SP不足 → 降级：若技能可用则用技能，否则普攻
                        has_skill = bool(unit.character.skill) if hasattr(unit.character, 'skill') else False
                        sealed = any(d.name == '技能封印' for d in unit.debuffs)
                        can_skill = unit.skill_cooldown == 0 and not sealed and has_skill and bool(self.get_targets_in_direction(unit, side_enemies))
                        if can_skill:
                            action = 'skill'
                            cost = 0
                        else:
                            action = 'normal'
                    elif action != 'normal' and sp < cost:
                        action = 'normal'  # SP不足降级为普攻
                    planned[id(unit)] = action
                    if action != 'normal':
                        sp -= cost

                # ===== P4+P5: 执行攻击 + 被攻击时触发（execute内部处理P5）=====
                for unit in sorted([u for u in side_units if u.alive], key=lambda x: x.character.speed, reverse=True):
                    if not unit.alive: continue
                    # 连携：被携带单位(A)不行动
                    if getattr(unit, 'carried_by', None):
                        continue
                    stunned = any(d.name in ('感电','气绝','制御不能') for d in unit.debuffs)
                    if stunned:
                        for d in list(unit.debuffs):
                            if d.name in ('感电','气绝','制御不能'): unit.debuffs.remove(d); break
                        side_sp = self.add_sp(side_sp, 15)
                        round_log.append(f'  [无法行动] {unit.character.name}')
                        _log(f'  [无法行动] {unit.character.name}', {"type": "stun_recover"})
                        continue
                    action = planned.get(id(unit), 'normal')
                    enemies = side_enemies

                    # 连携：携带者(B)只能普攻（即时降级，避免浪费SP）
                    if getattr(unit, 'carrying', None) and action in ('ultimate', 'skill'):
                        action = 'normal'
                    # 注：连携(A移动到B同列)已在换位阶段形成，P5 不再处理 combine 动作

                    # 记录攻击前HP（用于P6 HP阈值检测，含攻击方自身防反射）
                    hp_before = {}
                    for t in list(enemies) + [unit]:
                        if t.alive:
                            hp_before[id(t)] = t.current_hp

                    if action == 'ultimate':
                        side_sp -= ULT_COST
                        results, used, atk_sp, def_sp = self.execute_ultimate_attack(unit, enemies, True, side_units)
                    elif action == 'skill':
                        results, used, atk_sp, def_sp = self.execute_skill_attack(unit, enemies, True, 30, side_units)
                    elif action == 'normal':
                        results, atk_sp, def_sp = self.execute_normal_attack(unit, enemies, side_units)
                    else:
                        results, atk_sp, def_sp = [], 0, 0
                    round_log.extend(results); side_sp = self.add_sp(side_sp, atk_sp); defender_sp_total += def_sp

                    # 构建攻击事件信息
                    att_type = '终' if action == 'ultimate' else ('技' if action == 'skill' else '普')
                    defender_side_key = "enemy" if tag == 'P' else "player"
                    actual_hit_names = set(self._last_damage_info.get(defender_side_key, {}).keys())
                    actual_targets = [
                        e for e in enemies
                        if e.character.name in actual_hit_names
                    ]
                    if not actual_targets:
                        actual_targets = [e for e in enemies if id(e) in hp_before]
                    attack_info = {
                        "type": "attack",
                        "attack_type": att_type,
                        "attacker": unit.character.name,
                        "attacker_position": unit.position,
                        "attacker_arrow": self._get_arrow_by_position(unit.position, 'P' if tag == 'P' else 'E'),
                        "targets": [{"name": e.character.name, "position": e.position, "arrow": self._get_arrow_by_position(e.position, 'E' if tag == 'P' else 'P')} for e in actual_targets]
                    }
                    # 记录攻击帧（含hit_status）
                    if results:
                        _log(results[0], attack_info)
                        # 攻击内触发的A卡效果逐帧记录（自身技能时/暴击时/受到伤害时/使敌方退场时等）
                        for line in results[1:]:
                            if '[A]' in line:
                                # 解析效果描述 → GIF渲染器可直接使用
                                content = line.replace(' [A]', '').replace('[A]', '').strip()
                                parts = content.split(' ', 1)
                                target_name = parts[0] if parts else ""
                                effect_desc = parts[1] if len(parts) > 1 else content
                                _log(line, {
                                    "type": "assist_trigger",
                                    "phase": "attack_internal",
                                    "target_name": target_name,
                                    "effect_desc": effect_desc,
                                    "is_attack_internal": True
                                })

                    # ===== P5b: 敌方行动/自身以外友方触发 =====
                    # 从攻击函数读取本次攻击的暴击状态
                    is_crit = self._last_attack_had_crit
                    p5b_fired = False

                    # C类: 敌方行动时 → 触发防御方(被攻击方)单位的A卡
                    for defender in side_enemies:
                        if not defender.alive or defender.is_assist:
                            continue
                        if action == 'skill':
                            sp, logs = self.trigger_assist_effects(defender, side_enemies, side_units, '敌方技能时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                            if logs: p5b_fired = True
                        elif action == 'ultimate':
                            sp, logs = self.trigger_assist_effects(defender, side_enemies, side_units, '敌方必杀时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                            if logs: p5b_fired = True
                        if is_crit:
                            sp, logs = self.trigger_assist_effects(defender, side_enemies, side_units, '敌方对我方角色暴击时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                            if logs: p5b_fired = True

                    # D类: 自身以外的我方*时 → 触发除自己外的其他友方A卡
                    if action == 'skill':
                        for other in side_units:
                            if other is unit or other.is_assist or not other.alive:
                                continue
                            sp, logs = self.trigger_assist_effects(other, side_units, side_enemies, '自身以外的我方技能时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                            if logs: p5b_fired = True
                    elif action == 'ultimate':
                        for other in side_units:
                            if other is unit or other.is_assist or not other.alive:
                                continue
                            sp, logs = self.trigger_assist_effects(other, side_units, side_enemies, '自身以外的我方必杀时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                            if logs: p5b_fired = True

                    if p5b_fired:
                        _log(round_log[-1] if round_log else "", {"type": "trigger", "trigger_type": "P5b"})

                    # ===== P10: 自身退场时触发（击破时遗言效果）=====
                    p10_fired = False
                    dead_enemies = [e for e in enemies if id(e) in hp_before and not e.alive and hp_before[id(e)] > 0]
                    for dead in dead_enemies:
                        round_log.append(f'  [退场] {dead.character.name} 被击破！')
                        # 退场A卡"一对角色"需要原始position做相邻判断，临时恢复
                        _saved_dead_pos = dead.position
                        if _saved_dead_pos < 0 and hasattr(dead, '_last_valid_position') and dead._last_valid_position >= 0:
                            dead.position = dead._last_valid_position
                        sp_gained, r_logs = self.trigger_assist_effects(dead, side_enemies, side_units, '自身退场时')
                        side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(r_logs)
                        sp_gained, r_logs = self.trigger_assist_effects(dead, side_enemies, side_units, '我方一对角色退场时')
                        side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(r_logs)
                        for other in side_enemies:
                            if other is dead or other.is_assist or not other.alive: continue
                            sp, logs = self.trigger_assist_effects(other, side_enemies, side_units, '自身以外的我方退场时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                        dead.position = _saved_dead_pos
                        p10_fired = True
                    if id(unit) in hp_before and not unit.alive and hp_before[id(unit)] > 0:
                        round_log.append(f'  [退场] {unit.character.name} 被反射击破！')
                        _saved_unit_pos = unit.position
                        if _saved_unit_pos < 0 and hasattr(unit, '_last_valid_position') and unit._last_valid_position >= 0:
                            unit.position = unit._last_valid_position
                        sp_gained, r_logs = self.trigger_assist_effects(unit, side_units, side_enemies, '自身退场时')
                        side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(r_logs)
                        sp_gained, r_logs = self.trigger_assist_effects(unit, side_units, side_enemies, '我方一对角色退场时')
                        side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(r_logs)
                        for other in side_units:
                            if other is unit or other.is_assist or not other.alive: continue
                            sp, logs = self.trigger_assist_effects(other, side_units, side_enemies, '自身以外的我方退场时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                        unit.position = _saved_unit_pos
                        p10_fired = True

                    if p10_fired:
                        _log(round_log[-1] if round_log else "", {"type": "retreat"})

                    # ===== P6: HP阈值触发 =====
                    p6_fired = False
                    all_checked = set()
                    for target in list(enemies) + [unit]:
                        if not target.alive or id(target) in all_checked: continue
                        if id(target) not in hp_before: continue
                        all_checked.add(id(target))
                        hp_pct = target.current_hp / target.max_hp if target.max_hp > 0 else 0
                        hp_before_pct = hp_before[id(target)] / target.max_hp if target.max_hp > 0 else 0
                        target_allies = side_enemies if target in enemies else side_units
                        target_enemies = side_units if target in enemies else side_enemies
                        if hp_pct < 0.5 and hp_before_pct >= 0.5:
                            round_log.append(f'  [HP阈值] {target.character.name} HP低于50%')
                            sp_gained, hp_logs = self.trigger_assist_effects(target, target_allies, target_enemies, 'HP低于50%时')
                            side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(hp_logs)
                            p6_fired = True
                        if hp_pct < 0.3 and hp_before_pct >= 0.3:
                            round_log.append(f'  [HP阈值] {target.character.name} HP低于30%')
                            sp_gained, hp_logs = self.trigger_assist_effects(target, target_allies, target_enemies, 'HP低于30%时')
                            side_sp = self.add_sp(side_sp, sp_gained); round_log.extend(hp_logs)
                            p6_fired = True

                    if p6_fired:
                        _log(round_log[-1] if round_log else "", {"type": "hp_threshold"})

                    # ===== E类: 敌方行动结束且我方一对角色HP少于一半时 =====
                    e_fired = False
                    if tag == 'E':
                        for defender in list(side_enemies):
                            if not defender.alive or defender.is_assist: continue
                            hp_pct = defender.current_hp / defender.max_hp if defender.max_hp > 0 else 1
                            if hp_pct < 0.5:
                                sp, logs = self.trigger_assist_effects(defender, side_enemies, side_units,
                                    '敌方行动结束且我方一对角色HP少于一半时')
                                side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                                if logs: e_fired = True

                    if e_fired:
                        _log(round_log[-1] if round_log else "", {"type": "trigger", "trigger_type": "E"})

                    # ===== 自身从a卡以外被弱体时 =====
                    debuff_fired = False
                    for defender in side_enemies:
                        if defender.alive and not defender.is_assist and defender._got_debuff_non_assist:
                            sp, logs = self.trigger_assist_effects(defender, side_enemies, side_units,
                                '自身从a卡以外被弱体时')
                            side_sp = self.add_sp(side_sp, sp); round_log.extend(logs)
                            defender._got_debuff_non_assist = False
                            if logs: debuff_fired = True

                    if debuff_fired:
                        _log(round_log[-1] if round_log else "", {"type": "debuff_trigger"})

                    side_units[:] = [u for u in side_units if u.alive]
                    side_enemies[:] = [e for e in side_enemies if e.alive]
                    if not side_units or not side_enemies: break
                return side_sp, defender_sp_total

            # 半回合前刷新场上（替补进场由half_turn内部处理）
            # 只取3人上场，保持原有位置
            player_on_field = [u for u in player_units if not u.is_assist and u.alive and u.position >= 0][:INITIAL_DEPLOY_COUNT]
            player_on_field.sort(key=lambda x: x.position)
            enemy_on_field = [u for u in enemy_units if not u.is_assist and u.alive and u.position >= 0][:INITIAL_DEPLOY_COUNT]
            enemy_on_field.sort(key=lambda x: x.position)

            # ===== P3: 敌方行动开始时触发（Player turn前，敌方单位触发）=====
            p3_enemy_fired = False; p3_enemy_last = ''
            for eu in enemy_on_field:
                if eu.alive and not eu.is_assist:
                    sp_gain, a_logs = self.trigger_assist_effects(eu, enemy_on_field, player_on_field, '敌方行动开始时')
                    enemy_sp = self.add_sp(enemy_sp, sp_gain)
                    battle_log.extend(a_logs)
                    if a_logs: p3_enemy_fired = True; p3_enemy_last = a_logs[-1]
            if p3_enemy_fired:
                _log(p3_enemy_last, {"type": "assist_trigger", "trigger_type": "敌方行动开始时"})

            _log(f'\n[SP] player:{player_sp} enemy:{enemy_sp}', {"type": "sp_info", "player_sp": player_sp, "enemy_sp": enemy_sp})
            # 上半回合开始：半回合计数 +1，结算状态过期（上下半回合对称计时）
            self._half_turn_count += 1
            if self._tick_expiry(player_units + enemy_units):
                _log('', {"type": "buff_expiry"})
            _log('[Player turn]', {"type": "turn_switch", "side": "player"})
            player_sp, enemy_def_sp = half_turn(player_on_field, enemy_on_field, player_units, player_sp, 'P', round_log, defender_sp=enemy_sp)
            enemy_sp = self.add_sp(enemy_sp, enemy_def_sp)

            # 检查全部6个单位（含替补）
            player_alive = [u for u in player_units if not u.is_assist and u.alive]
            enemy_alive = [u for u in enemy_units if not u.is_assist and u.alive]
            if not player_alive:
                _log('Player all dead', {"type": "battle_end", "winner": "enemy", "reason": "player_dead"})
                return self._create_result('enemy', round_num, battle_log, parsable_battle_log, player_units, enemy_units)
            if not enemy_alive:
                _log('Enemy all dead', {"type": "battle_end", "winner": "player", "reason": "enemy_dead"})
                return self._create_result('player', round_num, battle_log, parsable_battle_log, player_units, enemy_units)

            # ===== P3: 敌方行动开始时触发（Enemy turn前，玩家单位触发）=====
            p3_player_fired = False; p3_player_last = ''
            for pu in player_on_field:
                if pu.alive and not pu.is_assist:
                    sp_gain, a_logs = self.trigger_assist_effects(pu, player_on_field, enemy_on_field, '敌方行动开始时')
                    player_sp = self.add_sp(player_sp, sp_gain)
                    battle_log.extend(a_logs)
                    if a_logs: p3_player_fired = True; p3_player_last = a_logs[-1]
            if p3_player_fired:
                _log(p3_player_last, {"type": "assist_trigger", "trigger_type": "敌方行动开始时"})

            _log('[Enemy turn]', {"type": "turn_switch", "side": "enemy"})
            # 下半回合开始：半回合计数 +1，结算状态过期（上下半回合对称计时）
            self._half_turn_count += 1
            if self._tick_expiry(player_units + enemy_units):
                _log('', {"type": "buff_expiry"})
            enemy_sp, player_def_sp = half_turn(enemy_on_field, player_on_field, enemy_units, enemy_sp, 'E', round_log, defender_sp=player_sp)
            player_sp = self.add_sp(player_sp, player_def_sp)  # 防守方(玩家)获得被攻击SP

            battle_log.extend(round_log)
        # 超时判定：挑战方判负
        winner = "enemy" if challenger == "player" else "player"
        _log(f'超时判定：{winner}胜利', {"type": "battle_end", "winner": winner, "reason": "timeout"})

        return self._create_result(winner, max_rounds, battle_log, parsable_battle_log, player_units, enemy_units)

    def start_boss_battle(self, player_team: dict, boss_card_id: str, initial_sp: int = 300,
                           extra_characters: dict = None,
                           player_initial_hp: dict = None,
                           boss_hp_override: int = None) -> dict:
        """Run a boss battle exclusively, including its temporary HP change."""
        with self._battle_lock:
            return self._start_boss_battle_unlocked(
                player_team,
                boss_card_id,
                initial_sp=initial_sp,
                extra_characters=extra_characters,
                player_initial_hp=player_initial_hp,
                boss_hp_override=boss_hp_override,
            )

    def _start_boss_battle_unlocked(self, player_team: dict, boss_card_id: str, initial_sp: int = 300,
                           extra_characters: dict = None,
                           player_initial_hp: dict = None,
                           boss_hp_override: int = None) -> dict:
        """BOSS战：玩家队伍 vs BOSS（12回合限制）

        :param player_team: 玩家队伍数据 {"battle_cards": [...], "assist_cards": [...]}
        :param boss_card_id: BOSS角色卡牌ID
        :param initial_sp: 玩家初始SP（默认300，即开局满SP）
        :param extra_characters: 额外角色数据（用于补充战斗数据库中没有的卡）
        :param player_initial_hp: 玩家角色初始HP覆盖 {card_id: hp}，用于RAID血量继承
        :param boss_hp_override: BOSS血量覆盖（RAID中BOSS有不同HP）
        :return: BOSS战结果字典
        """
        log_battle("=" * 50)
        log_battle(f"BOSS战开始！BOSS={boss_card_id}")

        # 获取BOSS角色信息（优先从extra_characters查找）
        boss_char = self.get_character(boss_card_id)
        if not boss_char and extra_characters:
            char_data = extra_characters.get(str(boss_card_id))
            if char_data:
                boss_char = Character(
                    card_id=str(boss_card_id),
                    name=char_data.get("name", f"BOSS({boss_card_id})"),
                    hp=char_data.get("hp", 100000),
                    attack=char_data.get("attack", 5000),
                    defense=char_data.get("defense", 3000),
                    speed=char_data.get("dexterity", char_data.get("speed", 1000)),
                    attribute=char_data.get("element", char_data.get("attribute", "红")),
                    attack_type=char_data.get("attack_type", "物理"),
                    side=char_data.get("side", "科学"),
                )
        if not boss_char:
            boss_char = self._get_fallback_character(boss_card_id)

        boss_name = boss_char.name

        # 设置BOSS HP
        original_hp = boss_char.hp
        BOSS_STARTING_HP = boss_hp_override if boss_hp_override else 15_000_000
        boss_char.hp = BOSS_STARTING_HP

        try:
            # 构建BOSS队伍（位置1=中间列，单卡，无A卡）
            boss_team = {"battle_cards": [None, boss_card_id], "assist_cards": []}

            # 调用现有战斗系统（player_hp_override在build_battle_team之后应用）
            result = self.start_battle(
                player_team, boss_team,
                challenger="player",
                initial_player_sp=initial_sp,
                extra_characters=extra_characters,
                player_hp_override=player_initial_hp,
            )
        finally:
            # 恢复BOSS原始HP
            boss_char.hp = original_hp

        # 计算伤害
        boss_ending_hp = 0
        for u in result.get("enemy_units", []):
            if not u.get("is_assist"):
                boss_ending_hp += u.get("hp", 0)

        damage_dealt = max(0, BOSS_STARTING_HP - boss_ending_hp)
        boss_killed = boss_ending_hp <= 0

        # 统计玩家存活
        player_battle_units = [u for u in result.get("player_units", []) if not u.get("is_assist")]
        player_survived = sum(1 for u in player_battle_units if u.get("alive"))
        player_total = len(player_battle_units)

        log_battle(f"BOSS战结束: boss={boss_name}, damage={damage_dealt}, pct={round(damage_dealt/BOSS_STARTING_HP*100, 2)}%, rounds={result['rounds']}")

        return {
            "boss_name": boss_name,
            "boss_card_id": boss_card_id,
            "boss_starting_hp": BOSS_STARTING_HP,
            "boss_ending_hp": boss_ending_hp,
            "damage_dealt": damage_dealt,
            "damage_percent": round(damage_dealt / BOSS_STARTING_HP * 100, 2),
            "rounds": result["rounds"],
            "player_survived": player_survived,
            "player_total": player_total,
            "boss_killed": boss_killed,
            "log": result.get("log", []),
            "player_units": result.get("player_units", []),
            "enemy_units": result.get("enemy_units", [])
        }

    def _create_result(self, winner: str, rounds: int, log: List[str], parsable_log: List[dict],
                      player_units: List[BattleUnit], enemy_units: List[BattleUnit]) -> dict:
        """创建战斗结果，返回前恢复潜能修改的基础属性"""
        # 恢复所有玩家单位的潜能加成（退出战斗时恢复原始属性）
        for u in player_units:
            if not u.is_assist:
                try:
                    self._restore_passive_stats(u)
                except Exception:
                    pass

        def _unit_dict(u):
            return {
                "name": u.character.name,
                "card_id": u.character.card_id,
                "hp": u.current_hp,
                "max_hp": u.max_hp,
                "alive": u.alive,
                "is_assist": u.is_assist,
                "position": u.position,
                "stars": u.character.stars,
                "attack_directions": u.character.attack_directions,
                "buffs": [{"name": b.name, "magnitude": b.magnitude} for b in u.buffs],
                "debuffs": [{"name": d.name, "magnitude": d.magnitude} for d in u.debuffs],
            }

        return {
            "winner": winner,
            "rounds": rounds,
            "log": log,
            "parsable_log": parsable_log,
            "player_units": [_unit_dict(u) for u in player_units],
            "enemy_units": [_unit_dict(u) for u in enemy_units],
        }


# ========== 格式化输出 ==========
def format_battle_result(result: dict) -> str:
    """格式化战斗结果"""
    lines = []

    lines.append(f"\n{'='*60}")
    lines.append(f"自动战斗")
    lines.append(f"{'='*60}")

    for log in result["log"]:
        if log.startswith("\n") and ("回合" in log):
            lines.append(log)
        elif not log.startswith("📊"):
            lines.append(log)

    lines.append(f"\n{'='*60}")
    if result["winner"] == "player":
        lines.append("玩家队伍胜利！")
    else:
        lines.append("敌方队伍胜利...")
    lines.append(f"{'='*60}")

    lines.append(f"\n战斗统计：")
    lines.append(f"   回合数：{result['rounds']}")

    lines.append(f"\n玩家队伍：")
    battle_units = [u for u in result["player_units"] if not u["is_assist"]]
    for u in battle_units:
        status = "存活" if u["alive"] else "阵亡"
        lines.append(f"   [{status}] {u['name']}: {u['hp']}/{u['max_hp']}")

    lines.append(f"\n敌方队伍：")
    battle_units = [u for u in result["enemy_units"] if not u["is_assist"]]
    for u in battle_units:
        status = "存活" if u["alive"] else "阵亡"
        lines.append(f"   [{status}] {u['name']}: {u['hp']}/{u['max_hp']}")

    return "\n".join(lines)


# ========== BOSS战结果格式化 ==========
def format_boss_result(result: dict, include_log: bool = False) -> str:
    """格式化BOSS战结果

    :param result: BOSS战结果字典
    :param include_log: 是否包含详细回合日志（战斗日志命令时使用）
    """
    boss_name = result.get("boss_name", "???")
    boss_start = result.get("boss_starting_hp", 15000000)
    boss_end = result.get("boss_ending_hp", 0)
    damage = result.get("damage_dealt", 0)
    damage_pct = result.get("damage_percent", 0)
    rounds = result.get("rounds", 0)
    survived = result.get("player_survived", 0)
    total = result.get("player_total", 0)
    boss_killed = result.get("boss_killed", False)

    def fmt_hp(n: int) -> str:
        return f"{n:,}"

    lines = []
    lines.append("")
    lines.append("=" * 40)
    lines.append("       BOSS战 结果")
    lines.append("=" * 40)
    lines.append(f"  BOSS: {boss_name}")
    lines.append(f"  BOSS HP: {fmt_hp(boss_start)} → {fmt_hp(boss_end)}")
    lines.append(f"  造成伤害: {fmt_hp(damage)} ({damage_pct}%)")

    if boss_killed:
        lines.append(f"  !! BOSS被击杀 !!")

    lines.append(f"  战斗回合: {rounds}/12")
    lines.append(f"  玩家存活: {survived}/{total}")

    # 详细回合日志
    if include_log and result.get("log"):
        lines.append("")
        lines.append("=" * 40)
        lines.append("      详细战斗日志")
        lines.append("=" * 40)
        for log_line in result["log"]:
            if log_line.startswith("\n") and ("回合" in log_line):
                lines.append(log_line)
            elif not log_line.startswith("📊"):
                lines.append(log_line)

    lines.append("=" * 40)

    return "\n".join(lines)


# ========== 帮助信息 ==========
def get_battle_help() -> str:
    """获取战斗系统帮助信息"""
    return """
╔══════════════════════════════════════════════════════════════╗
║         魔法禁书目录幻想收束 - 战斗系统                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  战斗命令：                                                   ║
║                                                              ║
║  · 战斗 / 对战                                               ║
║    使用当前配队与AI对战                                       ║
║                                                              ║
║  · 战斗 @玩家                                                ║
║    与指定玩家对战                                             ║
║                                                              ║
║  · BOSS战                                                    ║
║    挑战1500万血量BOSS（自动战斗，限12回合）                   ║
║                                                              ║
║  · 战斗日志                                                  ║
║    查看最近一场战斗的详细日志                                 ║
║                                                              ║
║  · 对战说明                                                  ║
║    查看战斗系统详细帮助                                       ║
║                                                              ║
║  · 排行榜                                                    ║
║    查看当前排行榜TOP10                                        ║
║                                                              ║
║  · 挑战 排名                                                 ║
║    挑战排行榜上指定排名的玩家/AI                              ║
║    （只能挑战排名比自己高且不超过3位的对手）                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""


# ========== 战斗GIF渲染 ==========
from io import BytesIO
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

STATE_ICON_DIR = BASE_DIR / "state_icon"
ICONIMAGE_DIR = BASE_DIR / "iconimage"
GIF_OUTPUT_DIR = BASE_DIR / "output"

# buff/debuff名 → state_icon 文件名映射
BUFF_ICON_MAP = {
    "攻击": "ATK", "防御": "DEF", "暴伤": "CRITICAL_DAMAGE_RATE",
    "暴击防御": "CRITICAL_RESIST_RATE", "暴击率": "CRITICAL_DAMAGE_RATE",
    "回避率": "DEX", "必杀威力": "SPECIAL_DAMAGE", "技能威力": "SKILL_DAMAGE",
    "SP获得量": "SP", "减伤": "DAMAGE_ZERO",
    "颜色耐性": "STATE_RESIST", "必杀耐性": "SKILL_RESIST",
    "颜色威力": "SPECIAL_ENHANCED", "盾": "DAMAGE_COVER", "外的御供": "OUTSIDE_OFFERING",
    "贯通": "PIERCING", "不屈": "GUTS", "强耐": "STATE_RESIST",
    "弱耐": "STATE_RESIST", "必暴": "SPECIAL_ENHANCED",
    "感电耐性": "STATE_RESIST", "移动不能耐性": "STATE_RESIST",
    "a卡封印耐性": "SEAL_RESIST", "必杀封印耐性": "SILENCE_RESIST",
    "感电": "SHOCK", "气绝": "FAINT", "制御不能": "UNCONTROL",
    "持续被害": "BLEED", "出血": "BLEED", "a卡封印": "SEAL", "技能封印": "SILENCE",
    "必杀封印": "SILENCE", "强化妨害": "VOID_BUFF_CONDITION_BAD",
    "攻击提升妨害": "VOID_BUFF_CONDITION_BAD", "HP回复妨害": "VOID_HP_HEAL",
    "弱体化解除妨害": "VOID_BUFF_CONDITION_GOOD", "移动不能": "WORLD_MOVE",
    "攻击方向+": "ATTACK_DIR_3WAY", "攻击方向-": "ATTACK_DIR_DOWN",
    "天罚": "DIVINE_RETRIBUTION_SPELL", "反射": "MIRROR_ATTACK",
    "矢量操作": "VECTOR_CONVERSION", "强制咏唱待机": "SPELL_INTERCEPT",
}
DEBUFF_ICON_SUFFIX = "_DOWN"
BUFF_ICON_SUFFIX = "_UP"
