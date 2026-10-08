# GitHub 发布指南

[返回 README](../README.md)

项目按源码仓库发布。用户克隆仓库或下载 GitHub 源码归档后，按 README 建立环境并运行 `python main.py`。

## 上传前

1. 按 [贡献指南](../CONTRIBUTING.md#验证改动) 检查运行与截图；交互改动再做真实窗口检查。
2. 阅读 [README](../README.md)，确认安装命令、功能、截图和已验证环境与当前版本一致。
3. 检查 [MIT 许可证](../LICENSE) 的署名。当前为 `Python2048 contributors`；维护者可替换为自己的姓名或 GitHub 名称。
4. 保留 README 引用的 `assets/preview.png`。测试产生的截图、日志和中间文件放在已忽略的 `tmp/` 下，发布前可清理。
5. 确认 `.venv/`、缓存、个人配置和凭据不会进入仓库；`.gitignore` 不会移除已经被 Git 跟踪的文件。

## 首次上传

先安装 Git；也可使用 GitHub Desktop 的“添加现有仓库”和“发布仓库”流程。命令行从项目根目录开始：

```bash
git init
git add .
git diff --cached --stat
git diff --cached
```

检查暂存内容后提交：

```bash
git commit -m "Prepare Python2048 for release"
git branch -M main
```

在 GitHub 创建空仓库；本地已有 README 和 LICENSE 时，不要在远端重复初始化它们。复制该仓库页面提供的真实地址，按 GitHub 指示添加 `origin` 并推送 `main`。首次提交前如尚未配置 Git 署名，使用自己的姓名和邮箱完成配置。

## 推送后

- 在 Actions 页面确认 CI 的每个操作系统与 Python 版本通过；失败时先读取安装和测试日志。
- 在本地生成截图并检查基础绘制；CI 生成的临时截图不会进入仓库。字体、DPI、鼠标和动画体验仍需真实窗口验证。
- 在仓库 About 中填写简短介绍，可添加 `python`、`2048`、`pygame`、`expectimax` 主题。
- 如需要 CI 徽章，从仓库 Actions 页面复制。
- 创建版本标签与 GitHub Release 时，说明新增功能、修复、验证环境和已知限制。直接使用 GitHub 生成的源码归档即可。

支持范围以实际平台测试和 Actions 记录为准。
