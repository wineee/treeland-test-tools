#!/usr/bin/env python3
"""
Treeland 应用程序压力测试工具

这个脚本用于测试 Wayland 合成器对频繁启动/关闭应用程序的处理能力。
它会从预定义的应用程序列表中随机选择程序启动，可以设置启动间隔和最大进程数。
支持监听treeland合成器状态，如果treeland意外退出则自动停止测试。
"""

import subprocess
import random
import time
import signal
import argparse
import sys
import os
from typing import List, Dict, Optional
import psutil

class AppTest:
    def __init__(self, monitor_treeland: bool = True):
        self.running_processes: Dict[int, subprocess.Popen] = {}
        self.monitor_treeland = monitor_treeland
        self.treeland_pid = None
        self.treeland_crashed = False
        self.app_list = [
            "foot",
            "deepin-terminal",
            "deepin-compressor",
            "xterm",
            "d-spy"
        ]

    def find_treeland_process(self) -> Optional[int]:
        """查找treeland进程"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == 'treeland':
                    return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None

    def check_treeland_status(self) -> bool:
        """检查treeland是否还在运行"""
        if not self.monitor_treeland:
            return True
        
        if self.treeland_crashed:
            return True  # 崩溃后继续运行，不停止测试
        
        if self.treeland_pid is None:
            self.treeland_pid = self.find_treeland_process()
            if self.treeland_pid is None:
                print("警告: 未找到treeland进程")
                return True
            print(f"找到treeland进程 PID: {self.treeland_pid}")
        
        try:
            proc = psutil.Process(self.treeland_pid)
            is_running = proc.is_running()
            if not is_running and not self.treeland_crashed:
                self.treeland_crashed = True
                print(f"\n🔥 TREELAND 崩溃检测 🔥")
                print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"treeland PID {self.treeland_pid} 已退出")
                print(f"当前运行的应用程序: {len(self.running_processes)} 个")
                print(f"应用程序PID列表: {list(self.running_processes.keys())}")
                print(f"脚本将暂停运行，不再启动新应用程序")
                print(f"应用程序进程保持运行状态，等待开发者处理")
                print(f"提示: 按 Ctrl+C 退出脚本（不会清理应用程序）")
                print("=" * 60)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            if not self.treeland_crashed:
                self.treeland_crashed = True
                print(f"\n🔥 TREELAND 崩溃检测 🔥")
                print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"treeland PID {self.treeland_pid} 已退出")
                print(f"当前运行的应用程序: {len(self.running_processes)} 个")
                print(f"应用程序PID列表: {list(self.running_processes.keys())}")
                print(f"脚本将暂停运行，不再启动新应用程序")
                print(f"应用程序进程保持运行状态，等待开发者处理")
                print(f"提示: 按 Ctrl+C 退出脚本（不会清理应用程序）")
                print("=" * 60)
            return True

    def launch_app(self, app_command: str) -> Optional[subprocess.Popen]:
        """启动应用程序

        Args:
            app_command: 应用程序命令

        Returns:
            subprocess.Popen: 启动的进程对象，如果启动失败则返回None
        """
        try:
            print(f"启动 {app_command}...")
            process = subprocess.Popen(
                app_command.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return process
        except Exception as e:
            print(f"错误: 无法启动 {app_command}: {e}")
            return None

    def cleanup(self) -> None:
        """清理所有运行的进程"""
        print("\n清理进程...")
        for pid, process in self.running_processes.items():
            try:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            except Exception as e:
                print(f"警告: 终止进程 {pid} 时出错: {e}")
        self.running_processes.clear()

    def check_processes(self, max_processes: int) -> None:
        """检查并清理已经退出的进程

        Args:
            max_processes: 最大允许的进程数
        """
        # 清理已退出的进程
        dead_pids = []
        for pid, process in self.running_processes.items():
            if process.poll() is not None:
                dead_pids.append(pid)
        for pid in dead_pids:
            del self.running_processes[pid]

        # 如果进程数超过限制，终止最早启动的进程
        while len(self.running_processes) >= max_processes:
            oldest_pid = next(iter(self.running_processes))
            oldest_process = self.running_processes[oldest_pid]
            try:
                oldest_process.terminate()
                try:
                    oldest_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    oldest_process.kill()
            except Exception as e:
                print(f"警告: 终止进程 {oldest_pid} 时出错: {e}")
            del self.running_processes[oldest_pid]

    def run_test(self, interval: float, max_processes: int, duration: int) -> None:
        """运行测试

        Args:
            interval: 启动应用程序的时间间隔（秒）
            max_processes: 最大允许的进程数
            duration: 测试持续时间（秒），0表示持续运行直到中断
        """
        start_time = time.time()
        launches = 0
        try:
            while True:
                if duration > 0 and time.time() - start_time > duration:
                    break

                # 检查treeland状态
                self.check_treeland_status()
                
                # 如果treeland已崩溃，暂停脚本运行
                if self.treeland_crashed:
                    print("treeland已崩溃，脚本暂停运行，应用程序保持打开状态...")
                    print("按 Ctrl+C 退出脚本")
                    try:
                        while True:
                            time.sleep(1)  # 无限等待，直到用户按Ctrl+C
                    except KeyboardInterrupt:
                        print("\n收到中断信号，退出脚本但不清理应用程序...")
                        return  # 直接返回，不执行cleanup

                # 检查和清理进程
                self.check_processes(max_processes)

                # 随机选择并启动一个应用
                app_command = random.choice(self.app_list)
                process = self.launch_app(app_command)
                if process:
                    self.running_processes[process.pid] = process
                    launches += 1
                    print(f"已启动 {launches} 个应用，当前运行 {len(self.running_processes)} 个进程")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n收到中断信号，正在停止测试...")
        finally:
            self.cleanup()
            elapsed = time.time() - start_time
            print(f"\n测试结束！")
            print(f"运行时间: {elapsed:.1f} 秒")
            print(f"启动次数: {launches}")
            if launches > 0:
                print(f"平均启动间隔: {elapsed/launches:.2f} 秒")

def main():
    parser = argparse.ArgumentParser(description='Treeland 应用程序压力测试工具')
    parser.add_argument('--interval', type=float, default=0.1,
                    help='应用程序启动间隔（秒），默认0.1秒')
    parser.add_argument('--max-processes', type=int, default=10,
                    help='最大同时运行的进程数，默认10个')
    parser.add_argument('--duration', type=int, default=0,
                    help='测试持续时间（秒），默认0表示持续运行直到中断')
    parser.add_argument('--no-monitor-treeland', action='store_true',
                    help='禁用treeland状态监控（默认启用监控）')
    args = parser.parse_args()

    tester = AppTest(monitor_treeland=not args.no_monitor_treeland)

    print("按 Ctrl+C 停止测试")
    print(f"启动间隔: {args.interval} 秒")
    print(f"最大进程数: {args.max_processes}")
    if args.duration > 0:
        print(f"测试时间: {args.duration} 秒")
    else:
        print("测试时间: 持续运行直到中断")
    if not args.no_monitor_treeland:
        print("监听treeland状态: 启用（崩溃时保持进程运行）")
    else:
        print("监听treeland状态: 禁用")
    print(f"应用程序列表: {tester.app_list}")
    
    tester.run_test(args.interval, args.max_processes, args.duration)

if __name__ == '__main__':
    main()
