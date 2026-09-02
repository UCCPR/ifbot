"""
配队系统 - 让玩家能够用抽到的三星卡配置队伍
第一行是6个BattleCard角色，每个BattleCard角色都能搭配一个AssistCard放在第二行
使用和抽卡一样的背景图配置，角色图的框使用gacha_tmb_frame.png
"""

import os
import random
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from card_image import (find_attribute_icon, find_type_icon, find_type_icon_non_gacha,
                         get_level_image, render_attack_arrows, render_rarity_stars)
from image_cache import get_rendered_image, load_shared_image, put_rendered_image
from json_store import atomic_write_json, read_json
from storage_maintenance import append_rotating_log


# ========== 日志模块 ==========
def log_info(message: str):
    """记录普通信息到info目录"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = INFO_DIR / "gacha_info.log"
    append_rotating_log(log_file, f"[{timestamp}] [INFO] {message}\n")
    print(f"[INFO] {message}")


def log_error(message: str):
    """记录错误信息到info目录"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = INFO_DIR / "gacha_error.log"
    append_rotating_log(log_file, f"[{timestamp}] [ERROR] {message}\n")
    print(f"[ERROR] {message}")


# ========== 配置 ==========
BASE_DIR = Path(__file__).parent
LEVEL_DIR = BASE_DIR / "level"
INFO_DIR = BASE_DIR / "info"
OUTPUT_DIR = BASE_DIR / "output"

# 队伍配置
BATTLE_CARD_COUNT = 6  # 战斗卡数量
ASSIST_CARD_COUNT = 6  # 支援卡数量（与战斗卡一一对应）

def _load_cached_image(path, mode="RGBA"):
    """使用进程级共享缓存加载小型素材；角色原图不会常驻内存。"""
    return load_shared_image(path, mode)


def _ensure_char_dict(characters):
    """确保characters是dict格式（card_id -> data）"""
    if characters is None:
        return {}
    if isinstance(characters, dict):
        return characters
    if isinstance(characters, list):
        result = {}
        for c in characters:
            cid = c.get("card_id") or c.get("id", "")
            if cid:
                result[str(cid)] = c
        return result
    return characters


# 确保目录存在
INFO_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ========== 队伍数据存储 ==========
def get_team_file(user_id: str) -> Path:
    """获取用户队伍配置文件路径"""
    return INFO_DIR / f"team_{user_id}.json"


def load_team_data(user_id: str) -> dict:
    """加载用户的队伍配置数据"""
    return read_json(get_team_file(user_id), create_default_team)


def create_default_team() -> dict:
    """创建默认队伍配置（空队伍）"""
    return {
        "battle_cards": [None] * BATTLE_CARD_COUNT,  # 6个战斗卡位置
        "assist_cards": [None] * ASSIST_CARD_COUNT    # 6个支援卡位置
    }


def save_team_data(user_id: str, team_data: dict):
    """保存用户的队伍配置数据"""
    atomic_write_json(get_team_file(user_id), team_data)


# ========== 队伍预设系统（11个预设槽位：1-6普通 + 7-11 RAID） ==========
MAX_PRESETS = 11
PRESET_CYCLE = 0  # 满了之后从第几个开始覆盖（递增）


def get_presets_file(user_id: str) -> Path:
    """获取用户预设文件路径"""
    return INFO_DIR / f"team_presets_{user_id}.json"


def load_presets(user_id: str) -> dict:
    """加载所有预设"""
    data = read_json(
        get_presets_file(user_id),
        lambda: {"presets": [None] * MAX_PRESETS, "cycle": 0, "active_slot": 0},
    )
    # 兼容旧格式并补齐新增槽位。
    if "presets" not in data:
        data = {"presets": [None] * MAX_PRESETS, "cycle": 0, "active_slot": 0}
    while len(data.get("presets", [])) < MAX_PRESETS:
        data["presets"].append(None)
    return data


def save_presets(user_id: str, data: dict):
    """保存所有预设（确保长度为MAX_PRESETS）"""
    # 确保 presets 列表长度为 MAX_PRESETS
    presets = data.get("presets", [])
    while len(presets) < MAX_PRESETS:
        presets.append(None)
    data["presets"] = presets[:MAX_PRESETS]
    atomic_write_json(get_presets_file(user_id), data)


def _get_active_slot(user_id: str) -> int:
    """获取当前活跃预设槽位（0=无活跃）"""
    data = load_presets(user_id)
    return data.get("active_slot", 0)


def auto_save_preset(user_id: str):
    """编辑队伍时自动保存到当前活跃预设槽位，无活跃则找空槽"""
    team_data = load_team_data(user_id)
    battle = team_data.get("battle_cards", [None] * BATTLE_CARD_COUNT)
    assist = team_data.get("assist_cards", [None] * ASSIST_CARD_COUNT)

    if not any(battle) and not any(assist):
        return -1

    presets_data = load_presets(user_id)
    presets = presets_data["presets"]
    active = presets_data.get("active_slot", 0)

    # 有活跃槽位 → 直接覆盖
    if active > 0 and active <= MAX_PRESETS:
        presets[active - 1] = {"battle_cards": list(battle), "assist_cards": list(assist)}
        save_presets(user_id, presets_data)
        return active

    # 无活跃 → 优先找普通槽(1-6)的空槽，再找RAID槽(7-11)的空槽
    for i in range(MAX_PRESETS):
        if presets[i] is None:
            presets[i] = {"battle_cards": list(battle), "assist_cards": list(assist)}
            presets_data["active_slot"] = i + 1
            save_presets(user_id, presets_data)
            return i + 1

    # 全满且无活跃 → 覆盖槽1
    presets[0] = {"battle_cards": list(battle), "assist_cards": list(assist)}
    presets_data["active_slot"] = 1
    save_presets(user_id, presets_data)
    return 1


def load_preset(user_id: str, slot: int) -> bool:
    """加载预设槽位(1-6)到当前队伍，并将其设为活跃槽位"""
    if slot < 1 or slot > MAX_PRESETS:
        return False
    presets_data = load_presets(user_id)
    preset = presets_data["presets"][slot - 1]
    if preset is None:
        return False
    team_data = load_team_data(user_id)
    team_data["battle_cards"] = list(preset.get("battle_cards", [None] * BATTLE_CARD_COUNT))
    team_data["assist_cards"] = list(preset.get("assist_cards", [None] * ASSIST_CARD_COUNT))
    save_team_data(user_id, team_data)
    # 标记活跃槽位
    presets_data["active_slot"] = slot
    save_presets(user_id, presets_data)
    return True


def copy_team(user_id: str, from_slot: int, to_slot: int) -> bool:
    """复制队伍：将from_slot的内容复制到to_slot"""
    if not (1 <= from_slot <= MAX_PRESETS and 1 <= to_slot <= MAX_PRESETS):
        return False
    if from_slot == to_slot:
        return False
    presets = load_presets(user_id)
    src = presets.get("presets", [None] * MAX_PRESETS)
    if src[from_slot - 1] is None:
        return False
    src[to_slot - 1] = dict(src[from_slot - 1])  # 深拷贝
    presets["presets"] = src
    save_presets(user_id, presets)
    return True


def list_presets_info(user_id: str, characters: list) -> str:
    """获取所有预设的摘要信息"""
    characters = _ensure_char_dict(characters)
    presets_data = load_presets(user_id)
    presets = presets_data["presets"]

    active = presets_data.get("active_slot", 0)
    lines = ["📋 队伍预设 (共11个槽位，槽7-11为RAID)："]
    for i in range(MAX_PRESETS):
        p = presets[i]
        slot_num = i + 1
        marker = " ◀当前" if slot_num == active else ""
        raid_tag = " [RAID]" if slot_num >= 7 else ""
        if p is None:
            lines.append(f"  槽{slot_num}{raid_tag}: 空{marker}")
        else:
            b_count = sum(1 for c in p.get("battle_cards", []) if c)
            a_count = sum(1 for c in p.get("assist_cards", []) if c)
            # 取第一张B卡名字作为标识
            first_name = "?"
            bc = p.get("battle_cards", [])
            if bc and bc[0] and characters:
                chara = next((c for c in characters.values() if str(c.get("card_id")) == str(bc[0])), None)
                if chara:
                    first_name = chara.get("name", "?")
            lines.append(f"  槽{slot_num}{raid_tag}: ⚔{b_count}+🛡{a_count} [{first_name}...]{marker}")
    return "\n".join(lines)


# ========== 获取用户的三星卡 ==========
def get_pity_file(user_id: str) -> Path:
    """获取用户抽卡记录文件路径"""
    return INFO_DIR / f"pity_{user_id}.json"


def load_pity_data(user_id: str) -> dict:
    """加载用户的抽卡记录数据"""
    return read_json(get_pity_file(user_id), dict)


def get_user_3star_cards(user_id: str, characters: dict = None,
                         filter_color: str = None, filter_type: str = None) -> list:
    """获取用户拥有的所有三星卡（支持按颜色和类型筛选）
    :param filter_color: 颜色筛选（红/绿/蓝/黄/紫），同时匹配超X版本
    :param filter_type: 类型筛选（"battle"或"assist"）
    """
    characters = _ensure_char_dict(characters)
    pity_data = load_pity_data(user_id)
    card_collection = pity_data.get("card_collection", {})

    three_star_cards = []
    for card_id, info in card_collection.items():
        if info.get("stars") == 3:
            # 获取卡类型和属性
            card_type = "battle"
            card_attribute = ""
            if characters:
                chara = characters.get(str(card_id))
                if chara:
                    card_type = chara.get("type", "battle")
                    card_attribute = str(chara.get("attribute", "")).strip()

            # 颜色筛选：
            #   "黄" → 匹配 "黄" 和 "超黄"
            #   "超黄" → 只匹配 "超黄"（不匹配普通"黄"）
            # 注意：xlsx文件中用 赤/緑/青，需映射为 红/绿/蓝
            if filter_color:
                if not card_attribute:
                    continue
                _XLSX_COLOR_MAP = {'赤': '红', '緑': '绿', '青': '蓝'}
                attr = card_attribute
                is_super = attr.startswith('超')
                base = attr[1:] if is_super else attr
                base = _XLSX_COLOR_MAP.get(base, base)  # 赤→红, 緑→绿, 青→蓝
                normalized = ('超' + base) if is_super else base

                if filter_color.startswith("超"):
                    # 精确匹配超属性（如"超红"只匹配"超赤"→"超红"）
                    if normalized != filter_color:
                        continue
                else:
                    # 基础颜色匹配：去除超前缀后对比（如"红"匹配"红"和"超红"）
                    norm_base = normalized[1:] if normalized.startswith("超") else normalized
                    if norm_base != filter_color:
                        continue

            # 类型筛选
            if filter_type:
                if card_type != filter_type:
                    continue

            three_star_cards.append({
                "card_id": card_id,
                "name": info.get("name", ""),
                "limit_type": info.get("limit_type", ""),
                "count": info.get("count", 1),
                "type": card_type  # 添加卡类型：battle 或 assist
            })

    return three_star_cards






# ========== 构建队伍图片 ==========
def _team_card_cache_key(character: dict, is_battle: bool):
    directions = character.get("attack_directions") or ()
    if isinstance(directions, list):
        directions = tuple(directions)
    return (
        str(character.get("card_id") or character.get("chara_id") or character.get("id") or ""),
        str(character.get("icon_path") or ""),
        int(character.get("stars", 3)),
        str(character.get("element") or character.get("attribute") or ""),
        str(character.get("type", "battle")),
        directions,
        bool(is_battle),
    )


def composite_team_card_image(character: dict, is_battle: bool = True) -> Image.Image:
    """
    合成队伍卡牌图片，直接返回 PIL Image。

    队伍图/VS图内部调用这个函数，避免中间 JPEG 编码后又立即解码。
    使用gacha_tmb_frame.png作为统一的框
    背景使用透明背景
    添加属性图标（左下角）和类型图标（正下方）
    """
    cache_key = _team_card_cache_key(character, is_battle)
    cached = get_rendered_image("team_card", cache_key)
    if cached is not None:
        return cached

    stars = character.get("stars", 3)
    icon_path = character.get("icon_path")

    # 加载统一的框
    frame_path = str(LEVEL_DIR / "gacha_tmb_frame.png")
    if os.path.exists(frame_path):
        frame_img = _load_cached_image(frame_path, 'RGBA')
    else:
        # 如果找不到统一框，使用星级框
        frame_path_fallback = get_level_image(stars, "frame")
        if frame_path_fallback and os.path.exists(frame_path_fallback):
            frame_img = _load_cached_image(frame_path_fallback, 'RGBA')
        else:
            # 创建一个简单的白色边框
            frame_img = Image.new('RGBA', (120, 160), (255, 255, 255, 128))
    
    # 加载角色图标
    if icon_path and os.path.exists(icon_path):
        char_img = _load_cached_image(icon_path, 'RGBA')
    else:
        # 创建占位图
        char_img = Image.new('RGBA', (100, 100), (100, 100, 100, 255))
    
    # 加载属性图标（根据角色属性）
    attribute = character.get("element") or character.get("attribute")
    attr_icon_path = find_attribute_icon(attribute) if attribute else None
    attr_img = None
    if attr_icon_path and os.path.exists(attr_icon_path):
        attr_img = _load_cached_image(attr_icon_path, 'RGBA')
    
    # 加载Battle/Assist图标（根据角色类型，非抽卡场景用battle_xxx.png）
    card_type = character.get("type", "battle")
    type_icon_path = find_type_icon_non_gacha(card_type)
    type_img = None
    if type_icon_path and os.path.exists(type_icon_path):
        type_img = _load_cached_image(type_icon_path, 'RGBA')
    
    bg_width, bg_height = frame_img.size
    
    # 裁剪角色图的指定区域（与抽卡一致）
    char_width, char_height = char_img.size
    crop_left = int(char_width * 0.25)
    crop_right = int(char_width * 0.75)
    crop_top = int(char_height * 0.15)
    crop_bottom = int(char_height * 0.65)
    char_img_cropped = char_img.crop((crop_left, crop_top, crop_right, crop_bottom))
    
    # 缩放裁剪后的图片以适应框
    cropped_width, cropped_height = char_img_cropped.size
    cropped_ratio = cropped_width / cropped_height
    frame_ratio = bg_width / bg_height
    
    if cropped_ratio > frame_ratio:
        char_target_width = int(bg_width * 0.85)
        char_target_height = int(char_target_width / cropped_ratio)
    else:
        char_target_height = int(bg_height * 0.85)
        char_target_width = int(char_target_height * cropped_ratio)
    
    char_img_resized = char_img_cropped.resize(
        (char_target_width, char_target_height),
        Image.Resampling.LANCZOS
    )
    
    # 创建输出画布（使用透明背景）
    output = Image.new('RGBA', (bg_width, bg_height), (0, 0, 0, 0))
    
    # 角色图居中放置
    char_x = (bg_width - char_target_width) // 2
    char_y = (bg_height - char_target_height) // 2
    output.paste(char_img_resized, (char_x, char_y), char_img_resized)
    
    # 粘贴框
    output.paste(frame_img, (0, 0), frame_img)
    
    # 添加属性图标（框的左下角，在框之上）
    if attr_img:
        attr_width, attr_height = attr_img.size
        attr_x = 5
        attr_y = bg_height - attr_height - 5
        output.paste(attr_img, (attr_x, attr_y), attr_img)
    
    # 添加Battle/Assist图标（卡牌最底部，在框之上）
    if type_img:
        type_width, type_height = type_img.size
        type_x = (bg_width - type_width) // 2
        type_y = bg_height - type_height
        output.paste(type_img, (type_x, type_y), type_img)

    # B卡：叠加攻击方向箭头（颜色由属性决定）
    if card_type == "battle":
        dire_raw = character.get("attack_directions")
        if dire_raw:
            render_attack_arrows(output, dire_raw, attribute)

    # 右下角星级标记（重复个数）
    stars = character.get("stars", 3)
    render_rarity_stars(output, stars)
    
    # 转换为RGB（保留透明度）
    output_rgb = Image.new('RGB', (bg_width, bg_height), (255, 255, 255))
    output_rgb.paste(output, (0, 0), output)

    put_rendered_image("team_card", cache_key, output_rgb)
    return output_rgb


def composite_team_card(character: dict, is_battle: bool = True) -> bytes:
    """兼容旧调用方：需要 bytes 时才进行 JPEG 编码。"""
    output_rgb = composite_team_card_image(character, is_battle=is_battle)
    bio = BytesIO()
    output_rgb.save(bio, format='JPEG', optimize=False, quality=55)
    return bio.getvalue()




def build_3star_cards_image(user_id: str, characters: list, page: int = 1, page_size: int = 50,
                             filter_color: str = None, filter_type: str = None) -> tuple:
    """
    构建三星卡展示图片（50张卡一页，10列x5行）
    使用bg_000001001.png作为背景
    :param filter_color: 颜色筛选（红/绿/蓝/黄/紫）
    :param filter_type: 类型筛选（"battle"或"assist"）
    :return: (图片路径, 当前页卡牌列表, 总页数)
    """
    characters = _ensure_char_dict(characters)
    user_cards = get_user_3star_cards(user_id, characters,
                                       filter_color=filter_color,
                                       filter_type=filter_type)
    
    if not user_cards:
        return None, [], 0
    
    # 分页
    total_cards = len(user_cards)
    total_pages = (total_cards + page_size - 1) // page_size
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_cards)
    current_page_cards = user_cards[start_idx:end_idx]
    
    # 获取卡牌图片
    card_imgs = []
    for card in current_page_cards:
        card_id = card.get("card_id")
        chara = characters.get(str(card_id)) if isinstance(characters, dict) else None
        if chara:
            card_img = composite_team_card_image(chara, is_battle=True)
            if card_img:
                card_imgs.append({
                    "img": card_img,
                    "count": card.get("count", 1),
                    "card_id": card_id,
                    "type": card.get("type", "battle")
                })
    
    if not card_imgs:
        return None, current_page_cards, total_pages
    
    # 使用bg_000001001.png作为背景
    bg_path = LEVEL_DIR / "bg_000001001.png"
    if bg_path.exists():
        bg_img = _load_cached_image(bg_path, 'RGB')
        bg_w, bg_h = bg_img.size
    else:
        # 如果没有背景，使用默认尺寸
        bg = Image.new('RGB', (1920, 1080), (50, 50, 50))
        bg_w, bg_h = bg.size
    
    # 布局：10列x5行 = 50张卡
    cols = 10
    rows = 5
    gap = 10
    
    # 计算卡牌大小以适应背景
    available_width = bg_w - 40  # 左右各留20像素边距
    available_height = bg_h - 40  # 上下各留20像素边距
    
    max_card_width = (available_width - gap * (cols - 1)) // cols
    max_card_height = (available_height - gap * (rows - 1)) // rows
    
    first_card = card_imgs[0]["img"]
    orig_w, orig_h = first_card.size
    scale = min(max_card_width / orig_w, max_card_height / orig_h)
    card_width = int(orig_w * scale)
    card_height = int(orig_h * scale)
    
    total_w = cols * (card_width + gap) - gap
    total_h = rows * (card_height + gap) - gap
    start_x = (bg_w - total_w) // 2
    start_y = (bg_h - total_h) // 2
    
    # 创建最终画布
    output = Image.new('RGB', (bg_w, bg_h), (50, 50, 50))
    output.paste(bg_img, (0, 0))
    
    # 粘贴卡牌
    for i, item in enumerate(card_imgs):
        if i >= cols * rows:  # 最多50张
            break
        img = item["img"]
        count = item["count"]
        col = i % cols
        row = i // cols
        x = start_x + col * (card_width + gap)
        y = start_y + row * (card_height + gap)
        
        img_copy = img.copy()
        img_copy.thumbnail((card_width, card_height), Image.Resampling.LANCZOS)
        thumb_w, thumb_h = img_copy.size
        
        paste_x = x + (card_width - thumb_w) // 2
        paste_y = y + (card_height - thumb_h) // 2
        
        output.paste(img_copy, (paste_x, paste_y))
        
        # 如果计数大于1，在右下角添加计数标记
        if count > 1:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(output)
            badge_w = 30
            badge_h = 20
            badge_x = paste_x + thumb_w - badge_w - 2
            badge_y = paste_y + thumb_h - badge_h - 2
            draw.rounded_rectangle([badge_x, badge_y, badge_x+badge_w, badge_y+badge_h], radius=4, fill=(0, 0, 0, 200))
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                font = ImageFont.load_default()
            text = f"x{count}"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            text_x = badge_x + (badge_w - text_w) // 2
            text_y = badge_y + (badge_h - text_h) // 2
            draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
    
    # 保存图片
    output_idx = random.randint(1000, 9999)
    img_path = OUTPUT_DIR / f"team_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.png"
    output.save(img_path, format='JPEG', optimize=False, quality=55)
    
    return str(img_path), current_page_cards, total_pages


def build_team_image(team_data: dict, characters: list, hp_data: dict = None, card_stars: dict = None) -> str:
    """
    构建队伍展示图片
    第一行：6个BattleCard
    第二行：6个AssistCard（与上方一一对应）
    背景为1920x1080，调整12张卡的位置使其舒适
    :param hp_data: raid血量数据 {"hp": [3000, 0, ...], "alive": [True, False, ...]}
                    非None时在A卡下方绘制简易血条
    :param card_stars: 玩家卡牌星级 {card_id: star_level}，用于覆盖默认3星
    """
    characters = _ensure_char_dict(characters)
    battle_cards = team_data.get("battle_cards", [None] * BATTLE_CARD_COUNT)
    assist_cards = team_data.get("assist_cards", [None] * ASSIST_CARD_COUNT)
    
    from PIL import ImageDraw
    # 获取卡牌图片
    battle_imgs = []
    assist_imgs = []
    
    for card_id in battle_cards:
        if card_id:
            chara = characters.get(str(card_id))  # 直接通过card_id获取
            if chara:
                if card_stars and str(card_id) in card_stars:
                    chara = dict(chara)
                    chara['stars'] = card_stars[str(card_id)]
                battle_imgs.append(composite_team_card_image(chara, is_battle=True))
            else:
                battle_imgs.append(create_empty_slot_image())
        else:
            battle_imgs.append(create_empty_slot_image())
    
    for card_id in assist_cards:
        if card_id:
            chara = characters.get(str(card_id))
            if chara:
                if card_stars and str(card_id) in card_stars:
                    chara = dict(chara)
                    chara['stars'] = card_stars[str(card_id)]
                assist_imgs.append(composite_team_card_image(chara, is_battle=False))
            else:
                assist_imgs.append(create_empty_slot_image())
        else:
            assist_imgs.append(create_empty_slot_image())
    
    if not battle_imgs and not assist_imgs:
        return None
    
    # 固定背景尺寸：1440x810
    bg_width = 1440
    bg_height = 810
    
    # 加载抽卡背景图
    bg_path = None
    for bg_name in ["bg_000001001.png", "gacha_tmb_bg_10.png", "gacha_tmb_10_bg.png", "gacha_bg_10.png"]:
        test_path = LEVEL_DIR / bg_name
        if test_path.exists():
            bg_path = str(test_path)
            break
    
    if bg_path:
        log_info(f"使用队伍背景图片: {bg_path}")
        bg_img = _load_cached_image(bg_path, 'RGB')
        # 缩放背景图以适应1920x1080
        bg_img_resized = bg_img.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
        output = Image.new('RGB', (bg_width, bg_height), (50, 50, 50))
        output.paste(bg_img_resized, (0, 0))
    else:
        # 没有背景，使用纯色背景
        output = Image.new('RGB', (bg_width, bg_height), (50, 50, 50))
    
    # 获取卡牌尺寸
    first_card = battle_imgs[0] if battle_imgs else assist_imgs[0]
    orig_card_width, orig_card_height = first_card.size
    
    # 计算合适的卡牌大小（适应1920x1080布局）
    # 6列卡牌，每列间距约20像素
    cols = 6
    rows = 2
    gap_x = 20  # 水平间距
    gap_y = 40  # 垂直间距（战斗卡和支援卡之间）
    
    # 计算卡牌最大尺寸
    available_width = bg_width - 80  # 左右各留40像素边距
    available_height = bg_height - 120  # 上下各留60像素边距
    
    max_card_width = (available_width - gap_x * (cols - 1)) // cols
    max_card_height = (available_height - gap_y) // rows
    
    # 缩放卡牌
    scale = min(max_card_width / orig_card_width, max_card_height / orig_card_height)
    card_width = int(orig_card_width * scale)
    card_height = int(orig_card_height * scale)
    
    # 计算卡牌区域总尺寸
    total_width = card_width * cols + gap_x * (cols - 1)
    total_height = card_height * rows + gap_y
    
    # 居中放置卡牌区域
    start_x = (bg_width - total_width) // 2
    start_y = (bg_height - total_height) // 2
    
    # 粘贴BattleCard（第一行）
    for i, img in enumerate(battle_imgs):
        col = i % cols
        x = start_x + col * (card_width + gap_x)
        y = start_y
        
        img_resized = img.resize((card_width, card_height), Image.Resampling.LANCZOS)
        output.paste(img_resized, (x, y))
    
    # 粘贴AssistCard（第二行）
    for i, img in enumerate(assist_imgs):
        col = i % cols
        x = start_x + col * (card_width + gap_x)
        y = start_y + card_height + gap_y
        
        img_resized = img.resize((card_width, card_height), Image.Resampling.LANCZOS)
        output.paste(img_resized, (x, y))
    
    # 绘制Raid血条（在A卡下方）
    if hp_data and isinstance(hp_data, dict):
        draw = ImageDraw.Draw(output)
        hp_list = hp_data.get("hp", [])
        alive_list = hp_data.get("alive", [])
        maxhp_list = hp_data.get("max_hp", [])
        bar_height = 6
        bar_y_offset = 8  # A卡下方间距
        for i in range(cols):
            if i >= len(hp_list):
                break
            col = i % cols
            bx = start_x + col * (card_width + gap_x)
            by = start_y + card_height + gap_y + card_height + bar_y_offset
            bw = card_width
            # 背景（灰色）
            draw.rectangle([bx, by, bx + bw, by + bar_height], fill=(80, 80, 80))
            # 血条
            if i < len(alive_list) and not alive_list[i]:
                # 阵亡（红色）
                draw.rectangle([bx, by, bx + bw, by + bar_height], fill=(200, 50, 50))
            else:
                # 存活，按HP/max_hp比例显示
                cur_hp = hp_list[i] if i < len(hp_list) else 0
                cur_max = maxhp_list[i] if i < len(maxhp_list) and maxhp_list[i] > 0 else 10000
                pct = min(1.0, max(0.0, cur_hp / cur_max))
                fill_w = max(1, int(bw * pct))
                # 颜色：>50%绿色，>25%黄色，否则红色
                if pct > 0.5:
                    bar_color = (50, 200, 80)
                elif pct > 0.25:
                    bar_color = (200, 200, 50)
                else:
                    bar_color = (200, 80, 50)
                draw.rectangle([bx, by, bx + fill_w, by + bar_height], fill=bar_color)
    
    # 保存图片
    output_idx = random.randint(1000, 9999)
    img_path = OUTPUT_DIR / f"team_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.png"
    output.save(img_path, format='JPEG', optimize=False, quality=55)
    
    return str(img_path)


def build_vs_team_image(player_team: dict, enemy_team: dict, characters: list, card_stars: dict = None) -> str:
    """
    构建双方对战配队图：玩家在上，敌方在下，中间VS图标
    紧凑布局，压缩输出
    :param card_stars: 玩家卡牌星级 {card_id: star_level}，用于覆盖默认3星
    """
    characters = _ensure_char_dict(characters)
    battle_cards_p = player_team.get("battle_cards", [None] * BATTLE_CARD_COUNT)
    assist_cards_p = player_team.get("assist_cards", [None] * ASSIST_CARD_COUNT)
    battle_cards_e = enemy_team.get("battle_cards", [None] * BATTLE_CARD_COUNT)
    assist_cards_e = enemy_team.get("assist_cards", [None] * ASSIST_CARD_COUNT)

    def _load_team_imgs(battle_ids, assist_ids):
        b_imgs, a_imgs = [], []
        for cid in battle_ids:
            if cid:
                chara = characters.get(str(cid)) if isinstance(characters, dict) else None
                if chara and card_stars and str(cid) in card_stars:
                    chara = dict(chara)
                    chara['stars'] = card_stars[str(cid)]
                b_imgs.append(composite_team_card_image(chara, is_battle=True) if chara else create_empty_slot_image())
            else:
                b_imgs.append(create_empty_slot_image())
        for cid in assist_ids:
            if cid:
                chara = characters.get(str(cid)) if isinstance(characters, dict) else None
                if chara and card_stars and str(cid) in card_stars:
                    chara = dict(chara)
                    chara['stars'] = card_stars[str(cid)]
                a_imgs.append(composite_team_card_image(chara, is_battle=False) if chara else create_empty_slot_image())
            else:
                a_imgs.append(create_empty_slot_image())
        return b_imgs, a_imgs

    p_battle, p_assist = _load_team_imgs(battle_cards_p, assist_cards_p)
    e_battle, e_assist = _load_team_imgs(battle_cards_e, assist_cards_e)

    # 600×600 方形布局
    bg_width = 600
    cols, rows = 6, 2
    gap_x, gap_y = 4, 2
    pad_x, pad_y = 10, 4
    avail_w = bg_width - pad_x * 2
    # 计算卡牌尺寸
    all_imgs = p_battle + p_assist + e_battle + e_assist
    first = next((img for img in all_imgs if img), None)
    if not first:
        return None
    orig_w, orig_h = first.size
    max_cw = (avail_w - gap_x * (cols - 1)) // cols
    cw = max_cw
    ch = int(orig_h * cw / orig_w)
    total_w = cw * cols + gap_x * (cols - 1)
    rows_h = ch * rows + gap_y
    section_h = rows_h + pad_y * 2
    start_x = (bg_width - total_w) // 2

    # VS图标
    vs_path = LEVEL_DIR / "arena_p_icon_vs_00.png"
    vs_img = None
    vs_h = 0
    if vs_path.exists():
        vs_img = _load_cached_image(vs_path, 'RGBA')
        vs_target_h = 30
        vs_scale = vs_target_h / vs_img.height
        vs_img = vs_img.resize((int(vs_img.width * vs_scale), vs_target_h), Image.Resampling.LANCZOS)
        vs_h = vs_target_h + 2

    total_h = section_h * 2 + vs_h

    # 加载背景图并铺满整张画布
    bg_path = None
    for bg_name in ["bg_000001001.png", "gacha_tmb_bg_10.png", "gacha_tmb_10_bg.png"]:
        test_path = LEVEL_DIR / bg_name
        if test_path.exists():
            bg_path = str(test_path)
            break
    if bg_path:
        output = _load_cached_image(bg_path, 'RGB').resize((bg_width, total_h), Image.Resampling.LANCZOS)
    else:
        output = Image.new('RGB', (bg_width, total_h), (40, 40, 60))

    def _render_team_section(battle_imgs, assist_imgs, y_offset):
        start_y = y_offset + pad_y
        for i, img in enumerate(battle_imgs):
            x = start_x + (i % cols) * (cw + gap_x)
            output.paste(img.resize((cw, ch), Image.Resampling.LANCZOS), (x, start_y))
        for i, img in enumerate(assist_imgs):
            x = start_x + (i % cols) * (cw + gap_x)
            output.paste(img.resize((cw, ch), Image.Resampling.LANCZOS), (x, start_y + ch + gap_y))

    _render_team_section(p_battle, p_assist, 0)
    _render_team_section(e_battle, e_assist, section_h + vs_h)

    # 粘贴VS图标（居中）
    if vs_img:
        vs_x = (bg_width - vs_img.width) // 2
        vs_y = section_h + (vs_h - vs_img.height) // 2
        output.paste(vs_img, (vs_x, vs_y), vs_img)

    output_idx = random.randint(1000, 9999)
    img_path = OUTPUT_DIR / f"vs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.jpg"
    output.save(img_path, format='JPEG', optimize=False, quality=65)
    return str(img_path)


def create_empty_slot_image() -> Image.Image:
    """创建空槽位的占位图片"""
    # 使用三星背景作为空槽位背景
    bg_path = get_level_image(3, "bg")
    if bg_path and os.path.exists(bg_path):
        bg_img = _load_cached_image(bg_path, 'RGB')
    else:
        bg_img = Image.new('RGB', (120, 160), (50, 50, 50))
    
    # 添加"空"字提示
    from PIL import ImageDraw, ImageFont
    
    draw = ImageDraw.Draw(bg_img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    text = "空"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (bg_img.width - text_w) // 2
    text_y = (bg_img.height - text_h) // 2
    draw.text((text_x, text_y), text, fill=(150, 150, 150), font=font)
    
    return bg_img


# ========== 队伍操作函数 ==========
def set_team_card(user_id: str, position: int, card_id: str, card_type: str = "battle") -> bool:
    """
    设置队伍卡牌
    :param user_id: 用户ID
    :param position: 位置（1-6）
    :param card_id: 卡牌ID
    :param card_type: battle或assist
    :return: 是否成功，-1表示RAID队伍重复角色
    """
    if position < 1 or position > 6:
        return False

    idx = position - 1
    team_data = load_team_data(user_id)

    # 验证卡牌是否属于用户且是三星卡
    user_cards = get_user_3star_cards(user_id)
    card_found = any(str(c.get("card_id")) == str(card_id) for c in user_cards)

    if not card_found:
        return False

    # 检查同一张卡是否已在队伍的其他位置使用
    all_placed = (team_data.get("battle_cards", []) +
                  team_data.get("assist_cards", []))
    for i, existing_id in enumerate(all_placed):
        if existing_id and str(existing_id) == str(card_id):
            # 如果是同一个位置且同类型，允许覆盖（更新）
            if i == idx and card_type == "battle":
                continue
            if i == idx + 6 and card_type == "assist":  # assist位置索引偏移
                continue
            return False  # 卡牌已在其他位置使用

    # RAID槽位（7-11）检查跨队伍重复角色
    presets_data = load_presets(user_id)
    active_slot = presets_data.get("active_slot", 0)
    if 7 <= active_slot <= 11:
        presets = presets_data.get("presets", [])
        for slot_idx in range(6, min(len(presets), 11)):  # 槽位7-11（索引6-10）
            if slot_idx == active_slot - 1:  # 跳过当前槽位
                continue
            other_preset = presets[slot_idx]
            if not other_preset or not isinstance(other_preset, dict):
                continue
            other_bc = other_preset.get("battle_cards", [])
            other_ac = other_preset.get("assist_cards", [])
            for existing_id in other_bc + other_ac:
                if existing_id and str(existing_id) == str(card_id):
                    return -1  # RAID队伍不允许重复角色

    if card_type == "battle":
        team_data["battle_cards"][idx] = card_id
    elif card_type == "assist":
        team_data["assist_cards"][idx] = card_id
    else:
        return False

    save_team_data(user_id, team_data)
    return True


def clear_team_card(user_id: str, position: int, card_type: str = "battle") -> bool:
    """
    清除队伍指定位置的卡牌
    :param user_id: 用户ID
    :param position: 位置（1-6）
    :param card_type: battle或assist
    :return: 是否成功
    """
    if position < 1 or position > 6:
        return False
    
    idx = position - 1
    team_data = load_team_data(user_id)
    
    if card_type == "battle":
        team_data["battle_cards"][idx] = None
    elif card_type == "assist":
        team_data["assist_cards"][idx] = None
    else:
        return False
    
    save_team_data(user_id, team_data)
    return True


def clear_all_team(user_id: str):
    """清除整个队伍配置"""
    team_data = create_default_team()
    save_team_data(user_id, team_data)


def get_team_info(user_id: str, characters: list) -> str:
    """获取队伍信息文本"""
    characters = _ensure_char_dict(characters)
    team_data = load_team_data(user_id)
    battle_cards = team_data.get("battle_cards", [])
    assist_cards = team_data.get("assist_cards", [])

    # 检查当前活跃槽位是否为RAID槽(7-11)
    active = _get_active_slot(user_id)
    raid_tag = " [RAID]" if 7 <= active <= 11 else ""

    info = f"⚔️ 战斗卡（第1行）{raid_tag}：\n"
    for i, card_id in enumerate(battle_cards, 1):
        if card_id:
            chara = next((c for c in characters.values() if str(c.get("card_id")) == str(card_id)), None)
            if chara:
                limit_badge = ""
                if chara.get("limit_type") == "フェス限定":
                    limit_badge = "🔹"
                elif chara.get("limit_type") == "期間限定":
                    limit_badge = "🔸"
                info += f"  {i}. {limit_badge}{chara.get('name', '未知')}\n"
            else:
                info += f"  {i}. 未知卡牌\n"
        else:
            info += f"  {i}. 空\n"
    
    info += "\n🛡️ 支援卡（第2行）：\n"
    for i, card_id in enumerate(assist_cards, 1):
        if card_id:
            chara = next((c for c in characters.values() if str(c.get("card_id")) == str(card_id)), None)
            if chara:
                limit_badge = ""
                if chara.get("limit_type") == "フェス限定":
                    limit_badge = "🔹"
                elif chara.get("limit_type") == "期間限定":
                    limit_badge = "🔸"
                info += f"  {i}. {limit_badge}{chara.get('name', '未知')}\n"
            else:
                info += f"  {i}. 未知卡牌\n"
        else:
            info += f"  {i}. 空\n"
    
    return info


def auto_build_team(user_id: str, characters: list, check_raid_duplicates: bool = False) -> dict:
    """
    自动配队：AI自动配队
    核心原则：同色+同攻击类型 >> 其他，尽可能塞满6个位置
    优先三星卡，不足时用低星卡填充
    :return: 配队结果 {"success": bool, "message": str, "team": dict}
    """
    characters = _ensure_char_dict(characters)
    # 获取用户全部卡牌（按星级排序，三星优先）
    pity_data = load_pity_data(user_id)
    card_collection = pity_data.get("card_collection", {})

    all_user_cards = []
    for card_id, info in card_collection.items():
        stars = info.get("stars", 1)
        # characters是字典，key是card_id，value是角色信息
        chara = characters.get(str(card_id))  # 直接通过card_id获取
        card_type = chara.get("type", "battle") if chara else "battle"
        all_user_cards.append({
            "card_id": card_id,
            "name": info.get("name", ""),
            "stars": stars,
            "limit_type": info.get("limit_type", ""),
            "count": info.get("count", 1),
            "type": card_type,
        })

    if not all_user_cards:
        return {"success": False, "message": "没有任何卡牌！请先抽卡", "team": None}

    # 按星级降序：三星 > 二星 > 一星
    all_user_cards.sort(key=lambda x: x["stars"], reverse=True)

    # ===== 1. 获取详细卡牌信息并打分 (星级权重极大) =====
    battle_cards = []
    assist_cards = []

    for card in all_user_cards:
        card_id = card.get("card_id")
        chara = characters.get(str(card_id))
        if not chara:
            continue

        hp = chara.get("hp", 5000)
        attack = chara.get("attack", 3000)
        defense = chara.get("defense", 2000)
        speed = chara.get("speed", 500)
        dire_raw = chara.get("attack_directions", [0])
        dire_count = len(dire_raw) if isinstance(dire_raw, list) else dire_raw
        stars = card["stars"]

        # 星级是压倒性因素: 三星卡远高于低星
        star_mult = {3: 10.0, 2: 1.0, 1: 0.1}[stars]

        # FES/期间限定加分
        limit_type = chara.get("limit_type", "")
        limit_mult = 1.5 if limit_type == "フェス限定" else (1.3 if limit_type == "期間限定" else 1.0)

        # 攻击技能加分
        sk2 = chara.get("skill2", {})
        sk2_desc = sk2.get("description", "") if isinstance(sk2, dict) else chara.get("skill2_description", "")
        has_attack_skill = bool(sk2_desc and ("威力" in sk2_desc or "攻撃" in sk2_desc))

        card_score = (
            attack * 0.5 + hp * 0.2 + speed * 0.2 + defense * 0.1
        ) * star_mult * limit_mult * (1.3 if has_attack_skill else 1.0) * (1.0 + 0.1 * (dire_count - 1))

        attr_raw = str(chara.get("attribute", "")).strip()
        attr_match = attr_raw[1:] if attr_raw.startswith("超") else attr_raw

        card_info = {
            "card_id": str(card_id),
            "name": chara.get("name", ""),
            "stars": stars,
            "attribute_raw": attr_raw,
            "attribute_match": attr_match,
            "attack_type": chara.get("attack_type", "物理"),
            "side": chara.get("side", "科学"),
            "type": chara.get("type", "battle"),
            "limit_type": limit_type,
            "is_fes": limit_type == "フェス限定",
            "has_attack_skill": has_attack_skill,
            "score": card_score,
            "hp": hp, "attack": attack, "defense": defense, "speed": speed,
            "attack_directions": dire_raw,
        }

        if card_info["type"] == "battle":
            battle_cards.append(card_info)
        else:
            assist_cards.append(card_info)

    # ===== RAID去重：排除已被其他RAID队使用的卡牌 =====
    if check_raid_duplicates:
        used_cards = set()
        presets = load_presets(user_id)
        for slot_idx in range(6, MAX_PRESETS):  # 槽位7-11
            preset = presets["presets"][slot_idx] if slot_idx < len(presets["presets"]) else None
            if preset:
                for c in preset.get("battle_cards", []) or []:
                    if c:
                        used_cards.add(str(c))
                for c in preset.get("assist_cards", []) or []:
                    if c:
                        used_cards.add(str(c))
        # 从可选卡牌中排除已用卡牌
        battle_cards = [c for c in battle_cards if str(c["card_id"]) not in used_cards]
        assist_cards = [c for c in assist_cards if str(c["card_id"]) not in used_cards]

    if not battle_cards:
        return {"success": False, "message": "没有战斗卡（Battle Card）！", "team": None}

    # ===== 2. 生成所有 B×A 配对并评分 =====
    # 同色+同攻击类型 = 最重要，大幅加分确保优先匹配
    # 不同色不惩罚，确保仍能填满6个位置
    all_pairs = []
    for bi, bc in enumerate(battle_cards):
        for ai, ac in enumerate(assist_cards):
            pair_score = bc["score"] + ac["score"]

            # 同色: 5%伤害加成 + 技能联动，大幅加分
            if bc["attribute_match"] == ac["attribute_match"]:
                pair_score *= 5.0

            # 同攻击类型: 潜能联动，大幅加分
            if bc["attack_type"] == ac["attack_type"]:
                pair_score *= 4.0

            # 同阵营: 势力加成
            if bc["side"] == ac["side"]:
                pair_score *= 1.5

            # FES/限定额外加分
            if bc["is_fes"] and ac["is_fes"]:
                pair_score *= 1.5
            elif bc["is_fes"] or ac["is_fes"]:
                pair_score *= 1.2

            # 双方都有攻击技能
            if bc["has_attack_skill"] and ac["has_attack_skill"]:
                pair_score *= 1.2

            all_pairs.append({
                "b_index": bi,
                "b_card": bc,
                "a_index": ai,
                "a_card": ac,
                "pair_score": pair_score,
            })

    # 按配对分降序排序
    all_pairs.sort(key=lambda x: x["pair_score"], reverse=True)

    # ===== 3. 贪心分配：优先高分B+A组合，尽量塞满6个位置 =====
    team_battle = [None] * 6
    team_assist = [None] * 6

    used_battle = set()
    used_assist = set()
    placed = 0

    # 第一轮：分配带A卡的配对
    for pair in all_pairs:
        if placed >= 6:
            break
        if pair["b_index"] in used_battle:
            continue
        if pair["a_index"] in used_assist:
            continue

        team_battle[placed] = pair["b_card"]["card_id"]
        team_assist[placed] = pair["a_card"]["card_id"]
        used_battle.add(pair["b_index"])
        used_assist.add(pair["a_index"])
        placed += 1

    # 第二轮：未满6个，填剩余B卡（无A卡匹配）
    if placed < 6:
        for bi, bc in enumerate(battle_cards):
            if placed >= 6:
                break
            if bi in used_battle:
                continue
            team_battle[placed] = bc["card_id"]
            used_battle.add(bi)
            placed += 1

    # 第三轮：仍未满6个，填剩余A卡到支援位（无B卡对应）
    if placed < 6:
        for ai, ac in enumerate(assist_cards):
            if placed >= 6:
                break
            if ai in used_assist:
                continue
            # 找到空位
            for pos in range(6):
                if team_battle[pos] is not None and team_assist[pos] is None:
                    team_assist[pos] = ac["card_id"]
                    used_assist.add(ai)
                    break

    # ===== 4. 优化前3位置 (上场位) =====
    # 前3位按速度排序（速度快的先出手），同时考虑攻防平衡
    front_positions = []
    for i in range(min(3, placed)):
        if team_battle[i]:
            bc = next((c for c in battle_cards if c["card_id"] == team_battle[i]), None)
            if bc:
                front_positions.append((i, bc))

    # 按速度降序排列前3位
    front_positions.sort(key=lambda x: x[1]["speed"], reverse=True)

    # 重新排列前3位: 速度最快的在中间(position 1, 对应index 1),
    # 第二快的在左边(position 0), 第三快的在右边(position 2)
    if len(front_positions) >= 3:
        speed_order = sorted(front_positions, key=lambda x: x[1]["speed"], reverse=True)
        new_front = [speed_order[1], speed_order[0], speed_order[2]]  # [次快, 最快, 第三]
        new_battle = [None]*3
        new_assist = [None]*3
        for target_idx, (orig_idx, bc) in enumerate(new_front):
            new_battle[target_idx] = bc["card_id"]
            new_assist[target_idx] = team_assist[orig_idx]
        for i in range(3):
            team_battle[i] = new_battle[i]
            team_assist[i] = new_assist[i]
    elif len(front_positions) >= 2:
        speed_order = sorted(front_positions, key=lambda x: x[1]["speed"], reverse=True)
        new_front = [speed_order[1], speed_order[0]]  # [次快, 最快]
        new_battle = [None]*3
        new_assist = [None]*3
        for i in range(3):
            new_assist[i] = team_assist[i]
        for target_idx, (orig_idx, bc) in enumerate(new_front):
            new_battle[target_idx] = bc["card_id"]
            new_assist[target_idx] = team_assist[orig_idx]
        for i in range(3):
            team_battle[i] = new_battle[i] if new_battle[i] else team_battle[i]
            team_assist[i] = new_assist[i] if new_assist[i] else team_assist[i]

    # ===== 5. 保存队伍 =====
    team_data = {
        "battle_cards": team_battle,
        "assist_cards": team_assist
    }
    save_team_data(user_id, team_data)
    # 同步保存到预设槽位
    auto_save_preset(user_id)

    # ===== 6. 统计配队结果 =====
    char_dict = {str(c.get("card_id")): c for c in characters.values()}

    perfect_pairs = 0
    star3_count = 0
    team_display = []
    for i in range(6):
        b_id = team_battle[i]
        a_id = team_assist[i]
        b_name = "空"
        a_name = "空"
        b_attr = a_attr = b_type = a_type = ""
        match_info = ""
        b_stars = a_stars = 0

        if b_id:
            b_chara = char_dict.get(str(b_id), {})
            b_name = b_chara.get("name", str(b_id))
            b_attr = str(b_chara.get("attribute", ""))
            if b_attr.startswith("超"):
                b_attr = b_attr[1:]
            b_type = b_chara.get("attack_type", "")
            b_stars = sum(1 for c in all_user_cards if str(c.get("card_id")) == str(b_id) and c.get("stars", 0) >= 3)
            # Get stars from card_collection
            for uc in all_user_cards:
                if str(uc.get("card_id")) == str(b_id):
                    b_stars = uc.get("stars", 0)
                    break
            if b_stars >= 3:
                star3_count += 1

        if a_id:
            a_chara = char_dict.get(str(a_id), {})
            a_name = a_chara.get("name", str(a_id))
            a_attr = str(a_chara.get("attribute", ""))
            if a_attr.startswith("超"):
                a_attr = a_attr[1:]
            a_type = a_chara.get("attack_type", "")
            for uc in all_user_cards:
                if str(uc.get("card_id")) == str(a_id):
                    a_stars = uc.get("stars", 0)
                    break
            if a_stars >= 3:
                star3_count += 1

        if b_id and a_id:
            if b_attr == a_attr and b_type == a_type:
                perfect_pairs += 1
                match_info = " ⭐完美"
            elif b_attr == a_attr:
                match_info = " ✓同色"
            elif b_type == a_type:
                match_info = " ✓同攻"

        star_label = ""
        if b_stars < 3:
            star_label = f" [{b_stars}★]"
        pos_label = "⚔️" if i < 3 else "🛡️"
        team_display.append(f"  {pos_label}位{i+1}: {b_name}{star_label} + {a_name}{match_info}")

    battle_count = sum(1 for c in team_battle if c)
    assist_count = sum(1 for c in team_assist if c)
    selected_pairs = sum(1 for i in range(6) if team_battle[i] and team_assist[i])

    # Count FES
    fes_count = 0
    for card_id in team_battle + team_assist:
        if card_id:
            c = char_dict.get(str(card_id), {})
            if c.get("limit_type") == "フェス限定":
                fes_count += 1

    total_b = len(battle_cards)
    total_a = len(assist_cards)

    message = f"🤖 AI自动配队完成！\n"
    message += f"✅ 战斗卡: {battle_count}/6 张 (共{total_b}张可用)"
    if battle_count < 6:
        message += f"\n   ⚠️ 缺少战斗卡，已全部放入"
    message += f"\n✅ 支援卡: {assist_count}/6 张 (共{total_a}张可用)"
    message += f"\n⭐ 完美配对(同色同攻): {perfect_pairs} 组"
    message += f"\n🌟 三星卡: {star3_count} 张"
    message += f"\n🔗 B+A组合: {selected_pairs} 组"
    if fes_count:
        message += f"\n🔹 FES限定: {fes_count} 张"
    message += f"\n📋 队伍配置:\n"
    message += "\n".join(team_display)
    message += f"\n💡 前3位=上场位 | 优先同色同攻 | 塞满6位"

    return {"success": True, "message": message, "team": team_data}


# ========== 防守队系统 ==========
DEFAULT_DEFENSE_SLOT = 1  # 默认防守队槽位为1


def get_defense_slot(user_id: str) -> int:
    """获取用户的防守队槽位（默认为1）"""
    presets_data = load_presets(user_id)
    return presets_data.get("defense_slot", DEFAULT_DEFENSE_SLOT)


def set_defense_slot(user_id: str, slot: int) -> bool:
    """设置用户的防守队槽位（1-6）"""
    if slot < 1 or slot > MAX_PRESETS:
        return False
    presets_data = load_presets(user_id)
    presets_data["defense_slot"] = slot
    save_presets(user_id, presets_data)
    return True


def get_defense_team(user_id: str) -> dict:
    """获取防守队：优先使用防守槽位预设，若为空则使用当前队伍

    当玩家被挑战/战斗时，使用此队伍迎战
    """
    defense_slot = get_defense_slot(user_id)
    presets_data = load_presets(user_id)
    preset = presets_data["presets"][defense_slot - 1]
    if preset is not None:
        bc = preset.get("battle_cards", [None] * BATTLE_CARD_COUNT)
        ac = preset.get("assist_cards", [None] * ASSIST_CARD_COUNT)
        # 确保至少有1张战斗卡，否则不算有效防守队
        if any(bc):
            return {
                "battle_cards": list(bc),
                "assist_cards": list(ac)
            }
    # 预设为空或无战斗卡，回退到当前队伍
    return load_team_data(user_id)


def get_defense_team_info(user_id: str, characters: list) -> str:
    """获取防守队信息文本"""
    characters = _ensure_char_dict(characters)
    defense_slot = get_defense_slot(user_id)
    team = get_defense_team(user_id)
    battle_cards = team.get("battle_cards", [])
    assist_cards = team.get("assist_cards", [])

    lines = [f"🛡️ 防守队 (预设槽{defense_slot})："]
    for i in range(min(6, len(battle_cards))):
        b_id = battle_cards[i] if i < len(battle_cards) else None
        a_id = assist_cards[i] if i < len(assist_cards) else None
        b_name = "空"
        a_name = "空"
        if b_id and characters:
            chara = next((c for c in characters.values() if str(c.get("card_id")) == str(b_id)), None)
            if chara:
                b_name = chara.get("name", "?")
        if a_id and characters:
            chara = next((c for c in characters.values() if str(c.get("card_id")) == str(a_id)), None)
            if chara:
                a_name = chara.get("name", "?")
        lines.append(f"  {i+1}. ⚔{b_name} + 🛡{a_name}")
    return "\n".join(lines)
