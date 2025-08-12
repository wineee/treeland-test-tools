#!/usr/bin/env python3
"""
Treeland 显示器配置测试脚本

这个脚本用于自动化测试 Wayland 合成器的显示器配置功能。它使用 wlr-randr 工具
按照预设的顺序测试各种显示器设置，包括分辨率、刷新率、旋转方向和缩放比例。

测试内容：
1. 分辨率和刷新率：
   - 遍历显示器支持的所有分辨率和刷新率组合
   - 按照 wlr-randr 输出的顺序逐个测试

2. 屏幕方向：
   - 使用 preferred 模式作为基准分辨率
   - 测试 8 种旋转方向：
     * normal: 正常方向
     * 90/180/270: 顺时针旋转相应角度
     * flipped: 水平翻转
     * flipped-90/180/270: 水平翻转后再旋转

3. 显示比例：
   - 使用 preferred 模式和 normal 方向
   - 从 0.5 到 1.5，以 0.2 为步长测试不同缩放值
   - 测试序列：0.5, 0.7, 0.9, 1.1, 1.3, 1.5

使用方法：
    ./test_display.py [--interval <秒数>]

参数说明：
    --interval: 每次更改配置后的等待时间（秒），支持小数
               默认值为 1.0 秒

示例：
    # 使用默认 1 秒间隔运行
    ./test_display.py

    # 使用 0.5 秒间隔运行
    ./test_display.py --interval 0.5

    # 使用 2.5 秒间隔运行
    ./test_display.py --interval 2.5

注意事项：
1. 确保系统已安装 wlr-randr 工具
2. 脚本会自动检测并测试所有连接的显示器
3. 可以随时按 Ctrl+C 中断测试
4. 某些显示器可能不支持特定的配置组合，遇到错误时会继续测试下一个配置
"""

import subprocess
import re
import random
import time
import argparse
from typing import Dict, List, NamedTuple

class DisplayMode(NamedTuple):
    """表示显示器支持的显示模式

    Attributes:
        width: 分辨率宽度（像素）
        height: 分辨率高度（像素）
        refresh_rate: 刷新率（赫兹）
    """
    width: int
    height: int
    refresh_rate: float

class Display:
    """表示一个显示器及其配置

    Attributes:
        name: 显示器名称（如 HDMI-A-1）
        modes: 支持的显示模式列表
        current_mode: 当前使用的显示模式
        position: 显示器位置坐标 (x, y)
        transform: 显示方向（normal、90、180等）
        scale: 显示缩放比例
        enabled: 显示器是否启用
        adaptive_sync: 自适应同步是否启用
    """
    def __init__(self, name: str):
        self.name = name
        self.modes: List[DisplayMode] = []
        self.current_mode: DisplayMode = None
        self.position = (0, 0)
        self.transform = "normal"
        self.scale = 1.0
        self.enabled = True
        self.adaptive_sync = False

def parse_wlr_randr_output() -> Dict[str, Display]:
    """解析 wlr-randr 命令的输出，获取显示器信息

    Returns:
        Dict[str, Display]: 显示器名称到显示器对象的映射字典
        
    Example:
        displays = parse_wlr_randr_output()
        for name, display in displays.items():
            print(f"显示器 {name} 支持 {len(display.modes)} 种显示模式")
    """
    displays = {}
    current_display = None

    output = subprocess.check_output(['wlr-randr'], text=True)
    print("\n=== 调试：原始输出 ===")
    print(output)
    print("=== 调试：开始解析 ===")
    
    for line in output.split('\n'):
        if not line.startswith(' '):  # 新显示器
            if '"' in line:
                name = line.split('"')[0].strip()
                print(f"\n找到显示器: {name}")
                current_display = Display(name)
                displays[name] = current_display
        elif current_display:  # 处理显示器的属性
            line = line.strip()
            if line.startswith('Modes:'):
                print("开始解析显示模式列表")
                continue
            elif line.startswith(('    ')):  # 解析模式
                print(f"正在解析模式行: {line}")
                # 使用非贪婪匹配来处理前导空格
                mode_match = re.match(r'\s*(\d+)x(\d+) px,\s*([\d.]+) Hz(\s+\([^)]*\))?', line)
                if mode_match:
                    width = int(mode_match.group(1))
                    height = int(mode_match.group(2))
                    refresh = float(mode_match.group(3))
                    flags = mode_match.group(4) or ""
                    print(f"  匹配组: width={width}, height={height}, refresh={refresh}, flags={flags}")
                    
                    mode = DisplayMode(width, height, refresh)
                    current_display.modes.append(mode)
                    print(f"  解析成功: {width}x{height}@{refresh}Hz {flags}")
                    
                    # 如果是当前模式，记录下来
                    if "current" in flags:
                        current_display.current_mode = mode
                        print("  这是当前模式")
                else:
                    print(f"  无法解析该行: {line}")
            elif 'Transform:' in line:
                current_display.transform = line.split(':')[1].strip()
                print(f"设置 transform: {current_display.transform}")
            elif 'Scale:' in line:
                current_display.scale = float(line.split(':')[1].strip())
                print(f"设置 scale: {current_display.scale}")
            elif 'Enabled:' in line:
                current_display.enabled = line.split(':')[1].strip() == 'yes'
                print(f"设置 enabled: {current_display.enabled}")

    print("\n=== 调试：解析结果 ===")
    for name, display in displays.items():
        print(f"\n显示器 {name}:")
        print(f"支持的模式数量: {len(display.modes)}")
        print(f"Transform: {display.transform}")
        print(f"Scale: {display.scale}")
        print(f"Enabled: {display.enabled}")
        if display.current_mode:
            print(f"当前模式: {display.current_mode.width}x{display.current_mode.height}@{display.current_mode.refresh_rate}Hz")

    return displays

def apply_random_config(display_name: str, display: Display):
    commands = []
    
    # 随机选择一个模式
    if display.modes:
        mode = random.choice(display.modes)
        commands.append(f'--mode {mode.width}x{mode.height}@{mode.refresh}Hz')
    
    # 随机选择一个变换
    transforms = ['normal', '90', '180', '270', 'flipped', 
                 'flipped-90', 'flipped-180', 'flipped-270']
    transform = random.choice(transforms)
    commands.append(f'--transform {transform}')
    
    # 随机缩放 (0.5 到 2.0 之间)
    scale = round(random.uniform(0.5, 2.0), 2)
    commands.append(f'--scale {scale}')
    
    # 随机开关自适应同步
    adaptive_sync = random.choice(['enabled', 'disabled'])
    commands.append(f'--adaptive-sync {adaptive_sync}')
    
    # 执行命令
    full_command = ['wlr-randr', '--output', display_name] + ' '.join(commands).split()
    print(f"执行命令: {' '.join(full_command)}")
    subprocess.run(full_command)

def run_command_with_check(command: List[str], description: str = "") -> bool:
    """执行命令并检查结果

    Args:
        command: 要执行的命令及其参数
        description: 命令的描述（用于错误信息）

    Returns:
        bool: 命令是否成功执行
    """
    print(f"执行命令: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"警告: {description}失败")
        if result.stderr:
            print(f"错误信息: {result.stderr.strip()}")
        return False
    return True

def verify_mode(display_name: str, expected_mode: DisplayMode) -> bool:
    """验证当前显示模式是否符合预期

    Args:
        display_name: 显示器名称
        expected_mode: 预期的显示模式

    Returns:
        bool: 当前模式是否符合预期
    """
    displays = parse_wlr_randr_output()
    if display_name not in displays:
        print(f"警告: 未找到显示器 {display_name}")
        return False
    
    display = displays[display_name]
    if display.current_mode is None:
        print("警告: 无法获取当前显示模式")
        return False
        
    # 验证当前模式是否与预期模式匹配
    current = display.current_mode
    if (current.width == expected_mode.width and 
        current.height == expected_mode.height and 
        abs(current.refresh_rate - expected_mode.refresh_rate) < 0.1):
        return True
    
    print(f"警告: 当前模式 {current.width}x{current.height}@{current.refresh_rate}Hz " 
          f"与预期模式 {expected_mode.width}x{expected_mode.height}@{expected_mode.refresh_rate}Hz 不匹配")
    return False

def test_all_modes(display_name: str, display: Display, interval: float):
    """测试所有可用的分辨率和刷新率

    Args:
        display_name: 显示器名称
        display: 显示器对象
        interval: 配置间隔时间（秒）
    """
    print(f"\n=== 测试所有分辨率和刷新率 ===")
    successful_modes = []
    
    # 记录初始模式
    initial_displays = parse_wlr_randr_output()
    initial_mode = None
    if display_name in initial_displays:
        initial_mode = initial_displays[display_name].current_mode

    for mode in display.modes:
        command = ['wlr-randr', '--output', display_name,
                  f'--mode {mode.width}x{mode.height}@{mode.refresh}Hz']
        
        if run_command_with_check(command, f"设置模式 {mode.width}x{mode.height}@{mode.refresh}Hz"):
            time.sleep(1)  # 等待模式切换
            if verify_mode(display_name, mode):
                successful_modes.append(mode)
                print(f"成功应用模式: {mode.width}x{mode.height}@{mode.refresh}Hz")
            else:
                print(f"警告: 模式可能未正确应用: {mode.width}x{mode.height}@{mode.refresh}Hz")
        
        time.sleep(interval)
    
    # 恢复初始模式
    if initial_mode:
        print("\n恢复初始显示模式...")
        command = ['wlr-randr', '--output', display_name,
                  f'--mode {initial_mode.width}x{initial_mode.height}@{initial_mode.refresh_rate}Hz']
        run_command_with_check(command, "恢复初始模式")
    
    print(f"\n成功测试的模式数量: {len(successful_modes)}/{len(display.modes)}")

def test_all_transforms(display_name: str, interval: float):
    """使用preferred模式测试所有方向

    Args:
        display_name: 显示器名称
        interval: 配置间隔时间（秒）
    """
    print(f"\n=== 使用preferred模式测试所有方向 ===")
    transforms = ['normal', '90', '180', '270', 'flipped', 
                 'flipped-90', 'flipped-180', 'flipped-270']
    
    successful_transforms = []
    
    # 首先设置preferred模式
    if run_command_with_check(['wlr-randr', '--output', display_name, '--preferred'],
                            "设置preferred模式"):
        time.sleep(1)  # 等待preferred模式生效
    else:
        print("警告: 无法设置preferred模式，继续使用当前模式")

    # 记录初始方向
    displays = parse_wlr_randr_output()
    initial_transform = displays[display_name].transform if display_name in displays else 'normal'
    
    for transform in transforms:
        command = ['wlr-randr', '--output', display_name, '--transform', transform]
        if run_command_with_check(command, f"设置方向 {transform}"):
            successful_transforms.append(transform)
        time.sleep(interval)
    
    # 恢复初始方向
    print("\n恢复初始方向...")
    run_command_with_check(['wlr-randr', '--output', display_name, 
                           '--transform', initial_transform],
                          "恢复初始方向")
    
    print(f"\n成功测试的方向数量: {len(successful_transforms)}/{len(transforms)}")
    if len(successful_transforms) < len(transforms):
        print("支持的方向: " + ", ".join(successful_transforms))

def test_all_scales(display_name: str, interval: float):
    """使用preferred模式和normal方向测试不同缩放值

    Args:
        display_name: 显示器名称
        interval: 配置间隔时间（秒）
    """
    print(f"\n=== 测试不同缩放值（0.5-1.5，步长0.2）===")
    
    # 记录初始配置
    displays = parse_wlr_randr_output()
    initial_scale = displays[display_name].scale if display_name in displays else 1.0
    
    # 首先设置preferred模式和normal方向
    if not run_command_with_check(['wlr-randr', '--output', display_name, '--preferred'],
                                "设置preferred模式"):
        print("警告: 无法设置preferred模式，继续使用当前模式")
    
    if not run_command_with_check(['wlr-randr', '--output', display_name, '--transform', 'normal'],
                                "设置normal方向"):
        print("警告: 无法设置normal方向，继续使用当前方向")
    
    time.sleep(1)  # 等待设置生效
    
    successful_scales = []
    scales = [round(x * 0.2 + 0.5, 1) for x in range(6)]  # 0.5到1.5，步长0.2
    
    for scale in scales:
        command = ['wlr-randr', '--output', display_name, '--scale', str(scale)]
        if run_command_with_check(command, f"设置缩放 {scale}"):
            # 验证缩放是否生效
            time.sleep(0.5)
            displays = parse_wlr_randr_output()
            if (display_name in displays and 
                abs(displays[display_name].scale - scale) < 0.01):
                successful_scales.append(scale)
                print(f"成功应用缩放: {scale}")
            else:
                print(f"警告: 缩放设置可能未生效: {scale}")
        time.sleep(interval)
    
    # 恢复初始缩放
    print("\n恢复初始缩放...")
    run_command_with_check(['wlr-randr', '--output', display_name, 
                           '--scale', str(initial_scale)],
                          "恢复初始缩放")
    
    print(f"\n成功测试的缩放值数量: {len(successful_scales)}/{len(scales)}")
    if len(successful_scales) < len(scales):
        print("支持的缩放值: " + ", ".join(map(str, successful_scales)))

def main():
    parser = argparse.ArgumentParser(description='测试显示器配置')
    parser.add_argument('--interval', type=float, default=1.0,
                    help='更改配置的时间间隔（秒，支持小数）')
    args = parser.parse_args()

    try:
        displays = parse_wlr_randr_output()
        
        for display_name, display in displays.items():
            print(f"\n开始测试显示器: {display_name}")
            
            # 1. 测试所有分辨率和刷新率
            test_all_modes(display_name, display, args.interval)
            
            # 2. 测试所有方向
            test_all_transforms(display_name, args.interval)
            
            # 3. 测试不同缩放值
            test_all_scales(display_name, args.interval)
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':
    main()
