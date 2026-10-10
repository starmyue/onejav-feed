# OneJav RSS · Cloudflare Worker

## 这是什么

一个无状态的 Cloudflare Worker：每次被访问时实时抓取 `https://onejav.com/new`，
用 Cloudflare 原生的 `HTMLRewriter` 按卡片结构解析，现场生成 RSS 2.0 + Media RSS。

- 图片优先：每个条目带 `media:thumbnail` / `media:content` / `enclosure` + 正文内嵌大图
- 线上订阅地址：`https://onejav-feed.starbee.workers.dev/onejav-feed.xml`（`/` 同样可用）
- 边缘缓存 30 分钟（`Cache-Control: public, max-age=1800`），短时间内大量刷新不会每次都回源

## 文件说明

| 文件 | 用途 |
|---|---|
| `worker.js` | 全部逻辑：抓取 → 解析 → 生成 RSS |
| `wrangler.toml` | wrangler 命令行部署配置（`name = "onejav-feed"`） |
| `README.md` | 本文档 |

## 部署方式一：网页控制台（推荐，不用装任何东西）

1. 登录 https://dash.cloudflare.com/ → 左侧 **Workers 和 Pages** → **创建应用程序** → 从 Hello World 模板开始
2. 命名为 `onejav-feed`（名称决定 `*.workers.dev` 子域名），点部署
3. 进入 Worker → **编辑代码** → 删除默认代码 → 把 `worker.js` 全文粘贴进去 → **保存并部署**
4. 注意：新版编辑器是 Monaco，直接粘贴可能无效；可先把代码粘到任意纯文本框（如 dpaste.org）再全选复制回来粘贴

## 部署方式二：wrangler 命令行

```bash
npm install -g wrangler
wrangler login
cd worker && wrangler deploy
```

## 验证

访问 `https://<你的子域名>.workers.dev/onejav-feed.xml`，应返回：

- HTTP 200，`Content-Type: application/rss+xml`
- 约 10 个 `<item>`，标题含番号，日期为当天
- 每个条目有 `<media:thumbnail>`，图片指向 `pics.dmm.co.jp` 封面图

## 故障排查

- 返回 502 / "订阅更新失败" → `onejav.com` 抽风（该站曾返回过 503），等几分钟再刷即可，无需干预
- 返回 Not found → 路径不对，订阅路径必须是 `/` 或 `/onejav-feed.xml`
- 域名打不开 → 检查 `workers.dev` 子域名拼写；国内直连 `workers.dev` 偏慢属正常

## 注意事项

- 每次只返回 `onejav.com/new` 当前页约 10 条，**不做历史累积**（和 GitHub Actions 版行为不同，后者会累积到 `items.json`）
- `onejav.com` 页面结构变化（class 名等）会导致解析失效，需同步更新 `worker.js` 里的 `HTMLRewriter` 选择器
- 本仓库的 GitHub Actions 定时任务（`.github/workflows/update-feed.yml`）已于 2026-10-10 停用，文件保留可随时 re-enable；如需历史累积版订阅，可重新启用它（订阅地址 `https://starmyue.github.io/onejav-feed/onejav-feed.xml`）

## 背景

GitHub Actions 的 `schedule` 触发连续两天失灵（2026-10-09、2026-10-10 均未触发），遂迁移到 Cloudflare Worker，订阅更新不再依赖定时任务。
