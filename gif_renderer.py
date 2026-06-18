"""
战斗GIF生成系统 - 修复版

战斗日志格式：
1. 普通攻击：(ratio)【称号】角色名[箭头] -> 【称号】角色名[箭头] (伤害) [攻击类型]
2. 换位：[换位] [P/E] 【称号】角色名[箭头] -> 新箭头
3. 替补上场：[上场] [P/E] 【称号】角色名[箭头]
4. A卡效果：【称号】角色名[箭头] buff1, buff2... [A]
"""
import re
import copy
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent
ICON_DIR = BASE_DIR / "iconimage"
LEVEL_DIR = BASE_DIR / "level"
STATE_DIR = BASE_DIR / "state_icon"

CARD_WIDTH = 80
CARD_HEIGHT = 100
ICON_SIZE = 16
ICON_GAP = 2
HP_BAR_HEIGHT = 16
SECTION_SPACING = 60
PADDING = 20

COLOR_HP_HIGH = (50, 200, 50)
COLOR_HP_MEDIUM = (200, 180, 50)
COLOR_HP_LOW = (200, 50, 50)
COLOR_HP_BG = (30, 30, 30)
COLOR_TEXT_WHITE = (255, 255, 255)
COLOR_TEXT_GOLD = (255, 220, 100)
COLOR_DAMAGE = (255, 80, 80)
COLOR_HEAL = (80, 255, 80)
COLOR_DAMAGE_BG = (60, 0, 0)
COLOR_HEAL_BG = (0, 60, 0)
COLOR_FRAME_BG = (20, 20, 35)
COLOR_INFO_BG = (15, 15, 30)
COLOR_INFO_BORDER = (40, 40, 80)
COLOR_EMPTY = (55, 55, 75)

ARROW_TO_COL = {'↙':0, '←':1, '↓':2, '→':3, '↘':4, '↖':0, '↑':2, '↗':4}
COL_TO_ARROW_P = {0:'↙', 1:'←', 2:'↓', 3:'→', 4:'↘'}
COL_TO_ARROW_E = {0:'↖', 1:'←', 2:'↑', 3:'→', 4:'↗'}

CROP_LEFT_RATIO = 0.25
CROP_RIGHT_RATIO = 0.75
CROP_TOP_RATIO = 0.15
CROP_BOTTOM_RATIO = 0.65

_CACHED_FONT = {}
_CACHED_FRAMES = {}

def _get_font(size):
    font_key = f"font_{size}"
    
    import platform
    system = platform.system()
    
    # 根据操作系统选择字体路径
    if system == "Windows":
        font_paths = [
            "C:/Windows/Fonts/msgothic.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "C:/Windows/Fonts/msmincho.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simkai.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/arialuni.ttf",
        ]
    else:  # Linux
        font_paths = [
            # Linux中文字体（优先级从高到低）
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            "/usr/share/fonts/truetype/arphic/ukai.ttc",
            "/usr/share/fonts/truetype/fireflysung/fireflysung.ttf",
            # 日文字体
            "/usr/share/fonts/truetype/vlgothic/VL-Gothic-Regular.ttf",
            "/usr/share/fonts/truetype/mona/Mona.ttf",
            # 回退到项目目录下的字体
            str(BASE_DIR / "fonts" / "NotoSansCJK-Regular.ttc"),
            str(BASE_DIR / "fonts" / "msgothic.ttc"),
            str(BASE_DIR / "fonts" / "simhei.ttf"),
        ]
    
    # 首先尝试找到支持CJK的字体
    for font_name in font_paths:
        try:
            font = ImageFont.truetype(font_name, size)
            # 缓存找到的字体
            _CACHED_FONT[font_key] = font
            return font
        except:
            continue
    
    # 如果缓存中已有，直接返回
    if font_key in _CACHED_FONT:
        return _CACHED_FONT[font_key]
    
    # 最后才使用默认字体（但不支持中文）
    font = ImageFont.load_default()
    _CACHED_FONT[font_key] = font
    return font

def _get_frame_image(frame_type, stars=3):
    cache_key = f"{frame_type}_{stars}"
    if cache_key in _CACHED_FRAMES:
        return _CACHED_FRAMES[cache_key]
    
    paths = {
        "outer": LEVEL_DIR / "gacha_tmb_frame.png",
        "inner_1": LEVEL_DIR / "gacha_tmb_02_01.png",
        "inner_2": LEVEL_DIR / "gacha_tmb_03_01.png",
        "inner_3": LEVEL_DIR / "gacha_tmb_04_01.png",
    }
    
    if frame_type == "outer":
        path = paths["outer"]
    elif stars == 1:
        path = paths["inner_1"]
    elif stars == 2:
        path = paths["inner_2"]
    else:
        path = paths["inner_3"]
    
    if path.exists():
        img = Image.open(str(path)).convert('RGBA')
        _CACHED_FRAMES[cache_key] = img
        return img
    return None

def _find_character_icon(chara_id):
    try:
        chara_id_int = int(float(chara_id))
    except:
        return None
    
    patterns = [
        f"card_cutin_{chara_id_int:09d}.png",
        f"card_cutin_{chara_id_int}.png",
        f"{chara_id_int:03d}.png",
        f"{chara_id_int}.png",
        f"chara_{chara_id_int:03d}.png",
        f"chara_{chara_id_int}.png",
    ]
    
    for pattern in patterns:
        path = ICON_DIR / pattern
        if path.exists():
            return str(path)
    
    for pattern in [f"card_cutin_{chara_id_int}*.png", f"*{chara_id_int}*.png"]:
        matches = list(ICON_DIR.glob(pattern))
        if matches:
            return str(matches[0])
    
    return None

def _get_state_icon(effect_name):
    # Debuff关键词（负面效果）
    debuff_keywords = ["下降", "封印", "沉默", "冻结", "昏迷", "流血", "灼烧", "中毒", "减伤",
                       "妨害", "被害", "感电", "气绝", "不能", "DOWN"]
    is_debuff = any(kw in effect_name for kw in debuff_keywords)
    
    icon_map = {
        # === 攻击/防御 ===
        "攻击": "state_icon_ATK_UP.png", "物攻提升": "state_icon_ATK_UP.png",
        "物攻下降": "state_icon_ATK_DOWN.png", "异攻提升": "state_icon_INT_UP.png",
        "异攻下降": "state_icon_INT_DOWN.png", "防御": "state_icon_DEF_UP.png",
        "物防提升": "state_icon_DEF_UP.png", "物防下降": "state_icon_DEF_DOWN.png",
        "异防提升": "state_icon_MIND_UP.png", "异防下降": "state_icon_MIND_DOWN.png",
        # === 暴击 ===
        "暴伤": "state_icon_CRITICAL_DAMAGE_RATE_UP.png", "暴伤提升": "state_icon_CRITICAL_DAMAGE_RATE_UP.png",
        "暴击率": "state_icon_CRITICAL_RESIST_RATE_UP.png", "暴击率提升": "state_icon_CRITICAL_RESIST_RATE_UP.png",
        "暴击防御": "state_icon_CRITICAL_DAMAGE_RATE_UP.png", "暴击防御提升": "state_icon_CRITICAL_DAMAGE_RATE_UP.png",
        # === 技能/必杀 ===
        "必杀威力": "state_icon_SKILL_DAMAGE_UP.png", "必杀威力提升": "state_icon_SKILL_DAMAGE_UP.png",
        "技能威力": "state_icon_SKILL_DAMAGE_UP.png", "技能威力提升": "state_icon_SKILL_DAMAGE_UP.png",
        # === SP ===
        "SP获得量": "state_icon_SP_UP.png", "SP获得量提升": "state_icon_SP_UP.png",
        # === 特殊防御 ===
        "盾": "state_icon_DAMAGE_COVER.png", "获得盾": "state_icon_DAMAGE_COVER.png",
        "不屈": "state_icon_GUTS.png", "减伤": "state_icon_DAMAGE_COVER.png",
        "回避率": "state_icon_SPECIAL_ENHANCED.png", "回避率提升": "state_icon_SPECIAL_ENHANCED.png",
        # === 特殊buff ===
        "必暴": "state_icon_CRITICAL_RESIST_RATE_UP.png",
        "贯通": "state_icon_PIERCING.png",
        "强耐": "state_icon_STATE_RESIST.png",
        "弱耐": "state_icon_STATE_RESIST.png",
        "嘲讽": "state_icon_TARGET_RED_DAMAGE_UP.png",
        # === 控制类debuff ===
        "封印": "state_icon_SEAL.png", "a卡封印": "state_icon_SILENCE.png",
        "技能封印": "state_icon_SEAL.png", "必杀封印": "state_icon_SEAL.png",
        "气绝": "state_icon_FAINT.png", "感电": "state_icon_SHOCK.png",
        "制御不能": "state_icon_UNCONTROL.png", "移动不能": "state_icon_WORLD_MOVE.png",
        "冻结": "state_icon_FREEZE.png", "昏迷": "state_icon_FAINT.png",
        "沉默": "state_icon_SILENCE.png",
        # === DoT ===
        "流血": "state_icon_BLEED.png", "灼烧": "state_icon_BURN.png",
        "中毒": "state_icon_BLEED.png", "持续被害": "state_icon_BLEED.png",
        # === 妨害 ===
        "强化妨害": "state_icon_VOID_BUFF_CONDITION_BAD.png",
        "弱体化解除妨害": "state_icon_VOID_BUFF_CONDITION_BAD.png",
        # === 矢/反射 ===
        "矢量操作": "state_icon_VECTOR_CONVERSION.png",
        "强制咏唱待机": "state_icon_SPELL_INTERCEPT.png",
        "全能神": "state_icon_SPELL_INTERCEPT.png",
        "预测不能": "state_icon_INVISIBLE_MONSTER.png",
        "天罚": "state_icon_DIVINE_RETRIBUTION_SPELL.png",
        # === 攻击方向 ===
        "攻击方向+": "state_icon_ATTACK_DIR_UP.png",
        "攻击方向-": "state_icon_ATTACK_DIR_DOWN.png",
        # === 属性颜色 ===
        "红": "state_icon_RED_RESIST_UP.png", "绿": "state_icon_GREEN_RESIST_UP.png",
        "蓝": "state_icon_BLUE_RESIST_UP.png", "黄": "state_icon_YELLOW_RESIST_UP.png",
        "紫": "state_icon_PURPLE_RESIST_UP.png",
        # === 回复 ===
        "HP回复": "state_icon_VOID_HP_HEAL.png",
        # === 反伤 ===
        "反射": "state_icon_MIRROR_ATTACK.png",
        "吸收": "state_icon_DAMAGE_ZERO.png",
    }
    # 颜色关键词映射到对应图标
    _color_resist = {"红":"RED","绿":"GREEN","蓝":"BLUE","黄":"YELLOW","紫":"PURPLE"}
    for _color, _code in _color_resist.items():
        icon_map[f"对{_color}色威力提升"] = f"state_icon_TARGET_{_code}_DAMAGE_UP.png"
        icon_map[f"{_color}色耐性下降"] = f"state_icon_{_code}_RESIST_DOWN.png"
        icon_map[f"{_color}色耐性提升"] = f"state_icon_{_code}_RESIST_UP.png"
    
    for keyword, icon_name in icon_map.items():
        if keyword in effect_name:
            # 如果是debuff，尝试使用对应的DOWN图标
            if is_debuff:
                base_name = icon_name.replace("_UP.png", "_DOWN.png")
                down_path = STATE_DIR / base_name
                if down_path.exists():
                    return str(down_path)
            
            icon_path = STATE_DIR / icon_name
            if icon_path.exists():
                return str(icon_path)
    return None

def _parse_arrow(name):
    for arrow in ['↖', '↑', '↗', '←', '↓', '→', '↙', '↘']:
        if arrow in name:
            return arrow
    return None

def _extract_base_name(name):
    """提取基础名字（去掉箭头和称号）"""
    # 去掉箭头
    name = re.sub(r'\[[↖↙←↑↓→↗↘]\]', '', name)
    # 去掉称号【】
    name = re.sub(r'【[^】]+】', '', name)
    return name.strip()

def _render_character_card(unit, card_w, card_h):
    output = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)

    if unit.get("is_empty", False):
        draw.rectangle([0, 0, card_w, card_h], fill=COLOR_EMPTY)
        draw.rectangle([0, 0, card_w, card_h], outline=(70, 70, 90), width=2)
        return output

    card_id = str(unit.get("card_id", ""))
    name = unit.get("name", "")
    stars = int(unit.get("stars", 3))
    
    icon_path = _find_character_icon(card_id)
    outer_frame = _get_frame_image("outer")
    inner_frame = _get_frame_image("inner", stars)
    
    if icon_path and os.path.exists(icon_path):
        try:
            char_img = Image.open(icon_path).convert('RGBA')
            char_width, char_height = char_img.size
            crop_left = int(char_width * CROP_LEFT_RATIO)
            crop_right = int(char_width * CROP_RIGHT_RATIO)
            crop_top = int(char_height * CROP_TOP_RATIO)
            crop_bottom = int(char_height * CROP_BOTTOM_RATIO)
            char_cropped = char_img.crop((crop_left, crop_top, crop_right, crop_bottom))
            
            cropped_w, cropped_h = char_cropped.size
            cropped_ratio = cropped_w / cropped_h
            
            if cropped_ratio > 1:
                char_target_w = int(card_w * 0.8)
                char_target_h = int(char_target_w / cropped_ratio)
            else:
                char_target_h = int(card_h * 0.8)
                char_target_w = int(char_target_h * cropped_ratio)
            
            char_resized = char_cropped.resize((char_target_w, char_target_h), Image.Resampling.LANCZOS)
            char_x = (card_w - char_target_w) // 2
            char_y = (card_h - char_target_h) // 2
            
            if inner_frame:
                inner_scaled = inner_frame.resize((card_w, card_h), Image.Resampling.LANCZOS)
                output.paste(inner_scaled, (0, 0), inner_scaled)
            
            output.paste(char_resized, (char_x, char_y), char_resized)
            
            if outer_frame:
                outer_scaled = outer_frame.resize((card_w, card_h), Image.Resampling.LANCZOS)
                output.paste(outer_scaled, (0, 0), outer_scaled)
        
        except Exception as e:
            draw.rectangle([0, 0, card_w, card_h], fill=(65, 65, 65))
            font = _get_font(9)
            short_name = name[:5] + ".." if len(name) > 5 else name
            try:
                tw = draw.textlength(short_name, font=font)
            except:
                tw = len(short_name) * 5
            tx = (card_w - tw) // 2
            draw.text((tx, card_h // 2 - 5), short_name, fill=(160, 160, 160), font=font)
            return output
    else:
        draw.rectangle([0, 0, card_w, card_h], fill=(65, 65, 65))
        font = _get_font(9)
        short_name = name[:5] + ".." if len(name) > 5 else name
        try:
            tw = draw.textlength(short_name, font=font)
        except:
            tw = len(short_name) * 5
        tx = (card_w - tw) // 2
        draw.text((tx, card_h // 2 - 5), short_name, fill=(160, 160, 160), font=font)
        return output
    
    alive = unit.get("alive", True)
    if isinstance(alive, str):
        alive = alive.lower() == 'true'
    
    # 阵亡角色处理：显示灰色占位符和X标记
    if not alive:
        # 创建灰色背景
        draw.rectangle([0, 0, card_w, card_h], fill=(50, 50, 50))
        # 添加红色覆盖层
        overlay = Image.new('RGBA', (card_w, card_h), (90, 0, 0, 100))
        output.paste(overlay, (0, 0), overlay)
        draw = ImageDraw.Draw(output)
        # 显示X标记
        draw.text((card_w//2 - 10, card_h//2 - 10), "X", fill=(255, 40, 40), font=_get_font(28))
        return output
    
    return output

def _render_buff_icons(canvas, x, y, buffs, debuffs, max_width):
    icons = []
    if not isinstance(buffs, list): buffs = []
    if not isinstance(debuffs, list): debuffs = []
    
    for b in buffs[:6]:
        icon_path = _get_state_icon(b.get("name", ""))
        if icon_path:
            icons.append((icon_path, False))
    for d in debuffs[:6]:
        icon_path = _get_state_icon(d.get("name", ""))
        if icon_path:
            icons.append((icon_path, True))
    
    row = col = 0
    max_row = 2
    
    for icon_path, is_debuff in icons:
        ix = x + col * (ICON_SIZE + ICON_GAP)
        iy = y + row * (ICON_SIZE + ICON_GAP)
        
        if ix + ICON_SIZE > x + max_width:
            row += 1
            col = 0
            ix = x
        
        if row >= max_row:
            break
        
        try:
            icon_img = Image.open(icon_path).convert('RGBA')
            icon_img = icon_img.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
            canvas.paste(icon_img, (ix, iy), icon_img)
        except:
            draw = ImageDraw.Draw(canvas)
            bg = (90, 25, 25) if is_debuff else (25, 90, 25)
            draw.rectangle([ix, iy, ix + ICON_SIZE, iy + ICON_SIZE], fill=bg)
        
        col += 1
    
    return (row + 1) * (ICON_SIZE + ICON_GAP)

def _render_hp_bar(draw, x, y, w, h, current_hp, max_hp):
    draw.rectangle([x, y, x+w, y+h], fill=COLOR_HP_BG)
    
    pct = current_hp / max_hp if max_hp > 0 else 0
    
    if pct > 0.5:
        color = COLOR_HP_HIGH
    elif pct > 0.25:
        color = COLOR_HP_MEDIUM
    else:
        color = COLOR_HP_LOW
    
    if pct > 0:
        fill_w = int((w - 4) * pct)
        draw.rectangle([x+2, y+2, x+2+fill_w, y+h-2], fill=color)
    
    font = _get_font(9)
    hp_text = f"{current_hp}/{max_hp}"
    try:
        tw = draw.textlength(hp_text, font=font)
    except:
        tw = len(hp_text) * 5
    tx = x + (w - tw) // 2
    draw.text((tx, y + 1), hp_text, fill=COLOR_TEXT_WHITE, font=font)

def _render_hp_change(draw, x, y, w, delta, tag):
    if delta == 0:
        return y + 16
    
    font = _get_font(12)
    
    if delta < 0:
        color = COLOR_DAMAGE
        bg = COLOR_DAMAGE_BG
        tag_text = f"【{tag}】" if tag else ""
        text = f"-{abs(delta)}{tag_text}"
    else:
        color = COLOR_HEAL
        bg = COLOR_HEAL_BG
        tag_text = f"【{tag}】" if tag else ""
        text = f"+{delta}{tag_text}"
    
    try:
        tw = draw.textlength(text, font=font)
    except:
        tw = len(text) * 8
    
    box_w = min(tw + 6, w)
    draw.rectangle([x, y, x + box_w, y + 14], fill=bg)
    draw.rectangle([x, y, x + box_w, y + 14], outline=(140, 140, 140), width=1)

    draw.text((x + 3, y + 3), text, fill=color, font=font)
    
    return y + 16


def _render_sp_bars(draw, x, y, w, player_sp, enemy_sp, max_sp=300):
    """在回合信息下方渲染双方SP条"""
    bar_h = 10
    gap = 4
    font_sp = _get_font(9)

    # 玩家SP条（蓝色）
    p_pct = min(1.0, player_sp / max_sp) if max_sp > 0 else 0
    draw.rectangle([x, y, x + w, y + bar_h], fill=(20, 20, 45))
    if p_pct > 0:
        fill_w = int((w - 2) * p_pct)
        draw.rectangle([x + 1, y + 1, x + 1 + fill_w, y + bar_h - 1], fill=(55, 110, 240))
    label_p = f"P-SP: {player_sp}/{max_sp}"
    try:
        tw = draw.textlength(label_p, font=font_sp)
    except:
        tw = len(label_p) * 9
    draw.text((x + (w - tw) // 2, y + 3), label_p, fill=(200, 220, 255), font=font_sp)

    y += bar_h + gap

    # 敌方SP条（红色）
    e_pct = min(1.0, enemy_sp / max_sp) if max_sp > 0 else 0
    draw.rectangle([x, y, x + w, y + bar_h], fill=(20, 20, 45))
    if e_pct > 0:
        fill_w = int((w - 2) * e_pct)
        draw.rectangle([x + 1, y + 1, x + 1 + fill_w, y + bar_h - 1], fill=(240, 65, 65))
    label_e = f"E-SP: {enemy_sp}/{max_sp}"
    try:
        tw = draw.textlength(label_e, font=font_sp)
    except:
        tw = len(label_e) * 9
    draw.text((x + (w - tw) // 2, y + 3), label_e, fill=(255, 200, 200), font=font_sp)

    return y + bar_h  # 返回SP条区域底部的y坐标


def _render_team_section(field_units, hp_changes, attack_directions, is_enemy=False):
    card_w = CARD_WIDTH
    card_h = CARD_HEIGHT
    gap = 10
    num_cols = 5  # 5列战场布局
    
    icon_area_h = 2 * (ICON_SIZE + ICON_GAP) + 4
    total_h = icon_area_h + card_h + HP_BAR_HEIGHT + 60
    total_w = num_cols * card_w + (num_cols - 1) * gap
    
    frame = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)
    
    positioned_units = [None] * 5
    unit_info = [None] * 5
    
    for u in field_units:
        if u.get("is_empty"):
            continue
        
        alive = u.get("alive", True)
        if isinstance(alive, str):
            alive = alive.lower() == 'true'
        
        # 即使角色阵亡也显示（用于显示阵亡过程）
        pos = u.get("position", -1)
        if 0 <= pos < 5:
            positioned_units[pos] = u
            unit_info[pos] = u
    
    for i in range(5):
        if positioned_units[i] is None:
            positioned_units[i] = {
                "is_empty": True, "name": "", "hp": 0, "max_hp": 1,
                "alive": True, "buffs": [], "debuffs": []
            }
    
    for col in range(5):
        x = col * (card_w + gap)
        unit = positioned_units[col]
        
        buffs = unit.get("buffs", [])
        debuffs = unit.get("debuffs", [])
        _render_buff_icons(frame, x, 2, buffs, debuffs, card_w)

        card = _render_character_card(unit, card_w, card_h)
        card_y = icon_area_h
        frame.paste(card, (x, card_y), card)

        hp_y = card_y + card_h + 3

        if not unit.get("is_empty"):
            # 渲染角色的相对攻击方向箭头（来自Excel数据，显示在卡片上方）
            atk_dirs = unit.get("attack_directions", [0])
            if isinstance(atk_dirs, list):
                dir_offsets = sorted(atk_dirs)
            elif atk_dirs == 3:
                dir_offsets = [-1, 0, 1]
            elif atk_dirs == 2:
                dir_offsets = [-1, 0]
            else:
                dir_offsets = [0]

            arrow_map_p = {-1: '↙', 0: '↓', 1: '↘'}
            arrow_map_e = {-1: '↖', 0: '↑', 1: '↗'}
            arrow_map = arrow_map_e if is_enemy else arrow_map_p
            dir_text = ''.join(arrow_map.get(o, '?') for o in sorted(dir_offsets))

            if dir_text:
                font_dir = _get_font(11)
                try:
                    dtw = draw.textlength(dir_text, font=font_dir)
                except:
                    dtw = len(dir_text) * 8
                dtx = x + (card_w - dtw) // 2
                dty = card_y - 14
                draw.rectangle([dtx - 3, dty - 1, dtx + dtw + 3, dty + 13], fill=(0, 0, 0, 170))
                draw.text((dtx, dty), dir_text, fill=COLOR_TEXT_GOLD, font=font_dir)

            current_hp = max(0, int(unit.get("hp", 0) or 0))
            max_hp = max(1, int(unit.get("max_hp", 1) or 1))
            _render_hp_bar(draw, x, hp_y, card_w, HP_BAR_HEIGHT, current_hp, max_hp)

            change_y = hp_y + HP_BAR_HEIGHT + 3
            # HP变化显示在当前列的角色下方
            if hp_changes and col in hp_changes:
                changes = hp_changes[col]
                for delta, tag in changes[:2]:
                    change_y = _render_hp_change(draw, x, change_y, card_w, delta, tag)

    return frame

def init_field_units(units_raw):
    field = []
    bench = []
    
    for u in units_raw:
        if u.get("is_assist") or str(u.get("is_assist", "")).lower() == 'true':
            continue
        
        name = u.get("name", "")
        max_hp = int(u.get("max_hp", u.get("hp", 10000)) or 10000)
        current_hp = int(u.get("hp", max_hp))
        card_id = u.get("card_id", "")
        stars = int(u.get("stars", 3))
        alive = u.get("alive", True)
        if isinstance(alive, str):
            alive = alive.lower() == 'true'
        
        # 优先使用数据中的position字段
        pos = u.get("position", -1)
        if pos < 0 or pos >= 5:
            # 如果position无效，从名称解析箭头
            arrow = _parse_arrow(name)
            pos = ARROW_TO_COL.get(arrow, -1) if arrow else -1
        
        # 攻击方向：优先使用数据中的列表，否则从stars推断（3星默认3方向，其他默认1方向）
        atk_dirs = u.get("attack_directions", None)
        if atk_dirs is None:
            atk_dirs = [-1, 0, 1] if stars >= 3 else [0]

        unit_data = {
            "name": name,
            "base_name": _extract_base_name(name),
            "card_id": card_id,
            "stars": stars,
            "max_hp": max_hp,
            "hp": current_hp,
            "alive": alive,
            "position": pos,
            "attack_directions": atk_dirs,
            "buffs": u.get("buffs", []),
            "debuffs": u.get("debuffs", []),
        }
        
        # 场上位置为0-4，position=-1表示在替补队列
        if 0 <= pos < 5:
            field.append(unit_data)
        else:
            unit_data["position"] = -1
            bench.append(unit_data)
    
    return field + bench[:3]


def _parse_battle_log(log, player_units_raw, enemy_units_raw):
    frames_data = []
    
    p_field = init_field_units(player_units_raw)
    e_field = init_field_units(enemy_units_raw)
    
    round_num = 1
    turn = "玩家行动"
    p_deltas = {}
    e_deltas = {}
    p_attack_dirs = {}
    e_attack_dirs = {}
    
    def save_frame(phase=""):
        frames_data.append({
            "round": round_num,
            "turn": turn,
            "phase": phase,
            "player_field": copy.deepcopy(p_field),
            "enemy_field": copy.deepcopy(e_field),
            "player_deltas": p_deltas.copy(),
            "enemy_deltas": e_deltas.copy(),
            "player_attack_dirs": p_attack_dirs.copy(),
            "enemy_attack_dirs": e_attack_dirs.copy(),
        })
    
    save_frame("战斗开始")
    
    for entry in log:
        if isinstance(entry, bytes):
            line = entry.decode('utf-8', errors='replace')
        else:
            line = str(entry).strip()
        
        if not line:
            continue
        
        m = re.search(r'第\s*(\d+)\s*回合', line)
        if m:
            round_num = int(m.group(1))
            p_deltas = {}
            e_deltas = {}
            save_frame(f"第{round_num}回合")
            continue
        
        if "[Player turn]" in line:
            turn = "玩家行动"
            p_deltas = {}
            e_deltas = {}
            continue
        if "[Enemy turn]" in line:
            turn = "敌方行动"
            p_deltas = {}
            e_deltas = {}
            continue
        
        m = re.match(r'\[换位\]\s*\[([PE])\]\s*(.+?)\s*\[([↖↙←↑↓→↗↘])\]\s*->\s*([↖↙←↑↓→↗↘])', line)
        if m:
            tag, name, old_arrow, new_arrow = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
            field = p_field if tag == 'P' else e_field
            
            old_pos = ARROW_TO_COL.get(old_arrow, -1)
            new_pos = ARROW_TO_COL.get(new_arrow, -1)
            if new_pos >= 0 and new_pos <= 4:
                moving_unit = None
                target_unit = None
                
                for u in field:
                    base = u.get("base_name", "")
                    if name in u["name"] or base in name or name in base:
                        moving_unit = u
                    if u["position"] == new_pos and u != moving_unit:
                        target_unit = u
                
                if moving_unit:
                    if target_unit:
                        target_unit["position"] = old_pos
                        old_arrow_sym = COL_TO_ARROW_P.get(old_pos) if tag == 'P' else COL_TO_ARROW_E.get(old_pos)
                        target_unit["name"] = f"{target_unit.get('base_name', '')}[{old_arrow_sym}]"
                    
                    moving_unit["position"] = new_pos
                    new_arrow_sym = COL_TO_ARROW_P.get(new_pos) if tag == 'P' else COL_TO_ARROW_E.get(new_pos)
                    moving_unit["name"] = f"{name}[{new_arrow_sym}]"
            
            save_frame("换位")
            continue
        
        m = re.match(r'\[上场\]\s*\[([PE])\]\s*(.+?)\s*\[([↖↙←↑↓→↗↘])\]', line)
        if m:
            tag, name, arrow = m.group(1), m.group(2).strip(), m.group(3)
            field = p_field if tag == 'P' else e_field
            
            target_pos = ARROW_TO_COL.get(arrow, -1)
            if target_pos >= 0 and target_pos <= 4:
                # 找一个阵亡的角色来代替
                dead_units = [u for u in field if not u["alive"]]
                # 同时找替补队列中的角色（position=-1）
                # name可能包含称号【】，base_name已经去掉了称号，所以需要模糊匹配
                bench_units = []
                for u in field:
                    if u["position"] == -1:
                        u_base_name = u.get("base_name", "")
                        u_full_name = u.get("name", "")
                        # 匹配方式：name在u的full name中，或者base_name在name中，或者name在base_name中
                        if name in u_full_name or u_base_name in name or name in u_base_name:
                            bench_units.append(u)
                
                if dead_units and bench_units:
                    dead = dead_units[0]
                    bench_unit = bench_units[0]
                    arrow_sym = COL_TO_ARROW_P.get(target_pos) if tag == 'P' else COL_TO_ARROW_E.get(target_pos)
                    dead["name"] = f"{name}[{arrow_sym}]"
                    dead["base_name"] = _extract_base_name(name)
                    dead["alive"] = True
                    dead["hp"] = bench_unit["max_hp"]
                    dead["max_hp"] = bench_unit["max_hp"]
                    dead["position"] = target_pos
                    dead["buffs"] = []
                    dead["debuffs"] = []
                    dead["card_id"] = bench_unit["card_id"]
                    dead["stars"] = bench_unit["stars"]
                    # 从替补队列中移除该角色
                    field.remove(bench_unit)
            
            save_frame("替补上场")
            continue
        
        m = re.match(r'\([\d.]+\)\s*(.+?)\[([↖↙←↑↓→↗↘])\]\s*->\s*(.+?)\[([↖↙←↑↓→↗↘])\]\s*\((\d+).*\[(.+?)\]', line)
        if m:
            attacker_name = m.group(1).strip()
            attacker_arrow = m.group(2)
            target_name = m.group(3).strip()
            target_arrow = m.group(4)
            damage = int(m.group(5))
            atk_type = m.group(6)
            
            atk_short = "终" if "必杀" in atk_type else "技" if "技能" in atk_type else "普"
            
            attacker_is_player = any(attacker_name in u["name"] or u["base_name"] in attacker_name for u in p_field)
            
            if attacker_is_player:
                target_field = e_field
                target_deltas = e_deltas
                atk_dirs = p_attack_dirs
                atk_field = p_field
            else:
                target_field = p_field
                target_deltas = e_deltas
                atk_dirs = e_attack_dirs
                atk_field = e_field
            
            p_attack_dirs = {}
            e_attack_dirs = {}
            
            for u in atk_field:
                if attacker_name in u["name"] or u["base_name"] in attacker_name:
                    if u["position"] >= 0 and u["position"] < 5:
                        # 存储攻击者箭头和目标箭头
                        atk_dirs[u["position"]] = [attacker_arrow, target_arrow]
                    break
            
            for u in target_field:
                if target_name in u["name"] or u["base_name"] in target_name:
                    u["hp"] = max(0, u["hp"] - damage)
                    if u["hp"] <= 0:
                        u["hp"] = 0
                        u["alive"] = False
                        u["buffs"] = []
                        u["debuffs"] = []
                        u["position"] = -1
                    idx = target_field.index(u)
                    target_deltas.setdefault(idx, []).append((-damage, f"[{atk_short}]"))
                    break
            
            save_frame("攻击")
            continue

        m = re.search(r'HP回复\+(\d+)', line)
        if m:
            heal = int(m.group(1))
            tag = "[A]" if "[A]" in line else "[自]"
            
            m2 = re.match(r'(.+?)\[([↖↙←↑↓→↗↘])\].*HP回复', line)
            if m2:
                target_name = m2.group(1).strip()
                
                for field, deltas in [(p_field, p_deltas), (e_field, e_deltas)]:
                    for u in field:
                        if target_name in u["name"] or u["base_name"] in target_name:
                            u["hp"] = min(u["max_hp"], u["hp"] + heal)
                            idx = field.index(u)
                            deltas.setdefault(idx, []).append((heal, tag))
                            break
            continue
        
        if '[A]' in line and 'HP回复' not in line and '伤害' not in line:
            m = re.match(r'(.+?)\[([↖↙←↑↓→↗↘])\]\s*(.+?)\s*\[A\]', line)
            if m:
                source_name = m.group(1).strip()
                effects_str = m.group(3).strip()
                
                effects = [e.strip() for e in effects_str.split(',')]
                
                for effect in effects:
                    eff_match = re.match(r'(.+?)\[([↖↙←↑↓→↗↘])\]\s*(.+)', effect)
                    if eff_match:
                        target_name_raw = eff_match.group(1).strip()
                        effect_name = eff_match.group(3).strip()
                    else:
                        target_name_raw = source_name
                        effect_name = effect
                    
                    is_debuff = any(kw in effect_name for kw in ["下降", "封印", "移动不能"])
                    key = "debuffs" if is_debuff else "buffs"
                    
                    for field in [p_field, e_field]:
                        for u in field:
                            if target_name_raw in u["name"] or u["base_name"] in target_name_raw:
                                u[key].append({"name": effect_name})
                                break
            continue
    
    save_frame("战斗结束")
    
    return frames_data

def _parse_parsable_log(parsable_log, p_raw, e_raw):
    """解析程序化日志生成战斗帧"""
    frames_data = []
    
    # 创建单位字典，从原始数据获取基础信息
    p_units_dict = {}
    for u in p_raw:
        if u.get("is_assist") or str(u.get("is_assist", "")).lower() == 'true':
            continue
        name = u.get("name", "")
        base_name = _extract_base_name(name)
        atk_dirs_raw = u.get("attack_directions", 3 if int(u.get("stars", 3)) >= 3 else 1)
        p_units_dict[base_name] = {
            "name": name,
            "base_name": base_name,
            "card_id": u.get("card_id", ""),
            "stars": int(u.get("stars", 3)),
            "max_hp": int(u.get("max_hp", u.get("hp", 10000)) or 10000),
            "hp": int(u.get("hp", 10000)),
            "alive": u.get("alive", True),
            "position": -1,
            "attack_directions": atk_dirs_raw,
            "buffs": u.get("buffs", []),
            "debuffs": u.get("debuffs", []),
        }

    e_units_dict = {}
    for u in e_raw:
        if u.get("is_assist") or str(u.get("is_assist", "")).lower() == 'true':
            continue
        name = u.get("name", "")
        base_name = _extract_base_name(name)
        atk_dirs_raw = u.get("attack_directions", 3 if int(u.get("stars", 3)) >= 3 else 1)
        e_units_dict[base_name] = {
            "name": name,
            "base_name": base_name,
            "card_id": u.get("card_id", ""),
            "stars": int(u.get("stars", 3)),
            "max_hp": int(u.get("max_hp", u.get("hp", 10000)) or 10000),
            "hp": int(u.get("hp", 10000)),
            "alive": u.get("alive", True),
            "position": -1,
            "attack_directions": atk_dirs_raw,
            "buffs": u.get("buffs", []),
            "debuffs": u.get("debuffs", []),
        }

    round_num = 1
    turn = "player"  # 初始设置为player，等待第一个turn_switch事件
    player_sp = 0
    enemy_sp = 0

    # 初始化玩家和敌方单位字典
    p_field = []
    e_field = []
    
    def init_field_from_log(positions, units_dict):
        """从程序化日志位置信息初始化场上单位"""
        field = [None] * 5
        bench = []
        
        for pos_info in positions:
            name = pos_info.get("name", "")
            base_name = _extract_base_name(name)
            
            if base_name in units_dict:
                unit = dict(units_dict[base_name])
                unit["position"] = pos_info.get("position", -1)
                unit["alive"] = pos_info.get("alive", True)
                unit["hp"] = pos_info.get("hp", unit["max_hp"])
                unit["max_hp"] = pos_info.get("max_hp", unit["max_hp"])
                unit["hp_change"] = pos_info.get("hp_change", 0)
                
                # 从程序化日志获取BUFF信息（如果有）
                if "buffs" in pos_info:
                    unit["buffs"] = pos_info["buffs"]
                if "debuffs" in pos_info:
                    unit["debuffs"] = pos_info["debuffs"]
                
                # 更新名称（包含箭头）
                arrow = _parse_arrow(name)
                if arrow:
                    unit["name"] = name
                
                if 0 <= unit["position"] < 5:
                    field[unit["position"]] = unit
                else:
                    unit["position"] = -1
                    bench.append(unit)
        
        # 填充空位
        for i in range(5):
            if field[i] is None:
                field[i] = {
                    "is_empty": True, "name": "", "hp": 0, "max_hp": 1,
                    "alive": True, "position": i, "buffs": [], "debuffs": [],
                    "base_name": "", "card_id": "", "stars": 0
                }
        
        return field + bench
    
    def save_frame(phase, p_field_data, e_field_data, attack_info=None, event_text=""):
        frame_data = {
            "round": round_num,
            "turn": turn,
            "phase": phase,
            "player_field": p_field_data,
            "enemy_field": e_field_data,
            "player_deltas": {},
            "enemy_deltas": {},
            "player_attack_dirs": {},
            "enemy_attack_dirs": {},
            "phase_text": phase,
            "attack_info": attack_info,
            "event_text": event_text.encode('utf-8').decode('utf-8', errors='replace'),
            "player_sp": player_sp,
            "enemy_sp": enemy_sp
        }
        frames_data.append(frame_data)
    
    # 从第一个round_start获取初始位置
    p_field = []
    e_field = []
    initial_set = False
    
    for entry in parsable_log:
        if entry.get("type") == "round_start" and not initial_set:
            p_positions = entry.get("player_positions", [])
            e_positions = entry.get("enemy_positions", [])
            p_field = init_field_from_log(p_positions, p_units_dict)
            e_field = init_field_from_log(e_positions, e_units_dict)
            
            # 确保敌方单位被正确初始化
            if not e_field or sum(1 for u in e_field if not u.get("is_empty")) == 0:
                # 如果敌方单位为空，从e_raw直接创建
                for u in e_raw:
                    if u.get("is_assist") or str(u.get("is_assist", "")).lower() == 'true':
                        continue
                    name = u.get("name", "")
                    pos = u.get("position", -1)
                    if 0 <= pos < 5 and not e_field[pos].get("is_empty"):
                        continue
                    for i in range(5):
                        if e_field[i].get("is_empty"):
                            e_field[i] = {
                                "name": name,
                                "base_name": _extract_base_name(name),
                                "card_id": u.get("card_id", ""),
                                "stars": int(u.get("stars", 3)),
                                "max_hp": int(u.get("max_hp", u.get("hp", 10000)) or 10000),
                                "hp": int(u.get("hp", u.get("max_hp", 10000))),
                                "alive": u.get("alive", True),
                                "position": pos,
                                "buffs": u.get("buffs", []),
                                "debuffs": u.get("debuffs", []),
                            }
                            break
            
            # Fix 3: 清空初始帧的BUFF/DEBUFF（A卡预触发在round_start之前已施加buff，
            # 但未生成parsable条目，应展示干净的开局状态）
            for u in p_field:
                if not u.get("is_empty"):
                    u["buffs"] = []
                    u["debuffs"] = []
            for u in e_field:
                if not u.get("is_empty"):
                    u["buffs"] = []
                    u["debuffs"] = []

            save_frame("战斗开始", [dict(u) for u in p_field], [dict(u) for u in e_field])
            # 不保存"回合开始"帧，等待第一个turn_switch事件
            round_num = entry.get("round", round_num)
            initial_set = True
            break
    
    # 继续处理后续日志
    for entry in parsable_log:
        entry_type = entry.get("type")
        
        if entry_type == "round_start":
            if initial_set:
                round_num = entry.get("round", round_num)
                # 更新现有单位的状态，而不是重新初始化
                for pos_info in entry.get("player_positions", []):
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in p_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["hp"] = pos_info.get("hp", u["hp"])
                            u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                            u["alive"] = pos_info.get("alive", u["alive"])
                            u["position"] = pos_info.get("position", u["position"])
                            u["hp_change"] = pos_info.get("hp_change", 0)
                            # 更新箭头
                            arrow = _parse_arrow(name)
                            if arrow:
                                u["name"] = name
                            break
                for pos_info in entry.get("enemy_positions", []):
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in e_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["hp"] = pos_info.get("hp", u["hp"])
                            u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                            u["alive"] = pos_info.get("alive", u["alive"])
                            u["position"] = pos_info.get("position", u["position"])
                            u["hp_change"] = pos_info.get("hp_change", 0)
                            # 更新箭头
                            arrow = _parse_arrow(name)
                            if arrow:
                                u["name"] = name
                            break
                save_frame("回合开始", [dict(u) for u in p_field], [dict(u) for u in e_field])

        elif entry_type == "sp_info":
            # 更新SP值（不创建独立帧，SP值通过save_frame随下一帧输出）
            player_sp = entry.get("player_sp", player_sp)
            enemy_sp = entry.get("enemy_sp", enemy_sp)
            # 同步单位状态
            for pos_info in entry.get("player_positions", []):
                pos_base = _extract_base_name(pos_info.get("name", ""))
                for u in p_field:
                    if not u.get("is_empty") and u.get("base_name") == pos_base:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["position"] = pos_info.get("position", u["position"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break
            for pos_info in entry.get("enemy_positions", []):
                pos_base = _extract_base_name(pos_info.get("name", ""))
                for u in e_field:
                    if not u.get("is_empty") and u.get("base_name") == pos_base:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["position"] = pos_info.get("position", u["position"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break

        elif entry_type == "turn_switch":
            turn = entry.get("side", turn)
            # 更新现有单位的状态
            if "player_positions" in entry:
                for pos_info in entry["player_positions"]:
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in p_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["hp"] = pos_info.get("hp", u["hp"])
                            u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                            u["alive"] = pos_info.get("alive", u["alive"])
                            u["position"] = pos_info.get("position", u["position"])
                            u["hp_change"] = pos_info.get("hp_change", 0)
                            arrow = _parse_arrow(name)
                            if arrow:
                                u["name"] = name
                            break
            if "enemy_positions" in entry:
                for pos_info in entry["enemy_positions"]:
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in e_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["hp"] = pos_info.get("hp", u["hp"])
                            u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                            u["alive"] = pos_info.get("alive", u["alive"])
                            u["position"] = pos_info.get("position", u["position"])
                            u["hp_change"] = pos_info.get("hp_change", 0)
                            arrow = _parse_arrow(name)
                            if arrow:
                                u["name"] = name
                            break
            save_frame(f"{turn}回合", [dict(u) for u in p_field], [dict(u) for u in e_field])
        
        elif entry_type == "swap":
            side = entry.get("side")
            name = entry.get("name")
            new_pos = entry.get("new_position")
            new_arrow = entry.get("new_arrow")
            
            # 构建事件描述
            chara_name = _extract_base_name(name)
            pos_names = ["左下", "左中", "中", "右中", "右下"] if side == "P" else ["左上", "左中", "上", "右中", "右上"]
            event_text = f"{chara_name}: 换位→{pos_names[new_pos]}" if 0 <= new_pos < 5 else f"{chara_name}: 换位"
            
            field = p_field if side == "P" else e_field
            for u in field:
                if not u.get("is_empty") and u.get("base_name"):
                    if name and (u["base_name"] in name or name in u["base_name"]):
                        u["position"] = new_pos
                        if new_arrow:
                            u["name"] = f"{name}[{new_arrow}]"
                        break
            
            save_frame("换位", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
        elif entry_type == "enter":
            side = entry.get("side")
            name = entry.get("name")
            pos = entry.get("position", -1)
            arrow = entry.get("arrow")
            
            # 构建事件描述
            chara_name = _extract_base_name(name)
            event_text = f"{chara_name}: 替补上场"
            
            field = p_field if side == "P" else e_field
            units_dict = p_units_dict if side == "P" else e_units_dict
            
            base_name = _extract_base_name(name)
            if base_name in units_dict:
                # 使用事件中的position，如果没有则找一个阵亡位置
                target_pos = pos if 0 <= pos < 5 else -1
                
                # 确保目标位置有效
                if target_pos >= 0 and target_pos < 5:
                    # 直接替换该位置的角色（无论是否阵亡）
                    unit = dict(units_dict[base_name])
                    unit["position"] = target_pos
                    unit["alive"] = True
                    unit["hp"] = unit["max_hp"]
                    unit["name"] = f"{name}[{arrow}]" if arrow else name
                    unit["is_empty"] = False
                    unit["buffs"] = []   # 替补上场时清空buff
                    unit["debuffs"] = []  # 替补上场时清空debuff
                    field[target_pos] = unit
                else:
                    # 找一个阵亡位置或空位置
                    for i in range(5):
                        if field[i] and (field[i].get("is_empty") or not field[i].get("alive", True)):
                            target_pos = i
                            unit = dict(units_dict[base_name])
                            unit["position"] = target_pos
                            unit["alive"] = True
                            unit["hp"] = unit["max_hp"]
                            unit["name"] = f"{name}[{arrow}]" if arrow else name
                            unit["is_empty"] = False
                            unit["buffs"] = []   # 替补上场时清空buff
                            unit["debuffs"] = []  # 替补上场时清空debuff
                            field[target_pos] = unit
                            break
            
            save_frame("替补上场", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
        elif entry_type == "attack":
            attack_type = entry.get("attack_type", "普")
            attacker = entry.get("attacker", "")
            attacker_pos = entry.get("attacker_position", -1)
            attacker_arrow = entry.get("attacker_arrow", "")
            targets = entry.get("targets", [])

            # 提取攻击者名字（去掉称号）
            attacker_name = _extract_base_name(attacker)

            # Fix 1: 从position数据同步HP变化（攻击后血量应立即反映在帧中）
            for pos_info in entry.get("player_positions", []):
                pos_name = pos_info.get("name", "")
                pos_base = _extract_base_name(pos_name)
                for u in p_field:
                    if not u.get("is_empty") and u.get("base_name") == pos_base:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["position"] = pos_info.get("position", u["position"])
                        u["hp_change"] = pos_info.get("hp_change", 0)
                        break
            for pos_info in entry.get("enemy_positions", []):
                pos_name = pos_info.get("name", "")
                pos_base = _extract_base_name(pos_name)
                for u in e_field:
                    if not u.get("is_empty") and u.get("base_name") == pos_base:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["position"] = pos_info.get("position", u["position"])
                        u["hp_change"] = pos_info.get("hp_change", 0)
                        break

            # Fix 2A: 从hit_status提取特殊效果（盾抵挡/反射/回避/不屈等）
            hit_status_map = {
                "抵挡": "盾抵挡", "反射": "反射", "吸收": "吸收",
                "减伤": "减伤", "回避": "回避", "不屈": "不屈"
            }
            special_effects = []
            for side_positions in [
                entry.get("player_positions", []),
                entry.get("enemy_positions", []),
            ]:
                for pos_info in side_positions:
                    hs = pos_info.get("hit_status", "")
                    if hs:
                        name = _extract_base_name(pos_info.get("name", ""))
                        # hit_status是2字符中文token的拼接（如"抵挡反射"）
                        mapped_parts = []
                        i = 0
                        while i < len(hs):
                            token = hs[i:i+2]
                            mapped_parts.append(hit_status_map.get(token, token))
                            i += 2
                        special_effects.append(f"{name}: {'+'.join(mapped_parts)}")

            # 构建事件描述
            event_text = ""
            if targets:
                target_name = _extract_base_name(targets[0].get("name", ""))
                # 根据攻击类型确定效果描述
                effect_text = "伤害"
                if attack_type == "技":
                    effect_text = "技能"
                elif attack_type == "终":
                    effect_text = "必杀"
                elif attack_type == "A":
                    effect_text = "支援"
                event_text = f"{attacker_name} → {target_name}: {effect_text}"

            # 追加特殊效果到事件文本
            if special_effects:
                effect_str = " | ".join(special_effects)
                event_text = f"{event_text}  [{effect_str}]" if event_text else effect_str

            # 记录攻击信息到帧数据
            attack_info = {
                "type": "普" if attack_type in ["普", "普通攻击"] else attack_type,
                "attack_type": attack_type,
                "attacker": attacker,
                "attacker_position": attacker_pos,
                "attacker_arrow": attacker_arrow,
                "targets": targets
            }

            save_frame(f"攻击[{attack_type}]", [dict(u) for u in p_field], [dict(u) for u in e_field], attack_info, event_text)

            # Fix 6: 攻击帧已记录阵亡状态，将死单位移出场外（position=-1）
            # 后续帧显示空位，等待enter事件替补上场
            for u in p_field:
                if not u.get("is_empty") and not u.get("alive", True):
                    u["position"] = -1
                    u["buffs"] = []
                    u["debuffs"] = []
            for u in e_field:
                if not u.get("is_empty") and not u.get("alive", True):
                    u["position"] = -1
                    u["buffs"] = []
                    u["debuffs"] = []

        elif entry_type == "assist_prepare":
            # A卡效果触发前的帧
            assist_name = entry.get("assist_name", "")
            source_unit = entry.get("source_unit", "")
            trigger_type = entry.get("trigger_type", "")
            
            # 构建事件描述
            source_name = _extract_base_name(source_unit)
            event_text = f"{assist_name}: 准备触发效果"
            
            # 更新BUFF信息（从player_positions和enemy_positions获取）
            if "player_positions" in entry:
                for pos_info in entry["player_positions"]:
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in p_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break
            if "enemy_positions" in entry:
                for pos_info in entry["enemy_positions"]:
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in e_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break
            
            save_frame("A卡准备", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
        elif entry_type == "assist_trigger":
            # A卡效果触发后的帧
            assist_name = entry.get("assist_name", "")
            effects = entry.get("effects", [])
            source_unit = entry.get("source_unit", "")
            
            # 构建事件描述
            source_name = _extract_base_name(source_unit)
            effect_text = effects[0] if effects else "效果触发"
            # 简化效果描述
            if effect_text and '[A]' in effect_text:
                # 提取效果内容
                effect_match = re.match(r'(.+?)\s+(.+?)\s+\[A\]', effect_text)
                if effect_match:
                    target_char = effect_match.group(1)
                    effect_content = effect_match.group(2)
                    event_text = f"{assist_name} → {target_char}: {effect_content}"
                else:
                    event_text = f"{assist_name}: {effect_text.replace('[A]', '')}"
            else:
                event_text = f"{assist_name}: 效果触发"
            
            # 更新BUFF信息（从player_positions和enemy_positions获取）
            if "player_positions" in entry:
                for pos_info in entry["player_positions"]:
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in p_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break
            if "enemy_positions" in entry:
                for pos_info in entry["enemy_positions"]:
                    name = pos_info.get("name", "")
                    base_name = _extract_base_name(name)
                    for u in e_field:
                        if not u.get("is_empty") and u.get("base_name") == base_name:
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break
            
            save_frame("A卡触发", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
        elif entry_type == "battle_end":
            winner = entry.get("winner")
            # Fix 4: 标记败方所有单位为阵亡状态
            losing_field = e_field if winner == "player" else p_field
            for u in losing_field:
                if not u.get("is_empty"):
                    u["alive"] = False
                    u["hp"] = 0
                    u["buffs"] = []
                    u["debuffs"] = []
            reason = entry.get("reason", "")
            event_text = f"战斗结束: {'玩家' if winner == 'player' else '敌方'}胜利"
            if reason:
                event_text += f" ({reason})"
            save_frame(f"{winner}胜利", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
    
    return frames_data


def _calculate_hp_changes(frames_data, log):
    """从帧数据中提取HP变化信息并设置攻击方向"""
    import re
    
    # 从普通日志中提取攻击类型
    attack_pattern = re.compile(r'\[(普通攻击|技能|必杀|普|技|终|A)\]')
    attack_types = []
    for entry in log:
        if isinstance(entry, bytes):
            entry = entry.decode('utf-8', errors='replace')
        type_match = attack_pattern.search(entry)
        if type_match:
            type_str = type_match.group(1)
            if type_str in ["普通攻击", "普"]:
                attack_types.append("普")
            elif type_str in ["技能", "技"]:
                attack_types.append("技")
            elif type_str in ["必杀", "终"]:
                attack_types.append("终")
            elif type_str == "A":
                attack_types.append("A")
            else:
                attack_types.append("")
        else:
            attack_types.append("")
    
    # 使用帧数据中的hp_change字段来计算HP变化
    # 每帧都有自己的hp_change，不需要追踪上一帧
    
    for i in range(len(frames_data)):
        curr_frame = frames_data[i]
        p_deltas = {}
        e_deltas = {}
        p_attack_dirs = {}
        e_attack_dirs = {}
        
        # 从attack_info中提取攻击方向
        attack_info = curr_frame.get("attack_info")
        if attack_info:
            attacker_pos = attack_info.get("attacker_position", -1)
            attacker_arrow = attack_info.get("attacker_arrow", "")
            targets = attack_info.get("targets", [])
            
            if attacker_pos >= 0 and attacker_pos < 5 and attacker_arrow:
                target_arrow = targets[0].get("arrow", "") if targets else ""
                if curr_frame.get("turn") == "player":
                    p_attack_dirs[attacker_pos] = [attacker_arrow, target_arrow]
                else:
                    e_attack_dirs[attacker_pos] = [attacker_arrow, target_arrow]
        
        # 从帧数据中获取HP变化（直接使用player_field和enemy_field中的hp_change）
        for pos in range(5):
            unit = curr_frame["player_field"][pos]
            if not unit.get("is_empty"):
                hp_change = unit.get("hp_change", 0)
                if hp_change != 0:
                    atk_type = attack_info.get("type", "") if attack_info else ""
                    p_deltas[pos] = [(hp_change, atk_type)]
        
        for pos in range(5):
            unit = curr_frame["enemy_field"][pos]
            if not unit.get("is_empty"):
                hp_change = unit.get("hp_change", 0)
                if hp_change != 0:
                    atk_type = attack_info.get("type", "") if attack_info else ""
                    e_deltas[pos] = [(hp_change, atk_type)]
        
        curr_frame["player_deltas"] = p_deltas
        curr_frame["enemy_deltas"] = e_deltas
        curr_frame["player_attack_dirs"] = p_attack_dirs
        curr_frame["enemy_attack_dirs"] = e_attack_dirs
    
    return frames_data


def battle_to_gif_new(result, characters=None, output_path=None, frame_duration=1200, delete_old=True):
    """
    生成战斗GIF并保存到磁盘
    
    Args:
        result: 战斗结果字典
        characters: 角色数据字典（可选）
        output_path: 输出路径，默认为output/battle_时间戳.gif
        frame_duration: 每帧持续时间（毫秒）
        delete_old: 是否删除旧的GIF文件（默认True，只保留最新的）
    
    Returns:
        生成的GIF文件路径
    """
    parsable_log = result.get("parsable_log", [])
    log = result.get("log", [])
    p_raw = result.get("player_units", [])
    e_raw = result.get("enemy_units", [])
    
    # 优先使用程序化日志
    if parsable_log:
        frames_data = _parse_parsable_log(parsable_log, p_raw, e_raw)
    else:
        frames_data = _parse_battle_log(log, p_raw, e_raw)
    
    # 计算HP变化
    frames_data = _calculate_hp_changes(frames_data, log)
    
    if not frames_data:
        print("GIF生成失败：没有解析到战斗帧")
        return None
    
    frames = []
    total_frames = len(frames_data)
    
    for frame_idx, frame_data in enumerate(frames_data):
        e_frame = _render_team_section(
            frame_data["enemy_field"], 
            frame_data["enemy_deltas"], 
            frame_data.get("enemy_attack_dirs", {}), 
            True
        )
        p_frame = _render_team_section(
            frame_data["player_field"], 
            frame_data["player_deltas"], 
            frame_data.get("player_attack_dirs", {}), 
            False
        )
        
        EVENT_TEXT_HEIGHT = 30
        SP_BAR_HEIGHT = 28
        fw = max(e_frame.width, p_frame.width) + PADDING * 2
        fh = e_frame.height + SECTION_SPACING + p_frame.height + PADDING * 2 + EVENT_TEXT_HEIGHT + SP_BAR_HEIGHT

        bg = Image.new('RGB', (fw, fh), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(bg)

        # 显示事件描述（最上方）
        event_text = frame_data.get("event_text", "")
        if event_text:
            font_event = _get_font(14)
            try:
                tw = draw.textlength(event_text, font=font_event)
            except:
                tw = len(event_text) * 8
            tx = (fw - tw) // 2
            ty = 8
            # 添加半透明背景框
            draw.rectangle([tx - 8, ty - 4, tx + tw + 8, ty + 16], fill=(0, 0, 0, 180))
            draw.text((tx, ty), event_text, fill=(255, 255, 200), font=font_event)

        ex = (fw - e_frame.width) // 2
        bg.paste(e_frame, (ex, PADDING + EVENT_TEXT_HEIGHT), e_frame)

        font_small = _get_font(11)
        frame_text = f"[{frame_idx+1}/{total_frames}]"
        draw.text((12, 12 + EVENT_TEXT_HEIGHT), frame_text, fill=(160, 160, 160), font=font_small)

        font_center = _get_font(16)

        turn_text = "Player Turn" if frame_data['turn'] == "player" else "Enemy Turn"
        round_info = f"Round {frame_data['round']} - {turn_text}"

        try:
            tw = draw.textlength(round_info, font=font_center)
        except:
            tw = len(round_info) * 10

        cx = (fw - tw) // 2
        cy = e_frame.height + PADDING + 12 + EVENT_TEXT_HEIGHT

        draw.rectangle([cx - 12, cy - 10, cx + tw + 12, cy + 16], fill=COLOR_INFO_BG)
        draw.rectangle([cx - 10, cy - 8, cx + tw + 10, cy + 14], fill=COLOR_INFO_BORDER)

        draw.text((cx, cy), round_info, fill=COLOR_TEXT_GOLD, font=font_center)

        # SP条（回合信息下方）
        sp_y = cy + 22
        sp_w = fw - PADDING * 4
        sp_x = (fw - sp_w) // 2
        _render_sp_bars(draw, sp_x, sp_y, sp_w,
                       frame_data.get("player_sp", 0),
                       frame_data.get("enemy_sp", 0))

        px = (fw - p_frame.width) // 2
        py = e_frame.height + SECTION_SPACING + PADDING + EVENT_TEXT_HEIGHT + SP_BAR_HEIGHT
        bg.paste(p_frame, (px, py), p_frame)

        frames.append(bg)

    if frames:
        winner = result.get("winner", "draw")
        win_text_dict = {"player": "Player WIN!", "enemy": "Enemy WIN!", "draw": "Draw!"}
        win_text = win_text_dict.get(winner, "Battle End")

        # 创建独立的胜利帧（避免与最后一帧信息重叠）
        cw, ch = frames[-1].size
        last = Image.new('RGB', (cw, ch), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(last)
        font_win = _get_font(28)
        try:
            tw = draw.textlength(win_text, font=font_win)
        except:
            tw = len(win_text) * 20
        cx = (cw - tw) // 2
        cy = (ch - 40) // 2
        draw.rectangle([cx - 12, cy - 4, cx + tw + 12, cy + 32], fill=(0, 0, 0))
        draw.text((cx, cy), win_text, fill=(255, 215, 0), font=font_win)
        frames.append(last)

    if output_path is None:
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = str(BASE_DIR / "output" / f"battle_{ts}.gif")
    
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    
    # 删除旧的GIF文件（只保留最新的）
    if delete_old:
        for old_file in output_dir.glob("battle_*.gif"):
            if old_file != Path(output_path):
                try:
                    old_file.unlink()
                    print(f"删除旧GIF文件: {old_file}")
                except:
                    pass
    
    scaled_frames = []
    scale_factor = 1
    for f in frames:
        new_size = (int(f.width * scale_factor), int(f.height * scale_factor))
        scaled_f = f.resize(new_size, Image.Resampling.LANCZOS)
        scaled_frames.append(scaled_f)
    
    scaled_frames[0].save(
        output_path,
        save_all=True,
        append_images=scaled_frames[1:],
        duration=frame_duration,
        loop=0,
        disposal=2,
        optimize=False, quality=30
    )
    
    print("GIF生成成功！")
    return output_path


def battle_to_gif_bytes(result, characters=None, frame_duration=1200):
    """
    生成战斗GIF并返回BytesIO对象（不保存到本地）
    
    Args:
        result: 战斗结果字典
        characters: 角色数据字典（可选）
        frame_duration: 每帧持续时间（毫秒）
    
    Returns:
        BytesIO对象，失败返回None
    """
    from io import BytesIO
    
    parsable_log = result.get("parsable_log", [])
    log = result.get("log", [])
    p_raw = result.get("player_units", [])
    e_raw = result.get("enemy_units", [])
    
    # 优先使用程序化日志
    if parsable_log:
        frames_data = _parse_parsable_log(parsable_log, p_raw, e_raw)
    else:
        frames_data = _parse_battle_log(log, p_raw, e_raw)
    
    # 计算HP变化
    frames_data = _calculate_hp_changes(frames_data, log)
    
    if not frames_data:
        print("GIF生成失败：没有解析到战斗帧")
        return None
    
    frames = []
    total_frames = len(frames_data)
    
    for frame_idx, frame_data in enumerate(frames_data):
        e_frame = _render_team_section(
            frame_data["enemy_field"], 
            frame_data["enemy_deltas"], 
            frame_data.get("enemy_attack_dirs", {}), 
            True
        )
        p_frame = _render_team_section(
            frame_data["player_field"], 
            frame_data["player_deltas"], 
            frame_data.get("player_attack_dirs", {}), 
            False
        )
        
        EVENT_TEXT_HEIGHT = 30
        SP_BAR_HEIGHT = 28
        fw = max(e_frame.width, p_frame.width) + PADDING * 2
        fh = e_frame.height + SECTION_SPACING + p_frame.height + PADDING * 2 + EVENT_TEXT_HEIGHT + SP_BAR_HEIGHT

        bg = Image.new('RGB', (fw, fh), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(bg)

        # 显示事件描述（最上方）
        event_text = frame_data.get("event_text", "")
        if event_text:
            font_event = _get_font(14)
            try:
                tw = draw.textlength(event_text, font=font_event)
            except:
                tw = len(event_text) * 8
            tx = (fw - tw) // 2
            ty = 8
            # 添加半透明背景框
            draw.rectangle([tx - 8, ty - 4, tx + tw + 8, ty + 16], fill=(0, 0, 0, 180))
            draw.text((tx, ty), event_text, fill=(255, 255, 200), font=font_event)

        ex = (fw - e_frame.width) // 2
        bg.paste(e_frame, (ex, PADDING + EVENT_TEXT_HEIGHT), e_frame)

        font_small = _get_font(11)
        frame_text = f"[{frame_idx+1}/{total_frames}]"
        draw.text((12, 12 + EVENT_TEXT_HEIGHT), frame_text, fill=(160, 160, 160), font=font_small)

        font_center = _get_font(16)

        turn_text = "Player Turn" if frame_data['turn'] == "player" else "Enemy Turn"
        round_info = f"Round {frame_data['round']} - {turn_text}"

        try:
            tw = draw.textlength(round_info, font=font_center)
        except:
            tw = len(round_info) * 10

        cx = (fw - tw) // 2
        cy = e_frame.height + PADDING + 12 + EVENT_TEXT_HEIGHT

        draw.rectangle([cx - 12, cy - 10, cx + tw + 12, cy + 16], fill=COLOR_INFO_BG)
        draw.rectangle([cx - 10, cy - 8, cx + tw + 10, cy + 14], fill=COLOR_INFO_BORDER)

        draw.text((cx, cy), round_info, fill=COLOR_TEXT_GOLD, font=font_center)

        # SP条（回合信息下方）
        sp_y = cy + 22
        sp_w = fw - PADDING * 4
        sp_x = (fw - sp_w) // 2
        _render_sp_bars(draw, sp_x, sp_y, sp_w,
                       frame_data.get("player_sp", 0),
                       frame_data.get("enemy_sp", 0))

        px = (fw - p_frame.width) // 2
        py = e_frame.height + SECTION_SPACING + PADDING + EVENT_TEXT_HEIGHT + SP_BAR_HEIGHT
        bg.paste(p_frame, (px, py), p_frame)

        frames.append(bg)

    if frames:
        winner = result.get("winner", "draw")
        win_text_dict = {"player": "Player WIN!", "enemy": "Enemy WIN!", "draw": "Draw!"}
        win_text = win_text_dict.get(winner, "Battle End")

        # 创建独立的胜利帧（避免与最后一帧信息重叠）
        cw, ch = frames[-1].size
        last = Image.new('RGB', (cw, ch), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(last)
        font_win = _get_font(28)
        try:
            tw = draw.textlength(win_text, font=font_win)
        except:
            tw = len(win_text) * 20
        cx = (cw - tw) // 2
        cy = (ch - 40) // 2
        draw.rectangle([cx - 12, cy - 4, cx + tw + 12, cy + 32], fill=(0, 0, 0))
        draw.text((cx, cy), win_text, fill=(255, 215, 0), font=font_win)
        frames.append(last)

    if not frames:
        print("GIF生成失败：没有帧数据")
        return None

    # 缩放并保存到BytesIO
    scaled_frames = []
    scale_factor = 1
    for f in frames:
        new_size = (int(f.width * scale_factor), int(f.height * scale_factor))
        scaled_f = f.resize(new_size, Image.Resampling.LANCZOS)
        scaled_frames.append(scaled_f)
    
    buffer = BytesIO()
    scaled_frames[0].save(
        buffer,
        format='GIF',
        save_all=True,
        append_images=scaled_frames[1:],
        duration=frame_duration,
        loop=0,
        disposal=2,
        optimize=False, quality=30
    )
    buffer.seek(0)
    
    print("GIF生成成功（BytesIO）！")
    return buffer