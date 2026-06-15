```neon
id:start
id:end0
next: c1
node start
# 最小 fixture：in → echo → end
node in ->p_tall
node echo p_tall
node end
```

```neon
id:c1
id:end0
node start
node end
```
