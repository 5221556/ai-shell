"""
uninstall.py - 卸载 AI Shell
"""

import os
import shutil
from pathlib import Path


def interactive_uninstall():
    """交互式卸载"""
    print()
    print("=" * 50)
    print("  AI Shell - 卸载")
    print("=" * 50)
    print()

    # 检测安装位置
    base_dir = Path(__file__).parent
    print(f"安装位置: {base_dir}")
    print()

    # 列出将要删除的内容
    items_to_remove = []

    # 数据目录
    data_dirs = ["logs", "context", "backups", "versions", "creative_space"]
    for d in data_dirs:
        path = base_dir / d
        if path.exists():
            size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            items_to_remove.append((path, size))

    # 配置文件
    config_files = ["config.yaml", ".env", "VERSION"]
    for f in config_files:
        path = base_dir / f
        if path.exists():
            items_to_remove.append((path, path.stat().st_size))

    # 显示将要删除的内容
    if not items_to_remove:
        print("没有找到需要清理的数据。")
        return True

    print("将要删除以下内容：")
    print()
    total_size = 0
    for path, size in items_to_remove:
        size_mb = size / 1024 / 1024
        total_size += size
        print(f"  {path.name:<20} {size_mb:.2f} MB")

    total_mb = total_size / 1024 / 1024
    print()
    print(f"  总计: {total_mb:.2f} MB")
    print()

    # 确认
    print("选项：")
    print("  1) 仅删除数据（保留程序文件）")
    print("  2) 完全卸载（删除所有文件）")
    print("  3) 取消")
    print()

    choice = input("选择 [3]: ").strip()

    if choice == "1":
        # 删除数据目录
        print()
        print("删除数据目录...")
        for path, size in items_to_remove:
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  已删除: {path.name}/")
            elif path.is_file():
                path.unlink()
                print(f"  已删除: {path.name}")

        # 重新创建空目录
        for d in data_dirs:
            (base_dir / d).mkdir(exist_ok=True)
        print()
        print("数据已清理，程序文件保留。")

    elif choice == "2":
        # 完全卸载
        print()
        print("正在删除所有文件...")

        # 删除所有内容（除了当前脚本所在的目录本身）
        for item in base_dir.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                print(f"  已删除: {item.name}")
            except Exception as e:
                print(f"  删除失败 {item.name}: {e}")

        print()
        print("卸载完成！")
        print(f"请手动删除目录: {base_dir}")

    else:
        print("取消卸载。")
        return False

    print()
    return True


def quick_uninstall():
    """快速卸载（非交互式，仅删除数据）"""
    base_dir = Path(__file__).parent

    data_dirs = ["logs", "context", "backups", "versions"]
    for d in data_dirs:
        path = base_dir / d
        if path.exists():
            shutil.rmtree(path)
            print(f"已删除: {d}/")

    config_files = ["config.yaml", ".env", "VERSION"]
    for f in config_files:
        path = base_dir / f
        if path.exists():
            path.unlink()
            print(f"已删除: {f}")

    print("数据已清理。")
