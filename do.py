import os
import json
from datetime import datetime
import exifread
import piexif
from PIL import Image, PngImagePlugin

# ===== 日志初始化 =====
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(log_dir, f"run_{run_id}.log")

log_file = open(log_path, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_file.write(msg + "\n")
    log_file.flush()

log(f"RUN_ID: {run_id}")
log("===== START =====")

# ===== 统计 =====
success_count = 0
skip_count = 0
fail_count = 0

fail_list = []
skip_list = []

# ===== 菜单 =====
def show_menu():
    print("选择模式：")
    print("1 自动设备+自动时间")
    print("2 手动设备+自动时间")
    print("3 手动日期序号")
    print("4 仅写作者")

root = input("路径：").strip().strip('"')
show_menu()
mode = input("模式：").strip()
extra4 = input("附加写作者？(y/n)：") == "y"

start_time = datetime.now()
log(f"时间: {start_time}")
log(f"路径: {root}")
log(f"模式: {mode}")
log(f"附加模式4: {extra4}")

# ===== 配置 =====
def load_json(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except:
        return {}

device_map = load_json("device_map.json")
photographer_map = load_json("photographer_map.json")

# ===== 工具函数 =====
def get_time(p):
    try:
        with open(p, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            d = tags.get("EXIF DateTimeOriginal")
            if d:
                return datetime.strptime(str(d), "%Y:%m:%d %H:%M:%S")
    except:
        pass
    return datetime.fromtimestamp(os.path.getmtime(p))

def get_device(p):
    try:
        with open(p, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            m = tags.get("Image Model")
            if m:
                raw = str(m)
                if raw in device_map:
                    return device_map[raw]
                for k in device_map:
                    if k.lower() in raw.lower():
                        return device_map[k]
    except:
        pass
    return "UNK"

def write_artist(p, author):
    ext = os.path.splitext(p)[1].lower()

    try:
        if ext in [".jpg", ".jpeg"]:
            exif_dict = piexif.load(p)
            before = exif_dict["0th"].get(piexif.ImageIFD.Artist, b"").decode("utf-8", "ignore")

            exif_dict["0th"][piexif.ImageIFD.Artist] = author.encode("utf-8")
            piexif.insert(piexif.dump(exif_dict), p)

            log(f"EXIF_CHANGE {p} | {before} -> {author}")
            return True

        elif ext == ".png":
            img = Image.open(p)
            meta = PngImagePlugin.PngInfo()
            meta.add_text("Author", author)
            img.save(p, pnginfo=meta)

            log(f"EXIF_CHANGE {p} | PNG -> {author}")
            return True

        else:
            return False

    except Exception as e:
        log(f"EXIF_FAIL {p} | {e}")
        return False

# ===== 输入 =====
if mode == "2":
    prefix = input("设备简称：")

elif mode == "3":
    prefix = input("设备简称：")
    date_str = input("日期(YYYY/ YYYYMM / YYYYMMDD)：")

if mode == "4" or extra4:
    key = input("摄影师key：")
    author = photographer_map.get(key, "UNKNOWN")

# ===== 确认 =====
if input("确认执行？(y/n)：") != "y":
    exit()

# ===== 主处理 =====
used = {}

for dp, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(dp, f)
        ext = os.path.splitext(f)[1].lower()

        try:
            if ext not in [".jpg", ".jpeg", ".png", ".mp4", ".mov", ".heic"]:
                skip_count += 1
                skip_list.append((p, "unsupported format"))
                continue

            if mode == "4":
                ok = write_artist(p, author)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    fail_list.append((p, "write artist failed"))
                continue

            if mode == "1":
                name = f"{get_device(p)}_{get_time(p).strftime('%Y%m%d_%H%M%S')}{ext}"

            elif mode == "2":
                name = f"{prefix}_{get_time(p).strftime('%Y%m%d_%H%M%S')}{ext}"

            elif mode == "3":
                key2 = f"{prefix}_{date_str}"
                used[key2] = used.get(key2, 0) + 1
                name = f"{key2}_{used[key2]:03d}{ext}"

            else:
                skip_count += 1
                skip_list.append((p, "invalid mode"))
                continue

            new = os.path.join(dp, name)

            if not os.path.exists(new):
                os.rename(p, new)
                log(f"OK {p} → {name}")
                success_count += 1
            else:
                skip_count += 1
                skip_list.append((p, "target exists"))
                continue

            if extra4:
                ok = write_artist(new, author)
                if not ok:
                    fail_count += 1
                    fail_list.append((new, "write artist failed"))

        except Exception as e:
            log(f"FAIL {p} | {e}")
            fail_count += 1
            fail_list.append((p, str(e)))

# ===== 结束 =====
end_time = datetime.now()
log(f"END: {end_time}")
log(f"耗时: {end_time - start_time}")

log("\n===== 统计结果 =====")
log(f"成功: {success_count}")
log(f"忽略: {skip_count}")
log(f"失败: {fail_count}")

log("\n===== 忽略详情 =====")
for p, reason in skip_list:
    log(f"SKIP {p} | {reason}")

log("\n===== 失败详情 =====")
for p, reason in fail_list:
    log(f"FAIL {p} | {reason}")

log_file.close()

print("\n===== 执行完成 =====")
print(f"成功: {success_count}")
print(f"忽略: {skip_count}")
print(f"失败: {fail_count}")
print(f"\n日志已生成: {log_path}")
