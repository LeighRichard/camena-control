#!/usr/bin/env python3
"""
代码问题修复脚本
修复 Python 3.6 兼容性和代码错误
"""

import os
import sys

print("=" * 60)
print("代码问题修复工具")
print("=" * 60)
print()

# 1. 修复 main.py 中的方法调用错误
print("[1] 修复 main.py 方法调用错误...")
main_file = "main.py"
if os.path.exists(main_file):
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'self.camera.stop()' in content:
        content = content.replace('self.camera.stop()', 'self.camera.close()')
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("    ✓ 已修复: self.camera.stop() -> self.camera.close()")
    else:
        print("    ✓ 无需修复")
else:
    print("    ✗ 文件不存在")
print()

# 2. 检查 requirements.txt
print("[2] 检查 requirements.txt...")
req_file = "requirements.txt"
if os.path.exists(req_file):
    with open(req_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    needs_update = False
    
    # 检查 dataclasses
    if 'dataclasses' not in content:
        print("    ⚠ 缺少 dataclasses 依赖")
        needs_update = True
    else:
        print("    ✓ dataclasses 已存在")
    
    # 检查 pydantic 版本
    if 'pydantic' in content and 'pydantic>=2' in content:
        print("    ⚠ Pydantic v2 不兼容 Python 3.6")
        needs_update = True
    else:
        print("    ✓ Pydantic 版本正确")
    
    if needs_update:
        print("    建议手动更新 requirements.txt:")
        print("      dataclasses>=0.6;python_version<\"3.7\"")
        print("      pydantic>=1.8.0,<2.0.0")
else:
    print("    ✗ 文件不存在")
print()

# 3. 检查 Pydantic API 使用
print("[3] 检查 Pydantic API 使用...")
config_models_file = "src/utils/config_models.py"
if os.path.exists(config_models_file):
    with open(config_models_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    if 'field_validator' in content:
        issues.append("使用了 field_validator (Pydantic v2)")
    if 'model_validator' in content:
        issues.append("使用了 model_validator (Pydantic v2)")
    if 'ConfigDict' in content:
        issues.append("使用了 ConfigDict (Pydantic v2)")
    
    if issues:
        print("    ⚠ 发现 Pydantic v2 API:")
        for issue in issues:
            print(f"      - {issue}")
        print("    需要降级到 Pydantic v1 API")
    else:
        print("    ✓ Pydantic API 兼容")
else:
    print("    ✗ 文件不存在")
print()

# 4. 检查静默异常
print("[4] 检查静默异常...")
files_to_check = [
    "src/camera/orbbec_controller.py",
    "src/camera/realsense_controller.py",
    "src/comm/manager.py",
    "src/state/manager.py"
]

silent_exceptions = []
for file_path in files_to_check:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            if 'except Exception:' in line and i < len(lines):
                next_line = lines[i].strip()
                if not next_line.startswith('logger.') and not next_line.startswith('log_'):
                    silent_exceptions.append((file_path, i, line.strip()))

if silent_exceptions:
    print(f"    ⚠ 发现 {len(silent_exceptions)} 处静默异常:")
    for file_path, line_num, line_content in silent_exceptions[:5]:
        print(f"      {file_path}:{line_num} - {line_content}")
    if len(silent_exceptions) > 5:
        print(f"      ... 还有 {len(silent_exceptions) - 5} 处")
else:
    print("    ✓ 无静默异常")
print()

# 5. 总结
print("=" * 60)
print("检查总结")
print("=" * 60)
print()
print("需要修复的问题:")
print("  1. 安装 dataclasses: pip install dataclasses")
print("  2. 降级 Pydantic: pip install 'pydantic<2.0.0'")
print("  3. 已修复 main.py 方法调用")
print()
print("建议:")
print("  - 为静默异常添加日志记录")
print("  - 完善配置解析逻辑")
print()
