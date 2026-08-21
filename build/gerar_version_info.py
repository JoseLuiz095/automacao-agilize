from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / "VERSAO.txt").read_text(encoding="utf-8-sig").strip()
nums = [int(x) for x in re.findall(r"\d+", version)[:4]]
while len(nums) < 4:
    nums.append(0)
a, b, c, d = nums
text = f'''VSVersionInfo(\n  ffi=FixedFileInfo(\n    filevers=({a}, {b}, {c}, {d}),\n    prodvers=({a}, {b}, {c}, {d}),\n    mask=0x3f,\n    flags=0x0,\n    OS=0x40004,\n    fileType=0x1,\n    subtype=0x0,\n    date=(0, 0)\n  ),\n  kids=[\n    StringFileInfo([\n      StringTable(\n        u'041604B0',\n        [\n          StringStruct(u'CompanyName', u'Jose Luiz'),\n          StringStruct(u'FileDescription', u'Automacao Agilize'),\n          StringStruct(u'FileVersion', u'{version}'),\n          StringStruct(u'InternalName', u'AutomacaoAgilize'),\n          StringStruct(u'LegalCopyright', u'Jose Luiz'),\n          StringStruct(u'OriginalFilename', u'AutomacaoAgilize.exe'),\n          StringStruct(u'ProductName', u'Automacao Agilize'),\n          StringStruct(u'ProductVersion', u'{version}')\n        ]\n      )\n    ]),\n    VarFileInfo([VarStruct(u'Translation', [1046, 1200])])\n  ]\n)\n'''
(ROOT / "build" / "version_info.txt").write_text(text, encoding="utf-8")
print(version)
