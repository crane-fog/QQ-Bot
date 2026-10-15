import base64
import io
import os

from PIL import Image


def encode_image(image_path: str, max_kb: int | None = None, max_dimension: int = 4096) -> str:
    try:
        need_reformat = False
        extension = os.path.splitext(image_path)[1].lower().replace(".", "")
        if extension == "jpg":
            extension = "jpeg"
        if extension in ["png", "webp", "gif", "jpeg"]:
            mime_type = f"image/{extension}"
        else:
            need_reformat = True
        image_size = os.path.getsize(image_path)
        target_bytes = int(max_kb * 1024) if (max_kb and max_kb > 0) else None
        with Image.open(image_path) as img:
            width, height = img.size
            need_resize = width > max_dimension or height > max_dimension

            if (
                not need_resize
                and (target_bytes is None or image_size <= target_bytes)
                and not need_reformat
            ):
                with open(image_path, "rb") as f:
                    image_data = f.read()
                return f"data:{mime_type};base64,{base64.b64encode(image_data).decode('utf-8')}"

            if img.mode != "RGB":
                if img.mode in ("RGBA", "LA", "P", "PA"):
                    img = img.convert("RGBA")
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                else:
                    img = img.convert("RGB")

            # 超过尺寸限制
            if need_resize:
                # 缩放逻辑
                scale = min(max_dimension / width, max_dimension / height)
                new_width = max(1, int(width * scale))
                new_height = max(1, int(height * scale))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            if need_resize or need_reformat:
                # 检查是否这时超过大小限制
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=90, optimize=True)
                if target_bytes is None or len(buf.getvalue()) <= target_bytes:
                    return (
                        f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
                    )

            # 超过大小限制
            quality = 80
            scale = 1.0
            while True:
                buffer = io.BytesIO()
                if scale < 1.0:
                    new_width = max(1, int(img.width * scale))
                    new_height = max(1, int(img.height * scale))
                    curr_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                else:
                    curr_img = img

                curr_img.save(buffer, format="JPEG", quality=quality, optimize=True)
                compressed_data = buffer.getvalue()
                if len(compressed_data) <= target_bytes:
                    image_data = compressed_data
                    break

                if quality > 30:
                    quality -= 10
                else:
                    scale *= 0.8
                    quality = 80

                if scale < 0.05:
                    image_data = compressed_data
                    break

            return f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('utf-8')}"
    except Exception:
        # 兜底空白图
        return "data:image/gif;base64,R0lGODlhAQABAHAAACwAAAAAAQABAIH///8AAAAAAAAAAAACAkQBADs="
