import os
import re
import argparse
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time
import platform

def pad_chapter_number(filename):
    """
    在章节编号前补0，确保章节编号至少4位
    示例: 
        "第254章 内容介绍.mp3" -> "第0254章 内容介绍.mp3"
        "第1节 开端.txt" -> "第0001节 开端.txt"
    """
    patterns = [
        r'(第)(\d+)(章)',
        r'(第)(\d+)(节)',
        r'(第)(\d+)(集)',
        r'(第)(\d+)(话)',
        r'(第)(\d+)(部分)',
        r'(第)(\d+)(卷)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            prefix = match.group(1)  # "第"
            number = match.group(2)  # "254"
            suffix = match.group(3)  # "章"
            
            # 将数字补零到至少4位
            padded_number = number.zfill(4)
            
            # 构造新章节字符串
            new_chapter = f"{prefix}{padded_number}{suffix}"
            
            # 替换原章节字符串
            return filename.replace(match.group(0), new_chapter)
    
    return filename

def process_file(args):
    """处理单个文件（多线程工作函数）"""
    file_path, dry_run, counter = args
    filename = os.path.basename(file_path)
    dirname = os.path.dirname(file_path)
    
    new_name = pad_chapter_number(filename)
    
    if new_name != filename:
        dst = os.path.join(dirname, new_name)
        if not dry_run:
            try:
                os.rename(file_path, dst)
                return (file_path, dst, True, None)
            except Exception as e:
                return (file_path, None, False, str(e))
        return (file_path, dst, True, None)
    return (file_path, file_path, False, None)

def pad_filenames(directory, dry_run=False, max_workers=4, output_log=None):
    """在文件名章节编号前补0"""
    # 支持的文件扩展名（音频 + 文本）
    supported_extensions = {
        # 音频格式
        '.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac',
        # 文本格式
        '.txt'
    }
    
    file_list = []
    log_entries = []
    
    # 收集所有支持的文件路径
    for root, _, files in os.walk(directory):
        for file in files:
            file_ext = Path(file).suffix.lower()
            if file_ext in supported_extensions:
                file_list.append(os.path.join(root, file))
    
    total_files = len(file_list)
    if total_files == 0:
        print(f"在 {directory} 中未找到支持的文件格式")
        print(f"支持的格式: {', '.join(supported_extensions)}")
        return 0, log_entries
    
    print(f"找到 {total_files} 个文件，开始处理章节编号补零...")
    changed_count = 0
    error_count = 0
    start_time = time.time()
    
    # 使用多线程处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future = executor.map(process_file, [(f, dry_run, i) for i, f in enumerate(file_list)])
        
        for i, (src, dst, changed, error) in enumerate(future, 1):
            if changed:
                changed_count += 1
                if dry_run:
                    log_entry = f"[试运行] 将重命名: {src} -> {dst}"
                    print(log_entry)
                    log_entries.append(log_entry)
                else:
                    if error:
                        log_entry = f"[错误] 重命名失败 ({src}): {error}"
                        print(log_entry)
                        log_entries.append(log_entry)
                        error_count += 1
                    else:
                        log_entry = f"已重命名: {src} -> {dst}"
                        log_entries.append(log_entry)
            
            # 进度显示
            elapsed = time.time() - start_time
            files_per_sec = i / elapsed if elapsed > 0 else 0
            
            # 每100个文件或最后更新一次进度
            if i % 100 == 0 or i == total_files:
                progress_percent = (i / total_files) * 100
                print(f"\r进度: {i}/{total_files} [{progress_percent:.1f}%] | "
                      f"速度: {files_per_sec:.2f} 文件/秒 | "
                      f"已更改: {changed_count} | "
                      f"错误: {error_count}", end='', flush=True)
    
    # 最终状态显示
    elapsed = time.time() - start_time
    print(f"\n处理完成! 用时: {elapsed:.2f}秒 | 总文件: {total_files} | 已更改: {changed_count} | 错误: {error_count}")
    
    # 写入日志文件
    if output_log:
        try:
            with open(output_log, 'w', encoding='utf-8') as log_file:
                log_file.write(f"处理目录: {directory}\n")
                log_file.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"总文件数: {total_files}\n")
                log_file.write(f"已更改文件: {changed_count}\n")
                log_file.write(f"错误数: {error_count}\n")
                log_file.write(f"用时: {elapsed:.2f}秒\n\n")
                log_file.write("详细操作日志:\n")
                for entry in log_entries:
                    log_file.write(entry + "\n")
            print(f"操作日志已保存至: {output_log}")
        except Exception as e:
            print(f"无法写入日志文件: {str(e)}")
    
    return changed_count, error_count

def is_valid_directory(path):
    """检查目录是否存在且可访问"""
    if not os.path.exists(path):
        print(f"错误: 路径 '{path}' 不存在")
        return False
    if not os.path.isdir(path):
        print(f"错误: '{path}' 不是目录")
        return False
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        print(f"错误: 没有权限访问目录 '{path}'")
        return False
    return True

def get_absolute_path(path):
    """获取绝对路径，解析相对路径和用户目录"""
    # 处理Windows盘符路径
    if platform.system() == "Windows" and len(path) == 2 and path[1] == ":":
        path += "\\"
    
    # 解析用户目录(~)
    expanded_path = os.path.expanduser(path)
    
    # 获取绝对路径
    return os.path.abspath(expanded_path)

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description='文件名章节编号补零工具 - 确保章节编号至少4位（前面补0）',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # 主要参数
    parser.add_argument(
        'directory', 
        nargs='?', 
        default='.', 
        help='要处理的目录路径（默认为当前目录）\n可以是相对路径或绝对路径\n支持 ~ 表示用户目录\n示例: /path/to/files 或 C:\\MyFiles 或 ~/Documents'
    )
    
    # 选项参数
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='试运行模式（不实际重命名文件，仅显示将要进行的更改）'
    )
    
    parser.add_argument(
        '--workers', 
        type=int, 
        default=4, 
        help='线程数（默认4，根据CPU核心数调整）\n推荐值: 4-8 (普通电脑) 或 8-16 (高性能电脑)'
    )
    
    parser.add_argument(
        '--log', 
        metavar='FILE', 
        help='将操作日志保存到指定文件\n示例: --log pad_log.txt'
    )
    
    # 添加示例说明
    parser.epilog = '''
使用示例:
1. 处理当前目录: 
   python pad_chapters.py 
   
2. 处理指定目录: 
   python pad_chapters.py "D:/有声书"
   
3. 处理用户目录: 
   python pad_chapters.py "~/Documents/AudioFiles"
   
4. 试运行模式（预览更改）: 
   python pad_chapters.py /path/to/files --dry-run
   
5. 使用8线程处理并保存日志: 
   python pad_chapters.py /path/to/files --workers 8 --log padding_log.txt

支持的文件格式:
  音频: .mp3, .wav, .flac, .m4a, .ogg, .aac
  文本: .txt

转换示例:
  第254章 内容介绍.mp3 → 第0254章 内容介绍.mp3
  第1集 开端.wav → 第0001集 开端.wav
  第25节 总结.txt → 第0025节 总结.txt
  第1234章 大结局.flac → 第1234章 大结局.flac (不变)
'''

    # 解析参数
    args = parser.parse_args()
    
    # 获取并验证目录
    target_dir = get_absolute_path(args.directory)
    
    if not is_valid_directory(target_dir):
        sys.exit(1)
    
    # 显示处理信息
    print(f"开始处理目录: {target_dir}")
    print(f"模式: {'试运行（不实际修改）' if args.dry_run else '实际重命名'}")
    print(f"线程数: {args.workers}")
    
    # 执行转换
    changed, errors = pad_filenames(
        target_dir,
        dry_run=args.dry_run,
        max_workers=args.workers,
        output_log=args.log
    )
    
    # 最终结果
    if args.dry_run:
        print(f"\n[试运行完成] 找到 {changed} 个需要补零的文件")
    else:
        print(f"\n[处理完成] 已为 {changed} 个文件补零")
    
    if errors > 0:
        print(f"警告: 发生 {errors} 个错误，请检查日志了解详情")
    
    print("\n操作结束")

if __name__ == "__main__":
    main()
