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
BATTLE_POSITIONS_ON_FIELD = 3  # 场上战斗位数量
MAX_BATTLE_ROUNDS = 30  # 最大战斗回合数

# SP配置
SP_PER_ATTACK = 15  # 攻击获得SP
SP_PER_DAMAGED = 10  # 被攻击获得SP
SP_MAX = 100  # SP上限

# 同色增益
SAME_COLOR_BONUS = 1.05  # B卡A卡同色时增益5%


# ========== buff/debuff关键词列表 ==========
ALL_TIME_LIST = [
    '行动开始时', '敌方行动开始时',
    '(我方一对角色|自身以外的我方|自身)(必杀|技能|对敌方暴击|对敌方造成伤害)时'
]

ALL_AREA_LIST = [
    '范围内', '三方向', '正面', '左侧', '右侧', '[前左右]+',
    '同色与有利色敌全体', '(同色|有利色)敌全体', '..侧敌全体',
    '(.色与)?.色敌全体', '敌全体', '该敌方角色',
    '同色我方', '该我方角色', '(.色与)?.色我方全体',
    '自身以外的我方全体', '我方全体', '其他我方', '自身与两邻', '自身', '两邻'
]

ALL_BUFF_LIST = [
    '盾', '矢量操作', '强制咏唱待机', '全能神', '嘲讽', '强耐', '弱耐', '不屈',
    '预测不能', '天罚', r'攻击方向\+.',
    '必暴', r'物攻提升\(.+?\)', r'异攻提升\(.+?\)', r'物防提升\(.+?\)',
    r'异防提升\(.+?\)', r'暴击防御提升\(.+?\)',
    r'暴击率提升\(.+?\)', r'回避率提升\(.+?\)', r'暴伤提升\(.+?\)',
    r'必杀威力提升\(.+?\)', r'技能威力提升\(.+?\)',
    r'SP获得量提升\(.+?\)', r'[^【]*减伤\(.+?\)', r'对.色威力提升\(.+?\)'
]

ALL_DEBUFF_LIST = [
    '强化妨害', '攻击提升妨害', 'HP回复妨害', '弱体化解除妨害',
    r'持续被害\(.+?\)', '感电', '气绝', '移动不能', '制御不能', 'a卡封印',
    r'攻击方向\-.', '技能封印', '必杀封印',
    r'物攻下降\(.+?\)', r'异攻下降\(.+?\)', r'物防下降\(.+?\)',
    r'异防下降\(.+?\)', r'必杀威力下降\(.+?\)',
    r'暴击率下降\(.+?\)', r'回避率下降\(.+?\)', r'暴击防御下降\(.+?\)',
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
            "必杀威力": params.ULTIMATE_POWER_BUFF
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
            "必杀威力": params.ULTIMATE_POWER_BUFF
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
    current_count: int = 0  # 当前触发计数
    current_cd: int = 0  # 当前冷却（初始为0）
    cd: int = 0  # 冷却回合
    
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
    skill_cooldown: int = 0  # 技能冷却（SP是阵营共用的）
    
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
            "必杀威力": params.ULTIMATE_POWER_BUFF_LIMIT
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
    
    def _parse_assist_text(self, text: str) -> Optional[AssistEffect]:
        """解析支援卡技能文本"""
        if not text:
            return None
        
        effect = AssistEffect()
        
        # 解析触发次数
        count_match = re.search(r'\((\d+)次\)', text)
        if count_match:
            effect.trigger_count = int(count_match.group(1))
        
        # 解析触发时机
        time_patterns = ['行动开始时', '敌方行动开始时', '必杀时', '技能时', '对敌方暴击时', '对敌方造成伤害时']
        for time in time_patterns:
            if time in text:
                effect.trigger_time = time
                break
        
        # 解析作用范围
        area_patterns = ['我方全体', '自身以外的我方全体', '自身', '同色我方', '敌全体', '同色敌全体']
        for area in area_patterns:
            if area in text:
                effect.area = area
                break
        
        # 解析效果
        effects = []
        for pattern in ALL_BUFF_LIST + ALL_DEBUFF_LIST + ALL_SP_LIST:
            matches = re.findall(pattern, text)
            effects.extend(matches)
        effect.effects = effects
        
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
                    assist_effect1 = self._parse_assist_text(skill_text1)
                    assist_effect2 = self._parse_assist_text(skill_text2)
                
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
                    speed=char_data.get("speed", 100),
                    attribute=attribute,
                    attack_type=char_data.get("attack_type", "物理"),
                    attack_directions=char_data.get("attack_directions", 1),
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
    
    def get_character(self, card_id: str) -> Optional[Character]:
        """获取角色"""
        return self.characters.get(str(card_id))
    
    def create_battle_unit(self, card_id: str, position: int, is_assist: bool = False) -> Optional[BattleUnit]:
        """创建战斗单位"""
        character = self.get_character(card_id)
        if not character:
            log_error(f"找不到角色: {card_id}")
            return None
        
        # 复制角色数据
        character_copy = copy.deepcopy(character)
        
        return BattleUnit(
            character=character_copy,
            position=position,
            is_assist=is_assist
        )
    
    def build_battle_team(self, team_data: dict) -> List[BattleUnit]:
        """构建战斗队伍"""
        units = []
        
        battle_cards = team_data.get("battle_cards", [])
        assist_cards = team_data.get("assist_cards", [])
        
        if not isinstance(battle_cards, list):
            battle_cards = []
        if not isinstance(assist_cards, list):
            assist_cards = []
        
        # 创建战斗单位
        for i in range(TOTAL_BATTLE_POSITIONS):
            card_id = battle_cards[i] if i < len(battle_cards) else None
            if card_id:
                unit = self.create_battle_unit(card_id, i, False)
                if unit:
                    units.append(unit)
        
        # 创建支援单位
        for i in range(TOTAL_ASSIST_POSITIONS):
            card_id = assist_cards[i] if i < len(assist_cards) else None
            if card_id:
                unit = self.create_battle_unit(card_id, i, True)
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
                         power_up_count: int = 0) -> Tuple[int, bool, str]:
        """
        计算伤害（基于calc_dmg.py的核心公式）
        
        :return: (伤害值, 是否暴击, 伤害类型描述)
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
            
            attack += extra_attack
            attack = int(attack * base_mult)
        
        # 4. 计算防御
        defense = self._calculate_defense(defender)
        
        # 5. 核心伤害公式：伤害 = 攻击^2 / (攻击 + 防御)
        damage = int(attack ** 2 / (attack + defense))
        
        # 6. 属性克制
        attr_mult = self._get_attribute_multiplier(attacker.character.attribute, defender.character.attribute)
        damage = int(damage * attr_mult)
        
        # 7. 暴击（5%概率）
        is_crit = random.random() < 0.05
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
        
        return max(1, damage), is_crit, damage_type
    
    def get_on_field_units(self, units: List[BattleUnit]) -> List[BattleUnit]:
        """获取场上战斗单位"""
        alive_battle_units = [u for u in units if not u.is_assist and u.alive]
        alive_battle_units.sort(key=lambda x: x.position)
        return alive_battle_units[:BATTLE_POSITIONS_ON_FIELD]
    
    def get_targets_in_direction(self, attacker: BattleUnit, enemies: List[BattleUnit], area: str = "正面") -> List[BattleUnit]:
        """根据攻击方向和技能范围获取目标"""
        if not enemies:
            return []
        
        attacker_pos = attacker.position % 3
        directions = attacker.character.attack_directions
        
        # 根据技能范围确定目标
        if "敌全体" in area or "三方向" in area:
            return enemies[:]
        
        if "范围内" in area:
            # 范围内攻击：攻击方向数决定目标数
            target_count = min(directions, len(enemies))
            return enemies[:target_count]
        
        # 根据攻击方向确定可攻击位置
        if directions == 1:
            targetable_positions = [attacker_pos]
        elif directions == 2:
            if attacker_pos == 0:
                targetable_positions = [0, 1]
            elif attacker_pos == 2:
                targetable_positions = [1, 2]
            else:
                targetable_positions = [0, 1]
        else:
            targetable_positions = [0, 1, 2]
        
        targets = []
        for enemy in enemies:
            enemy_pos = enemy.position % 3
            if enemy_pos in targetable_positions:
                targets.append(enemy)
        
        return targets if targets else enemies
    
    def add_sp(self, side_sp: int, sp_amount: int) -> int:
        """增加阵营SP，返回新的SP值"""
        new_sp = min(SP_MAX, side_sp + sp_amount)
        return new_sp
    
    def use_sp(self, side_sp: int, sp_amount: int) -> Tuple[bool, int]:
        """消耗阵营SP，返回(是否成功, 剩余SP)"""
        if side_sp >= sp_amount:
            return True, side_sp - sp_amount
        return False, side_sp
    
    def execute_normal_attack(self, attacker: BattleUnit, enemies: List[BattleUnit]) -> Tuple[List[str], int]:
        """执行普通攻击，返回(战斗日志, 获得的SP)"""
        results = []
        targets = self.get_targets_in_direction(attacker, enemies)
        
        if not targets:
            return results, 0
        
        damage_results = []
        sp_gained = 0
        for target in targets:
            damage, is_crit, damage_type = self.calculate_damage(attacker, target, "normal")
            
            target.current_hp -= damage
            sp_gained += SP_PER_DAMAGED  # 目标被攻击获得SP
            
            if target.current_hp <= 0:
                target.current_hp = 0
                target.alive = False
                if target.assist_unit:
                    target.assist_unit.alive = False
                damage_results.append((target, damage, True))
            else:
                damage_results.append((target, damage, False))
        
        sp_gained += SP_PER_ATTACK  # 攻击者获得SP
        
        if damage_results:
            target_names = "、".join([
                f"{d[0].character.name}（{d[1]}点伤害{'，阵亡' if d[2] else ''}）"
                for d in damage_results
            ])
            results.append(f"{attacker.character.name} 使用普通攻击对 {target_names}")
        
        return results, sp_gained
    
    def execute_skill_attack(self, attacker: BattleUnit, enemies: List[BattleUnit], 
                            can_use_skill: bool = True, skill_sp: int = 30,
                            allies: List[BattleUnit] = None) -> Tuple[List[str], int, int]:
        """执行技能攻击，返回(战斗日志, 消耗的SP, 获得的SP)"""
        results = []
        
        if not attacker.character.skill:
            return self.execute_normal_attack(attacker, enemies)
        
        if not can_use_skill or skill_sp < 30:
            return self.execute_normal_attack(attacker, enemies)
        
        if attacker.skill_cooldown > 0:
            return self.execute_normal_attack(attacker, enemies)
        
        targets = self.get_targets_in_direction(attacker, enemies, attacker.character.skill.area)
        
        if not targets:
            return results, 0, 0
        
        damage_results = []
        sp_gained = 0
        for target in targets:
            damage, is_crit, damage_type = self.calculate_damage(
                attacker, target, "skill", attacker.character.skill.power_rank
            )
            
            target.current_hp -= damage
            sp_gained += SP_PER_DAMAGED
            
            if target.current_hp <= 0:
                target.current_hp = 0
                target.alive = False
                if target.assist_unit:
                    target.assist_unit.alive = False
                damage_results.append((target, damage, True))
            else:
                damage_results.append((target, damage, False))
        
        sp_gained += SP_PER_ATTACK
        
        attacker.skill_cooldown = attacker.character.skill.cooldown
        
        if damage_results:
            target_names = "、".join([
                f"{d[0].character.name}（{d[1]}点伤害{'，阵亡' if d[2] else ''}）"
                for d in damage_results
            ])
            results.append(f"{attacker.character.name} 使用技能对 {target_names}")
        
        # 应用技能增益效果
        if allies:
            buff_results = self._apply_skill_effect(attacker, attacker.character.skill, allies, enemies)
            results.extend(buff_results)
        
        return results, 30, sp_gained
    
    def execute_ultimate_attack(self, attacker: BattleUnit, enemies: List[BattleUnit],
                               can_use_ultimate: bool = True,
                               allies: List[BattleUnit] = None) -> Tuple[List[str], int, int]:
        """执行必杀技，返回(战斗日志, 消耗的SP, 获得的SP)"""
        results = []
        
        if not attacker.character.ultimate:
            return self.execute_skill_attack(attacker, enemies, can_use_ultimate, SP_MAX, allies)
        
        if not can_use_ultimate:
            return self.execute_skill_attack(attacker, enemies, True, 30, allies)
        
        ultimate = attacker.character.ultimate
        targets = self.get_targets_in_direction(attacker, enemies, ultimate.area)
        
        if not targets:
            return results, 0, 0
        
        # 计算威力上升数量（强化数/弱体数）
        power_up_count = 0
        if ultimate.power_up_type == "强化数":
            power_up_count = len(attacker.buffs)
        elif ultimate.power_up_type == "弱体数":
            power_up_count = len(attacker.debuffs)
        
        damage_results = []
        sp_gained = 0
        for target in targets:
            damage, is_crit, damage_type = self.calculate_damage(
                attacker, target, "ultimate", ultimate.power_rank, power_up_count
            )
            
            target.current_hp -= damage
            sp_gained += SP_PER_DAMAGED
            
            if target.current_hp <= 0:
                target.current_hp = 0
                target.alive = False
                if target.assist_unit:
                    target.assist_unit.alive = False
                damage_results.append((target, damage, True))
            else:
                damage_results.append((target, damage, False))
        
        if damage_results:
            target_names = "、".join([
                f"{d[0].character.name}（{d[1]}点伤害{'，阵亡' if d[2] else ''}）"
                for d in damage_results
            ])
            results.append(f"{attacker.character.name} 使用终结技对 {target_names}")
        
        # 应用技能增益效果
        if allies:
            buff_results = self._apply_skill_effect(attacker, ultimate, allies, enemies)
            results.extend(buff_results)
        
        return results, 100, sp_gained
    
    def trigger_assist_effects(self, unit: BattleUnit, allies: List[BattleUnit], 
                               enemies: List[BattleUnit], trigger_type: str = "行动开始时") -> int:
        """触发支援卡效果，返回SP变化量"""
        total_sp_gained = 0
        
        if not unit.assist_unit:
            return 0
        
        assist_char = unit.assist_unit.character
        
        # 检查效果1
        if assist_char.assist_effect1 and assist_char.assist_effect1.is_ready():
            if assist_char.assist_effect1.trigger_time == trigger_type:
                total_sp_gained += self._apply_assist_effect(unit, assist_char.assist_effect1, allies, enemies)
                assist_char.assist_effect1.current_count += 1
        
        # 检查效果2
        if assist_char.assist_effect2 and assist_char.assist_effect2.is_ready():
            if assist_char.assist_effect2.trigger_time == trigger_type:
                total_sp_gained += self._apply_assist_effect(unit, assist_char.assist_effect2, allies, enemies)
                assist_char.assist_effect2.current_count += 1
        
        return total_sp_gained
    
    def _apply_assist_effect(self, source_unit: BattleUnit, effect: AssistEffect,
                            allies: List[BattleUnit], enemies: List[BattleUnit]) -> int:
        """应用支援卡效果，返回SP变化量"""
        sp_gained = 0
        
        # 确定目标
        targets = []
        
        if "自身" in effect.area:
            targets = [source_unit]
        elif "我方全体" in effect.area:
            targets = [u for u in allies if not u.is_assist and u.alive]
        elif "敌全体" in effect.area:
            targets = enemies[:]
        elif "同色" in effect.area:
            source_attr = self._get_base_attribute(source_unit.character.attribute)
            if "我方" in effect.area:
                targets = [u for u in allies if not u.is_assist and u.alive and 
                          self._get_base_attribute(u.character.attribute) == source_attr]
            else:
                targets = [e for e in enemies if self._get_base_attribute(e.character.attribute) == source_attr]
        else:
            targets = [source_unit]
        
        # 应用效果
        for effect_text in effect.effects:
            # 攻击buff
            m = re.match(r'物攻提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                for target in targets:
                    if target in allies:
                        target.buffs.append(BuffEffect(name="攻击", magnitude=magnitude, source="a卡"))
            
            # 防御buff
            m = re.match(r'物防提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                for target in targets:
                    if target in allies:
                        target.buffs.append(BuffEffect(name="防御", magnitude=magnitude, source="a卡"))
            
            # 暴伤buff
            m = re.match(r'暴伤提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                for target in targets:
                    if target in allies:
                        target.buffs.append(BuffEffect(name="暴伤", magnitude=magnitude, source="a卡"))
            
            # 必杀威力buff
            m = re.match(r'必杀威力提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                for target in targets:
                    if target in allies:
                        target.buffs.append(BuffEffect(name="必杀威力", magnitude=magnitude, source="a卡"))
            
            # SP获得
            # 格式1: SP([0-9]+)上升 - 固定SP上升（如SP10上升）
            m = re.match(r'SP([0-9]+)上升', effect_text)
            if m:
                sp_amount = int(m.group(1))
                sp_gained += sp_amount
            
            # 格式2: 根据(..侧|.色)数量SP(大)?上升 - 根据某侧或某色数量SP上升
            m = re.match(r'根据(..侧|.色)数量SP(大)?上升', effect_text)
            if m:
                condition = m.group(1)  # 如"前侧"、"红"等
                is_large = m.group(2) == "大"
                sp_base = 10 if is_large else 5
                
                # 计算符合条件的己方角色数量
                count = 0
                for ally in allies:
                    if ally.is_assist or not ally.alive:
                        continue
                    ally_attr = self._get_base_attribute(ally.character.attribute)
                    # 检查是侧还是颜色
                    if condition.endswith("侧"):
                        # 前侧: 位置0, 后侧: 位置2
                        if condition == "前侧" and ally.position % 3 == 0:
                            count += 1
                        elif condition == "后侧" and ally.position % 3 == 2:
                            count += 1
                    else:
                        # 颜色
                        if ally_attr == condition:
                            count += 1
                
                # 给符合条件的己方角色增加SP
                sp_amount = sp_base * count
                sp_gained += sp_amount
            
            # 防御debuff
            m = re.match(r'物防下降\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                for target in targets:
                    if target in enemies:
                        target.debuffs.append(BuffEffect(name="防御", magnitude=magnitude, source="a卡"))
            
            # 颜色耐性debuff
            m = re.match(r'.色耐性下降\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                for target in targets:
                    if target in enemies:
                        target.debuffs.append(BuffEffect(name="颜色耐性", magnitude=magnitude, source="a卡"))
        
        return sp_gained
    
    def _apply_skill_effect(self, attacker: BattleUnit, skill: Skill, 
                           allies: List[BattleUnit], enemies: List[BattleUnit]) -> List[str]:
        """应用技能效果，返回增益日志"""
        results = []
        
        # 确定目标
        targets = []
        is_ally_target = False
        
        if "我方全体" in skill.area:
            targets = [u for u in allies if not u.is_assist and u.alive]
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
        for effect_text in skill.effects:
            # 攻击buff
            m = re.match(r'物攻提升\((.+?)\)', effect_text)
            if m:
                magnitude = m.group(1)
                if is_ally_target:
                    buff_targets = targets
                else:
                    buff_targets = [attacker]
                for target in buff_targets:
                    target.buffs.append(BuffEffect(name="攻击", magnitude=magnitude, source="技能"))
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
                    target.buffs.append(BuffEffect(name="防御", magnitude=magnitude, source="技能"))
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
                    target.buffs.append(BuffEffect(name="暴伤", magnitude=magnitude, source="技能"))
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
                    target.buffs.append(BuffEffect(name="必杀威力", magnitude=magnitude, source="技能"))
                target_names = "、".join([t.character.name for t in buff_targets])
                results.append(f"{attacker.character.name} 对 {target_names} {effect_text}")
        
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
        if side_sp >= SP_MAX and self._can_one_shot_kill(unit, enemies, "ultimate"):
            return "ultimate"
        
        # 2. 技能就绪且可以一击必杀 -> 技能
        if unit.skill_cooldown == 0 and side_sp >= 30 and self._can_one_shot_kill(unit, enemies, "skill"):
            return "skill"
        
        # 3. 正常优先级：大招 > 技能 > 普攻
        if side_sp >= SP_MAX:
            return "ultimate"
        if unit.skill_cooldown == 0 and side_sp >= 30:
            return "skill"
        return "normal"
    
    def start_battle(self, player_team: dict, enemy_team: dict) -> dict:
        """开始战斗"""
        log_battle("=" * 50)
        log_battle("战斗开始！")
        
        player_units = self.build_battle_team(player_team)
        enemy_units = self.build_battle_team(enemy_team)
        
        # 阵营SP池（共用SP）
        player_sp = 0
        enemy_sp = 0
        
        battle_log = []
        
        for round_num in range(1, MAX_BATTLE_ROUNDS + 1):
            round_log = [f"\n{'='*50}\n第 {round_num} 回合\n{'='*50}"]
            
            # 刷新场上单位
            player_on_field = self.get_on_field_units(player_units)
            enemy_on_field = self.get_on_field_units(enemy_units)
            
            # 检查胜负
            if len(player_on_field) == 0:
                round_log.append("玩家队伍全灭！")
                round_log.append("敌方胜利！")
                return self._create_result("enemy", round_num, battle_log + round_log, player_units, enemy_units)
            
            if len(enemy_on_field) == 0:
                round_log.append("玩家队伍胜利！")
                round_log.append("敌方全灭！")
                return self._create_result("player", round_num, battle_log + round_log, player_units, enemy_units)
            
            # ===== 回合开始前：触发双方A卡技能 =====
            # 先手方A卡触发（奇数回合：玩家先手）
            first_side = player_on_field if round_num % 2 == 1 else enemy_on_field
            second_side = enemy_on_field if round_num % 2 == 1 else player_on_field
            first_allies = player_units if round_num % 2 == 1 else enemy_units
            second_allies = enemy_units if round_num % 2 == 1 else player_units
            
            for unit in first_side:
                e = enemy_on_field if unit in player_on_field else player_on_field
                sp_gained = self.trigger_assist_effects(unit, first_allies, e, "行动开始时")
                if round_num % 2 == 1:
                    player_sp = self.add_sp(player_sp, sp_gained)
                else:
                    enemy_sp = self.add_sp(enemy_sp, sp_gained)
            
            for unit in second_side:
                e = player_on_field if unit in player_on_field else player_on_field
                sp_gained = self.trigger_assist_effects(unit, second_allies, e, "行动开始时")
                if round_num % 2 == 1:
                    enemy_sp = self.add_sp(enemy_sp, sp_gained)
                else:
                    player_sp = self.add_sp(player_sp, sp_gained)
            
            # 减少冷却
            for unit in player_units + enemy_units:
                if unit.skill_cooldown > 0:
                    unit.skill_cooldown -= 1
            
            # ===== 显示当前SP状态 =====
            round_log.append(f"\n📊 SP状态 | 玩家: {player_sp} | 敌方: {enemy_sp}")
            
            # ===== 先手方全员行动（按速度排序，使用position追踪）=====
            first_acted_positions = set()
            first_sorted = sorted([u for u in first_side if u.alive], 
                                 key=lambda x: x.character.speed, reverse=True)
            
            for unit in first_sorted:
                if not unit.alive or unit.position in first_acted_positions:
                    continue
                
                allies = first_allies
                enemies = second_side if unit in first_side else first_side
                if not enemies:
                    continue
                
                # 检查SP并选择行动
                can_ultimate = player_sp >= SP_MAX if unit in player_on_field else enemy_sp >= SP_MAX
                can_skill = (player_sp >= 30 if unit in player_on_field else enemy_sp >= 30) and unit.skill_cooldown == 0
                
                if can_ultimate and unit.character.ultimate:
                    # 释放大招
                    if unit in player_on_field:
                        player_sp = player_sp - 100
                    else:
                        enemy_sp = enemy_sp - 100
                    results, used, gained = self.execute_ultimate_attack(unit, enemies, True, allies)
                    round_log.extend(results)
                    if unit in player_on_field:
                        player_sp = self.add_sp(player_sp, gained)
                    else:
                        enemy_sp = self.add_sp(enemy_sp, gained)
                    first_acted_positions.add(unit.position)
                elif can_skill and unit.character.skill:
                    # 释放技能
                    if unit in player_on_field:
                        player_sp = player_sp - 30
                    else:
                        enemy_sp = enemy_sp - 30
                    results, used, gained = self.execute_skill_attack(unit, enemies, True, 30, allies)
                    round_log.extend(results)
                    if unit in player_on_field:
                        player_sp = self.add_sp(player_sp, gained)
                    else:
                        enemy_sp = self.add_sp(enemy_sp, gained)
                    first_acted_positions.add(unit.position)
                else:
                    # 普通攻击
                    results, gained = self.execute_normal_attack(unit, enemies)
                    round_log.extend(results)
                    if unit in player_on_field:
                        player_sp = self.add_sp(player_sp, gained)
                    else:
                        enemy_sp = self.add_sp(enemy_sp, gained)
                    first_acted_positions.add(unit.position)
                
                # 刷新场上单位
                player_on_field = self.get_on_field_units(player_units)
                enemy_on_field = self.get_on_field_units(enemy_units)
                
                # 检查是否结束
                if len(player_on_field) == 0 or len(enemy_on_field) == 0:
                    break
            
            # 刷新SP显示
            round_log.append(f"\n📊 SP状态 | 玩家: {player_sp} | 敌方: {enemy_sp}")
            
            # ===== 检查胜负 =====
            player_on_field = self.get_on_field_units(player_units)
            enemy_on_field = self.get_on_field_units(enemy_units)
            
            if len(player_on_field) == 0:
                battle_log.extend(round_log)
                round_log.append("玩家队伍全灭！")
                round_log.append("敌方胜利！")
                return self._create_result("enemy", round_num, battle_log + round_log, player_units, enemy_units)
            
            if len(enemy_on_field) == 0:
                battle_log.extend(round_log)
                round_log.append("玩家队伍胜利！")
                round_log.append("敌方全灭！")
                return self._create_result("player", round_num, battle_log + round_log, player_units, enemy_units)
            
            # ===== 后手方全员行动（按速度排序，可反弹）=====
            second_acted_positions = set()
            second_sorted = sorted([u for u in second_side if u.alive], 
                                  key=lambda x: x.character.speed, reverse=True)
            
            for unit in second_sorted:
                if not unit.alive or unit.position in second_acted_positions:
                    continue
                
                allies = second_allies
                enemies = first_side if unit in second_side else second_side
                if not enemies:
                    continue
                
                # 检查SP并选择行动
                can_ultimate = player_sp >= SP_MAX if unit in player_on_field else enemy_sp >= SP_MAX
                can_skill = (player_sp >= 30 if unit in player_on_field else enemy_sp >= 30) and unit.skill_cooldown == 0
                
                if can_ultimate and unit.character.ultimate:
                    # 释放大招
                    if unit in player_on_field:
                        player_sp = player_sp - 100
                    else:
                        enemy_sp = enemy_sp - 100
                    results, used, gained = self.execute_ultimate_attack(unit, enemies, True, allies)
                    round_log.extend(results)
                    if unit in player_on_field:
                        player_sp = self.add_sp(player_sp, gained)
                    else:
                        enemy_sp = self.add_sp(enemy_sp, gained)
                    second_acted_positions.add(unit.position)
                elif can_skill and unit.character.skill:
                    # 释放技能
                    if unit in player_on_field:
                        player_sp = player_sp - 30
                    else:
                        enemy_sp = enemy_sp - 30
                    results, used, gained = self.execute_skill_attack(unit, enemies, True, 30, allies)
                    round_log.extend(results)
                    if unit in player_on_field:
                        player_sp = self.add_sp(player_sp, gained)
                    else:
                        enemy_sp = self.add_sp(enemy_sp, gained)
                    second_acted_positions.add(unit.position)
                else:
                    # 普通攻击
                    results, gained = self.execute_normal_attack(unit, enemies)
                    round_log.extend(results)
                    if unit in player_on_field:
                        player_sp = self.add_sp(player_sp, gained)
                    else:
                        enemy_sp = self.add_sp(enemy_sp, gained)
                    second_acted_positions.add(unit.position)
                
                # 刷新场上单位
                player_on_field = self.get_on_field_units(player_units)
                enemy_on_field = self.get_on_field_units(enemy_units)
                
                # 检查是否结束
                if len(player_on_field) == 0 or len(enemy_on_field) == 0:
                    break
            
            battle_log.extend(round_log)
        
        # 超时判定
        player_hp = sum(u.current_hp for u in self.get_on_field_units(player_units))
        enemy_hp = sum(u.current_hp for u in self.get_on_field_units(enemy_units))
        
        if player_hp > enemy_hp:
            winner = "player"
        elif enemy_hp > player_hp:
            winner = "enemy"
        else:
            winner = random.choice(["player", "enemy"])
        
        return self._create_result(winner, MAX_BATTLE_ROUNDS, battle_log, player_units, enemy_units)
    
    def _create_result(self, winner: str, rounds: int, log: List[str],
                      player_units: List[BattleUnit], enemy_units: List[BattleUnit]) -> dict:
        """创建战斗结果"""
        return {
            "winner": winner,
            "rounds": rounds,
            "log": log,
            "player_units": [{
                "name": u.character.name,
                "hp": u.current_hp,
                "max_hp": u.max_hp,
                "alive": u.alive,
                "is_assist": u.is_assist,
                "position": u.position
            } for u in player_units],
            "enemy_units": [{
                "name": u.character.name,
                "hp": u.current_hp,
                "max_hp": u.max_hp,
                "alive": u.alive,
                "is_assist": u.is_assist,
                "position": u.position
            } for u in enemy_units]
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