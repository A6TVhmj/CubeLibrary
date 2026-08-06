# CubeLibrary (CL)

**CubeLibrary** 是一个现代魔方桌面工作站：交互式展开图、双引擎求解、残缺状态推导、
专业测速、高级公式解析，基于 Python + Cython 与 ttkbootstrap 2.x 全新实现。

算法思想受 Herbert Kociemba 两阶段理论启发，从零实现；计时器模块的设计参考了
csTimer。Cube Explorer 仅作为算法灵感来源与对比参照，本项目不包含其代码。

## 核心能力

- **交互式展开图**：经典等距视角，基础填色 + 自动推导面色（Ctrl 忽略整块 / Shift 忽略朝向）
- **双引擎求解**：
  - 两阶段极速模式：快解先行、逐步优化，25 步打乱毫秒级出解
  - 最少步最优模式：迭代加深保证绝对最短，支持无穷搜索
- **残缺状态推导**：输入带 `?`（未知）或小写（颜色已知、朝向忽略）的状态，自动枚举所有物理合法补全并求解；支持转体/中层转动状态（x/y/z/M/E/S）
- **专业测速**：WCA 计时器、+2/DNF、Ao5/Ao12、历史记录与动态回看、一键同步到编辑器
- **高级公式解析**：交换子 `[R, U]`、共轭 `F: [R, U]`、循环 `(R U)3`、整体逆运算
- **状态导入/导出**：54 字符状态字符串导入（可指定顶面/正面朝向）+ 导出；导入自动合法性检查
- **多语言与主题**：简体中文 / 繁體中文 / English / Polski 热切换；15 个主题家族 × 明暗

## 与 Cube Explorer 5.15 的对比（依据其公开源码）

| 维度 | Cube Explorer 5.15 | CubeLibrary |
|---|---|---|
| 语言/平台 | Delphi | Python + Cython，跨平台 |
| 两阶段求解 | 有（快解逐步优化） | 有（快解先行 + 窗口收紧） |
| 最优求解 | 有（Huge/UltraHuge 大剪枝表） | 有（双层迭代 + 小表） |
| 残缺求解 | 子空间坐标 + 专属剪枝表（down 坐标、EdgeUnknown 等） | 枚举补全（Cython 迭代 DFS + 奇偶匹配） |
| 对称性 | 48 对称表 + 对称编辑器 + 搜索降维 | 无（仅输入 24 转体规范化） |
| 图案搜索 | 有（PatternSearch） | 无 |
| Coset Explorer | 有（批量最优解） | 无 |
| 三循环求解 | 有（TripSearch） | 无 |
| 外设接口 | WebServer（机器人接口）、WebCam 读色 | 无 |
| 中心朝向（Supergroup） | 支持 | 不支持（M/E/S 报不可解） |
| 计时器 | 无 | 有（WCA 风格，参考 csTimer） |
| 公式解析 | 机动字符串输入（基础） | 交换子/共轭/循环（高级） |
| 界面 | 原生控件 | ttkbootstrap 2.x（30 主题、明暗、4 语言） |
| 随机数 | MT19937 | Python random |

## 引擎设计

- **坐标系统**：twist / flip / slice / corner / edge 分解，相位内剪枝表
- **剪枝表**：twist×slice、flip×slice、twist×flip 三张 2D 表 + 残差缓存
- **快解模式**：phase-1 到达 G1 即在小窗口内尝试 phase-2（首解秒级），窗口失败自动扩大兜底
- **搜索规范**：同面连续、相对面镜像、交替三次（X-Y-X）冗余消除
- **线程安全**：每次求解独立状态，Cython 搜索释放 GIL，残缺补全可多核并行
- **残缺补全**：角块 DFS（朝向和）+ 棱块 DFS（朝向和）+ 角棱奇偶匹配，Cython 迭代实现（生成速度数百倍于 Python 版）

## 运行

```bash
pip install -r requirements.txt
python CubeLibrary.py
```

- Python ≥ 3.10（推荐 3.13）
- 依赖：numpy、ttkbootstrap~=2.1
- 引擎为 Cython 扩展：`python setup.py build_ext --inplace`

## 构建（Nuitka）

```bash
python -m nuitka --standalone --enable-plugin=tk-inter --windows-console-mode=disable \
    --windows-icon-from-ico=icon.ico \
    --include-data-files=cl_tables_cache.npz=cl_tables_cache.npz \
    --include-data-files=icon.ico=icon.ico --include-data-files=icon.png=icon.png \
    --include-module=cl_search CubeLibrary.py
```

## 许可与致谢

GPL-3.0。

- **Herbert Kociemba**：两阶段算法理论——算法思想来源
- **csTimer**：计时器模块的设计参考
- **Cube Explorer**：经典参考实现（算法对照）
