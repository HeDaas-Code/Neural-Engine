# 跨章节跳转目标（chapter_route）

> V2-04 task 5 fixture —— chapter01_route.md 的路由目标。
> 末尾 `id:end2`（无路由）触发 ChapterEndEvt，ChapterManager.run() 退出。

```neon
id:start
id:end2
node start
chapter_route: reached via RouteEvt from chapter01_route
chapter_route: end of story
node end
```
