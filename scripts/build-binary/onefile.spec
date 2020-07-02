# -*- mode: python -*-

from PyInstaller.building.build_main import Analysis
import platform
import pp
import sys
from frtls.introspection.pkg_env import PythonEnvMetadata

block_cipher = None

# remove tkinter dependency ( https://github.com/pyinstaller/pyinstaller/wiki/Recipe-remove-tkinter-tcl )
sys.modules["FixTk"] = None

project_dir = os.path.abspath(os.path.join(DISTPATH, "..", ".."))

print(f"project dir: {project_dir}")
pkg_md = PythonEnvMetadata(project_dir=project_dir, main_pkg="bring")

analysis_args = pkg_md.analysis_data

print("---------------------------------------------------")
print()
print(f"app name: {pkg_md.app_name}")
print(f"main_pkg: {pkg_md.main_pkg}")
print()
print("pkg_meta:")
pp(pkg_md.pkg_meta)
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
    name=pkg_md.app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,
)
