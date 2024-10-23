# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import copy_metadata
datas = []
datas = copy_metadata('google-api-python-client')
datas += [('public_html', 'public_html'), ('plugins', 'plugins')]

a = Analysis(['nut_gui.py'],
             pathex=['nut', 'C:\\nut'],
             binaries=[('C:\\Windows\\System32\\libusb0.dll', '.')],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='nut_gui',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True , icon='public_html\\images\\favicon.ico')
