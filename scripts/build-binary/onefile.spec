# -*- mode: python -*-

from PyInstaller.building.build_main import Analysis
import platform
import pp
import sys
from bring import BRING as APP
from frkl.project_meta.build_binary import get_analysis_args_from_app_env

block_cipher = None

# remove tkinter dependency ( https://github.com/pyinstaller/pyinstaller/wiki/Recipe-remove-tkinter-tcl )
sys.modules["FixTk"] = None

project_dir = os.path.abspath(os.path.join(DISTPATH, "..", ".."))

analysis_args = get_analysis_args_from_app_env(APP)

print("---------------------------------------------------")
print()
print(f"app name: {APP.exe_name}")
print(f"main_module: {APP.main_module}")
print()
print("app_meta:")
pp(APP.app_meta)
print()
print("analysis data:")
pp(analysis_args)
print()
print("---------------------------------------------------")

a = a = Analysis(**analysis_args)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

#a.binaries - TOC([('libtinfo.so.5', None, None)]),
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP.exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,
)
