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
from image_cache import get_rendered_image, load_shared_image, put_rendered_image

BASE_DIR = Path(__file__).parent
ICON_DIR = BASE_DIR / "iconimage"
LEVEL_DIR = BASE_DIR / "level"
STATE_DIR = BASE_DIR / "state_icon"

# 从战斗系统导入权威 buff icon 映射（单一数据源）
from battle_system import BUFF_ICON_MAP, BUFF_ICON_SUFFIX, DEBUFF_ICON_SUFFIX

CARD_WIDTH = 80
CARD_HEIGHT = 100
ICON_SIZE = 16
ICON_GAP = 2
HP_BAR_HEIGHT = 16
SECTION_SPACING = 60
PADDING = 20
GIF_MAX_COLORS = 96
GIF_MAX_FRAMES = 80

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


def _load_rgba_asset(path):
    """共享加载小型素材；1024×1024 角色原图不会进入常驻缓存。"""
    return load_shared_image(path, 'RGBA')

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
    elif system == "Darwin":
        font_paths = [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
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
        except (IOError, OSError):
            continue
    
    # 如果缓存中已有，直接返回
    if font_key in _CACHED_FONT:
        return _CACHED_FONT[font_key]
    
    # 最后才使用默认字体（但不支持中文）
    font = ImageFont.load_default()
    _CACHED_FONT[font_key] = font
    return font

def _get_frame_image(frame_type, stars=3):
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
        return _load_rgba_asset(path)
    return None

def _find_character_icon(chara_id):
    try:
        chara_id_int = int(float(chara_id))
    except (ValueError, TypeError):
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

def _get_state_icon(effect_name, is_debuff=False):
    """根据 buff/debuff 名称获取 state_icon 路径。
    优先查 battle_system.BUFF_ICON_MAP（单一数据源），找不到再 fallback 本地扩展。
    """
    if not effect_name:
        return None

    # 未传 is_debuff 时根据关键词自动检测
    if not is_debuff:
        debuff_keywords = ["下降", "封印", "沉默", "冻结", "昏迷", "流血", "灼烧",
                           "中毒", "减伤", "妨害", "被害", "感电", "气绝", "不能", "DOWN"]
        is_debuff = any(kw in effect_name for kw in debuff_keywords)

    suffix = DEBUFF_ICON_SUFFIX if is_debuff else BUFF_ICON_SUFFIX  # _DOWN / _UP

    # ---- 根据名称查找图标 ----

    # 1. 处理复合关键词 (长→短 匹配，避免 "a卡封印" 被 "封印" 误匹配)
    for keyword in sorted(BUFF_ICON_MAP.keys(), key=len, reverse=True):
        if keyword in effect_name:
            base = BUFF_ICON_MAP[keyword]
            # 特殊效果（感电/气绝等）没有 UP/DOWN 后缀
            if base in ("SHOCK", "FAINT", "UNCONTROL", "BLEED", "SEAL", "SILENCE",
                        "FREEZE", "BURN", "VOID_BUFF_CONDITION_BAD", "VOID_BUFF_CONDITION_GOOD",
                        "VOID_HP_HEAL", "WORLD_MOVE", "DIVINE_RETRIBUTION_SPELL",
                        "MIRROR_ATTACK", "VECTOR_CONVERSION", "SPELL_INTERCEPT",
                        "STATE_RESIST", "DAMAGE_COVER", "GUTS", "PIERCING"):
                path = STATE_DIR / f"state_icon_{base}.png"
                if path.exists():
                    return str(path)
            # 标准 buff/debuff 带后缀
            path = STATE_DIR / f"state_icon_{base}{suffix}.png"
            if path.exists():
                return str(path)
            # 后缀文件不存在时尝试无后缀
            path = STATE_DIR / f"state_icon_{base}.png"
            if path.exists():
                return str(path)

    # 2. Fallback: A卡扩展效果 (不在 BUFF_ICON_MAP 中但战斗日志会出现)
    _extras = {
        "物攻": "ATK", "异攻": "INT", "物防": "DEF", "异防": "MIND",
        "冻结": "FREEZE", "昏迷": "FAINT", "沉默": "SILENCE",
        "流血": "BLEED", "灼烧": "BURN", "中毒": "BLEED",
        "嘲讽": ("TARGET_RED_DAMAGE", True),  # (base, never use suffix)
        "全能神": "SPELL_INTERCEPT", "预测不能": "INVISIBLE_MONSTER",
        "HP回复": "VOID_HP_HEAL", "吸收": "DAMAGE_ZERO",
    }
    for keyword, spec in sorted(_extras.items(), key=lambda x: len(x[0]), reverse=True):
        if keyword in effect_name:
            if isinstance(spec, tuple):
                base, no_suffix = spec
                path = STATE_DIR / f"state_icon_{base}.png"
            else:
                # 控制/DoT 类不需要后缀
                if spec in ("FREEZE", "FAINT", "SILENCE", "BLEED", "BURN",
                            "VOID_HP_HEAL", "DAMAGE_ZERO", "SPELL_INTERCEPT",
                            "INVISIBLE_MONSTER"):
                    path = STATE_DIR / f"state_icon_{spec}.png"
                else:
                    path = STATE_DIR / f"state_icon_{spec}{suffix}.png"
            if path.exists():
                return str(path)
            if not path.exists() and not isinstance(spec, tuple):
                path = STATE_DIR / f"state_icon_{spec}.png"
                if path.exists():
                    return str(path)

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

def _render_character_card_uncached(unit, card_w, card_h):
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
            char_img = _load_rgba_asset(icon_path)
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
            except (AttributeError, OSError):
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
        except (AttributeError, OSError):
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


def _render_character_card(unit, card_w, card_h):
    """缓存 GIF 中重复出现的静态角色卡面。"""
    alive = unit.get("alive", True)
    if isinstance(alive, str):
        alive = alive.lower() == 'true'
    card_id = str(unit.get("card_id", ""))
    fallback_name = "" if card_id else str(unit.get("name", ""))
    cache_key = (
        bool(unit.get("is_empty", False)),
        card_id,
        fallback_name,
        int(unit.get("stars", 3)),
        bool(alive),
        int(card_w),
        int(card_h),
    )
    cached = get_rendered_image("gif_character_card", cache_key)
    if cached is not None:
        return cached

    rendered = _render_character_card_uncached(unit, card_w, card_h)
    put_rendered_image("gif_character_card", cache_key, rendered)
    return rendered

def _render_buff_icons(canvas, x, y, buffs, debuffs, max_width):
    icons = []
    if not isinstance(buffs, list): buffs = []
    if not isinstance(debuffs, list): debuffs = []
    
    for b in buffs[:6]:
        icon_path = _get_state_icon(b.get("name", ""), is_debuff=False)
        if icon_path:
            icons.append((icon_path, False))
    for d in debuffs[:6]:
        icon_path = _get_state_icon(d.get("name", ""), is_debuff=True)
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
            icon_key = (os.path.abspath(icon_path), ICON_SIZE)
            icon_img = get_rendered_image("gif_state_icon", icon_key)
            if icon_img is None:
                icon_img = _load_rgba_asset(icon_path).resize(
                    (ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS
                )
                put_rendered_image("gif_state_icon", icon_key, icon_img)
            canvas.paste(icon_img, (ix, iy), icon_img)
        except (IOError, OSError):
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
    except (AttributeError, OSError):
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
    except (AttributeError, OSError):
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
    except (AttributeError, OSError):
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
    except (AttributeError, OSError):
        tw = len(label_e) * 9
    draw.text((x + (w - tw) // 2, y + 3), label_e, fill=(255, 200, 200), font=font_sp)

    return y + bar_h  # 返回SP条区域底部的y坐标


def _quantize_gif_frame(frame, colors=GIF_MAX_COLORS):
    return frame.quantize(
        colors=colors,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    )


def _limit_gif_frames(frames_data, max_frames=GIF_MAX_FRAMES):
    """限制长战斗帧数，优先保留攻击、换位、退场与回合边界。"""
    if len(frames_data) <= max_frames:
        return frames_data
    important_phases = {
        "attack", "enter", "swap", "retreat", "hp_threshold",
        "round_start", "turn_switch", "battle_end",
    }
    selected = {0, len(frames_data) - 1}
    important = [
        index for index, frame in enumerate(frames_data)
        if str(frame.get("phase", "")) in important_phases
    ]
    available = max_frames - len(selected)
    if len(important) > available:
        important = [
            important[round(i * (len(important) - 1) / max(1, available - 1))]
            for i in range(available)
        ]
    selected.update(important)
    remaining = max_frames - len(selected)
    candidates = [i for i in range(1, len(frames_data) - 1) if i not in selected]
    if remaining > 0 and candidates:
        if len(candidates) <= remaining:
            selected.update(candidates)
        else:
            selected.update(
                candidates[round(i * (len(candidates) - 1) / max(1, remaining - 1))]
                for i in range(remaining)
            )
    return [frames_data[index] for index in sorted(selected)[:max_frames]]


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

        # 连携单位与携带者同列，用右上角小卡叠放展示，避免直接丢失其画面状态。
        stacked_units = unit.get("stacked_units", [])
        for stack_idx, stacked in enumerate(stacked_units[:2]):
            mini_w, mini_h = 34, 43
            mini = _render_character_card(stacked, mini_w, mini_h)
            mini_x = x + card_w - mini_w - 2 - stack_idx * 8
            mini_y = card_y + 2 + stack_idx * 8
            frame.paste(mini, (mini_x, mini_y), mini)
            draw.rectangle(
                [mini_x - 1, mini_y - 1, mini_x + mini_w, mini_y + mini_h],
                outline=(255, 215, 80), width=1
            )

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

            arrow_map_p = {-1: '↖', 0: '↑', 1: '↗'}
            arrow_map_e = {-1: '↙', 0: '↓', 1: '↘'}
            arrow_map = arrow_map_e if is_enemy else arrow_map_p
            dir_text = ''.join(arrow_map.get(o, '?') for o in sorted(dir_offsets))

            if dir_text:
                font_dir = _get_font(11)
                try:
                    dtw = draw.textlength(dir_text, font=font_dir)
                except (AttributeError, OSError):
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

def _visual_state_signature(state):
    """只比较 GIF 真正能呈现的状态，用于消除相同帧。"""
    parts = [state.get("player_sp", 0), state.get("enemy_sp", 0)]
    for side_key in ("player_units", "enemy_units"):
        units = sorted(state.get(side_key, []), key=lambda u: u.get("unit_id", ""))
        for unit in units:
            buffs = tuple(sorted(
                (b.get("name", ""), b.get("magnitude", ""), b.get("charges", 0))
                for b in unit.get("buffs", [])
            ))
            debuffs = tuple(sorted(
                (d.get("name", ""), d.get("magnitude", ""), d.get("charges", 0))
                for d in unit.get("debuffs", [])
            ))
            parts.append((
                unit.get("unit_id"), unit.get("position", -1), unit.get("hp", 0),
                unit.get("max_hp", 1), bool(unit.get("alive", True)),
                bool(unit.get("is_broken", False)), buffs, debuffs,
                unit.get("carrying_id"), unit.get("carried_by_id"),
            ))
    return tuple(parts)


def _snapshot_unit_map(state):
    result = {}
    for key in ("player_units", "enemy_units"):
        for unit in state.get(key, []):
            result[unit.get("unit_id")] = unit
    return result


def _state_change_summary(before, after):
    """生成该事件真正造成的可视变化摘要。"""
    before_map = _snapshot_unit_map(before)
    after_map = _snapshot_unit_map(after)
    changes = []
    for unit_id, current in after_map.items():
        previous = before_map.get(unit_id, {})
        name = _extract_base_name(current.get("name", "")) or unit_id
        hp_delta = int(current.get("hp", 0)) - int(previous.get("hp", current.get("hp", 0)))
        if hp_delta:
            changes.append(f"{name} HP{hp_delta:+d}")
        old_pos = previous.get("position", current.get("position", -1))
        new_pos = current.get("position", -1)
        if old_pos != new_pos:
            changes.append(f"{name} {old_pos}→{new_pos}")
        if bool(previous.get("alive", True)) != bool(current.get("alive", True)):
            changes.append(f"{name}{'退场' if not current.get('alive', True) else '入场'}")

        old_buffs = {(b.get("name", ""), b.get("magnitude", ""), b.get("charges", 0))
                     for b in previous.get("buffs", [])}
        new_buffs = {(b.get("name", ""), b.get("magnitude", ""), b.get("charges", 0))
                     for b in current.get("buffs", [])}
        old_debuffs = {(d.get("name", ""), d.get("magnitude", ""), d.get("charges", 0))
                       for d in previous.get("debuffs", [])}
        new_debuffs = {(d.get("name", ""), d.get("magnitude", ""), d.get("charges", 0))
                       for d in current.get("debuffs", [])}
        for effect in sorted(new_buffs - old_buffs):
            changes.append(f"{name} +{effect[0]}")
        for effect in sorted(old_buffs - new_buffs):
            changes.append(f"{name} -{effect[0]}")
        for effect in sorted(new_debuffs - old_debuffs):
            changes.append(f"{name} +{effect[0]}")
        for effect in sorted(old_debuffs - new_debuffs):
            changes.append(f"{name} -{effect[0]}")
        if previous.get("carried_by_id") != current.get("carried_by_id"):
            changes.append(f"{name} {'形成连携' if current.get('carried_by_id') else '解除连携'}")

    p_sp_delta = int(after.get("player_sp", 0)) - int(before.get("player_sp", 0))
    e_sp_delta = int(after.get("enemy_sp", 0)) - int(before.get("enemy_sp", 0))
    if p_sp_delta:
        changes.append(f"P-SP{p_sp_delta:+d}")
    if e_sp_delta:
        changes.append(f"E-SP{e_sp_delta:+d}")
    return changes


def _snapshot_to_field(state, side):
    key = "player_units" if side == "P" else "enemy_units"
    arrows = COL_TO_ARROW_P if side == "P" else COL_TO_ARROW_E
    fields = [{
        "is_empty": True, "name": "", "hp": 0, "max_hp": 1,
        "alive": True, "position": pos, "buffs": [], "debuffs": [],
        "base_name": "", "card_id": "", "stars": 0, "unit_id": "",
    } for pos in range(5)]

    for raw in state.get(key, []):
        pos = int(raw.get("position", -1))
        if not 0 <= pos < 5:
            continue
        unit = copy.deepcopy(raw)
        base_name = _extract_base_name(unit.get("name", ""))
        unit["base_name"] = base_name
        unit["name"] = f"{base_name}[{arrows.get(pos, '')}]"
        unit["hp_change"] = 0
        unit["is_empty"] = False
        existing = fields[pos]
        if existing.get("is_empty"):
            fields[pos] = unit
        else:
            # 连携会让两个单位处于同列：携带者作为主卡，被携带者作为叠放卡。
            if unit.get("carrying_id") and not existing.get("carrying_id"):
                unit["stacked_units"] = [existing]
                fields[pos] = unit
            else:
                existing.setdefault("stacked_units", []).append(unit)
    return fields


def _event_title(entry, changes):
    event_type = entry.get("type", "event")
    content = str(entry.get("content") or "").strip()
    titles = {
        "round_start": f"第{entry.get('round', '?')}回合",
        "turn_switch": "我方行动" if entry.get("side") == "player" else "敌方行动",
        "sp_info": "SP变化",
        "swap": "换位",
        "enter": "替补入场",
        "combo_form": "形成连携",
        "attack": {"普": "普通攻击", "技": "技能", "终": "必杀"}.get(entry.get("attack_type"), "攻击"),
        "assist_trigger": "A卡触发",
        "trigger": "效果触发",
        "hp_threshold": "HP阈值触发",
        "dot_damage": "持续伤害",
        "buff_expiry": "状态到期",
        "debuff_trigger": "弱体触发",
        "stun_recover": "无法行动",
        "retreat": "退场",
        "battle_end": "战斗结束",
    }
    title = titles.get(event_type, content or event_type)
    if event_type == "attack" and entry.get("attacker"):
        title = f"{_extract_base_name(entry.get('attacker', ''))}: {title}"
    detail = " | ".join(changes[:4])
    return f"{title} | {detail}" if detail else title


def _parse_snapshot_log(parsable_log):
    """GIF v2：完全依据战斗引擎提供的 before/after 快照生成帧。"""
    frames = []
    round_num = 1
    turn = "player"
    last_signature = None

    def append_state(state, phase, event_text, entry=None, before=None):
        nonlocal last_signature
        signature = _visual_state_signature(state)
        p_field = _snapshot_to_field(state, "P")
        e_field = _snapshot_to_field(state, "E")
        if before:
            before_map = _snapshot_unit_map(before)
            for field in (p_field, e_field):
                for unit in field:
                    if unit.get("is_empty"):
                        continue
                    previous = before_map.get(unit.get("unit_id"), {})
                    unit["hp_change"] = int(unit.get("hp", 0)) - int(previous.get("hp", unit.get("hp", 0)))
        attack_info = None
        if entry and entry.get("type") == "attack":
            attack_info = {
                "type": entry.get("attack_type", ""),
                "attacker_position": entry.get("attacker_position", -1),
                "attacker_arrow": entry.get("attacker_arrow", ""),
                "targets": entry.get("targets", []),
            }
        frames.append({
            "round": round_num, "turn": turn, "phase": phase,
            "player_field": p_field, "enemy_field": e_field,
            "player_deltas": {}, "enemy_deltas": {},
            "player_attack_dirs": {}, "enemy_attack_dirs": {},
            "phase_text": phase, "attack_info": attack_info,
            "event_text": event_text,
            "player_sp": state.get("player_sp", 0),
            "enemy_sp": state.get("enemy_sp", 0),
        })
        last_signature = signature

    first = next((e for e in parsable_log if e.get("before_state")), None)
    if not first:
        return []
    append_state(first["before_state"], "战斗开始", "战斗开始")

    boundary_types = {"round_start", "turn_switch", "battle_end"}
    for entry in parsable_log:
        before = entry.get("before_state")
        after = entry.get("after_state")
        if not before or not after:
            continue
        event_type = entry.get("type")
        if event_type == "assist_prepare":
            continue
        if event_type == "round_start":
            round_num = entry.get("round", round_num)
        elif event_type == "turn_switch":
            turn = entry.get("side", turn)

        before_sig = _visual_state_signature(before)
        after_sig = _visual_state_signature(after)
        changed = before_sig != after_sig
        if not changed and event_type not in boundary_types:
            continue

        changes = _state_change_summary(before, after) if changed else []
        title = _event_title(entry, changes)
        # 若日志中间有未出帧的状态，先补一张无标题的真实 before 帧。
        if last_signature != before_sig:
            append_state(before, "状态同步", "状态同步")
        append_state(after, event_type, title, entry=entry, before=before if changed else None)

    return frames


def _parse_parsable_log(parsable_log, p_raw, e_raw):
    """解析程序化日志生成战斗帧"""
    if any(entry.get("schema_version", 0) >= 2 and entry.get("before_state")
           for entry in parsable_log):
        return _parse_snapshot_log(parsable_log)

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
            # SP变化事件：生成pre+post帧展示SP变动
            new_player_sp = entry.get("player_sp", player_sp)
            new_enemy_sp = entry.get("enemy_sp", enemy_sp)
            delta_p = new_player_sp - player_sp
            delta_e = new_enemy_sp - enemy_sp
            delta_text = []
            if delta_p != 0: delta_text.append(f"P SP{'+' if delta_p>0 else ''}{delta_p}")
            if delta_e != 0: delta_text.append(f"E SP{'+' if delta_e>0 else ''}{delta_e}")
            event_text = " | ".join(delta_text) if delta_text else "SP变更"

            # === 变化前帧 ===
            save_frame("SP变化前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

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
            player_sp = new_player_sp
            enemy_sp = new_enemy_sp

            save_frame("SP变化后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

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
            
            # === 变化前帧 ===
            save_frame("换位前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            field = p_field if side == "P" else e_field
            for u in field:
                if not u.get("is_empty") and u.get("base_name"):
                    if name and (u["base_name"] in name or name in u["base_name"]):
                        u["position"] = new_pos
                        if new_arrow:
                            u["name"] = f"{name}[{new_arrow}]"
                        break
            
            save_frame("换位后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
        elif entry_type == "enter":
            side = entry.get("side")
            name = entry.get("name")
            pos = entry.get("position", -1)
            arrow = entry.get("arrow")
            
            # 构建事件描述
            chara_name = _extract_base_name(name)
            event_text = f"{chara_name}: 替补上场"
            
            # === 变化前帧 ===
            save_frame("替补上场前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

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
            
            save_frame("替补上场后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
        elif entry_type == "attack":
            attack_type = entry.get("attack_type", "普")
            attacker = entry.get("attacker", "")
            attacker_pos = entry.get("attacker_position", -1)
            attacker_arrow = entry.get("attacker_arrow", "")
            targets = entry.get("targets", [])

            # 提取攻击者名字（去掉称号）
            attacker_name = _extract_base_name(attacker)

            # 构建攻击前帧描述
            target_name = _extract_base_name(targets[0].get("name", "")) if targets else ""
            pre_effect = {"技": "技能", "终": "必杀", "A": "支援"}.get(attack_type, "攻击")
            pre_text = f"{attacker_name} → {target_name}: {pre_effect}" if target_name else f"{attacker_name}: {pre_effect}"

            # === 变化前帧：记录攻击前的状态 ===
            save_frame(f"攻击前[{attack_type}]", [dict(u) for u in p_field], [dict(u) for u in e_field], None, pre_text)

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

            save_frame(f"攻击后[{attack_type}]", [dict(u) for u in p_field], [dict(u) for u in e_field], attack_info, event_text)

            # Fix 6: 攻击帧已记录阵亡状态，清空死单位的buffs/debuffs
            # 不再设置position=-1，让retreat事件或round_start/turn_switch来处理位移
            for u in p_field:
                if not u.get("is_empty") and not u.get("alive", True):
                    u["buffs"] = []
                    u["debuffs"] = []
            for u in e_field:
                if not u.get("is_empty") and not u.get("alive", True):
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
            
            # === 变化前帧：记录A卡触发前的状态 ===
            save_frame("A卡准备前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            # 同步HP/alive/position/buffs/debuffs（参照attack handler的同步模式）
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break
            
            save_frame("A卡准备后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
        elif entry_type == "assist_trigger":
            # A卡效果触发后的帧
            is_attack_internal = entry.get("is_attack_internal", False)

            if is_attack_internal:
                # 攻击内触发的A卡效果（自身受到伤害时/使敌方退场时等）
                target_name = _extract_base_name(entry.get("target_name", ""))
                effect_desc = entry.get("effect_desc", "效果触发")
                event_text = f"A卡 → {target_name}: {effect_desc}"
            else:
                assist_name = entry.get("assist_name", "")
                effects = entry.get("effects", [])
                source_unit = entry.get("source_unit", "")

                source_name = _extract_base_name(source_unit)
                effect_text = effects[0] if effects else "效果触发"
                if effect_text and '[A]' in effect_text:
                    effect_match = re.match(r'(.+?)\s+(.+?)\s+\[A\]', effect_text)
                    if effect_match:
                        target_char = effect_match.group(1)
                        effect_content = effect_match.group(2)
                        event_text = f"{assist_name} → {target_char}: {effect_content}"
                    else:
                        event_text = f"{assist_name}: {effect_text.replace('[A]', '')}"
                else:
                    event_text = f"{assist_name}: 效果触发"

            # === 变化前帧：记录A卡触发前的状态 ===
            save_frame("A卡触发前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            # 同步HP/alive/position/buffs/debuffs（参照attack handler的同步模式）
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break

            save_frame("A卡触发后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

        elif entry_type == "hp_threshold":
            # HP阈值触发事件
            threshold_name = entry.get("name", "")
            threshold_value = entry.get("threshold", "")
            effect_desc = entry.get("effect_desc", "阈值触发")
            
            chara_name = _extract_base_name(threshold_name)
            event_text = f"{chara_name}: HP阈值({threshold_value}) → {effect_desc}"
            
            # === 变化前帧：记录HP阈值触发前的状态 ===
            save_frame("HP阈值前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            # 同步所有单位的HP/alive/position/buffs/debuffs
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break
            
            save_frame("HP阈值后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

        elif entry_type == "trigger":
            # 通用触发事件（被动技能/条件触发等）
            trigger_name = entry.get("name", "")
            trigger_effect = entry.get("effect_desc", entry.get("effect", "触发"))
            trigger_target = entry.get("target_name", "")
            
            chara_name = _extract_base_name(trigger_name)
            if trigger_target:
                target_name = _extract_base_name(trigger_target)
                event_text = f"{chara_name} → {target_name}: {trigger_effect}"
            else:
                event_text = f"{chara_name}: {trigger_effect}"
            
            # === 变化前帧：记录触发前的状态 ===
            save_frame("触发前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            # 同步所有单位的HP/alive/position/buffs/debuffs
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
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
                            u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                            u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                            break
            
            save_frame("触发后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

        elif entry_type == "retreat":
            # 退场帧：标记阵亡单位，清除场上位置
            # === 变化前帧 ===
            save_frame("退场前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, "退场前")

            retreat_names = []
            for pos_info in entry.get("player_positions", []):
                name = pos_info.get("name", "")
                base_name = _extract_base_name(name)
                alive = pos_info.get("alive", True)
                # 同步存活单位的 hp/max_hp/alive/position/hp_change（参照 attack handler）
                for u in p_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["position"] = pos_info.get("position", u["position"])
                        u["hp_change"] = pos_info.get("hp_change", 0)
                        if not u.get("alive", True):
                            retreat_names.append(base_name)
                            u["alive"] = False
                            u["hp"] = 0
                            u["buffs"] = []
                            u["debuffs"] = []
                            u["position"] = -1
                        break
            for pos_info in entry.get("enemy_positions", []):
                name = pos_info.get("name", "")
                base_name = _extract_base_name(name)
                alive = pos_info.get("alive", True)
                # 同步存活单位的 hp/max_hp/alive/position/hp_change（参照 attack handler）
                for u in e_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["position"] = pos_info.get("position", u["position"])
                        u["hp_change"] = pos_info.get("hp_change", 0)
                        if not u.get("alive", True):
                            retreat_names.append(base_name)
                            u["alive"] = False
                            u["hp"] = 0
                            u["buffs"] = []
                            u["debuffs"] = []
                            u["position"] = -1
                        break

            event_text = f"退场: {', '.join(retreat_names)}" if retreat_names else "退场"
            save_frame("退场后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)
        
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

        elif entry_type == "dot_damage":
            # DoT伤害事件
            content = entry.get("content", "")
            event_text = f"DoT伤害: {content}" if content else "DoT伤害"

            # === 变化前帧 ===
            save_frame("DoT前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            # 同步HP变化
            for pos_info in entry.get("player_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in p_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break
            for pos_info in entry.get("enemy_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in e_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["max_hp"] = pos_info.get("max_hp", u["max_hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break

            save_frame("DoT后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

        elif entry_type == "buff_expiry":
            # buff到期事件
            event_text = "BUFF到期"

            # === 变化前帧 ===
            save_frame("BUFF到期前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            # 同步变更后的状态（buffs/debuffs已更新）
            for pos_info in entry.get("player_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in p_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break
            for pos_info in entry.get("enemy_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in e_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break

            save_frame("BUFF到期后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

        elif entry_type == "debuff_trigger":
            # debuff触发事件
            content = entry.get("content", "")
            event_text = f"Debuff触发: {content}" if content else "Debuff触发"

            # === 变化前帧 ===
            save_frame("Debuff触发前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            for pos_info in entry.get("player_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in p_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break
            for pos_info in entry.get("enemy_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in e_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break

            save_frame("Debuff触发后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

        elif entry_type == "stun_recover":
            # 无法行动恢复事件
            content = entry.get("content", "")
            event_text = f"无法行动恢复: {content}" if content else "无法行动恢复"

            # === 变化前帧 ===
            save_frame("硬直前", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

            for pos_info in entry.get("player_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in p_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break
            for pos_info in entry.get("enemy_positions", []):
                base_name = _extract_base_name(pos_info.get("name", ""))
                for u in e_field:
                    if not u.get("is_empty") and u.get("base_name") == base_name:
                        u["hp"] = pos_info.get("hp", u["hp"])
                        u["alive"] = pos_info.get("alive", u["alive"])
                        u["buffs"] = pos_info.get("buffs", u.get("buffs", []))
                        u["debuffs"] = pos_info.get("debuffs", u.get("debuffs", []))
                        break

            save_frame("硬直后", [dict(u) for u in p_field], [dict(u) for u in e_field], None, event_text)

    # 插入buff/debuff变化标记帧（仅在非攻击事件间检测）
    frames_data = _insert_buff_change_frames(frames_data)

    return frames_data


def _buffs_differ(f1, f2):
    """Return 'B' if buffs changed, 'D' if debuffs."""
    changed = []
    for field_name in ["player_field", "enemy_field"]:
        f1f = f1.get(field_name, [])
        f2f = f2.get(field_name, [])
        for i in range(min(len(f1f), len(f2f))):
            u1 = f1f[i]
            u2 = f2f[i]
            b1 = frozenset((b.get("name",""), b.get("magnitude","")) for b in u1.get("buffs", []))
            b2 = frozenset((b.get("name",""), b.get("magnitude","")) for b in u2.get("buffs", []))
            d1 = frozenset((d.get("name",""), d.get("magnitude","")) for d in u1.get("debuffs", []))
            d2 = frozenset((d.get("name",""), d.get("magnitude","")) for d in u2.get("debuffs", []))
            if b1 != b2: changed.append("B")
            if d1 != d2: changed.append("D")
    return "".join(sorted(set(changed)))

def _insert_buff_change_frames(frames_data):
    """在帧序列中检测buff/debuff变化，在非攻击/A卡帧间插入标记帧。"""
    import copy
    result = []
    SKIP = {"回合开始", "战斗开始", "战斗结束", "退场前", "退场后",
            "SP变化前", "SP变化后", "BUFF到期前", "BUFF到期后",
            "DoT前", "DoT后", "Debuff触发前", "Debuff触发后",
            "HP阈值前", "HP阈值后", "触发前", "触发后",
            "硬直前", "硬直后"}

    for i, frame in enumerate(frames_data):
        if i > 0:
            prev = result[-1]
            pp = prev.get("phase", "")
            cp = frame.get("phase", "")
            if pp in SKIP or cp in SKIP or "攻击" in pp or "攻击" in cp or "A卡" in pp or "A卡" in cp:
                result.append(frame)
                continue
            diff = _buffs_differ(prev, frame)
            if diff:
                desc = []
                if "B" in diff: desc.append("BUFF增减")
                if "D" in diff: desc.append("DEBUFF增减")
                marker = copy.deepcopy(prev)
                marker["event_text"] = ", ".join(desc)
                marker["phase"] = "状态变化"
                result.append(marker)
        result.append(frame)
    return result


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
    frames_data = _limit_gif_frames(frames_data)
    
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
        SP_BAR_HEIGHT = 24
        fw = max(e_frame.width, p_frame.width) + PADDING * 2
        fh = e_frame.height + SECTION_SPACING + p_frame.height + PADDING * 2 + EVENT_TEXT_HEIGHT + SP_BAR_HEIGHT

        bg = Image.new('RGBA', (fw, fh), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(bg)

        # 显示事件描述（最上方）
        event_text = frame_data.get("event_text", "")
        if event_text:
            font_event = _get_font(14)
            try:
                tw = draw.textlength(event_text, font=font_event)
            except (IOError, OSError):
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
        except (IOError, OSError):
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

        # 立即压缩为调色板帧，不让全部 RGBA 画布同时常驻内存。
        frames.append(_quantize_gif_frame(bg))

    if frames:
        winner = result.get("winner", "draw")
        win_text_dict = {"player": "Player WIN!", "enemy": "Enemy WIN!", "draw": "Draw!"}
        win_text = win_text_dict.get(winner, "Battle End")

        # 创建独立的胜利帧（避免与最后一帧信息重叠）
        cw, ch = frames[-1].size
        last = Image.new('RGBA', (cw, ch), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(last)
        font_win = _get_font(28)
        try:
            tw = draw.textlength(win_text, font=font_win)
        except (IOError, OSError):
            tw = len(win_text) * 20
        cx = (cw - tw) // 2
        cy = (ch - 40) // 2
        draw.rectangle([cx - 12, cy - 4, cx + tw + 12, cy + 32], fill=(0, 0, 0))
        draw.text((cx, cy), win_text, fill=(255, 215, 0), font=font_win)
        frames.append(_quantize_gif_frame(last))

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
                except (IOError, OSError):
                    pass
    
    scale_factor = 1
    if scale_factor == 1:
        scaled_frames = frames
    else:
        scaled_frames = []
        for f in frames:
            new_size = (int(f.width * scale_factor), int(f.height * scale_factor))
            scaled_frames.append(f.resize(new_size, Image.Resampling.LANCZOS))

    palette_frames = scaled_frames
    palette_frames[0].save(
        output_path,
        save_all=True,
        append_images=palette_frames[1:],
        duration=frame_duration,
        loop=0,
        disposal=2,
        optimize=False
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
    frames_data = _limit_gif_frames(frames_data)
    
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
        SP_BAR_HEIGHT = 24
        fw = max(e_frame.width, p_frame.width) + PADDING * 2
        fh = e_frame.height + SECTION_SPACING + p_frame.height + PADDING * 2 + EVENT_TEXT_HEIGHT + SP_BAR_HEIGHT

        bg = Image.new('RGBA', (fw, fh), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(bg)

        # 显示事件描述（最上方）
        event_text = frame_data.get("event_text", "")
        if event_text:
            font_event = _get_font(14)
            try:
                tw = draw.textlength(event_text, font=font_event)
            except (IOError, OSError):
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
        except (IOError, OSError):
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

        # 立即压缩为调色板帧，不让全部 RGBA 画布同时常驻内存。
        frames.append(_quantize_gif_frame(bg))

    if frames:
        winner = result.get("winner", "draw")
        win_text_dict = {"player": "Player WIN!", "enemy": "Enemy WIN!", "draw": "Draw!"}
        win_text = win_text_dict.get(winner, "Battle End")

        # 创建独立的胜利帧（避免与最后一帧信息重叠）
        cw, ch = frames[-1].size
        last = Image.new('RGBA', (cw, ch), COLOR_FRAME_BG)
        draw = ImageDraw.Draw(last)
        font_win = _get_font(28)
        try:
            tw = draw.textlength(win_text, font=font_win)
        except (IOError, OSError):
            tw = len(win_text) * 20
        cx = (cw - tw) // 2
        cy = (ch - 40) // 2
        draw.rectangle([cx - 12, cy - 4, cx + tw + 12, cy + 32], fill=(0, 0, 0))
        draw.text((cx, cy), win_text, fill=(255, 215, 0), font=font_win)
        frames.append(_quantize_gif_frame(last))

    if not frames:
        print("GIF生成失败：没有帧数据")
        return None

    # 缩放并保存到BytesIO
    scale_factor = 1
    if scale_factor == 1:
        scaled_frames = frames
    else:
        scaled_frames = []
        for f in frames:
            new_size = (int(f.width * scale_factor), int(f.height * scale_factor))
            scaled_frames.append(f.resize(new_size, Image.Resampling.LANCZOS))
    
    palette_frames = scaled_frames
    buffer = BytesIO()
    palette_frames[0].save(
        buffer,
        format='GIF',
        save_all=True,
        append_images=palette_frames[1:],
        duration=frame_duration,
        loop=0,
        disposal=2,
        optimize=False
    )
    buffer.seek(0)
    
    print("GIF生成成功（BytesIO）！")
    return buffer
