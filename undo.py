import os
import re
import piexif

log_path = input("输入日志文件路径：").strip().strip('"')

rename_pairs = []
artist_changes = []

success_count = 0
fail_count = 0

# ===== 解析日志 =====
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:

        # ===== 重命名 =====
        if line.startswith("OK ") and "→" in line:
            parts = line.strip().split(" → ")
            old = parts[0][3:]
            new_name = parts[1]
            new = os.path.join(os.path.dirname(old), new_name)

            rename_pairs.append((old, new))

        # ===== EXIF =====
        if "EXIF_CHANGE" in line:
            m = re.search(r"EXIF_CHANGE (.+?) \| (.*?) -> (.*)", line)
            if m:
                path = m.group(1)
                before = m.group(2)
                artist_changes.append((path, before))

# ❗反转顺序（关键）
rename_pairs.reverse()

# ===== 确认 =====
print(f"\n将撤销日志：{log_path}")
print(f"重命名数量: {len(rename_pairs)}")
print(f"EXIF修改数量: {len(artist_changes)}")

if input("确认继续？(y/n)：") != "y":
    exit()

# ===== 执行重命名回滚 =====
for old, new in rename_pairs:
    try:
        if os.path.exists(new):
            os.rename(new, old)
            print("恢复:", new, "→", old)
            success_count += 1
        else:
            print("缺失文件:", new)
            fail_count += 1
    except Exception as e:
        print("失败:", new, "|", e)
        fail_count += 1

# ===== 恢复EXIF =====
for path, before in artist_changes:
    try:
        if os.path.exists(path):
            exif_dict = piexif.load(path)
            exif_dict["0th"][piexif.ImageIFD.Artist] = before.encode("utf-8")
            piexif.insert(piexif.dump(exif_dict), path)
            print("恢复Artist:", path)
            success_count += 1
        else:
            print("文件不存在(EXIF):", path)
            fail_count += 1
    except Exception as e:
        print("EXIF失败:", path, "|", e)
        fail_count += 1

# ===== 结果 =====
print("\n===== 撤销完成 =====")
print(f"成功: {success_count}")
print(f"失败: {fail_count}")
