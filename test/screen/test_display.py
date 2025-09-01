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
import random
import time
import argparse
import json
from typing import Dict, List, NamedTuple

# 全局调试模式开关
DEBUG_MODE = False

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
    """解析 wlr-randr --json 命令的输出，获取显示器信息

    Returns:
        Dict[str, Display]: 显示器名称到显示器对象的映射字典
        
    Example:
        displays = parse_wlr_randr_output()
        for name, display in displays.items():
            print(f"显示器 {name} 支持 {len(display.modes)} 种显示模式")
    """
    displays = {}

    try:
        output = subprocess.check_output(['wlr-randr', '--json'], text=True)
        data = json.loads(output)
        
        if DEBUG_MODE:
            print(f"\n=== 调试：JSON 数据 ===")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        
        for display_data in data:
            name = display_data['name']
            display = Display(name)
            
            # 解析基本信息
            display.enabled = display_data.get('enabled', True)
            display.transform = display_data.get('transform', 'normal')
            display.scale = display_data.get('scale', 1.0)
            display.adaptive_sync = display_data.get('adaptive_sync', False)
            
            # 解析位置信息
            if 'position' in display_data:
                pos = display_data['position']
                display.position = (pos.get('x', 0), pos.get('y', 0))
            
            # 解析显示模式
            for mode_data in display_data.get('modes', []):
                mode = DisplayMode(
                    width=mode_data['width'],
                    height=mode_data['height'],
                    refresh_rate=mode_data['refresh']
                )
                display.modes.append(mode)
                
                # 记录当前模式
                if mode_data.get('current', False):
                    display.current_mode = mode
            
            displays[name] = display
            if DEBUG_MODE:
                print(f"解析显示器 {name}: {len(display.modes)} 种模式")
                print(f"  当前模式: {display.current_mode}")
                print(f"  Transform: {display.transform}")
                print(f"  Scale: {display.scale}")
                print(f"  Position: {display.position}")
            
    except subprocess.CalledProcessError as e:
        print(f"错误: 无法执行 wlr-randr --json: {e}")
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败: {e}")
    except Exception as e:
        print(f"错误: 解析显示器信息时出错: {e}")

    return displays

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
                  '--mode', f'{mode.width}x{mode.height}@{mode.refresh_rate}']
        
        if run_command_with_check(command, f"设置模式 {mode.width}x{mode.height}@{mode.refresh_rate}Hz"):
            time.sleep(1)  # 等待模式切换
            if verify_mode(display_name, mode):
                successful_modes.append(mode)
                print(f"成功应用模式: {mode.width}x{mode.height}@{mode.refresh_rate}Hz")
            else:
                print(f"警告: 模式可能未正确应用: {mode.width}x{mode.height}@{mode.refresh_rate}Hz")
        
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
    parser.add_argument('--interval', type=float, default=5.0,
                    help='更改配置的时间间隔（秒，支持小数）')
    parser.add_argument('--debug', action='store_true',
                    help='启用详细的调试输出')
    args = parser.parse_args()

    global DEBUG_MODE
    DEBUG_MODE = args.debug

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
