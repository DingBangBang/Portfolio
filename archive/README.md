# archive/ — 归档区

> English version: [README_EN.md](./README_EN.md)

这里存放**不属于核心作品集展示、但为了保留历史记录而不删除**的文件。归档内容不参与根目录 README 的项目导航，也不会作为作品对外展示。

## 归档内容

| 路径 | 说明 | 来源 |
| --- | --- | --- |
| `src_my_project/my_project/` | 早期用 `uv init` 生成的脚手架包（仅含一个 `__init__.py` / `main()`），无实际业务逻辑 | 原根目录 `src/my_project` |
| `pyproject.toml` | 上述脚手架对应的项目配置（包名 `my-project`，为自动生成的占位描述） | 原根目录 `pyproject.toml` |
| `uv.lock` | 上述脚手架对应的依赖锁文件 | 原根目录 `uv.lock` |
| `.python-version` | 上述脚手架对应的 Python 版本声明（3.14） | 原根目录 `.python-version` |

## 为什么单独放在 `archive/` 而不是 `projects/`

`projects/` 目录只收录**可以对外展示、有真实业务价值**的项目作品。`src/my_project` 是 `uv` 初始化时自动生成的空脚手架，既没有业务逻辑，也不构成作品，因此：

- **不删除**：保留在 Git 历史中的可追溯性，方便日后回看当时的工程脚手架写法；
- **不放 `projects/`**：避免污染作品集导航，让 `projects/` 的语义保持干净；
- **连带归档配置文件**：`pyproject.toml` / `uv.lock` / `.python-version` 原本指向 `src/my_project`，如果只移动源码而把配置留在根目录，会产生"孤立配置"。因此一并移入 `archive/`，保证归档区自洽、根目录整洁。

> 若未来需要在仓库内重新初始化一个 Python 工程，请在根目录重新生成 `pyproject.toml`，不要把归档文件挪回来。
