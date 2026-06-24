# 第一章：雨夜（v1 形态）

> v1 表达式子系统端到端测试 fixture。
> 使用原生 Python 表达式 + ← / → 箭头符号。

```neon
id:start
next: c1
node start
雨夜。
雨声从破旧窗户的缝隙中渗入。
你坐在窗边，听着雨声。
@style bgm:rain.mp3
node in → mood
node echo mood + ，是啊。
node end
```

```neon
id:c1
id:end0
t_a ← next : ca
t_b ← next : cb
node start
你听到门外传来两声敲门。
node in → pick
node if pick == 1 [t_a, t_b]
node end
```

```neon
id:ca
id:end0
node start
@style bgm:storm.mp3
你打开门，雨中站着一个人。
node end
```

```neon
id:cb
id:end0
node start
@style bgm
你没有开门。雨声渐小。
node end
```
