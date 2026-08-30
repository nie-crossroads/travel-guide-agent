---
name: git-commit
description: >-
  Git commit and GitHub push rules for this repo: conventional Chinese prefixes,
  author must be the repo owner only, never Cursor Agent. Use when committing,
  amending, or pushing to GitHub.
---

# Git 提交要求

远程仓库：https://github.com/nie-crossroads/travel-guide-agent.git

## 作者（必须）

GitHub Contributors **只能出现仓库作者**，不能出现 Cursor / Cursor Agent / `cursoragent@cursor.com`。

- author 与 committer 一律：`打酱油的大白菜 <51286508+nie-crossroads@users.noreply.github.com>`
- 用 `git -c user.name=... -c user.email=...` 提交，**不要改** `git config`
- **禁止** `Co-authored-by: Cursor` 或任何 Cursor 相关 trailer
- 提交后立刻检查：`git log -1 --format=%an%n%ae%n%cn%n%ce%n%B`
- 若混入 Cursor 身份或 trailer：立刻 `--amend` 去掉后再推送

## Commit 信息

按下面前缀写，不涉及的不用写：

- `refactor`：重构
- `docs`：优化文档
- `chore`：升级 SDK、移除废弃代码
- `style`：样式调整
- `fix`：bug 修复
- `feat`：增加一个功能
- `perf`：优化代码
