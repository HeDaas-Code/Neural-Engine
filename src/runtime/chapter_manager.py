"""V2-04 · Task 2 — runtime 章节管理器。

职责：
- 监听 EngineBus 上的 RouteEvt → 加载新章节 .md → 新建 Executor → run
- 监听 ChapterEndEvt → 退出主循环
- 支持嵌套：chapter02.md 内部 id:end:chapter03 → chapter03.md
  （外层 run() 循环持续处理 RouteEvt，遇到 ChapterEndEvt 才 break）

设计：
- executor_factory 注入：默认 `lambda story, bus, **kw: Executor(story, bus, **kw)`
  测试可传 RecordingExecutor 替代真 Executor
- shared_state 可选：跨章节复用同一 GameState（V2-04 OQ-3）
- 路径加载复用 runtime.load_chapter.load_chapter_safe（间接复用 P0-S1 校验）

不依赖：
- core.engine.executor 的具体类（仅在默认 factory 引用）
- EngineBus 类（仅假设 bus 有 get_evt + put_evt + get_cmd 接口）
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.engine.executor import Executor, GameState
from core.engine.protocol import RouteEvt, ChapterEndEvt

from runtime.load_chapter import load_chapter_safe


def _default_executor_factory(story, bus, **kwargs) -> Executor:
    """默认 executor 工厂：用 core.engine.executor.Executor 构造。

    测试可注入自己的 factory 走 mock 路径（避免真跑 blocks）。
    """
    return Executor(story, bus, **kwargs)


class ChapterManager:
    """章节加载器 —— 监听 RouteEvt 跨章节跳转。

    Args:
        chapters_root: 章节 .md 文件所在目录。RouteEvt(target="chapter02")
            会拼成 chapters_root / "chapter02.md"。
        bus: 双向 bus（GUI ↔ Engine 进程间）。需要有 get_evt() / put_evt() 接口。
        executor_factory: 可选，构造 Executor 的工厂。
            签名 `(story, bus, **kwargs) -> Executor`。
            默认 `_default_executor_factory`。
        shared_state: 可选，跨章节复用的 GameState。None → 每个章节新建（v0 行为）。

    Example:
        >>> mgr = ChapterManager(Path("chapters"), bus, shared_state=GameState())
        >>> mgr.run()  # 阻塞循环：RouteEvt → 加载新章节 + run executor；ChapterEndEvt → break
    """

    def __init__(
        self,
        chapters_root: Path,
        bus,
        *,
        executor_factory: Optional[Callable] = None,
        shared_state: Optional[GameState] = None,
        initial_story=None,
    ):
        """构造 ChapterManager。

        Args:
            chapters_root: 章节 .md 文件所在目录。
            bus: 双向 bus。
            executor_factory: 构造 Executor 的工厂。默认 Executor(story, bus, **kw)。
            shared_state: 跨章节复用的 GameState（V2-04 OQ-3）。
            initial_story: 第一个章节的 Story（CLI 单章节入口用）。
                None → 等待 RouteEvt 启动；非 None → run() 时先跑这个 story，
                然后进入 while 循环处理 RouteEvt / ChapterEndEvt。
        """
        self.chapters_root = Path(chapters_root)
        self.bus = bus
        self._executor_factory = executor_factory or _default_executor_factory
        self._shared_state = shared_state
        self._initial_story = initial_story

    def handle_route_evt(self, evt: RouteEvt) -> None:
        """处理一个 RouteEvt：加载目标章节 → 跑 Executor（同步阻塞）。

        走 load_chapter_safe → 间接走 P0-S1 路径校验（4 条闸门）。
        路径拼装：`chapters_root / f"{evt.target}.md"`
        """
        chapter_path = self.chapters_root / f"{evt.target}.md"
        story = load_chapter_safe(chapter_path)

        # 跨章节状态共享：shared_state 非 None 时透传给 Executor
        kwargs = {}
        if self._shared_state is not None:
            kwargs["state"] = self._shared_state

        executor = self._executor_factory(story, self.bus, **kwargs)
        executor.run()  # 同步阻塞（v2 简化；v3+ 可后台线程）

    def _build_executor(self, story):
        """根据 shared_state 构造 executor kwargs。"""
        kwargs = {}
        if self._shared_state is not None:
            kwargs["state"] = self._shared_state
        return self._executor_factory(story, self.bus, **kwargs)

    def run(self) -> None:
        """主循环：跑 initial_story（如果有）→ 处理 RouteEvt / ChapterEndEvt。

        流程：
        1. 如果 initial_story 非 None → 构造 executor → 跑（可能 emit RouteEvt 或 ChapterEndEvt）
        2. 进入 while：
           - RouteEvt → handle_route_evt（嵌套支持：chapter 内部 end:route 触发后，
             while 会再次循环处理新 RouteEvt）
           - ChapterEndEvt → break
           - 其他 evt（TextEvt / PromptInputEvt / DecoratorEvt / LogEvt）→ 忽略
             （executor 已通过 self.sink.put_evt → bus.put_evt 直接推到 bus，
             GUI 进程侧有自己订阅 loop）
        """
        if self._initial_story is not None:
            exe = self._build_executor(self._initial_story)
            exe.run()

        while True:
            evt = self.bus.get_evt()
            if isinstance(evt, RouteEvt):
                self.handle_route_evt(evt)
            elif isinstance(evt, ChapterEndEvt):
                break
            # 其他事件：executor 跑时已经直接 put_evt 到 bus，无需 ChapterManager 中转
