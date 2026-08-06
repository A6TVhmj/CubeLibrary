# CubeLibrary (CL)

**CubeLibrary** 是对 Herbert Kociemba 经典 Cube Explorer（Delphi）的**彻底重构**——
不是移植、不是更新，而是以现代技术栈从零重写的魔方工作站。

汲取了两阶段算法的思想，但**架构、引擎、界面、残缺推导能力全部重新设计**。

## 为什么说是"重构"

| 维度 | 经典 Cube Explorer | CubeLibrary |
|---|---|---|
| 语言/平台 | Delphi 单文件程序 | Python + Cython，跨平台 |
| 求解引擎 | 单体过程式搜索 | 模块化：坐标层 / Cython IDA* 核 / 残缺补全 / 解析器 分层解耦 |
| 求解策略 | 两阶段 + 最优（经典） | **快解模式**（毫秒级首解，gmin 逐步收紧）+ 最优模式（保证最短） |
| 残缺状态 | 无 | **补全推导**：DFS 枚举物理合法补全 + 朝向/奇偶校验 + 并行流式出解 |
| 界面 | 原生控件 | ttkbootstrap 2.x 全新主题化（30 主题、明暗切换、4 语言） |
| 可中断性 | 有限 | **搜索中途可停止**（Cython 周期检查，UI 秒级响应） |

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

## 引擎设计（重构要点）

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
- 引擎为 Cython 扩展：`python setup.py build_ext --inplace`（附 MinGW 编译脚本可参考）

## 构建（Nuitka）

```bash
python -m nuitka --enable-plugin=tk-inter --include-package=numpy CubeLibrary.py
```

## 许可

GPL-3.0。算法思想致敬 Herbert Kociemba 的两阶段理论（`sc.pdf` 收录论文）；本项目全部代码为独立重构实现。
