# Cube Library v1.0

魔方藏书阁 — Python 复刻的 Cube Explorer（Kociemba 两阶段算法）魔方求解器。

## 功能

- **展开图编辑器** — 涂色、自定义配色、AutoFix 自动推导
- **双引擎求解** — 两阶段极速 / 最少步最优，支持无尽搜索
- **残缺魔方补全** — 部分色块推理所有合法完整状态
- **实用工具** — WCA 打乱、公式执行、中英切换、多主题

## 构建

```bash
pip install -r requirements.txt
nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter ^
       --windows-icon-from-ico=icon.ico ^
       --include-data-files=icon.png=icon.png ^
       --include-data-files=cl_config.json=cl_config.json ^
       --include-data-files=cl_tables_cache.npz=cl_tables_cache.npz ^
       CubeLibrary.py
```

输出：`dist_final/CubeLibrary.exe`（25 MB，双击即用）

---

**维护：** A6　**发布日：** 2026-05-16
