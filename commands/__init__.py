"""
dt-sim commands module - 命令處理
"""

# 導入所有命令處理器
from .dtc_command import execute as execute_dtc

# 如果有其他命令，可以在這裡添加
# from .overlay_command import execute as execute_overlay
# from .fdtoverlay_command import execute as execute_fdtoverlay

__all__ = ['execute_dtc']
