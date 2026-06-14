# Issue tracker: GitHub

项目的问题追踪使用 GitHub Issues，通过 `gh` CLI 进行操作。

## 规范

- **创建 issue**：`gh issue create --title "..." --body "..."`。多行内容使用 heredoc。
- **查看 issue**：`gh issue view <number> --comments`
- **列出 issues**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`
- **评论 issue**：`gh issue comment <number> --body "..."`
- **添加/移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭**：`gh issue close <number> --comment "..."`

从 `git remote -v` 推断仓库路径，在仓库内运行 `gh` 时会自动识别。

## 当 skill 说"发布到 issue tracker"

创建一个 GitHub issue。

## 当 skill 说"获取相关 ticket"

运行 `gh issue view <number> --comments`。
