"""
卡牌图片合成模块
"""
import os
import math
from io import BytesIO
from datetime import datetime
from pathlib import Path
from PIL import Image
from image_cache import get_rendered_image, load_shared_image, put_rendered_image

BASE_DIR = Path(__file__).parent
ICON_DIR = BASE_DIR / "iconimage"
LEVEL_DIR = BASE_DIR / "level"
OUTPUT_DIR = BASE_DIR / "output"

CROP_LEFT_RATIO = 0.25
CROP_RIGHT_RATIO = 0.75
CROP_TOP_RATIO = 0.15
CROP_BOTTOM_RATIO = 0.65

# 属性→RGB颜色映射（保留透明度用）
ATTRIBUTE_COLORS = {
    "红": (220, 50, 50), "赤": (220, 50, 50),
    "绿": (50, 180, 60), "緑": (50, 180, 60),
    "蓝": (50, 80, 220), "青": (50, 80, 220),
    "黄": (220, 200, 30),
    "紫": (160, 50, 210),
}
# 超属性：在基础色上加亮
for base, base_color in list(ATTRIBUTE_COLORS.items()):
    if not base.startswith("超") and len(base) == 1:
        r, g, b = base_color
        ATTRIBUTE_COLORS[f"超{base}"] = (min(255, r+40), min(255, g+40), min(255, b+40))

# 攻击方向 → 箭头文件名
DIRECTION_ARROW_MAP = {
    -1: "common_tmb_arrow_left_outline.png",   # ↖
    0:  "common_tmb_arrow_center_outline.png",  # ↑
    1:  "common_tmb_arrow_right_outline.png",   # ↗
}

# 箭头在卡牌内的位置（归一化：左=0, 中=0.5, 右=1.0）
ARROW_POSITIONS = {-1: 0.0, 0: 0.5, 1: 1.0}


def _load_asset(path, mode='RGBA'):
    return load_shared_image(path, mode)

def get_level_image(stars, layer_type):
    star_idx = stars - 1
    layer_idx = 0 if layer_type == "bg" else 1
    filename = f"gacha_tmb_{star_idx:02d}_{layer_idx:02d}"
    if stars == 3 and layer_type == "bg":
        filename += "_b"
    path = LEVEL_DIR / f"{filename}.png"
    return str(path) if path.exists() else None

def find_attribute_icon(attribute):
    if not attribute: return None
    attr_name = str(attribute).strip()
    attr_mapping = {"红":"赤","绿":"緑","蓝":"青","黄":"黄","紫":"紫",
                    "超红":"超赤","超绿":"超緑","超蓝":"超青","超黄":"超黄","超紫":"超紫"}
    mapped = attr_mapping.get(attr_name, attr_name)
    for p in [f"common_tmb_label_element_{mapped}.png",f"common_tmb_label_element_{attr_name}.png",
              f"attr_{attr_name}.png",f"attribute_{attr_name}.png",f"type_{attr_name}.png",
              f"{attr_name}_attr.png",f"{attr_name}.png"]:
        path = LEVEL_DIR / p
        if path.exists(): return str(path)
    return None

def find_type_icon(card_type):
    if not card_type: return None
    tn = str(card_type).strip().lower()
    ln = "battle" if tn == "battle" else "assist"
    for p in [f"gacha_tmb_label_{ln}.png",f"battle_{tn}.png",f"{tn}_icon.png",f"{tn}.png"]:
        path = LEVEL_DIR / p
        if path.exists(): return str(path)
    return None

def find_type_icon_non_gacha(card_type):
    """非抽卡场景使用的类型图标（优先battle_xxx.png）"""
    if not card_type: return None
    tn = str(card_type).strip().lower()
    ln = "battle" if tn == "battle" else "assist"
    for p in [f"battle_{ln}.png", f"gacha_tmb_label_{ln}.png", f"battle_{tn}.png", f"{tn}_icon.png"]:
        path = LEVEL_DIR / p
        if path.exists(): return str(path)
    return None

def get_attribute_color(attribute):
    """获取属性对应的RGB颜色，找不到返回默认灰色"""
    if not attribute: return (180, 180, 180)
    attr_name = str(attribute).strip()
    # 处理可能带超属性的
    return ATTRIBUTE_COLORS.get(attr_name, (180, 180, 180))

def colorize_image(img: Image.Image, color: tuple) -> Image.Image:
    """用指定颜色替换图像的非透明像素，保留透明度"""
    img = img.convert('RGBA')
    r, g, b, a = img.split()
    # 创建纯色图
    colored = Image.new('RGBA', img.size, (*color, 255))
    # 用原图alpha做mask
    colored.putalpha(a)
    return colored

def load_arrow_images():
    """加载3个方向箭头图片，返回dict"""
    arrows = {}
    for dire, fname in DIRECTION_ARROW_MAP.items():
        fp = LEVEL_DIR / fname
        if fp.exists():
            arrows[dire] = _load_asset(fp, 'RGBA')
    return arrows

def render_attack_arrows(card_output: Image.Image, attack_directions: list, attribute: str):
    """在卡牌图片内叠加攻击方向箭头（颜色由属性决定）。
    使用预生成的 level/common_tmb_arrow_{name}.png，colorize 一次即可。
    """
    if not attack_directions:
        return
    dire_list = attack_directions if isinstance(attack_directions, list) else [attack_directions]
    if not dire_list:
        return

    # 方向组合 → 文件名后缀
    key = tuple(sorted(dire_list))
    COMBO_NAMES = {
        (-1,): 'L', (0,): 'C', (1,): 'R',
        (-1, 0): 'LC', (0, 1): 'CR', (-1, 0, 1): 'LCR',
    }
    name = COMBO_NAMES.get(key)
    if not name:
        return

    arrow_path = LEVEL_DIR / f"common_tmb_arrow_{name}.png"
    if not arrow_path.exists():
        return

    arrow_img = _load_asset(arrow_path, 'RGBA')
    colored = colorize_image(arrow_img, get_attribute_color(attribute))
    card_output.paste(colored, (0, 0), colored)


def render_rarity_stars(card_output: Image.Image, stars: int, anchor_height: int = None,
                        right_margin: int = 4, bottom_margin: int = 10):
    """使用单颗点亮星素材，在卡牌右下角按星级横向排列。"""
    stars = max(1, min(int(stars or 1), 6))
    star_path = LEVEL_DIR / "common_tmb_icon_rarity_on.png"
    if not star_path.exists():
        return

    star_img = _load_asset(star_path, 'RGBA')
    # 原始素材为22×22；缩小并略微交叠，比例更接近原作结果页。
    star_size = 16
    step = 12
    star_img = star_img.resize((star_size, star_size), Image.Resampling.LANCZOS)
    CW, CH = card_output.size
    anchor_height = min(anchor_height or CH, CH)
    total_width = star_size + step * (stars - 1)
    sx = CW - total_width - right_margin
    sy = anchor_height - star_size - bottom_margin
    for index in range(stars):
        card_output.paste(star_img, (sx + index * step, sy), star_img)

def composite_card(character, result_style: bool = False):
    from qq_bot_ws import find_character_icon
    stars = character["stars"]
    icon_path = character.get("icon_path") or find_character_icon(character["chara_id"], stars)
    if not icon_path or not os.path.exists(icon_path):
        img = Image.new('RGBA', (150, 150), (100, 100, 100, 255))
        bio = BytesIO(); img.save(bio, format='PNG'); return bio.getvalue()
    cache_key = (
        str(character.get("card_id") or character.get("chara_id") or ""),
        os.path.abspath(str(icon_path)),
        int(stars),
        str(character.get("attribute") or ""),
        str(character.get("type") or "battle"),
        bool(result_style),
    )
    cached = get_rendered_image("gacha_card", cache_key)
    if cached is not None:
        bio = BytesIO(); cached.save(bio, format='PNG'); return bio.getvalue()
    try:
        bg = _load_asset(get_level_image(stars,"bg"), 'RGBA')
        frame = _load_asset(get_level_image(stars,"frame"), 'RGBA')
        char = _load_asset(icon_path, 'RGBA')
        CARD=122
        cw,ch=char.size
        cl,cr,ct,cb=int(cw*CROP_LEFT_RATIO),int(cw*CROP_RIGHT_RATIO),int(ch*CROP_TOP_RATIO),int(ch*CROP_BOTTOM_RATIO)
        cc=char.crop((cl,ct,cr,cb))
        ccw,cch=cc.size; ratio=ccw/cch
        if ratio>1: tw=int(CARD*0.85); th=int(tw/ratio)
        else: th=int(CARD*0.85); tw=int(th*ratio)
        cr=cc.resize((tw,th),Image.Resampling.LANCZOS)
        # 抽卡结果页需要给类型标签留出卡框外的空间；其他场景继续保持122×122。
        output_height = CARD + 18 if result_style else CARD
        out=Image.new('RGBA',(CARD,output_height),(0,0,0,0))
        cx,cy=(CARD-tw)//2,(CARD-th)//2
        out.paste(bg,(0,0)); out.paste(cr,(cx,cy),cr); out.paste(frame,(0,0),frame)
        attr=character.get("attribute")
        if attr:
            ap=find_attribute_icon(attr)
            if ap and os.path.exists(ap):
                ai=_load_asset(ap, 'RGBA'); aw,ah=ai.size
                out.paste(ai,(5,CARD-ah-5),ai)
        if result_style:
            # 星级位于卡面右下角、类型标签上方，与原作结果页层级一致。
            render_rarity_stars(out, stars, anchor_height=CARD, right_margin=4, bottom_margin=10)
        tp=find_type_icon(character.get("type","battle"))
        if tp and os.path.exists(tp):
            ti=_load_asset(tp, 'RGBA'); tw2,th2=ti.size
            type_y = CARD - th2 + (18 if result_style else 0)
            out.paste(ti,((CARD-tw2)//2,type_y),ti)
        put_rendered_image("gacha_card", cache_key, out)
        bio=BytesIO(); out.save(bio,format='PNG'); return bio.getvalue()
    except: return None

def save_card_image(card_data, output_idx):
    if not card_data: return None
    try:
        if len(card_data)==1:
            ib=composite_card(card_data[0])
            if not ib: return None
            fn=f"gacha_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.png"
            fp=OUTPUT_DIR/fn
            with open(fp,'wb') as f: f.write(ib)
            return str(fp)
        else:
            imgs=[]
            for ch in card_data:
                ib=composite_card(ch)
                if ib: imgs.append(Image.open(BytesIO(ib)))
            if not imgs: return None
            cw,ch=imgs[0].size; gap=18
            tw2=cw*5+gap*4; th=ch*2+gap
            out=Image.new('RGBA',(tw2,th),(50,50,50,255))
            for idx,img in enumerate(imgs):
                r,c=idx//5,idx%5
                x=c*(cw+gap); y=r*(ch+gap)
                out.paste(img,(x,y),img if img.mode=='RGBA' else None)
            or2=Image.new('RGB',out.size,(255,255,255))
            or2.paste(out,(0,0),out)
            fn=f"gacha_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.jpg"
            fp=OUTPUT_DIR/fn
            or2.save(str(fp),format='JPEG',optimize=True,quality=60)
            return str(fp)
    except: return None
