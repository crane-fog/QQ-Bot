from Plugins import plugin_main, Plugins
from Event.EventHandler import GroupMessageEventHandler
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
import re

def filter_cq_code(text: str) -> str:
    face_dict = {4: "[得意]", 5: "[流泪]", 8: "[睡]", 9: "[大哭]", 10: "[尴尬]", 12: "[调皮]", 14: "[微笑]", 16: "[酷]", 21: "[可爱]", 23: "[傲慢]", 24: "[饥饿]", 25: "[困]", 26: "[惊恐]", 27: "[流汗]", 28: "[憨笑]", 29: "[悠闲]", 30: "[奋斗]", 32: "[疑问]", 33: "[嘘]", 34: "[晕]", 38: "[敲打]", 39: "[再见]", 41: "[发抖]", 42: "[爱情]", 43: "[跳跳]", 49: "[拥抱]", 53: "[蛋糕]", 60: "[咖啡]", 63: "[玫瑰]", 66: "[爱心]", 74: "[太阳]", 75: "[月亮]", 76: "[赞]", 78: "[握手]", 79: "[胜利]", 85: "[飞吻]", 89: "[西瓜]", 96: "[冷汗]", 97: "[擦汗]", 98: "[抠鼻]", 99: "[鼓掌]", 100: "[糗大了]", 101: "[坏笑]", 102: "[左哼哼]", 103: "[右哼哼]", 104: "[哈欠]", 106: "[委屈]", 109: "[左亲亲]", 111: "[可怜]", 116: "[示爱]", 118: "[抱拳]", 120: "[拳头]", 122: "[爱你]", 123: "[NO]", 124: "[OK]", 125: "[转圈]", 129: "[挥手]", 144: "[喝彩]", 147: "[棒棒糖]", 171: "[茶]", 173: "[泪奔]", 174: "[无奈]", 175: "[卖萌]", 176: "[小纠结]", 179: "[doge]", 180: "[惊喜]", 181: "[骚扰]", 182: "[笑哭]", 183: "[我最美]", 201: "[点赞]", 203: "[托脸]", 212: "[托腮]", 214: "[啵啵]", 219: "[蹭一蹭]", 222: "[抱抱]", 227: "[拍手]", 232: "[佛系]", 240: "[喷脸]", 243: "[甩头]", 246: "[加油抱抱]", 262: "[脑阔疼]", 264: "[捂脸]", 265: "[辣眼睛]", 266: "[哦哟]", 267: "[头秃]", 268: "[问号脸]", 269: "[暗中观察]", 270: "[emm]", 271: "[吃瓜]", 272: "[呵呵哒]", 273: "[我酸了]", 277: "[汪汪]", 278: "[汗]", 281: "[无眼笑]", 282: "[敬礼]", 284: "[面无表情]", 285: "[摸鱼]", 287: "[哦]", 289: "[睁眼]", 290: "[敲开心]", 293: "[摸锦鲤]", 294: "[期待]", 297: "[拜谢]", 298: "[元宝]", 299: "[牛啊]", 305: "[右亲亲]", 306: "[牛气冲天]", 307: "[喵喵]", 314: "[仔细分析]", 315: "[加油]", 318: "[崇拜]", 319: "[比心]", 320: "[庆祝]", 322: "[拒绝]", 324: "[吃糖]", 326: "[生气]"}

    # 处理 at
    text = re.sub(r'\[CQ:at,qq=[^,]+,name=([^\]]+)\]', r'\1', text)

    # 处理 face
    def face_replacer(match):
        face_id_str = match.group(1)   # 正则捕获的 id
        try:
            face_id = int(face_id_str)
        except ValueError:
            face_id = face_id_str
        return face_dict.get(face_id, face_id_str)
    text = re.sub(r'\[CQ:face,id=(\d+)\]', face_replacer, text)

    # 处理其他CQ码 -> xxx
    def other_cq_replacer(match):
        cq_type = '[' + match.group(1) + ']'
        return cq_type
    text = re.sub(r'\[CQ:([^,\]]+)[^\]]*\]', other_cq_replacer, text)

    return text

def generate_img(text: str, output_path: str, base_image_path: str = "C:/monika/Plugins/TheresaDora/base.jpg"):
    text = filter_cq_code(text)
    # 打开原始图片
    img = Image.open(base_image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 限制区域 (可调安全边距)
    box_x, box_y = 10, 10       # 区域左上角
    max_width, max_height = 400, 400
    safe_pad = 4  # 安全边距防止贴边

    # 字体
    def get_font(size):
        font_paths = [
            "msyh.ttc",  # 中文微软雅黑
            "seguiemj.ttf",  # Windows Emoji 字体
            "C:/Users/Administrator/AppData/Local/Microsoft/Windows/Fonts/unifont-17.0.01.otf",
            "C:/Users/Administrator/AppData/Local/Microsoft/Windows/Fonts/unifont_upper-17.0.01.otf"
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size, encoding="utf-8")
            except Exception:
                continue
        return ImageFont.load_default()

    # 按像素宽度手动换行并检测是否溢出
    def layout_lines(font):
        lines = []
        line_heights = []
        current_line = ""
        # 行距：随字号调整
        line_spacing = max(4, round(font.size * 0.12))
        for ch in text:
            test_line = current_line + ch
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w + safe_pad * 2 > max_width and current_line:  # 换行
                # 记录当前行
                bbox_line = draw.textbbox((0, 0), current_line, font=font)
                h = bbox_line[3] - bbox_line[1]
                lines.append(current_line)
                line_heights.append(h)
                current_line = ch
            else:
                current_line = test_line
        if current_line:
            bbox_line = draw.textbbox((0, 0), current_line, font=font)
            h = bbox_line[3] - bbox_line[1]
            lines.append(current_line)
            line_heights.append(h)
        # 计算总高度
        if not lines:
            return False, [], [], 0, line_spacing
        total_height = sum(line_heights) + line_spacing * (len(lines) - 1)
        fits = total_height + safe_pad * 2 <= max_height
        return fits, lines, line_heights, total_height, line_spacing

    # 选择合适字体大小（自顶向下）
    font_size = 80
    best = None
    while font_size >= 10:
        font = get_font(font_size)
        ok, lines, line_heights, total_h, line_spacing = layout_lines(font)
        if ok:
            best = (font_size, font, lines, line_heights, total_h, line_spacing)
            break
        font_size -= 2
    if best is None:
        # 退化：使用最小字号强制截断
        font_size = 10
        font = get_font(font_size)
        ok, lines, line_heights, total_h, line_spacing = layout_lines(font)
        best = (font_size, font, lines, line_heights, total_h, line_spacing)
    font_size, font, lines, line_heights, total_height, line_spacing = best

    # 垂直居中起点
    y = box_y + (max_height - total_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = line_heights[i]
        x = box_x + (max_width - w) // 2
        with Pilmoji(img) as pilmoji:
            pilmoji.text(
                (x, y),
                line,
                fill=(0, 0, 0),
                font=font,
                emoji_position_offset=(0, font.size // 5)  # 👈 下移 1/5 字号
            )
        y += line_heights[i] + line_spacing

    img.save(output_path)

class TheresaDora(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaDora"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                制作哆啦A梦大叫图片
                                usage: Dora <内容>
                            """
        self.init_status()

    @plugin_main(check_group=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        group_id = event.group_id
        message = event.message
        if not message.startswith("Dora"):
            return

        cmd = " ".join(message.split(" ")[1:])
        if not cmd:
            self.api.GroupService.send_group_msg(self, group_id=group_id, message="请输入内容")
            return
        cmd += "！"

        path = f"C:/monika/Plugins/TheresaDora/temp/{event.user_id}_{event.message_id}.jpg"

        generate_img(cmd, path)

        self.api.GroupService.send_group_img(self, group_id=group_id, image_path=path)
        return
