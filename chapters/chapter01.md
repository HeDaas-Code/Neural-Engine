# 第一章：雨夜

> 这是 v0 MVP 测试章节的源文件。
> 引擎 v0 实现完成后，应可正确解析并执行此文件。

本章为 v0 全语法演示章节。

```neon
id:start
# 入口块：单 next 简写，NEXT = ref(c1)，直达下一节点
next:c1
node start
# 引擎开始执行——以下三行是普通文本行
雨夜。
雨声从破旧窗户的缝隙中渗入。
你坐在窗边，听着雨声。
# @style 修饰器：v0 阶段仅广播到 GUI，不真渲染
@style bgm:rain.mp3
# 等待用户输入，存到普通变量 p_mood
node in ->p_mood
# 回声：把 p_mood 推送给 GUI 显示
node echo p_mood
node end
```

```neon
id:c1
# 多 next 演示：必须带变量名，NEXT=null，待显式设置
t_a<-next:ca
t_b<-next:cb
node start
你听到门外传来两声敲门。
node in ->p_pick
# 多元条件：p_pick 是普通变量，对应 1/2
# 3 分支演示把 echo 当 next 变量名：执行 echo 节点（演示用，实际游戏不太会这么写）
node if p_pick [1:t_a,2:t_b,3:echo p_pick]
node end
```

```neon
id:ca
node start
# 切换音轨
@style bgm:storm.mp3
你打开门，雨中站着一个人。
node end
```

```neon
id:cb
node start
# 休止符：@style 裸 key 等价于清空 bgm
@style bgm
你没有开门。雨声渐小。
node end
```

```neon
id:end1:chapter02
# 路由标记：endX 后第三段是目标章节名
# node end 时广播 route 事件，payload 含 chapter02
node start
故事停在这里。
node end
```

```neon
id:end2
# 普通结局：endX 后无章节名
# node end 时 NEXT=null，广播 chapter_end 事件
node start
测试结束。
node end
```
