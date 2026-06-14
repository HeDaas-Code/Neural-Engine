# Neural Engine

> 中文文字游戏引擎 v0 baseline

## 状态

**v0-issue-1 骨架已就位，引擎未实现。**

## 安装

```bash
# 开发依赖（pytest 等）
python3 -m pip install -r requirements-dev.txt

# 可选：PyQt6 GUI（v0 占位）
python3 -m pip install -r requirements-gui.txt
```

## 跑测

```bash
python3 -m pytest tests/
```

## 项目结构

```
src/
├── core/                  # 核心引擎（v0-issue-2 起实现）
│   ├── engine/            # 引擎进程（main / bus / protocol / interpreter / executor）
│   └── decorators/        # 修饰器实现（@style 等）
├── runtime/               # 运行时（v0-issue-18 起实现）
│   └── gui/               # PyQt6 GUI 占位
└── editor/                # 剧情编辑器（v0 不实现）

tests/                     # pytest 测试
├── parser/                # 解析器测试 + inputs/ fixture
└── executor/              # 执行器测试 + inputs/ fixture

chapters/                  # 端到端 fixture（v0-issue-19 落地）
docs/
├── adr/                   # 架构决策记录
├── prds/                  # 产品需求文档
└── agents/                # Agent 协作说明
```

## 规范与设计

- 规范：[`docs/adr/0001-v0-baseline-script-spec.md`](docs/adr/0001-v0-baseline-script-spec.md)（ADR-0001）
- 需求：[`docs/prds/0001-v0-engine-implementation.md`](docs/prds/0001-v0-engine-implementation.md)（PRD-0001）

## 进程模型

v0 采用双进程模型：core 进程负责解析+执行，runtime/gui 进程负责渲染。两进程通过 `multiprocessing.Queue` 数据总线通信。
