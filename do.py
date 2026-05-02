import os
import json
from datetime import datetime
import exifread
import piexif
from PIL import Image, PngImagePlugin
from colorama import Fore, Style, init
init(autoreset=True)

# ===== 配置 =====
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".heic"}

# ===== 缓存 =====
exif_cache = {}
device_cache = {}

# ===== 工具 =====
def load_json(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except:
        return {}

device_map = load_json("device_map.json")
photographer_map = load_json("photographer_map.json")
device_map_lower = {k.lower(): v for k, v in device_map.items()}

# ===== 自动登记设备 =====
def resolve_device(raw_model):
    if not raw_model:
        return "UNK"

    raw = str(raw_model).strip()

    if raw in device_map:
        return device_map[raw]

    for k, v in device_map_lower.items():
        if k in raw.lower():
            return v

    print(f"\n[新设备] {raw}")
    short = input("设备简称(回车=UNK)：").strip() or "UNK"

    device_map[raw] = short
    json.dump(device_map, open("device_map.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    return short

# ===== 自动登记摄影师 =====
def resolve_photographer(key):
    if key in photographer_map:
        return photographer_map[key]

    print(f"\n[新摄影师key] {key}")
    name = input("摄影师名称(回车=UNKNOWN)：").strip() or "UNKNOWN"

    photographer_map[key] = name
    json.dump(photographer_map, open("photographer_map.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    return name

# ===== EXIF =====
def get_exif(p):
    if p in exif_cache:
        return exif_cache[p]
    try:
        with open(p, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            exif_cache[p] = tags
            return tags
    except:
        exif_cache[p] = {}
        return {}

# ==== 修复 EXIF ====
def fix_exif_value(tag, value):
    try:
        # ===== SceneType / FileSource 等 =====
        if tag in (41729, 41728):  # UNDEFINED
            if isinstance(value, bytes):
                return value
            if isinstance(value, int):
                return bytes([value])
            if isinstance(value, str):
                return value.encode("utf-8")
            return None

        # ===== ASCII =====
        if isinstance(value, str):
            return value.encode("utf-8")

        # ===== bytes OK =====
        if isinstance(value, bytes):
            return value

        # ===== int OK =====
        if isinstance(value, int):
            return value

        # ===== RATIONAL =====
        if isinstance(value, tuple):
            # 单个 (num, den)
            if len(value) == 2 and all(isinstance(i, int) for i in value):
                return value

            # 多个 ((num, den), ...)
            if all(
                isinstance(v, tuple) and len(v) == 2
                for v in value
            ):
                return value

        # ===== float → rational =====
        if isinstance(value, float):
            return (int(value * 10000), 10000)

        # ===== list → tuple =====
        if isinstance(value, list):
            return tuple(value)

    except:
        pass

    return None  # 无法修复

# ==== 清洗 EXIF ====
def clean_exif_full(exif_dict, log=None):
    removed = 0
    fixed = 0

    for ifd_name, ifd in exif_dict.items():
        if not isinstance(ifd, dict):
            continue

        bad_tags = []

        for tag, value in list(ifd.items()):
            new_value = fix_exif_value(tag, value)

            if new_value is None:
                bad_tags.append(tag)
                removed += 1
                if log:
                    log(f"EXIF_REMOVE | IFD={ifd_name} TAG={tag}", level="EXIF_REMOVE")
            else:
                if new_value != value:
                    ifd[tag] = new_value
                    fixed += 1
                    if log:
                        log(f"EXIF_FIX | IFD={ifd_name} TAG={tag}", level="EXIF_FIX")

        for tag in bad_tags:
            del ifd[tag]

    if log:
        log(f"EXIF_CLEAN_SUMMARY | fixed={fixed} removed={removed}", level="EXIF_CLEAN_SUMMARY")

    return exif_dict

# ==== 获取时间和设备 ====
def get_time_and_device(p):
    tags = get_exif(p)

    t = None
    d = tags.get("EXIF DateTimeOriginal")
    if d:
        try:
            t = datetime.strptime(str(d), "%Y:%m:%d %H:%M:%S")
        except:
            pass

    if not t:
        t = datetime.fromtimestamp(os.path.getmtime(p))

    dev = "UNK"
    m = tags.get("Image Model")
    if m:
        dev = resolve_device(m)

    return t, dev

def get_cached_info(p):
    if p in device_cache:
        return device_cache[p]
    t, dev = get_time_and_device(p)
    device_cache[p] = (t, dev)
    return t, dev

# ===== 写作者 =====
def write_artist(p, author, log):
    ext = os.path.splitext(p)[1].lower()

    try:
        if ext in [".jpg", ".jpeg"]:
            exif_dict = piexif.load(p)
            before = exif_dict["0th"].get(piexif.ImageIFD.Artist, b"").decode("utf-8", "ignore")

            exif_dict["0th"][piexif.ImageIFD.Artist] = author.encode("utf-8")
            exif_dict = clean_exif_full(exif_dict, log)
            piexif.insert(piexif.dump(exif_dict), p)

            log(f"EXIF_CHANGE | {p} | {before} -> {author}", level="EXIF_CHANGE")
            return True

        elif ext == ".png":
            img = Image.open(p)
            meta = PngImagePlugin.PngInfo()

            for k, v in img.info.items():
                meta.add_text(k, str(v))

            meta.add_text("Author", author)
            img.save(p, pnginfo=meta)

            log(f"EXIF_CHANGE | {p} | PNG -> {author}", level="EXIF_CHANGE")
            return True

        return False

    except Exception as e:
        log(f"EXIF_FAIL | {p} | {e}", level="FAIL")
        return False

# ===== 命名 =====
def build_name(p, used, prefix=None):
    t, device = get_cached_info(p)

    base_time = t.strftime('%Y%m%d_%H%M%S')
    key = f"{device}_{base_time}_{os.path.dirname(p)}"

    used[key] = used.get(key, 0) + 1
    idx = used[key]

    time_part = base_time if idx == 1 else f"{base_time}_{idx:03d}"

    return f"{prefix or device}_{time_part}"

# ===== 日志颜色 =====
def colorize(msg):
    if "[RENAME]" in msg: return Fore.GREEN + msg
    if "[EXIF_CHANGE]" in msg: return Fore.CYAN + msg
    if "[FAIL]" in msg: return Fore.RED + msg
    if "[SKIP]" in msg: return Fore.LIGHTBLACK_EX + msg
    if "[DRY]" in msg: return Fore.WHITE + msg
    if "[EXIF_CLEAN_SUMMARY]" in msg: return Fore.YELLOW + msg

    content = msg.split("] ", 1)[-1] if "]" in msg else msg
    if content.startswith("EXIF_FIX"): return Fore.BLUE + msg
    if content.startswith("EXIF_REMOVE"): return Fore.MAGENTA + msg
    
    return msg

# ===== 主程序 =====
def main():
    root = input("路径：").strip().strip('"')

    print("1 自动设备+自动时间")
    print("2 手动设备+自动时间")
    print("3 手动日期序号")
    print("4 仅写作者")

    mode = input("模式：").strip()
    extra4 = input("附加写作者？(y/n)：") == "y"
    dry_run = input("模拟运行(dry-run)？(y/n)：") == "y"

    prefix = None
    date_str = None

    if mode == "2":
        prefix = input("设备简称：")

    elif mode == "3":
        prefix = input("设备简称：")
        date_str = input("日期(YYYY/ YYYYMM / YYYYMMDD)：")

    author = None
    if mode == "4" or extra4:
        key = input("摄影师key：")
        author = resolve_photographer(key)

    # ===== 参数确认 =====
    print("\n===== 参数确认 =====")
    print(f"路径: {root}")
    print(f"模式: {mode}")
    print(f"prefix: {prefix}")
    print(f"date: {date_str}")
    print(f"author: {author}")
    print(f"dry_run: {dry_run}")
    print("====================")

    if input("确认执行？(y/n)：") != "y":
        return

    os.makedirs("logs", exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"logs/run_{run_id}.log"

    skip_list = []
    fail_list = []

    with open(log_path, "w", encoding="utf-8") as log_file:

        def log(msg, level="INFO"):
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}][{level}] {msg}"
            print(colorize(line))
            log_file.write(line + "\n")
            log_file.flush()

        log("===== RUN START =====")
        log(f"ROOT: {root}")
        log(f"MODE: {mode}")
        log(f"PREFIX: {prefix}")
        log(f"DATE: {date_str}")
        log(f"AUTHOR: {author}")
        log(f"DRY_RUN: {dry_run}")
        log(f"====================")
        
        used = {}
        success = skip = fail = 0

        for dp, _, fs in os.walk(root):
            for f in fs:
                p = os.path.join(dp, f)
                ext = os.path.splitext(f)[1].lower()

                try:
                    if ext not in SUPPORTED_EXT:
                        skip += 1
                        skip_list.append(p)
                        log(f"SKIP | {p} | unsupported", level="SKIP")
                        continue

                    if mode == "4":
                        ok = write_artist(p, author, log) if not dry_run else True
                        success += int(ok)
                        fail += int(not ok)
                        continue

                    if mode == "1":
                        name = build_name(p, used) + ext
                    elif mode == "2":
                        name = build_name(p, used, prefix) + ext
                    elif mode == "3":
                        key2 = f"{prefix}_{date_str}_{dp}"
                        used[key2] = used.get(key2, 0) + 1
                        name = f"{prefix}_{date_str}_{used[key2]:03d}{ext}"
                    else:
                        continue

                    new_path = os.path.join(dp, name)

                    if not os.path.exists(new_path):
                        if not dry_run:
                            os.rename(p, new_path)
                            log(f"RENAME | {p} -> {new_path}", level="RENAME")
                        else:
                            log(f"DRY_RENAME | {p} -> {new_path}", level="DRY")

                        success += 1
                        target = new_path
                    else:
                        skip += 1
                        skip_list.append(p)
                        log(f"SKIP | {p} | exists", level="SKIP")
                        target = p

                    if extra4:
                        ok = write_artist(target, author, log) if not dry_run else True
                        if not ok:
                            fail += 1
                            fail_list.append((target, "EXIF_WRITE_FAIL"))

                except Exception as e:
                    fail += 1
                    fail_list.append((p, str(e)))
                    log(f"FAIL | {p} | {e}", level="FAIL")

        log("===== RUN END =====")

    print("\n===== 汇总 =====")
    print(f"成功: {success}")
    print(f"跳过: {skip}")
    print(f"失败: {fail}")

    print("\n===== 失败文件 =====")
    for f, reason in fail_list:
        print(f"{f}  |  {reason}")

    print("\n===== 跳过文件 =====")
    for f in skip_list:
        print(f)

    print(f"\n日志: {log_path}")

if __name__ == "__main__":
    main()
