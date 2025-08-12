#!/usr/bin/env python3
"""
Treeland 应用程序压力测试工具

这个脚本用于测试 Wayland 合成器对频繁启动/关闭应用程序的处理能力。
它会从预定义的应用程序列表中随机选择程序启动，可以设置启动间隔和最大进程数。
"""

import subprocess
import random
import time
import signal
import argparse
import sys
import os
from typing import List, Dict, Optional
import json
import psutil

class AppTest:
    def __init__(self):
        self.running_processes: Dict[int, subprocess.Popen] = {}
        self.app_list = [
            {
                "name": "foot",
                "command": "foot",
                "category": "terminal"
            },
            {
                "name": "deepin-terminal",
                "command": "deepin-terminal",
                "category": "terminal"
            },
            {
                "name": "deepin-compressor",
                "command": "deepin-compressor",
                "category": "utility"
            },
            {
                "name": "xterm",
                "command": "xterm",
                "category": "terminal"
            },
            {
                "name": "d-spy",
                "command": "d-spy",
                "category": "development"
            }
        ]

    def load_app_list(self, file_path: str) -> None:
        """从JSON文件加载应用程序列表"""
        try:
            with open(file_path, 'r') as f:
                self.app_list = json.load(f)
        except Exception as e:
            print(f"警告: 无法加载应用程序列表文件 {file_path}: {e}")
            print("使用默认应用程序列表")

    def save_app_list(self, file_path: str) -> None:
        """保存应用程序列表到JSON文件"""
        try:
            with open(file_path, 'w') as f:
                json.dump(self.app_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"错误: 无法保存应用程序列表到 {file_path}: {e}")

    def launch_app(self, app: dict) -> Optional[subprocess.Popen]:
        """启动应用程序

        Args:
            app: 应用程序信息字典

        Returns:
            subprocess.Popen: 启动的进程对象，如果启动失败则返回None
        """
        try:
            print(f"启动 {app['name']}...")
            process = subprocess.Popen(
                app['command'].split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return process
        except Exception as e:
            print(f"错误: 无法启动 {app['name']}: {e}")
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

                # 检查和清理进程
                self.check_processes(max_processes)

                # 随机选择并启动一个应用
                app = random.choice(self.app_list)
                process = self.launch_app(app)
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
            print(f"平均启动间隔: {elapsed/launches:.2f} 秒")

def main():
    parser = argparse.ArgumentParser(description='Treeland 应用程序压力测试工具')
    parser.add_argument('--interval', type=float, default=0.1,
                    help='应用程序启动间隔（秒），默认0.1秒')
    parser.add_argument('--max-processes', type=int, default=10,
                    help='最大同时运行的进程数，默认10个')
    parser.add_argument('--duration', type=int, default=0,
                    help='测试持续时间（秒），默认0表示持续运行直到中断')
    parser.add_argument('--app-list', type=str,
                    help='应用程序列表配置文件的路径（JSON格式）')
    args = parser.parse_args()

    tester = AppTest()
    if args.app_list:
        tester.load_app_list(args.app_list)

    print("按 Ctrl+C 停止测试")
    print(f"启动间隔: {args.interval} 秒")
    print(f"最大进程数: {args.max_processes}")
    if args.duration > 0:
        print(f"测试时间: {args.duration} 秒")
    else:
        print("测试时间: 持续运行直到中断")
    print(f"应用程序列表: {[app['name'] for app in tester.app_list]}")
    
    tester.run_test(args.interval, args.max_processes, args.duration)

if __name__ == '__main__':
    main()
