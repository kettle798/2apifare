#!/usr/bin/env python3
"""
检查项目中所有 import 的第三方库是否都在 requirements.txt 中
"""
import os
import re
import sys
from pathlib import Path

# Python 标准库模块（不需要安装）
STDLIB_MODULES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
    'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
    'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
    'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
    'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
    'dis', 'distutils', 'doctest', 'email', 'encodings', 'enum', 'errno', 'faulthandler',
    'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'formatter', 'fractions', 'ftplib',
    'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib', 'grp',
    'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr', 'imp',
    'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword',
    'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap',
    'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt',
    'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse',
    'os', 'ossaudiodev', 'parser', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes',
    'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'posixpath', 'pprint',
    'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue',
    'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
    'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
    'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd',
    'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct',
    'subprocess', 'sunau', 'symbol', 'symtable', 'sys', 'sysconfig', 'syslog',
    'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap',
    'threading', 'time', 'timeit', 'tkinter', 'token', 'tokenize', 'trace', 'traceback',
    'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing', 'unicodedata',
    'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
    'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp',
    'zipfile', 'zipimport', 'zlib', '_thread'
}

def extract_imports_from_file(filepath):
    """从 Python 文件中提取所有 import 语句"""
    imports = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 匹配 import xxx 和 from xxx import yyy
        import_pattern = r'^\s*(?:from\s+(\S+)|import\s+(\S+))'
        
        for line in content.split('\n'):
            match = re.match(import_pattern, line)
            if match:
                module = match.group(1) or match.group(2)
                # 获取顶级模块名
                top_module = module.split('.')[0]
                imports.add(top_module)
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}")
    
    return imports

def get_all_python_files(root_dir):
    """获取所有 Python 文件"""
    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # 跳过虚拟环境和缓存目录
        dirs[:] = [d for d in dirs if d not in {'.venv', 'venv', '__pycache__', '.git', 'node_modules', 'build', 'dist'}]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files

def parse_requirements(requirements_file):
    """解析 requirements.txt 文件"""
    packages = set()
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue
                # 提取包名（去掉版本号和额外选项）
                package = re.split(r'[>=<\[;]', line)[0].strip()
                # 标准化包名（转小写，替换下划线和连字符）
                package = package.lower().replace('_', '-').replace('python-', '')
                packages.add(package)
    except FileNotFoundError:
        print(f"Error: {requirements_file} not found")
        return set()
    
    return packages

def main():
    project_root = Path(__file__).parent
    
    print("🔍 检查项目依赖...")
    print("=" * 70)
    
    # 获取所有 Python 文件
    python_files = get_all_python_files(project_root)
    print(f"📁 找到 {len(python_files)} 个 Python 文件")
    
    # 提取所有 import
    all_imports = set()
    for filepath in python_files:
        imports = extract_imports_from_file(filepath)
        all_imports.update(imports)
    
    # 过滤掉标准库和本地模块
    third_party_imports = {
        imp for imp in all_imports 
        if imp  # 不为空
        and imp not in STDLIB_MODULES 
        and not imp.startswith('src')
        and not imp.startswith('antigravity')
        and imp not in {'config', 'log', 'web'}
    }
    
    print(f"📦 找到 {len(third_party_imports)} 个第三方库导入")
    
    # 解析 requirements.txt
    requirements_file = project_root / 'requirements.txt'
    required_packages = parse_requirements(requirements_file)
    
    print(f"📋 requirements.txt 中有 {len(required_packages)} 个包")
    print("=" * 70)
    
    # 包名映射（import 名称 -> PyPI 包名）
    PACKAGE_MAPPING = {
        'jwt': 'pyjwt',
        'dotenv': 'python-dotenv',
        'multipart': 'python-multipart',
        'starlette': 'fastapi',  # starlette 是 fastapi 的依赖
        'PIL': 'pillow',
        'cv2': 'opencv-python',
        'sklearn': 'scikit-learn',
        'yaml': 'pyyaml',
    }
    
    # 检查缺失的依赖
    missing = []
    for imp in sorted(third_party_imports):
        # 标准化导入名称
        package_name = PACKAGE_MAPPING.get(imp, imp).lower().replace('_', '-')
        
        if package_name not in required_packages:
            missing.append((imp, package_name))
    
    if missing:
        print("❌ 发现缺失的依赖:")
        for imp, pkg in missing:
            print(f"   - {imp} (应该添加: {pkg})")
        print("\n建议添加到 requirements.txt:")
        for imp, pkg in missing:
            print(f"   {pkg}")
        return 1
    else:
        print("✅ 所有第三方库都已在 requirements.txt 中!")
        print("\n已声明的第三方库:")
        for imp in sorted(third_party_imports):
            print(f"   ✓ {imp}")
        return 0

if __name__ == '__main__':
    sys.exit(main())
