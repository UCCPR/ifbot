"""
完整战斗系统 - 魔法禁书目录幻想收束
基于配队进行回合制自动战斗

战斗规则：
1. 配队：6个战斗位 + 6个支援位（每个战斗位对应一个支援位）
2. 上场：只有3个战斗位在场上，角色阵亡后下一个战斗位替补
3. 支援跟随：支援位跟随对应的战斗位，战斗位阵亡则支援位也阵亡
4. 回合制：普通攻击 / 技能 / 必杀技
5. 连携攻击：攻击方向数量限制连携次数
6. Break Point系统：需要被攻击指定次数才能破防
7. 属性克制：红→绿→蓝→红循环，黄、紫独立
8. SP值：攻击或被攻击积攒SP，攒满可释放必杀技
9. 自动战斗
"""

import os
import json
import random
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


# ========== 日志模块 ==========
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


# ========== 配置 ==========
BASE_DIR = Path(__file__).parent
LEVEL_DIR = BASE_DIR / "level"
INFO_DIR = BASE_DIR / "info"

INFO_DIR.mkdir(exist_ok=True)

# 战斗配置
TOTAL_BATTLE_POSITIONS = 6   # 总战斗位数量
TOTAL_ASSIST_POSITIONS = 6   # 总支援位数量
BATTLE_POSITIONS_ON_FIELD = 3  # 场上战斗位数量
MAX_BATTLE_ROUNDS = 30  # 最大战斗回合数

# SP配置
SP_PER_ATTACK = 15  # 攻击获得SP
SP_PER_DAMAGED = 10  # 被攻击获得SP
SP_MAX = 100  # SP上限

# 属性克制配置（赤→緑→青→赤循环，黄↔紫互相克制）
# 克制伤害 +50%，被克制 -40%
ATTRIBUTE_ADVANTAGE = {
    "赤": {"緑": 1.5, "青": 0.6, "赤": 1.0, "黄": 1.0, "紫": 1.0},
    "緑": {"青": 1.5, "赤": 0.6, "緑": 1.0, "黄": 1.0, "紫": 1.0},
    "青": {"赤": 1.5, "緑": 0.6, "青": 1.0, "黄": 1.0, "紫": 1.0},
    "黄": {"紫": 1.5, "赤": 1.0, "緑": 1.0, "青": 1.0, "黄": 1.0},
    "紫": {"黄": 1.5, "赤": 1.0, "緑": 1.0, "青": 1.0, "紫": 1.0}
}

# 属性别名映射
ATTRIBUTE_ALIASES = {
    "红": "赤",
    "绿": "緑",
    "蓝": "青",
    "yellow": "黄",
    "purple": "紫"
}

# 超属性增益（额外伤害加成）
SUPER_ATTRIBUTE_BONUS = {
    "超赤": 1.1,
    "超緑": 1.1,
    "超青": 1.1,
    "超黄": 1.1,
    "超紫": 1.1
}

# 技能倍率配置
SKILL_MULTIPLIER = {
    "小": 1.2,
    "中": 1.5,
    "大": 1.7,
    "特大": 2.0
}


# ========== 数据结构 ==========
@dataclass
class Skill:
    """技能"""
    name: str
    sp_cost: int = 30
    cooldown: int = 2
    multiplier_key: str = "中"
    effect: str = ""


@dataclass
class UltimateSkill:
    """必杀技"""
    name: str
    sp_cost: int = 100
    multiplier_key: str = "特大"
    effect: str = ""


@dataclass
class AssistEffect:
    """支援卡效果"""
    cd: int = 0  # 冷却回合
    keywords: str = ""  # 效果关键词（如物理贯通、弱化解除等）
    condition: str = ""  # 触发条件（如自身、左右队友、全体等）
    description: str = ""  # 描述
    current_cd: int = 0  # 当前冷却
    
    def is_ready(self) -> bool:
        """检查是否可以触发"""
        return self.current_cd <= 0

@dataclass
class Character:
    """角色数据"""
    card_id: str
    name: str
    hp: int
    attack: int
    defense: int
    speed: int
    attribute: str  # 红/绿/蓝/黄/紫
    attack_type: str  # 物理/异能
    attack_directions: int = 1  # 攻击方向数 1~3
    break_point: int = 0  # Break Point计数，0表示无
    
    # 技能（可选）
    skill: Optional[Skill] = None
    ultimate: Optional[UltimateSkill] = None
    
    # 支援效果（支援卡专用）
    assist_effect1: Optional[AssistEffect] = None
    assist_effect2: Optional[AssistEffect] = None
    
    # 星级加成
    stars: int = 3


@dataclass
class BattleUnit:
    """战斗单位"""
    character: Character
    position: int  # 在配队中的位置 0-5
    is_assist: bool = False
    
    # 当前状态
    current_hp: int = 0
    max_hp: int = 0
    sp: int = 0
    skill_cooldown: int = 0  # 技能冷却回合
    
    # 状态
    alive: bool = True
    break_count: int = 0  # 累计被攻击次数
    is_broken: bool = False  # 是否已破防
    
    # 标记
    assist_unit: Optional['BattleUnit'] = None  # 关联的支援单位
    
    def __post_init__(self):
        if self.current_hp == 0:
            self.current_hp = self.character.hp
        if self.max_hp == 0:
            self.max_hp = self.character.hp


# ========== 战斗系统 ==========
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
        """标准化属性名称（处理别名和超属性）"""
        if not attr:
            return "赤"
        
        # 转换别名
        attr = attr.strip()
        if attr in ATTRIBUTE_ALIASES:
            return ATTRIBUTE_ALIASES[attr]
        
        # 检查超属性
        for super_attr in SUPER_ATTRIBUTE_BONUS.keys():
            if attr.startswith(super_attr):
                return attr
        
        # 返回原始属性
        return attr
    
    def _load_characters(self, characters_data: List[dict]):
        """加载角色数据"""
        for char_data in characters_data:
            try:
                # 获取技能数据
                skill = None
                ultimate = None
                
                if char_data.get("skill_name"):
                    skill = Skill(
                        name=char_data.get("skill_name", "技能"),
                        sp_cost=char_data.get("skill_sp", 30),
                        cooldown=char_data.get("skill_cooldown", 2),
                        multiplier_key=char_data.get("skill_power", "中"),
                        effect=char_data.get("skill_effect", "")
                    )
                
                if char_data.get("ultimate_name"):
                    ultimate = UltimateSkill(
                        name=char_data.get("ultimate_name", "必杀技"),
                        sp_cost=char_data.get("ultimate_sp", 100),
                        multiplier_key=char_data.get("ultimate_power", "特大"),
                        effect=char_data.get("ultimate_effect", "")
                    )
                
                # 获取支援效果（支援卡专用）
                assist_effect1 = None
                assist_effect2 = None
                
                skill1_data = char_data.get("skill1", {})
                if skill1_data:
                    assist_effect1 = AssistEffect(
                        cd=skill1_data.get("cd", 0),
                        keywords=skill1_data.get("keywords", ""),
                        condition=skill1_data.get("condition", ""),
                        description=skill1_data.get("description", "")
                    )
                
                skill2_data = char_data.get("skill2", {})
                if skill2_data:
                    assist_effect2 = AssistEffect(
                        cd=skill2_data.get("cd", 0),
                        keywords=skill2_data.get("keywords", ""),
                        condition=skill2_data.get("condition", ""),
                        description=skill2_data.get("description", "")
                    )
                
                # 标准化属性名称
                attribute = self._normalize_attribute(char_data.get("attribute", "赤"))
                
                # 创建角色对象
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
                    break_point=char_data.get("break_point", 0),
                    skill=skill,
                    ultimate=ultimate,
                    assist_effect1=assist_effect1,
                    assist_effect2=assist_effect2,
                    stars=char_data.get("stars", 3)
                )
                
                # 应用星级加成
                star_mult = 1 + (character.stars - 1) * 0.2
                character.hp = int(character.hp * star_mult)
                character.attack = int(character.attack * star_mult)
                character.defense = int(character.defense * star_mult)
                character.speed = int(character.speed * star_mult)
                
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
        
        return BattleUnit(
            character=character,
            position=position,
            is_assist=is_assist
        )
    
    def build_battle_team(self, team_data: dict) -> List[BattleUnit]:
        """构建战斗队伍（6个战斗位 + 6个支援位）"""
        units = []
        
        # 创建战斗单位
        battle_cards = team_data.get("battle_cards", [])
        assist_cards = team_data.get("assist_cards", [])
        
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
        
        # 关联支援单位到对应的战斗单位，并应用B+A属性加成
        SAME_ATTR_BONUS = 1.1  # 同属性增益10%
        for battle_unit in units:
            if not battle_unit.is_assist:
                for assist_unit in units:
                    if assist_unit.is_assist and assist_unit.position == battle_unit.position:
                        battle_unit.assist_unit = assist_unit
                        
                        # B+A属性相加
                        battle_unit.max_hp += assist_unit.character.hp
                        battle_unit.current_hp = battle_unit.max_hp
                        battle_unit.character.attack += assist_unit.character.attack
                        battle_unit.character.defense += assist_unit.character.defense
                        battle_unit.character.speed += assist_unit.character.speed
                        
                        # 同属性增益
                        battle_attr = self.get_base_attribute(battle_unit.character.attribute)
                        assist_attr = self.get_base_attribute(assist_unit.character.attribute)
                        if battle_attr == assist_attr:
                            battle_unit.character.hp = int(battle_unit.character.hp * SAME_ATTR_BONUS)
                            battle_unit.character.attack = int(battle_unit.character.attack * SAME_ATTR_BONUS)
                            battle_unit.character.defense = int(battle_unit.character.defense * SAME_ATTR_BONUS)
                            battle_unit.character.speed = int(battle_unit.character.speed * SAME_ATTR_BONUS)
                            battle_unit.max_hp = int(battle_unit.max_hp * SAME_ATTR_BONUS)
                            battle_unit.current_hp = battle_unit.max_hp
                            
                            log_battle(f"✨ 同属性增益！{battle_unit.character.name}({battle_attr}) + {assist_unit.character.name}({assist_attr})")
                        break
        
        return units
    
    def get_on_field_units(self, units: List[BattleUnit]) -> List[BattleUnit]:
        """获取场上战斗单位（存活的前3个单位按位置顺序）"""
        # 获取所有存活的战斗单位（非支援）
        alive_battle_units = [u for u in units if not u.is_assist and u.alive]
        # 按位置排序
        alive_battle_units.sort(key=lambda x: x.position)
        # 返回前3个作为场上单位
        return alive_battle_units[:BATTLE_POSITIONS_ON_FIELD]
    
    def get_substitute_units(self, units: List[BattleUnit]) -> List[BattleUnit]:
        """获取替补单位（存活的第4-6位）"""
        alive_battle_units = [u for u in units if not u.is_assist and u.alive]
        alive_battle_units.sort(key=lambda x: x.position)
        # 返回第4-6个作为替补
        return alive_battle_units[BATTLE_POSITIONS_ON_FIELD:]
    
    def substitute_dead_units(self, units: List[BattleUnit]) -> None:
        """替补阵亡单位（立即替补，直到6个角色全部阵亡）"""
        # 获取所有存活的战斗单位
        alive_battle_units = [u for u in units if not u.is_assist and u.alive]
        alive_battle_units.sort(key=lambda x: x.position)
        
        # 检查场上是否有空缺（少于3个）
        current_on_field = len(alive_battle_units[:BATTLE_POSITIONS_ON_FIELD])
        
        # 如果场上有空缺且还有替补
        if current_on_field < BATTLE_POSITIONS_ON_FIELD:
            # 替补数量 = 空缺数量
            needed = BATTLE_POSITIONS_ON_FIELD - current_on_field
            substitutes = alive_battle_units[BATTLE_POSITIONS_ON_FIELD:BATTLE_POSITIONS_ON_FIELD + needed]
            
            for sub in substitutes:
                log_battle(f"🔄 替补单位 {sub.character.name} 从位置{sub.position+1}上场！")
    
    def get_adjacent_units(self, unit: BattleUnit, units: List[BattleUnit]) -> List[BattleUnit]:
        """获取相邻的队友（左右队友）"""
        adjacent = []
        position = unit.position
        
        # 位置关系：0的右队友是1，1的左队友是0、右队友是2，2的左队友是1
        # 位置3的右队友是4，4的左队友是3、右队友是5，5的左队友是4
        if position % 3 == 0:  # 位置0或3
            # 只有右队友
            right_pos = position + 1
            for u in units:
                if not u.is_assist and u.position == right_pos and u.alive:
                    adjacent.append(u)
        elif position % 3 == 2:  # 位置2或5
            # 只有左队友
            left_pos = position - 1
            for u in units:
                if not u.is_assist and u.position == left_pos and u.alive:
                    adjacent.append(u)
        else:  # 位置1或4
            # 左右都有
            left_pos = position - 1
            right_pos = position + 1
            for u in units:
                if not u.is_assist and u.alive and u.position in [left_pos, right_pos]:
                    adjacent.append(u)
        
        return adjacent
    
    def get_active_units(self, units: List[BattleUnit]) -> List[BattleUnit]:
        """获取场上存活的单位（战斗+支援）"""
        active = []
        for u in units:
            if not u.is_assist and u.alive:
                active.append(u)
                # 如果战斗单位存活，其支援单位也计入
                if u.assist_unit:
                    u.assist_unit.alive = True
                    active.append(u.assist_unit)
        return active
    
    def get_base_attribute(self, attr: str) -> str:
        """获取基础属性（去除超属性前缀）"""
        base_attrs = ["赤", "緑", "青", "黄", "紫"]
        for base in base_attrs:
            if base in attr:
                return base
        return multiplier
    
    def trigger_assist_effects(self, unit: BattleUnit, allies: List[BattleUnit], enemies: List[BattleUnit], round_log: list) -> None:
        """触发支援卡效果"""
        if not unit.assist_unit:
            return
        
        assist_char = unit.assist_unit.character
        
        # 处理效果1
        if assist_char.assist_effect1 and assist_char.assist_effect1.is_ready():
            self._apply_assist_effect(unit, assist_char.assist_effect1, allies, enemies, round_log)
            assist_char.assist_effect1.current_cd = assist_char.assist_effect1.cd
        
        # 处理效果2
        if assist_char.assist_effect2 and assist_char.assist_effect2.is_ready():
            self._apply_assist_effect(unit, assist_char.assist_effect2, allies, enemies, round_log)
            assist_char.assist_effect2.current_cd = assist_char.assist_effect2.cd
    
    def _apply_assist_effect(self, source_unit: BattleUnit, effect: AssistEffect, 
                           allies: List[BattleUnit], enemies: List[BattleUnit], round_log: list) -> None:
        """应用支援卡效果"""
        condition = effect.condition
        keywords = effect.keywords
        
        # 根据条件确定目标
        targets = []
        condition_lower = condition.lower()
        
        # 解析条件
        if "自身" in condition or "自分" in condition:
            targets = [source_unit]
        elif "左右" in condition:
            targets = self.get_adjacent_units(source_unit, allies)
            if source_unit in allies:
                targets.append(source_unit)
        elif "全体" in condition or "全員" in condition:
            targets = [u for u in allies if not u.is_assist and u.alive]
        elif "前方" in condition:
            # 前方目标（敌方）
            targets = enemies[:]
        elif "敵" in condition or "相手" in condition:
            targets = enemies[:]
        else:
            # 默认对自身生效
            targets = [source_unit]
        
        if not targets:
            return
        
        # 根据关键词应用效果
        effect_str = f"🎯 {source_unit.assist_unit.character.name} 触发支援效果: {keywords}"
        round_log.append(effect_str)
        log_battle(effect_str)
        
        # 处理各种效果关键词
        if "物理贯通" in keywords:
            # 物理贯通：无视部分防御
            for target in targets:
                if target in allies:
                    target.character.attack = int(target.character.attack * 1.2)
                    round_log.append(f"   → {target.character.name} 物理攻击+20%")
        elif "弱化解除" in keywords:
            # 弱化解除：解除负面状态
            for target in targets:
                if target in allies:
                    round_log.append(f"   → {target.character.name} 弱化状态已解除")
        elif "回復" in keywords or "回复" in keywords:
            # 回复HP
            heal_amount = int(source_unit.character.attack * 0.3)
            for target in targets:
                if target in allies and target.alive:
                    heal = min(heal_amount, target.max_hp - target.current_hp)
                    target.current_hp += heal
                    round_log.append(f"   → {target.character.name} 回复 {heal} HP")
        elif "防御" in keywords:
            # 提升防御
            for target in targets:
                if target in allies:
                    target.character.defense = int(target.character.defense * 1.2)
                    round_log.append(f"   → {target.character.name} 防御+20%")
        elif "加速" in keywords or "速さ" in keywords:
            # 提升速度
            for target in targets:
                if target in allies:
                    target.character.speed = int(target.character.speed * 1.15)
                    round_log.append(f"   → {target.character.name} 速度+15%")
        elif "SP" in keywords or "スキルポイント" in keywords:
            # 恢复SP
            for target in targets:
                if target in allies:
                    target.sp = min(100, target.sp + 20)
                    round_log.append(f"   → {target.character.name} SP+20%")
        elif "バリア" in keywords or "屏障" in keywords:
            # 屏障效果
            for target in targets:
                if target in allies:
                    round_log.append(f"   → {target.character.name} 获得屏障")
        else:
            # 未知效果，记录描述
            round_log.append(f"   → 效果: {effect.description}")
    
    def select_target_by_direction(self, attacker: BattleUnit, enemies: List[BattleUnit]) -> BattleUnit:
        """根据攻击方向选择目标（位置对应：己方1→敌方1, 己方2→敌方2, 己方3→敌方3）"""
        # 获取攻击者在场上的位置（0=位置1, 1=位置2, 2=位置3）
        attacker_field_pos = attacker.position % 3
        
        # 优先攻击对应位置的敌人
        for enemy in enemies:
            enemy_field_pos = enemy.position % 3
            if enemy_field_pos == attacker_field_pos:
                return enemy
        
        # 如果对应位置没有敌人，随机选择一个
        return random.choice(enemies)
    
    def get_attribute_advantage(self, attacker_attr: str, defender_attr: str) -> float:
        """获取属性克制倍率（包含超属性增益）"""
        # 获取基础属性用于克制计算
        attacker_base = self.get_base_attribute(attacker_attr)
        defender_base = self.get_base_attribute(defender_attr)
        
        # 获取克制倍率
        multiplier = ATTRIBUTE_ADVANTAGE.get(attacker_base, {}).get(defender_base, 1.0)
        
        # 检查超属性增益
        if attacker_attr in SUPER_ATTRIBUTE_BONUS:
            multiplier *= SUPER_ATTRIBUTE_BONUS[attacker_attr]
        
        return multiplier
    
    def calculate_damage(self, attacker: BattleUnit, defender: BattleUnit, 
                        attack_type: str = "normal", skill_multiplier: float = 1.0) -> Tuple[int, bool, bool, str]:
        """
        计算伤害
        :param attacker: 攻击方
        :param defender: 防御方
        :param attack_type: 攻击类型 "normal"/"skill"/"ultimate"
        :param skill_multiplier: 技能倍率
        :return: (伤害值, 是否暴击, 是否克制, 伤害类型描述)
        """
        # 基础伤害
        base_damage = attacker.character.attack
        
        # 攻击类型加成
        if attack_type == "skill":
            base_damage = int(base_damage * skill_multiplier)
            damage_type = "技能伤害"
        elif attack_type == "ultimate":
            base_damage = int(base_damage * skill_multiplier * 2.0)
            damage_type = "必杀技伤害"
        else:
            damage_type = "普通攻击"
        
        # 属性克制
        is_advantage = self.get_attribute_advantage(attacker.character.attribute, defender.character.attribute)
        advantage_text = ""
        if is_advantage > 1.0:
            base_damage = int(base_damage * is_advantage)
            advantage_text = "⚡属性克制！"
        elif is_advantage < 1.0:
            base_damage = int(base_damage * is_advantage)
            advantage_text = "⚠️属性被克制！"
        
        # 防御减伤
        defense_reduction = defender.character.defense / (defender.character.defense + 200)
        final_damage = int(base_damage * (1 - defense_reduction * 0.5))
        
        # Break状态加成
        if defender.is_broken:
            final_damage = int(final_damage * 2.0)
            advantage_text += "💥破防加成！"
        
        # 暴击（5%基础概率）
        is_crit = random.random() < 0.05
        if is_crit:
            final_damage = int(final_damage * 1.5)
            advantage_text += "💥暴击！"
        
        return max(1, final_damage), is_crit, is_advantage != 1.0, advantage_text
    
    def add_sp(self, unit: BattleUnit, sp_amount: int):
        """增加SP"""
        unit.sp = min(SP_MAX, unit.sp + sp_amount)
    
    def use_sp(self, unit: BattleUnit, sp_amount: int) -> bool:
        """消耗SP，返回是否成功"""
        if unit.sp >= sp_amount:
            unit.sp -= sp_amount
            return True
        return False
    
    def check_break_point(self, defender: BattleUnit):
        """检查Break Point"""
        if defender.character.break_point > 0:
            defender.break_count += 1
            if defender.break_count >= defender.character.break_point and not defender.is_broken:
                defender.is_broken = True
                return True
        return False
    
    def execute_normal_attack(self, attacker: BattleUnit, defender: BattleUnit) -> List[str]:
        """执行普通攻击"""
        results = []
        
        # 计算连携次数（根据攻击方向数）
        combo_count = attacker.character.attack_directions
        
        for i in range(combo_count):
            damage, is_crit, is_adv, text = self.calculate_damage(attacker, defender, "normal")
            
            # 造成伤害
            defender.current_hp -= damage
            
            # SP获得
            self.add_sp(attacker, SP_PER_ATTACK)
            self.add_sp(defender, SP_PER_DAMAGED)
            
            # Break Point检查
            if self.check_break_point(defender):
                results.append(f"💥 {defender.character.name} 破防了！受到伤害翻倍！")
            
            # 死亡检查
            if defender.current_hp <= 0:
                defender.current_hp = 0
                defender.alive = False
                if defender.assist_unit:
                    defender.assist_unit.alive = False
                results.append(f"💀 {defender.character.name} 被击败了！")
                break
            
            # 连携攻击描述
            combo_text = f"[{i+1}/{combo_count}]" if combo_count > 1 else ""
            results.append(f"⚔️ {attacker.character.name} 的普通攻击 {combo_text} → {defender.character.name}，造成 {damage} 伤害 {text}")
        
        return results
    
    def execute_skill_attack(self, attacker: BattleUnit, defender: BattleUnit) -> List[str]:
        """执行技能攻击"""
        results = []
        
        if not attacker.character.skill:
            return self.execute_normal_attack(attacker, defender)
        
        skill = attacker.character.skill
        
        # 检查SP和冷却
        if not self.use_sp(attacker, skill.sp_cost):
            results.append(f"⚠️ {attacker.character.name} SP不足，使用普通攻击")
            return self.execute_normal_attack(attacker, defender)
        
        if attacker.skill_cooldown > 0:
            results.append(f"⚠️ {attacker.character.name} 技能冷却中，使用普通攻击")
            return self.execute_normal_attack(attacker, defender)
        
        # 执行技能
        multiplier = SKILL_MULTIPLIER.get(skill.multiplier_key, 1.5)
        damage, is_crit, is_adv, text = self.calculate_damage(attacker, defender, "skill", multiplier)
        
        # 造成伤害
        defender.current_hp -= damage
        
        # SP获得
        self.add_sp(attacker, SP_PER_ATTACK)
        self.add_sp(defender, SP_PER_DAMAGED)
        
        # 设置冷却
        attacker.skill_cooldown = skill.cooldown
        
        # Break Point检查
        if self.check_break_point(defender):
            results.append(f"💥 {defender.character.name} 破防了！受到伤害翻倍！")
        
        # 死亡检查
        if defender.current_hp <= 0:
            defender.current_hp = 0
            defender.alive = False
            if defender.assist_unit:
                defender.assist_unit.alive = False
            results.append(f"💀 {defender.character.name} 被击败了！")
        else:
            results.append(f"✨ {attacker.character.name} 使用 {skill.name} → {defender.character.name}，造成 {damage} 伤害 {text}")
        
        return results
    
    def execute_ultimate_attack(self, attacker: BattleUnit, defenders: List[BattleUnit]) -> List[str]:
        """执行必杀技（可攻击多个目标）"""
        results = []
        
        if not attacker.character.ultimate:
            return self.execute_skill_attack(attacker, defenders[0] if defenders else None)
        
        ultimate = attacker.character.ultimate
        
        # 检查SP
        if not self.use_sp(attacker, ultimate.sp_cost):
            results.append(f"⚠️ {attacker.character.name} SP不足，使用技能")
            return self.execute_skill_attack(attacker, defenders[0] if defenders else None)
        
        # 执行必杀技
        multiplier = SKILL_MULTIPLIER.get(ultimate.multiplier_key, 2.0)
        results.append(f"🌟 {attacker.character.name} 发动必杀技：{ultimate.name}！")
        
        # 对所有目标造成伤害
        for defender in defenders:
            if not defender.alive:
                continue
            
            damage, is_crit, is_adv, text = self.calculate_damage(attacker, defender, "ultimate", multiplier)
            defender.current_hp -= damage
            
            # SP获得
            self.add_sp(defender, SP_PER_DAMAGED)
            
            # Break Point检查
            if self.check_break_point(defender):
                results.append(f"💥 {defender.character.name} 破防了！受到伤害翻倍！")
            
            # 死亡检查
            if defender.current_hp <= 0:
                defender.current_hp = 0
                defender.alive = False
                if defender.assist_unit:
                    defender.assist_unit.alive = False
                results.append(f"💀 {defender.character.name} 被击败了！")
            else:
                results.append(f"💫 → {defender.character.name}，造成 {damage} 伤害 {text}")
        
        return results
    
    def ai_choose_action(self, unit: BattleUnit, enemies: List[BattleUnit]) -> str:
        """AI选择行动（有大招立刻放大招）"""
        # SP满100%立刻释放必杀技
        if unit.sp >= 100:
            return "ultimate"
        
        # 技能就绪且SP足够则释放技能
        if unit.skill_cooldown == 0 and unit.sp >= 30:
            return "skill"
        
        # 普通攻击
        return "normal"
    
    def start_battle(self, player_team: dict, enemy_team: dict) -> dict:
        """开始战斗
        
        :param player_team: 玩家队伍 {"battle_cards": [...], "assist_cards": [...]}
        :param enemy_team: 敌方队伍 {"battle_cards": [...], "assist_cards": [...]}
        :return: 战斗结果
        """
        log_battle("=" * 50)
        log_battle("⚔️ 战斗开始！")
        log_battle("=" * 50)
        
        # 构建战斗单位
        player_units = self.build_battle_team(player_team)
        enemy_units = self.build_battle_team(enemy_team)
        
        # 获取场上单位
        player_on_field = self.get_on_field_units(player_units)
        enemy_on_field = self.get_on_field_units(enemy_units)
        
        battle_log = []
        max_rounds = MAX_BATTLE_ROUNDS
        
        for round_num in range(1, max_rounds + 1):
            round_log = [f"\n{'='*50}\n⚡ 第 {round_num} 回合\n{'='*50}"]
            log_battle(f"第 {round_num} 回合开始")
            
            # 刷新场上单位（检查是否有单位死亡需要替补）
            player_on_field = self.get_on_field_units(player_units)
            enemy_on_field = self.get_on_field_units(enemy_units)
            
            # 执行替补
            self.substitute_dead_units(player_units)
            self.substitute_dead_units(enemy_units)
            
            # 重新获取场上单位
            player_on_field = self.get_on_field_units(player_units)
            enemy_on_field = self.get_on_field_units(enemy_units)
            
            # 检查胜负
            if len(player_on_field) == 0:
                round_log.append("💀💀💀 玩家队伍全灭！ 💀💀💀")
                round_log.append("🏆 敌方胜利！")
                log_battle(f"第{round_num}回合: 玩家失败")
                return self._create_result("enemy", round_num, battle_log + round_log, player_units, enemy_units)
            
            if len(enemy_on_field) == 0:
                round_log.append("🏆🏆🏆 玩家队伍胜利！ 🏆🏆🏆")
                round_log.append("💀 敌方全灭！")
                log_battle(f"第{round_num}回合: 玩家胜利")
                return self._create_result("player", round_num, battle_log + round_log, player_units, enemy_units)
            
            # 回合开始：所有单位减少冷却
            for unit in player_units + enemy_units:
                if unit.skill_cooldown > 0:
                    unit.skill_cooldown -= 1
                # 减少支援效果冷却
                if unit.assist_unit:
                    if unit.assist_unit.character.assist_effect1:
                        if unit.assist_unit.character.assist_effect1.current_cd > 0:
                            unit.assist_unit.character.assist_effect1.current_cd -= 1
                    if unit.assist_unit.character.assist_effect2:
                        if unit.assist_unit.character.assist_effect2.current_cd > 0:
                            unit.assist_unit.character.assist_effect2.current_cd -= 1
            
            # 触发支援卡效果
            for unit in player_on_field + enemy_on_field:
                self.trigger_assist_effects(unit, player_units if unit in player_on_field else enemy_units, 
                                           enemy_on_field if unit in player_on_field else player_on_field, round_log)
            
            # 获取所有存活的战斗单位并按速度排序
            all_units = self.get_active_units(player_units + enemy_units)
            all_units.sort(key=lambda x: x.character.speed, reverse=True)
            
            # 依次行动
            for unit in all_units:
                if not unit.alive:
                    continue
                
                # 检查是否在场上（如果是战斗单位）
                if not unit.is_assist:
                    if unit not in self.get_on_field_units(player_units + enemy_units):
                        continue
                
                # 选择行动
                enemies = enemy_on_field if unit not in player_on_field else player_on_field
                if not enemies:
                    continue
                
                # 根据攻击方向选择目标（位置对应：1→1, 2→2, 3→3）
                target = self.select_target_by_direction(unit, enemies)
                action = self.ai_choose_action(unit, enemies)
                
                # 执行行动
                if action == "ultimate":
                    results = self.execute_ultimate_attack(unit, enemies)
                    round_log.extend(results)
                    for r in results:
                        log_battle(r)
                elif action == "skill":
                    results = self.execute_skill_attack(unit, target)
                    round_log.extend(results)
                    for r in results:
                        log_battle(r)
                else:
                    results = self.execute_normal_attack(unit, target)
                    round_log.extend(results)
                    for r in results:
                        log_battle(r)
                
                # 刷新场上单位
                player_on_field = self.get_on_field_units(player_units)
                enemy_on_field = self.get_on_field_units(enemy_units)
                
                # 检查场上是否有人全灭
                if len(player_on_field) == 0 or len(enemy_on_field) == 0:
                    break
            
            battle_log.extend(round_log)
            
            # 显示场上状态
            player_status = ", ".join([f"{u.character.name}({u.current_hp}/{u.max_hp})" 
                                       for u in player_on_field])
            enemy_status = ", ".join([f"{u.character.name}({u.current_hp}/{u.max_hp})" 
                                      for u in enemy_on_field])
            round_log.append(f"\n📊 场上状态：")
            round_log.append(f"   玩家: {player_status}")
            round_log.append(f"   敌方: {enemy_status}")
        
        # 超时判定
        player_hp = sum(u.current_hp for u in player_on_field)
        enemy_hp = sum(u.current_hp for u in enemy_on_field)
        
        if player_hp > enemy_hp:
            winner = "player"
            battle_log.append(f"\n⏰ 回合耗尽！")
            battle_log.append(f"玩家剩余HP: {player_hp} vs 敌方剩余HP: {enemy_hp}")
            battle_log.append("🏆 玩家队伍以HP优势获胜！")
        elif enemy_hp > player_hp:
            winner = "enemy"
            battle_log.append(f"\n⏰ 回合耗尽！")
            battle_log.append(f"玩家剩余HP: {player_hp} vs 敌方剩余HP: {enemy_hp}")
            battle_log.append("💀 敌方队伍以HP优势获胜！")
        else:
            winner = random.choice(["player", "enemy"])
            battle_log.append(f"\n⏰ 回合耗尽！HP相同，随机判定：{'玩家' if winner == 'player' else '敌方'}获胜！")
        
        log_battle(f"战斗结束: {winner}胜利")
        return self._create_result(winner, max_rounds, battle_log, player_units, enemy_units)
    
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
    lines.append(f"⚔️  {'自动战斗' if True else '手动战斗'} ⚔️")
    lines.append(f"{'='*60}")
    
    # 战斗日志
    for log in result["log"]:
        lines.append(log)
    
    # 胜负结果
    lines.append(f"\n{'='*60}")
    if result["winner"] == "player":
        lines.append("🏆🏆🏆 玩家队伍胜利！ 🏆🏆🏆")
    else:
        lines.append("💀💀💀 敌方队伍胜利... 💀💀💀")
    lines.append(f"{'='*60}")
    
    # 战斗统计
    lines.append(f"\n📊 战斗统计：")
    lines.append(f"   回合数：{result['rounds']}")
    
    # 玩家单位状态
    lines.append(f"\n👥 玩家队伍：")
    for u in result["player_units"]:
        status = "✅" if u["alive"] else "❌"
        assist_mark = " [支援]" if u["is_assist"] else ""
        lines.append(f"   {status} {u['name']}{assist_mark}: {u['hp']}/{u['max_hp']}")
    
    # 敌方单位状态
    lines.append(f"\n👹 敌方队伍：")
    for u in result["enemy_units"]:
        status = "✅" if u["alive"] else "❌"
        assist_mark = " [支援]" if u["is_assist"] else ""
        lines.append(f"   {status} {u['name']}{assist_mark}: {u['hp']}/{u['max_hp']}")
    
    return "\n".join(lines)


# ========== 帮助信息 ==========
def get_battle_help() -> str:
    """获取战斗系统帮助信息"""
    return """
╔══════════════════════════════════════════════════════════════╗
║         ⚔️ 魔法禁书目录幻想收束 - 战斗系统 ⚔️                 ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📋 战斗命令：                                                ║
║  · 战斗 / 对战 - 使用当前配队与AI对战                         ║
║  · 战斗 @玩家 - 与指定玩家对战                               ║
║  · 战斗日志 - 查看最近一场战斗的详细日志                     ║
║                                                              ║
║  📊 战斗规则：                                                ║
║  · 配队：每队6个战斗卡(B) + 6个支援卡(A)                     ║
║  · 同位置B/A卡需同属性、同攻击类型                           ║
║  · 场上：每队只有3个战斗位同时在场上(位置1/2/3)             ║
║  · 替补：位置4/5/6为替补，阵亡后立即自动替补                 ║
║  · 支援：支援卡跟随对应战斗卡行动，提供额外效果              ║
║                                                              ║
║  ⚔️ 攻击类型：                                                ║
║  · 普通攻击：基础伤害，可触发连携攻击                        ║
║  · 技能：造成较高伤害，有冷却回合                            ║
║  · 必杀技：消耗100%SP，造成大量伤害，优先释放                ║
║                                                              ║
║  💥 属性克制：                                                ║
║  · 🔴赤 → 🟢緑 → 🔵青 → 🔴赤 （循环）                       ║
║  · 🟡黄 ↔ 🟣紫 互相克制                                     ║
║  · 超属性(超赤/超緑等)额外+10%伤害                          ║
║                                                              ║
║  ⚡ SP系统：                                                  ║
║  · 攻击获得15% SP，被攻击获得10% SP                         ║
║  · SP攒满100%自动释放必杀技                                 ║
║                                                              ║
║  🔄 连携攻击：                                                ║
║  · 根据攻击方向数(1~3)决定连携次数                          ║
║  · 相邻队友可触发连携攻击                                    ║
║                                                              ║
║  🎮 自动战斗逻辑：                                            ║
║  · SP满100%立刻释放必杀技                                   ║
║  · 技能就绪且SP足够则释放技能                               ║
║  · 否则执行普通攻击                                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
