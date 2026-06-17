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
    '行动开始时', '敌方行动开始时', '替补入场时',
    '自身技能时', '自身必杀时', '自身对敌方暴击时', '自身对敌方造成伤害时',
    '自身退场时',
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
    '盾', '矢量操作', '强制咏唱待机', '全能神', '嘲讽', '强耐', '弱耐', '不屈',
    '预测不能', '天罚', r'攻击方向\+.',
    '必暴', '贯通', r'HP回复\(.+?\)', r'物攻提升\(.+?\)', r'异攻提升\(.+?\)', r'物防提升\(.+?\)',
    r'异防提升\(.+?\)', r'暴击防御提升\(.+?\)',
    r'暴击率提升\(.+?\)', r'回避率提升\(.+?\)', r'暴伤提升\(.+?\)',
    r'必杀威力提升\(.+?\)', r'技能威力提升\(.+?\)',
    r'SP获得量提升\(.+?\)', r'[^【]*减伤\(.+?\)', r'对.色威力提升\(.+?\)'
]

ALL_DEBUFF_LIST = [
    '强化妨害', '攻击提升妨害', 'HP回复妨害', '弱体化解除妨害',
    r'强化解除(\(.+?\))?',
    r'持续被害\(.+?\)', '感电', '气绝', '移动不能', '制御不能', 'a卡封印',
    r'攻击方向\-.', '技能封印', '必杀封印',
    r'物攻下降\(.+?\)', r'异攻下降\(.+?\)', r'物防下降\(.+?\)',
    r'异防下降\(.+?\)', r'必杀威力下降\(.+?\)',
    r'暴击率下降\(.+?\)', r'回避率下降\(.+?\)', r'暴击防御下降\(.+?\)',
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
    """潜能"""
    name: str  # 潜能名称
    level: int = 1  # 等级
    
    def get_attack_bonus(self) -> int:
        """获取攻击加成"""
        params = BattleParams
        if self.name in params.ATTACK_POTENTIAL:
            return params.ATTACK_POTENTIAL[self.name] * self.level
        return 0
    
    def get_multiplier(self) -> float:
        """获取倍率加成"""
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
    ultimate: Optional[Skill] = None  # 技能2（必杀技）
    
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
        area_patterns = ['范围内', '三方向', '正面', '敌全体', '左侧', '右侧', '前右', '前左']
        for area in area_patterns:
            if area in text:
                skill.area = area
                break
        
        # 解析效果
        effects = []
        for pattern in ALL_BUFF_LIST + ALL_DEBUFF_LIST + ALL_ATTACK_LIST:
            matches = re.findall(pattern, text)
            effects.extend(matches)
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
            '自身对敌方造成伤害时', '自身对敌方暴击时',
            '敌方行动开始时', '行动开始时',
            '替补入场时',
            '自身技能时', '自身必杀时',
            '自身退场时',
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
    
    def _parse_passive_text(self, text: str, level: int, attack_type: str, enemy_side: str) -> List[Passive]:
        """解析潜能文本"""
        if not text:
            return []
        
        passives = []
        parts = text.strip().split('+')
        
        for part in parts:
            part = part.strip()
            
            # 物攻向上/异攻向上
            m = re.fullmatch(r'(.)攻向上(\(.+\))?', part)
            if m and m.group(1) == attack_type[0]:
                magnitude = m.group(2)[1:-1] if m.group(2) else "中"
                passive_name = "攻击" + magnitude
                if len(parts) == 1:
                    passive_name = "单" + passive_name
                passives.append(Passive(name=passive_name, level=level))
                continue
            
            # 方向攻击强化
            m = re.fullmatch(r'(.+)方向攻击强化(\(.+\))?', part)
            if m:
                magnitude = m.group(2)[1:-1] if m.group(2) else "中"
                passives.append(Passive(name="方向" + magnitude))
                continue
            
            # SP获得量向上
            m = re.fullmatch(r'SP获得量向上(\(.+\))?', part)
            if m:
                magnitude = m.group(1)[1:-1] if m.group(1) else "小"
                sp_name = "SP" + magnitude
                if len(parts) == 2:
                    sp_name = "单" + sp_name
                passives.append(Passive(name=sp_name))
                continue
            
            # 解析
            m = re.fullmatch(r'(..)解析\((.)\)', part)
            if m:
                if (m.group(1), enemy_side) in [('构造', '科学'), ('术式', '魔法')]:
                    passives.append(Passive(name="解析" + m.group(2)))
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
                
                # 解析潜能
                passives = []
                passive_text1 = char_data.get("passive1", "")
                passive_text2 = char_data.get("passive2", "")
                level = char_data.get("level", 1)
                attack_type = char_data.get("attack_type", "物理")
                side = char_data.get("side", "科学")
                
                passives.extend(self._parse_passive_text(passive_text1, level, attack_type, side))
                if passive_text2:
                    passives.extend(self._parse_passive_text(passive_text2, level, attack_type, side))
                
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
                    attack_directions=len(char_data.get("attack_directions", [0])) if isinstance(char_data.get("attack_directions"), list) else char_data.get("attack_directions", 1),
                    side=char_data.get("side", "科学"),
                    skill=skill,
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
            attribute='红', attack_type='物理', attack_directions=1, side='科学',
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
                    attack_directions=len(char_data.get("attack_directions", [0])) if isinstance(char_data.get("attack_directions"), list) else 1, 
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
    
    def build_battle_team(self, team_data: dict, extra_characters: dict = None) -> List[BattleUnit]:
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
        
        return units
    
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
                         power_up_count: int = 0) -> Tuple[int, bool, str, float, float]:
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
        damage = int(attack ** 2 / (attack + defense))
        
        # 6. 属性克制
        attr_mult = self._get_attribute_multiplier(attacker.character.attribute, defender.character.attribute)
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
            crit_def_mult, crit_def_extra = attacker.get_buff_multiplier("暴击防御")
            
            # 暴击伤害 = 伤害 * (1.5 + 暴伤倍率 + 暴击防御倍率) + 附加伤害
            damage = int(damage * (1.5 + crit_mult + crit_def_mult) + crit_extra + crit_def_extra)
        
        # 8. 颜色耐性/必杀耐性/颜色威力
        color_resist_mult, color_resist_extra = defender.get_buff_multiplier("颜色耐性")
        ult_resist_mult, ult_resist_extra = defender.get_buff_multiplier("必杀耐性")
        color_power_mult, color_power_extra = attacker.get_buff_multiplier("颜色威力")
        
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
        targets = [e for e in enemies if e.alive and e.position < 5 and (e.position%5) in cols]
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
                if e.name == name: e.duration = max(e.duration, duration); e.magnitude = magnitude; return
            for e in target.debuffs:
                if e.name == name: e.duration = max(e.duration, duration); e.magnitude = magnitude; return
        if any(d.name == '强化妨害' for d in target.debuffs): return
        if name == '攻击' and any(d.name == '攻击提升妨害' for d in target.debuffs): return
        target.buffs.append(BuffEffect(name=name, magnitude=magnitude, source=source, duration=duration))

    def _apply_debuff(self, target, name, magnitude='中', source='', duration=0):
        """应用debuff: 特殊buff覆盖刷新, 弱耐阻止"""
        if name in self.SPECIAL_BUFFS:
            for e in target.debuffs:
                if e.name == name: e.duration = max(e.duration, duration); e.magnitude = magnitude; return
            for e in target.buffs:
                if e.name == name: e.duration = max(e.duration, duration); e.magnitude = magnitude; return
        if any(b.name == '弱耐' for b in target.buffs): return
        target.debuffs.append(BuffEffect(name=name, magnitude=magnitude, source=source, duration=duration))

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
                              allies: List[BattleUnit] = None) -> Tuple[List[str], int, int]:
        """执行普通攻击，返回(战斗日志, 攻击方获得SP, 防守方获得SP)"""
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
                results.append(f"{attacker.character.name} -> {target.character.name} (回避！)")
                defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))
                continue

            damage, is_crit, damage_type, attr_mult, ratio = self.calculate_damage(attacker, target, "normal")
            target_name = f"({ratio:.2f}){attacker.character.name} -> {target.character.name}"

            defender_sp += int(SP_PER_DAMAGED * self._get_sp_rate(target))

            # 天罚/反射判定
            damage, reflect_logs, attacker_died = self._handle_counter_effects(target, attacker, damage)
            results.extend(reflect_logs)

            # 记录受击状态
            hit_status = {"blocked": False, "reflected": False, "absorbed": False, "reduced": False}
            
            # 检查是否有反射效果
            if len(reflect_logs) > 0 and "反射" in reflect_logs[-1]:
                hit_status["reflected"] = True

            # 盾判定：抵挡一次非贯通伤害
            if self._check_shield(target, attacker):
                hit_status["blocked"] = True
                # 判断目标是玩家还是敌方：攻击方在allies中说明是玩家攻击，目标是敌方
                side = "enemy" if attacker in allies else "player"
                self._last_damage_info[side][target.character.name] = hit_status
                results.append(f"{target_name} ({damage}伤害，盾抵挡！) [{damage_type}]")
                continue

            # 检查减伤
            dmg_reduce_mult, _ = target.get_buff_multiplier("减伤")
            if dmg_reduce_mult > 0:
                hit_status["reduced"] = True

            # 记录受击状态
            side = "enemy" if attacker in allies else "player"
            self._last_damage_info[side][target.character.name] = hit_status

            target.current_hp -= damage
            has_damage_this_attack = True
            if is_crit:
                has_crit_this_attack = True

            if target.current_hp <= 0:
                if self._check_tenacity(target):
                    results.append(f"{target_name} ({damage}伤害，不屈！HP={target.current_hp}) [{damage_type}]")
                else:
                    target.current_hp = 0; target.alive = False
                    if target.assist_unit: target.assist_unit.alive = False
                    results.append(f"{target_name} ({damage}伤害，击破！) [{damage_type}]")
            else:
                results.append(f"{target_name} ({damage}伤害) [{damage_type}]")

        # ===== P5: 被攻击时触发 =====
        if allies and has_damage_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '对敌方造成伤害时')
            assist_sp += sp; results.extend(a_logs)
        if allies and has_crit_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)

        attacker_sp = int(SP_PER_ATTACK * self._get_sp_rate(attacker)) + assist_sp

        return results, attacker_sp, defender_sp
    
    def execute_skill_attack(self, attacker: BattleUnit, enemies: List[BattleUnit],
                            can_use_skill: bool = True, skill_sp: int = 30,
                            allies: List[BattleUnit] = None) -> Tuple[List[str], int, int, int]:
        """执行技能攻击，返回(战斗日志, 消耗的SP, 攻击方获得SP, 防守方获得SP)"""
        results = []

        if not attacker.character.skill:
            r, atk_sp, def_sp = self.execute_normal_attack(attacker, enemies, allies)
            return r, 0, atk_sp, def_sp

        if not can_use_skill or skill_sp < 30:
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
                results.append(f"{target_name} ({damage}伤害，盾抵挡！) [{damage_type}]")
                continue

            target.current_hp -= damage
            has_damage_this_attack = True
            if is_crit:
                has_crit_this_attack = True
            if target.current_hp <= 0:
                if self._check_tenacity(target):
                    results.append(f"{target_name} ({damage}伤害，不屈！HP={target.current_hp}) [{damage_type}]")
                else:
                    target.current_hp = 0; target.alive = False
                    if target.assist_unit: target.assist_unit.alive = False
                    results.append(f"{target_name} ({damage}伤害，击破！) [{damage_type}]")
            else:
                results.append(f"{target_name} ({damage}伤害) [{damage_type}]")
        attacker.skill_cooldown = attacker.character.skill.cooldown

        # 应用技能增益效果
        if allies:
            buff_results = self._apply_skill_effect(attacker, attacker.character.skill, allies, enemies)
            results.extend(buff_results)

        # ===== P5: 被攻击时触发 + 技能时 =====
        if allies and has_damage_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '对敌方造成伤害时')
            assist_sp += sp; results.extend(a_logs)
        if allies and has_crit_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)
        if allies:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '技能时')
            assist_sp += sp; results.extend(a_logs)

        attacker_sp = int(SP_PER_ATTACK * self._get_sp_rate(attacker)) + assist_sp

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
                results.append(f"{target_name} ({damage}伤害，盾抵挡！) [{damage_type}]")
                continue

            target.current_hp -= damage
            has_damage_this_attack = True
            if is_crit:
                has_crit_this_attack = True
            if target.current_hp <= 0:
                if self._check_tenacity(target):
                    results.append(f"{target_name} ({damage}伤害，不屈！HP={target.current_hp}) [{damage_type}]")
                else:
                    target.current_hp = 0; target.alive = False
                    if target.assist_unit: target.assist_unit.alive = False
                    results.append(f"{target_name} ({damage}伤害，击破！) [{damage_type}]")
            else:
                results.append(f"{target_name} ({damage}伤害) [{damage_type}]")

        # 应用技能增益效果
        if allies:
            buff_results = self._apply_skill_effect(attacker, ultimate, allies, enemies)
            results.extend(buff_results)

        # ===== P5: 被攻击时触发 + 必杀时 =====
        if allies and has_damage_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '对敌方造成伤害时')
            assist_sp += sp; results.extend(a_logs)
        if allies and has_crit_this_attack:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '对敌方暴击时')
            assist_sp += sp; results.extend(a_logs)
        if allies:
            sp, a_logs = self.trigger_assist_effects(attacker, allies, enemies, '必杀时')
            assist_sp += sp; results.extend(a_logs)

        attacker_sp = int(SP_PER_ATTACK * self._get_sp_rate(attacker)) + assist_sp

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
            # 自身 + 相邻1格的友方（5列布局中相邻即±1）
            targets = [source_unit]
            for ally in allies:
                if ally != source_unit and not ally.is_assist and ally.alive:
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

            # 强化解除: 消除敌方buff（强耐可阻挡）
            if '强化解除' in effect_text:
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

            # 弱体化解除: 清除我方debuff（弱体化解除妨害可阻挡）
            if '弱体化解除' in effect_text:
                for ally in allies:
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
                                results.append(f"{ally.character.name} 弱体化解除: {', '.join(removed)}")

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
    
    def start_battle(self, player_team: dict, enemy_team: dict, challenger: str = "player", initial_player_sp: int = 0, extra_characters: dict = None) -> dict:
        """开始战斗"""
        log_battle("=" * 50)
        log_battle("战斗开始！")

        player_units = self.build_battle_team(player_team, extra_characters)
        enemy_units = self.build_battle_team(enemy_team, extra_characters)

        # 给角色名加位置箭头: 友方5列, 敌方5列
        p_arrows = {0:'↙', 1:'←', 2:'↓', 3:'→', 4:'↘'}
        e_arrows = {0:'↖', 1:'←', 2:'↑', 3:'→', 4:'↗'}

        # 阵营SP池（共用SP）
        player_sp = initial_player_sp
        enemy_sp = 0

        battle_log = []
        parsable_battle_log = []
        
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
        
        def _log(text, parsable=None):
            nonlocal last_player_hp, last_enemy_hp
            """同时记录文本日志和可解析日志"""
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
                """获取受击状态（抵挡、反射、特殊BUFF）"""
                status = ""
                damage_info = self._last_damage_info.get(side, {}).get(name, {})
                if damage_info.get("blocked", False):
                    status += "抵挡"
                if damage_info.get("reflected", False):
                    status += "反射"
                if damage_info.get("absorbed", False):
                    status += "吸收"
                if damage_info.get("reduced", False):
                    status += "减伤"
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
                parsable_battle_log.append(entry)
            
            # 更新上一个状态的HP值
            last_player_hp = current_player_hp
            last_enemy_hp = current_enemy_hp
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
        
        for unit in player_starters:
            sp_gained, p1_logs = self.trigger_assist_effects(unit, player_starters, enemy_starters, '行动开始时')
            player_sp = self.add_sp(player_sp, sp_gained)
            battle_log.extend(p1_logs)
        for unit in enemy_starters:
            sp_gained, p1_logs = self.trigger_assist_effects(unit, enemy_starters, player_starters, '行动开始时')
            enemy_sp = self.add_sp(enemy_sp, sp_gained)
            battle_log.extend(p1_logs)

        for round_num in range(1, MAX_BATTLE_ROUNDS + 1):
            round_title = f"\n{'='*50}\n第 {round_num} 回合\n{'='*50}"
            _log(round_title, {"type": "round_start", "round": round_num})
            round_log = []

            # ===== P1: 波次/回合开始 — CD递减 + 回合开始触发 =====
            for unit in player_units + enemy_units:
                if unit.skill_cooldown > 0: unit.skill_cooldown -= 1
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
            player_on_field = player_alive_all[:INITIAL_DEPLOY_COUNT]
            player_on_field.sort(key=lambda x: x.position)
            enemy_on_field = enemy_alive_all[:INITIAL_DEPLOY_COUNT]
            enemy_on_field.sort(key=lambda x: x.position)
            
            # ===== 半回合处理 =====
            # 优先级: P2替补→P3行动开始→P4攻击→P5被攻击→P6 HP阈值→P7 SP满→P8 Break
            def half_turn(side_units, side_enemies, all_units, side_sp, tag, round_log):
                """执行半回合，返回(攻击方新SP, 防守方获得SP)"""
                defender_sp_total = 0  # 防守方本回合被攻击获得的SP

                # ===== P2: 替补入场（继承阵亡单位的位置）=====
                # 从替补队列中获取可用替补（position=-1表示在替补队列）
                alive_bench = sorted([u for u in all_units if not u.is_assist and u.alive and u.position == -1], key=lambda x: x.character.name)
                needed = max(0, INITIAL_DEPLOY_COUNT - len(side_units))
                # 找出阵亡单位的位置
                dead_positions = []
                for u in all_units:
                    if not u.is_assist and not u.alive:
                        pos = u.position
                        if pos >= 0 and pos < 5 and pos not in dead_positions:
                            dead_positions.append(pos)
                dead_positions.sort()
                for i, u in enumerate(alive_bench[:needed]):
                    # 替补继承阵亡位置（按原顺序分配）
                    if i < len(dead_positions):
                        u.position = dead_positions[i]
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
                side_units.sort(key=lambda x: x.position)
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
                dot_pcts = {'小': 0.03, '中': 0.05, '大': 0.08}
                for unit in list(side_units):
                    if unit.alive:
                        for d in list(unit.debuffs):
                            if d.name == '持续被害':
                                dot_pct = dot_pcts.get(d.magnitude, 0.05)
                                dot_dmg = max(1, int(unit.max_hp * dot_pct))
                                unit.current_hp -= dot_dmg
                                round_log.append(f'  [持续被害] {unit.character.name} -{dot_dmg}HP')
                                if unit.current_hp <= 0:
                                    if not self._check_tenacity(unit):
                                        unit.current_hp = 0
                                        unit.alive = False
                                        if unit.assist_unit:
                                            unit.assist_unit.alive = False
                                        round_log.append(f'  [持续被害] {unit.character.name} 被DoT击破！')
                                        # P10: 自身退场时触发
                                        sp_gained, r_logs = self.trigger_assist_effects(unit, side_units, side_enemies, '自身退场时')
                                        side_sp = self.add_sp(side_sp, sp_gained)
                                        round_log.extend(r_logs)
                                break  # 每种持续被害只触发一次

                # ===== P4: 攻击决策 =====
                planned = {}
                sp = side_sp

                # ===== P7: 敌方SP满时触发 (在攻击方行动前，防御方SP满时触发) =====
                # 检查防守方是否有人SP满了
                opp_tag = 'E' if tag == 'P' else 'P'
                for opp_unit in side_enemies:
                    if opp_unit.alive and not opp_unit.is_assist:
                        sp_gained, p7_logs = self.trigger_assist_effects(
                            opp_unit, side_enemies, side_units, '敌方SP满时')
                        side_sp = self.add_sp(side_sp, sp_gained)
                        round_log.extend(p7_logs)

                for unit in sorted([u for u in side_units if u.alive], key=lambda x: x.character.speed, reverse=True):
                    has_ult = bool(unit.character.ultimate) if hasattr(unit.character, 'ultimate') else False
                    has_skill = bool(unit.character.skill) if hasattr(unit.character, 'skill') else False
                    sealed_skill = any(d.name == '技能封印' for d in unit.debuffs)
                    sealed_ult = any(d.name == '必杀封印' for d in unit.debuffs)
                    sealed_assist = any(d.name == 'a卡封印' for d in unit.debuffs)
                    has_targets = bool(self.get_targets_in_direction(unit, side_enemies))
                    if has_targets and sp >= ULT_COST and unit.ult_cooldown == 0 and not sealed_ult and has_ult:
                        planned[id(unit)] = 'ultimate'; sp -= ULT_COST
                    elif has_targets and sp >= 30 and unit.skill_cooldown == 0 and not sealed_skill and has_skill:
                        planned[id(unit)] = 'skill'; sp -= 30
                    else:
                        planned[id(unit)] = 'normal'

                # ===== P4+P5: 执行攻击 + 被攻击时触发（execute内部处理P5）=====
                for unit in sorted([u for u in side_units if u.alive], key=lambda x: x.character.speed, reverse=True):
                    if not unit.alive: continue
                    stunned = any(d.name in ('感电','气绝','制御不能') for d in unit.debuffs)
                    if stunned:
                        for d in list(unit.debuffs):
                            if d.name in ('感电','气绝','制御不能'): unit.debuffs.remove(d); break
                        side_sp = self.add_sp(side_sp, 15)
                        round_log.append(f'  [无法行动] {unit.character.name}')
                        continue
                    action = planned.get(id(unit), 'normal')
                    enemies = side_enemies

                    # 记录攻击前HP（用于P6 HP阈值检测，含攻击方自身防反射）
                    hp_before = {}
                    for t in list(enemies) + [unit]:
                        if t.alive:
                            hp_before[id(t)] = t.current_hp

                    if action == 'ultimate':
                        side_sp -= ULT_COST
                        results, used, atk_sp, def_sp = self.execute_ultimate_attack(unit, enemies, True, side_units)
                        round_log.extend(results); side_sp = self.add_sp(side_sp, atk_sp); defender_sp_total += def_sp
                        # 立即记录攻击日志，确保HP变化及时反映
                        attack_info = {
                            "type": "attack",
                            "attack_type": "终",
                            "attacker": unit.character.name,
                            "attacker_position": unit.position,
                            "attacker_arrow": self._get_arrow_by_position(unit.position, 'P' if tag == 'P' else 'E'),
                            "targets": [{"name": e.character.name, "position": e.position, "arrow": self._get_arrow_by_position(e.position, 'E' if tag == 'P' else 'P')} for e in enemies if e.alive]
                        }
                        _log(results[-1] if results else "", attack_info)
                    elif action == 'skill':
                        side_sp -= 30
                        results, used, atk_sp, def_sp = self.execute_skill_attack(unit, enemies, True, 30, side_units)
                        round_log.extend(results); side_sp = self.add_sp(side_sp, atk_sp); defender_sp_total += def_sp
                        # 立即记录攻击日志，确保HP变化及时反映
                        attack_info = {
                            "type": "attack",
                            "attack_type": "技",
                            "attacker": unit.character.name,
                            "attacker_position": unit.position,
                            "attacker_arrow": self._get_arrow_by_position(unit.position, 'P' if tag == 'P' else 'E'),
                            "targets": [{"name": e.character.name, "position": e.position, "arrow": self._get_arrow_by_position(e.position, 'E' if tag == 'P' else 'P')} for e in enemies if e.alive]
                        }
                        _log(results[-1] if results else "", attack_info)
                    else:
                        results, atk_sp, def_sp = self.execute_normal_attack(unit, enemies, side_units)
                        round_log.extend(results); side_sp = self.add_sp(side_sp, atk_sp); defender_sp_total += def_sp
                        # 立即记录攻击日志，确保HP变化及时反映
                        attack_info = {
                            "type": "attack",
                            "attack_type": "普",
                            "attacker": unit.character.name,
                            "attacker_position": unit.position,
                            "attacker_arrow": self._get_arrow_by_position(unit.position, 'P' if tag == 'P' else 'E'),
                            "targets": [{"name": e.character.name, "position": e.position, "arrow": self._get_arrow_by_position(e.position, 'E' if tag == 'P' else 'P')} for e in enemies if e.alive]
                        }
                        _log(results[-1] if results else "", attack_info)

                    # ===== P10: 自身退场时触发（击破时遗言效果）=====
                    # 检查哪些敌方单位在本轮攻击中被击破
                    dead_enemies = [e for e in enemies if id(e) in hp_before and not e.alive and hp_before[id(e)] > 0]
                    for dead in dead_enemies:
                        round_log.append(f'  [退场] {dead.character.name} 被击破！')
                        # 触发死者自身的退场效果（allies=敌方，enemies=我方）
                        sp_gained, r_logs = self.trigger_assist_effects(dead, side_enemies, side_units, '自身退场时')
                        side_sp = self.add_sp(side_sp, sp_gained)
                        round_log.extend(r_logs)
                    # 检查攻击者是否被反射击杀
                    if id(unit) in hp_before and not unit.alive and hp_before[id(unit)] > 0:
                        round_log.append(f'  [退场] {unit.character.name} 被反射击破！')
                        sp_gained, r_logs = self.trigger_assist_effects(unit, side_units, side_enemies, '自身退场时')
                        side_sp = self.add_sp(side_sp, sp_gained)
                        round_log.extend(r_logs)

                    # ===== P6: HP阈值触发 =====
                    all_checked = set()
                    for target in list(enemies) + [unit]:
                        if not target.alive or id(target) in all_checked:
                            continue
                        if id(target) not in hp_before:
                            continue
                        all_checked.add(id(target))
                        hp_pct = target.current_hp / target.max_hp if target.max_hp > 0 else 0
                        hp_before_pct = hp_before[id(target)] / target.max_hp if target.max_hp > 0 else 0
                        # target is in enemies → its allies are side_enemies
                        target_allies = side_enemies if target in enemies else side_units
                        target_enemies = side_units if target in enemies else side_enemies
                        # HP跌破50%
                        if hp_pct < 0.5 and hp_before_pct >= 0.5:
                            round_log.append(f'  [HP阈值] {target.character.name} HP低于50%')
                            sp_gained, hp_logs = self.trigger_assist_effects(target, target_allies, target_enemies, 'HP低于50%时')
                            side_sp = self.add_sp(side_sp, sp_gained)
                            round_log.extend(hp_logs)
                        # HP跌破30%
                        if hp_pct < 0.3 and hp_before_pct >= 0.3:
                            round_log.append(f'  [HP阈值] {target.character.name} HP低于30%')
                            sp_gained, hp_logs = self.trigger_assist_effects(target, target_allies, target_enemies, 'HP低于30%时')
                            side_sp = self.add_sp(side_sp, sp_gained)
                            round_log.extend(hp_logs)

                    side_units[:] = [u for u in side_units if u.alive]
                    side_enemies[:] = [e for e in side_enemies if e.alive]
                    if not side_units or not side_enemies: break
                return side_sp, defender_sp_total

            # 半回合前刷新场上（替补进场由half_turn内部处理）
            # 只取3人上场，保持原有位置
            player_on_field = [u for u in player_units if not u.is_assist and u.alive][:INITIAL_DEPLOY_COUNT]
            player_on_field.sort(key=lambda x: x.position)
            enemy_on_field = [u for u in enemy_units if not u.is_assist and u.alive][:INITIAL_DEPLOY_COUNT]
            enemy_on_field.sort(key=lambda x: x.position)

            # ===== P3: 敌方行动开始时触发（Player turn前，敌方单位触发）=====
            for eu in enemy_on_field:
                if eu.alive and not eu.is_assist:
                    sp_gain, a_logs = self.trigger_assist_effects(eu, enemy_on_field, player_on_field, '敌方行动开始时')
                    enemy_sp = self.add_sp(enemy_sp, sp_gain)
                    battle_log.extend(a_logs)

            _log(f'\n[SP] player:{player_sp} enemy:{enemy_sp}', {"type": "sp_info", "player_sp": player_sp, "enemy_sp": enemy_sp})
            _log('[Player turn]', {"type": "turn_switch", "side": "player"})
            player_sp, enemy_def_sp = half_turn(player_on_field, enemy_on_field, player_units, player_sp, 'P', round_log)
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
            for pu in player_on_field:
                if pu.alive and not pu.is_assist:
                    sp_gain, a_logs = self.trigger_assist_effects(pu, player_on_field, enemy_on_field, '敌方行动开始时')
                    player_sp = self.add_sp(player_sp, sp_gain)
                    battle_log.extend(a_logs)

            _log('[Enemy turn]', {"type": "turn_switch", "side": "enemy"})
            enemy_sp, player_def_sp = half_turn(enemy_on_field, player_on_field, enemy_units, enemy_sp, 'E', round_log)
            player_sp = self.add_sp(player_sp, player_def_sp)  # 防守方(玩家)获得被攻击SP

            for u in player_units + enemy_units:
                for b in list(u.buffs):
                    if b.duration > 0: b.duration -= 1
                    if b.duration <= 0 and b.duration != 0: u.buffs.remove(b)
                for d in list(u.debuffs):
                    if d.duration > 0: d.duration -= 1
                    if d.duration <= 0 and d.duration != 0: u.debuffs.remove(d)

            battle_log.extend(round_log)
        # 超时判定：挑战方判负
        winner = "enemy" if challenger == "player" else "player"
        _log(f'超时判定：{winner}胜利', {"type": "battle_end", "winner": winner, "reason": "timeout"})
        
        return self._create_result(winner, MAX_BATTLE_ROUNDS, battle_log, parsable_battle_log, player_units, enemy_units)

    def start_boss_battle(self, player_team: dict, boss_card_id: str, initial_sp: int = 300) -> dict:
        """BOSS战：玩家队伍 vs 单个1500万血量BOSS（12回合限制）

        :param player_team: 玩家队伍数据 {"battle_cards": [...], "assist_cards": [...]}
        :param boss_card_id: BOSS角色卡牌ID
        :param initial_sp: 玩家初始SP（默认300，即开局满SP）
        :return: BOSS战结果字典
        """
        log_battle("=" * 50)
        log_battle(f"BOSS战开始！BOSS={boss_card_id}")

        # 获取BOSS角色信息
        boss_char = self.get_character(boss_card_id)
        if not boss_char:
            boss_char = self._get_fallback_character(boss_card_id)

        boss_name = boss_char.name

        # 临时将BOSS角色HP改为1500万
        original_hp = boss_char.hp
        boss_char.hp = 15_000_000
        BOSS_STARTING_HP = 15_000_000

        try:
            # 构建BOSS队伍（位置1=中间列，单卡，无A卡）
            boss_team = {"battle_cards": [None, boss_card_id], "assist_cards": []}

            # 调用现有战斗系统
            result = self.start_battle(
                player_team, boss_team,
                challenger="player",
                initial_player_sp=initial_sp
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
        """创建战斗结果"""
        def _unit_dict(u):
            return {
                "name": u.character.name,
                "card_id": u.character.card_id,
                "hp": u.current_hp,
                "max_hp": u.max_hp,
                "alive": u.alive,
                "is_assist": u.is_assist,
                "position": u.position,
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

    # 玩家队伍状态
    lines.append("")
    lines.append("-" * 40)
    lines.append("  玩家队伍:")
    player_units = [u for u in result.get("player_units", []) if not u.get("is_assist")]
    for u in player_units:
        status = "O" if u.get("alive") else "X"
        name = u.get("name", "???")
        hp = u.get("hp", 0)
        max_hp = u.get("max_hp", 0)
        lines.append(f"   [{status}] {name}: {fmt_hp(hp)}/{fmt_hp(max_hp)}")

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
    "颜色威力": "SPECIAL_ENHANCED", "盾": "DAMAGE_COVER",
    "贯通": "PIERCING", "不屈": "GUTS", "强耐": "STATE_RESIST",
    "弱耐": "STATE_RESIST", "必暴": "SPECIAL_ENHANCED",
    "感电": "SHOCK", "气绝": "FAINT", "制御不能": "UNCONTROL",
    "持续被害": "BLEED", "a卡封印": "SEAL", "技能封印": "SILENCE",
    "必杀封印": "SILENCE", "强化妨害": "VOID_BUFF_CONDITION_BAD",
    "攻击提升妨害": "VOID_BUFF_CONDITION_BAD", "HP回复妨害": "VOID_HP_HEAL",
    "弱体化解除妨害": "VOID_BUFF_CONDITION_GOOD", "移动不能": "WORLD_MOVE",
    "攻击方向+": "ATTACK_DIR_3WAY", "攻击方向-": "ATTACK_DIR_DOWN",
    "天罚": "DIVINE_RETRIBUTION_SPELL", "反射": "MIRROR_ATTACK",
    "矢量操作": "VECTOR_CONVERSION", "强制咏唱待机": "SPELL_INTERCEPT",
}
DEBUFF_ICON_SUFFIX = "_DOWN"
BUFF_ICON_SUFFIX = "_UP"


def _get_state_icon(buff_name: str, is_debuff: bool = False) -> str:
    """根据buff名获取state_icon路径，找不到返回None"""
    base = BUFF_ICON_MAP.get(buff_name)
    if not base:
        return None
    suffix = DEBUFF_ICON_SUFFIX if is_debuff else BUFF_ICON_SUFFIX
    path = STATE_ICON_DIR / f"state_icon_{base}{suffix}.png"
    if path.exists():
        return str(path)
    # fallback: try without suffix (for status effects like SHOCK, SEAL)
    path = STATE_ICON_DIR / f"state_icon_{base}.png"
    return str(path) if path.exists() else None


def _get_character_icon(card_id: str, name: str = "", characters: list = None) -> str:
    """获取角色立绘路径（兼容旧数据无card_id时用角色名查characters列表）"""
    if not card_id and name and characters:
        # 从 【卡名】角色名[箭头] 提取角色名
        clean = re.sub(r'^【[^】]*】', '', name)
        clean = re.sub(r'\[[↙←↓→↘↖↑↗]\]$', '', clean).strip()
        for c in characters:
            cname = c.get('name', '')
            if '|' in cname:
                cname = cname.split('|')[0].strip()
            if clean and clean in cname:
                card_id = str(c.get('card_id', ''))
                break
    if card_id:
        for p in [f"card_cutin_{card_id}.png", f"card_icon_{card_id}.png"]:
            path = ICONIMAGE_DIR / p
            if path.exists(): return str(path)
        matches = list(ICONIMAGE_DIR.glob(f"*{card_id}*"))
        if matches: return str(matches[0])
    return None


def _get_font(size: int = 10):
    for fn in ["C:\\Windows\\Fonts\\simhei.ttf", "C:\\Windows\\Fonts\\msyh.ttc",
               "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "arial.ttf"]:
        if os.path.exists(fn):
            try: return ImageFont.truetype(fn, size)
            except: pass
    return ImageFont.load_default()


# 卡牌框架缓存
_CACHED_INNER_FRAME = None
_CACHED_OUTER_FRAME = None

def _get_card_frames():
    """加载卡牌框架（缓存）"""
    global _CACHED_INNER_FRAME, _CACHED_OUTER_FRAME
    if _CACHED_INNER_FRAME is None:
        inner_path = BASE_DIR / "level" / "gacha_tmb_02_01.png"
        outer_path = BASE_DIR / "level" / "gacha_tmb_frame.png"
        if inner_path.exists():
            _CACHED_INNER_FRAME = Image.open(str(inner_path)).convert('RGBA')
        if outer_path.exists():
            _CACHED_OUTER_FRAME = Image.open(str(outer_path)).convert('RGBA')
    return _CACHED_INNER_FRAME, _CACHED_OUTER_FRAME


def _render_empty_card(card_w: int, card_h: int) -> Image.Image:
    """渲染空位卡（1星背景+框，无立绘）"""
    _, outer_frame = _get_card_frames()
    card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    # 1星背景
    bg_path = BASE_DIR / "level" / "gacha_tmb_00_00.png"
    if bg_path.exists():
        try:
            bg = Image.open(str(bg_path)).convert('RGBA').resize((card_w, card_h), Image.Resampling.LANCZOS)
            card.paste(bg, (0, 0))
        except: pass
    # 外框
    if outer_frame:
        scaled = outer_frame.resize((card_w, card_h), Image.Resampling.LANCZOS)
        card.paste(scaled, (0, 0), scaled)
    # 半透明暗色覆盖
    ov = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 100))
    card.paste(ov, (0, 0), ov)
    return card


def _render_card(icon_path: str, card_w: int, card_h: int, alive: bool = True, death_tag: str = "") -> Image.Image:
    """渲染带框角色卡，死亡时叠加阵亡标签"""
    inner_frame, outer_frame = _get_card_frames()
    card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    inner_margin = 4
    inner_w = card_w - inner_margin * 2
    inner_h = card_h - inner_margin * 2

    # 角色立绘
    if icon_path:
        try:
            char_img = Image.open(icon_path).convert('RGBA')
            cw, ch = char_img.size
            sz = min(cw, ch)
            left = (cw - sz) // 2; top = (ch - sz) // 2
            char_cropped = char_img.crop((left, top, left + sz, top + sz))
            char_resized = char_cropped.resize((inner_w, inner_h), Image.Resampling.LANCZOS)
            card.paste(char_resized, (inner_margin, inner_margin), char_resized)
        except: pass

    # 星级框
    if inner_frame:
        scaled_inner = inner_frame.resize((card_w, card_h), Image.Resampling.LANCZOS)
        card.paste(scaled_inner, (0, 0), scaled_inner)

    # 外框
    if outer_frame:
        scaled_outer = outer_frame.resize((card_w, card_h), Image.Resampling.LANCZOS)
        card.paste(scaled_outer, (0, 0), scaled_outer)

    # 阵亡标签（保留立绘可见，仅底部标注+红色调）
    if not alive:
        # 红色半透明叠加
        ov = Image.new('RGBA', (card_w, card_h), (200, 30, 30, 80))
        card.paste(ov, (0, 0), ov)
        draw = ImageDraw.Draw(card)
        font_death = _get_font(10)
        dtext = f"阵亡 {death_tag}" if death_tag else "阵亡"
        try: tw = draw.textlength(dtext, font=font_death)
        except: tw = len(dtext) * 8
        dx = (card_w - tw) // 2
        dy = card_h - 16
        draw.rectangle([dx - 3, dy - 1, dx + tw + 3, dy + 13], fill=(0, 0, 0, 200))
        draw.text((dx, dy), dtext, fill=(255, 60, 60), font=font_death)

    return card


def _render_battle_frame(units: list, hp_deltas: dict, card_w: int = 90, card_h: int = 120, characters: list = None) -> Image.Image:
    """渲染单侧队伍（带框立绘+血条含HP文字+状态图标+血量变化紧贴血条下方）"""
    n = len(units)
    icon_size = 20  # 增大图标尺寸
    gap = 12  # 增大间距
    total_w = n * card_w + (n - 1) * gap
    hp_h = 16  # 增大血条高度
    delta_h = 32  # 增大变化量区域高度
    # 图标区：每个角色独立一行图标
    icon_rows = 2
    icon_area_h = icon_size * icon_rows + 6
    total_h = icon_area_h + card_h + hp_h + 4 + delta_h + 8

    frame = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)
    font_hp = _get_font(12)  # 增大字体
    font_hp_text = _get_font(11)  # 增大字体
    font_delta = _get_font(14)  # HP变化量专用字体（更大）

    for i, u in enumerate(units):
        x = i * (card_w + gap)

        # 状态图标 — 每个角色独立排列，最多2行
        icons = []
        for b in u.get("buffs", [])[:6]:
            p = _get_state_icon(b.get("name", ""), False)
            if p: icons.append((p, False))  # (路径, 是否debuff)
        for d in u.get("debuffs", [])[:6]:
            p = _get_state_icon(d.get("name", ""), True)
            if p: icons.append((p, True))
        
        # 每个角色的图标在自己的区域内排列
        max_icons_per_row = 5
        for j, (ip, is_debuff) in enumerate(icons[:10]):
            try:
                si = Image.open(ip).convert('RGBA').resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                # 计算图标位置：在角色卡上方，按行列排列
                icon_x = x + (j % max_icons_per_row) * (icon_size + 2)
                icon_y = (j // max_icons_per_row) * (icon_size + 2) + 2
                frame.paste(si, (icon_x, icon_y), si)
            except: pass

        # 带框角色卡（空位用1星底图，死亡时标注击杀来源）
        card_y = icon_area_h
        is_empty = u.get("is_empty", False)
        if is_empty:
            # 空位：1星背景 + 外框，无立绘
            card = _render_empty_card(card_w, card_h)
        else:
            icon_path = _get_character_icon(str(u.get("card_id", "")), str(u.get("name", "")), characters)
            alive_raw = u.get("alive", True)
            alive = alive_raw if isinstance(alive_raw, bool) else str(alive_raw).lower() != 'false'
            death_tag = ""
            if not alive and hp_deltas.get(i):
                for amount, tag in hp_deltas[i]:
                    if amount < 0: death_tag = tag; break
            card = _render_card(icon_path, card_w, card_h, alive, death_tag)
        frame.paste(card, (x, card_y), card)

        # 空位不渲染HP条和变化量
        if is_empty:
            continue

        # HP条（加高，内含白色HP文字，兼容字符串格式）
        hy = card_y + card_h + 3
        mx = max(int(u.get("max_hp", 1) or 1), 1)
        cur = max(0, int(u.get("hp", 0) or 0))
        pct = cur / mx
        # 血条背景（深灰色）
        draw.rectangle([x, hy, x + card_w, hy + hp_h], fill=(30, 30, 30))
        # 血条填充
        c = (50, 200, 50) if pct > 0.5 else (200, 180, 50) if pct > 0.25 else (200, 50, 50)
        if pct > 0:
            draw.rectangle([x + 1, hy + 1, x + int((card_w - 2) * pct), hy + hp_h - 1], fill=c)
        # HP文字（居中显示）
        hp_text = f"{cur}/{mx}"
        try: tw = draw.textlength(hp_text, font=font_hp_text)
        except: tw = len(hp_text) * 8
        tx = x + (card_w - tw) // 2
        draw.text((tx, hy + 2), hp_text, fill=(255, 255, 255), font=font_hp_text)

        # HP变化量 — 更显眼的显示（大字体、带背景）
        dy = hy + hp_h + 3
        for amount, tag in hp_deltas.get(i, [])[:2]:
            # 根据伤害/回复量选择颜色和显示方式
            if amount < 0:
                # 伤害：红色背景、白色文字
                color = (255, 80, 80)
                bg_color = (40, 0, 0)
                txt = f"-{abs(amount)}"
            else:
                # 回复：绿色背景、白色文字
                color = (80, 255, 80)
                bg_color = (0, 40, 0)
                txt = f"+{amount}"
            
            # 添加攻击类型标签
            if tag:
                txt = f"{tag} {txt}"
            
            # 计算文字宽度
            try: tw = draw.textlength(txt, font=font_delta)
            except: tw = len(txt) * 10
            
            # 绘制背景框
            draw.rectangle([x, dy, x + tw + 6, dy + 18], fill=bg_color)
            # 绘制文字
            draw.text((x + 3, dy + 1), txt, fill=color, font=font_delta)
            dy += 20

    return frame


def _parse_battle_state(segments, p_units, e_units):
    """回放战斗日志，计算每段的单位状态（HP变化+状态图标+存活）
    返回: [(p_field, e_field, p_deltas, e_deltas, round_label, turn_label), ...]
    """
    import re as _re, copy
    def _init_field(units):
        result = []
        for u in units:
            if u.get("is_assist") or u.get("is_assist") == 'True':
                continue
            # 兼容旧数据：hp/alive可能是字符串或数字
            raw_hp = u.get("max_hp", u.get("hp", 10000))
            max_hp = int(raw_hp) if raw_hp is not None else 10000
            pos_raw = u.get("position", 0)
            position = int(pos_raw) if pos_raw is not None else 0
            cid = u.get("card_id", "")
            result.append({
                "name": u.get("name", "?"), "card_id": cid,
                "max_hp": max_hp, "hp": max_hp,
                "alive": True, "buffs": [], "debuffs": [],
                "position": position,
            })
        return result

    p_field = _init_field(p_units)
    e_field = _init_field(e_units)
    p_names = {u["name"]: i for i, u in enumerate(p_field)}
    e_names = {u["name"]: i for i, u in enumerate(e_field)}

    frames_data = []

    for seg_idx, (rlabel, tlabel, phase, seg_lines) in enumerate(segments):
        p_deltas_cur, e_deltas_cur = {}, {}

        for line in seg_lines:
            line = str(line)

            # === 换位 ===
            m = _re.match(r'\s*\[换位\]\s*\[([PE])\]\s*(.+?)\s*->\s*(.)', line)
            if m:
                tag, name, arrow = m.group(1), m.group(2).strip(), m.group(3)
                field = p_field if tag == 'P' else e_field
                arrow_map = {'↙':0,'←':1,'↓':2,'→':3,'↘':4,'↖':0,'↑':2,'↗':4}
                new_col = arrow_map.get(arrow, None)
                if new_col is not None:
                    for u in field:
                        if u["name"] == name:
                            u["position"] = new_col
                            break
                continue

            # === 替补上场（继承阵亡单位位置）===
            m = _re.match(r'\s*\[上场\]\s*\[([PE])\]\s*(.+?)\[(.+?)\]', line)
            if m:
                tag, name, arrow = m.group(1), m.group(2).strip(), m.group(3).strip()
                field = p_field if tag == 'P' else e_field
                names = p_names if tag == 'P' else e_names
                # 从箭头确定位置
                arrow_map = {'↙':0,'←':1,'↓':2,'→':3,'↘':4,'↖':0,'↑':2,'↗':4}
                new_pos = arrow_map.get(arrow, 0)
                # 找第一个阵亡槽位（按位置顺序），替补继承该位置
                dead_sorted = sorted([u for u in field if not u["alive"]], key=lambda u: field.index(u))
                if dead_sorted:
                    dead = dead_sorted[0]
                    old_name = dead["name"]
                    dead["name"] = f"{name}[{arrow}]"; dead["alive"] = True; dead["hp"] = dead["max_hp"]
                    dead["buffs"] = []; dead["debuffs"] = []
                    dead["position"] = new_pos  # 使用箭头确定的位置
                    if old_name in names: del names[old_name]
                    names[f"{name}[{arrow}]"] = field.index(dead)
                continue

            # === 伤害（提取方向+攻击类型）===
            m = _re.match(r'\([\d.]+\).+?\[(.[→←]?)\]\s*->\s*(.+?)\s*\((\d+)伤害.*\[(.+?)\]', line)
            if m:
                src_arrow, df_name, dmg, atk_type = m.group(1), m.group(2).strip(), int(m.group(3)), m.group(4)
                # 攻击类型缩写: 普通攻击→普, 技能→技, 必杀→终
                atk_short = "终" if "必杀" in atk_type else "技" if "技能" in atk_type else "普"
                tag = f"[{src_arrow}]【{atk_short}】"
                for field, names in [(p_field, p_names), (e_field, e_names)]:
                    if df_name in names:
                        idx = names[df_name]
                        field[idx]["hp"] = max(0, field[idx]["hp"] - dmg)
                        if field[idx]["hp"] <= 0:
                            field[idx]["hp"] = 0; field[idx]["alive"] = False
                            field[idx]["buffs"] = []; field[idx]["debuffs"] = []
                        (p_deltas_cur if field is p_field else e_deltas_cur).setdefault(idx, []).append((-dmg, tag))
                        break
                continue

            # === HP回复（提取来源A卡方向）===
            m = _re.match(r'(.+?)\s+HP回复\+(\d+)', line)
            if m:
                un, heal = m.group(1).strip(), int(m.group(2))
                # 从名字中的箭头判断来源
                tag = ""
                for arr in ['↙','←','↓','→','↘','↖','↑','↗']:
                    if arr in un: tag = f"[{arr}A]"; break
                if not tag: tag = "[A]" if "[A]" in line else "[自]"
                for field, names, deltas in [(p_field, p_names, p_deltas_cur), (e_field, e_names, e_deltas_cur)]:
                    if un in names:
                        idx = names[un]
                        field[idx]["hp"] = min(field[idx]["max_hp"], field[idx]["hp"] + heal)
                        deltas.setdefault(idx, []).append((heal, tag))
                        break

            # === 不屈触发（HP回复到30%）===
            m = _re.match(r'.+?\((\d+)伤害，不屈！HP=(\d+)\)', line)
            if m:
                for field, names in [(p_field, p_names), (e_field, e_names)]:
                    # Find which unit just got hit - it's the one with HP=0 before this
                    for u in field:
                        if u["hp"] <= 0:
                            u["hp"] = int(m.group(2)); u["alive"] = True
                            break

            # === Buff/Debuff 应用（逗号分隔多效果行）===
            if '[A]' in line and 'HP回复' not in line and '伤害' not in line and '击破' not in line and '不屈' not in line:
                stripped = line.rsplit('[A]', 1)[0].strip()
                parts = [p.strip() for p in stripped.split(',')]
                # 找第一个完整目标名
                first_target = None
                for field, names in [(p_field, p_names), (e_field, e_names)]:
                    for nm in names:
                        if nm in parts[0]:
                            first_target = (field, names, names[nm]); break
                    if first_target: break
                if not first_target: continue
                tf, tn, ti = first_target
                ALL_BUFF_NAMES = ["必杀威力提升","技能威力提升","物攻提升","异攻提升",
                    "物防提升","异防提升","暴伤提升","暴击率提升","回避率提升",
                    "暴击防御提升","SP获得量提升","减伤","盾","贯通","不屈",
                    "必暴","强耐","弱耐","物攻下降","异攻下降","物防下降",
                    "异防下降","暴击率下降","回避率下降","颜色耐性下降",
                    "SP获得量下降","感电","气绝","移动不能","制御不能",
                    "a卡封印","技能封印","必杀封印","强化妨害","持续被害",
                    "HP回复妨害","弱体化解除妨害"]
                for part in parts:
                    for bname in ALL_BUFF_NAMES:
                        if bname in part:
                            mag = "中"
                            for mt in ["特大","大","中","小"]:
                                if mt in part: mag = mt; break
                            is_debuff = any(kw in bname for kw in ["下降","封印","妨害","感电","气绝","移动不能","制御不能","持续被害"])
                            key = "debuffs" if is_debuff else "buffs"
                            existing = [e["name"] for e in tf[ti][key]]
                            if bname not in existing:
                                tf[ti][key].append({"name": bname, "magnitude": mag})
                            break

            # === 持续被害 (DoT) ===
            m = _re.match(r'\s*\[持续被害\]\s*(.+?)\s*-(\d+)HP', line)
            if m:
                un, dot = m.group(1).strip(), int(m.group(2))
                for field, names in [(p_field, p_names), (e_field, e_names)]:
                    if un in names:
                        idx = names[un]
                        field[idx]["hp"] = max(0, field[idx]["hp"] - dot)
                        if field[idx]["hp"] <= 0:
                            field[idx]["hp"] = 0; field[idx]["alive"] = False
                            field[idx]["buffs"] = []; field[idx]["debuffs"] = []
                        break

        # Snapshot current state for this frame
        p_snap = copy.deepcopy(p_field)
        e_snap = copy.deepcopy(e_field)
        frames_data.append((p_snap, e_snap, p_deltas_cur, e_deltas_cur, rlabel, tlabel, phase))

    return frames_data


def battle_to_gif(result: dict, player_team: dict = None, enemy_team: dict = None,
                  characters: list = None, output_path: str = None,
                  frame_duration: int = 1000, card_w: int = 90, card_h: int = 120) -> str:
    """将战斗结果渲染为GIF动画（使用新渲染器）"""
    if not HAS_PIL:
        return None
    
    # 使用新的GIF渲染器
    try:
        from gif_renderer import battle_to_gif_new
        return battle_to_gif_new(result, characters, output_path, frame_duration)
    except ImportError as e:
        log_error(f"Failed to import gif_renderer: {e}")
        return None

# 保留旧的辅助函数供其他地方使用
def _render_card(icon_path: str, card_w: int, card_h: int, alive: bool = True, death_tag: str = "") -> Image.Image:
    """渲染带框角色卡，死亡时叠加阵亡标签"""
    inner_frame, outer_frame = _get_card_frames()
    card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    inner_margin = 4
    inner_w = card_w - inner_margin * 2
    inner_h = card_h - inner_margin * 2

    # 角色立绘
    if icon_path:
        try:
            char_img = Image.open(icon_path).convert('RGBA')
            cw, ch = char_img.size
            sz = min(cw, ch)
            left = (cw - sz) // 2; top = (ch - sz) // 2
            char_cropped = char_img.crop((left, top, left + sz, top + sz))
            char_resized = char_cropped.resize((inner_w, inner_h), Image.Resampling.LANCZOS)
            card.paste(char_resized, (inner_margin, inner_margin), char_resized)
        except: pass

    # 星级框
    if inner_frame:
        scaled_inner = inner_frame.resize((card_w, card_h), Image.Resampling.LANCZOS)
        card.paste(scaled_inner, (0, 0), scaled_inner)

    # 外框
    if outer_frame:
        scaled_outer = outer_frame.resize((card_w, card_h), Image.Resampling.LANCZOS)
        card.paste(scaled_outer, (0, 0), scaled_outer)

    # 阵亡标签（保留立绘可见，仅底部标注+红色调）
    if not alive:
        # 红色半透明叠加
        ov = Image.new('RGBA', (card_w, card_h), (200, 30, 30, 80))
        card.paste(ov, (0, 0), ov)
        draw = ImageDraw.Draw(card)
        font_death = _get_font(10)
        dtext = f"阵亡 {death_tag}" if death_tag else "阵亡"
        try: tw = draw.textlength(dtext, font=font_death)
        except: tw = len(dtext) * 8
        dx = (card_w - tw) // 2
        dy = card_h - 16
        draw.rectangle([dx - 3, dy - 1, dx + tw + 3, dy + 13], fill=(0, 0, 0, 200))
        draw.text((dx, dy), dtext, fill=(255, 60, 60), font=font_death)

    return card