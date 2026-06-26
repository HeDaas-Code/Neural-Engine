# 第一章：路由测试（chapter01_route）

> V2-04 task 5 fixture —— 验证 ChapterManager 跨章节跳转。
> 末尾 `id:end1:chapter_route` 触发 RouteEvt('chapter_route')，由 ChapterManager 加载 `chapter_route.md`。

```neon
id:start
id:end1:chapter_route
node start
chapter01_route: start of chapter01
chapter01_route: routing to chapter_route
node end
```
