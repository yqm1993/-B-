# B站 UP主动态监控 → 推送到 iPhone

只盯 **一个** UP 主（默认「鳄鱼派」UID 470672214），他一发新动态就通过 **Bark** 推送到你 iPhone，其他人完全不打扰。

两种用法：
- **方式 A：GitHub Actions（推荐）** — 云端免费跑，电脑关机也能收到。
- **方式 B：本地电脑** — 只在电脑开着时检查，关机会漏。

---

## 第一步（两种方式都要做）：装 Bark，拿到你的推送 key

1. iPhone App Store 搜 **Bark**，下载安装（免费、开源）。
2. 打开 Bark，首页会有一条形如这样的地址：
   `https://api.day.app/AbCdEf123456/`
   其中 **`AbCdEf123456`** 就是你的 **BARK_KEY**，复制下来。
3. 点一下 App 里的「测试」或 Safari 打开 `https://api.day.app/你的KEY/测试一下`，手机能弹通知就说明 Bark 正常。

---

## 方式 A：GitHub Actions（推荐，电脑不用开）

### 1. 建一个 GitHub 仓库
- 没账号就去 https://github.com 注册（免费）。
- 右上角 **+ → New repository**，名字随便（比如 `bili-monitor`），选 **Private（私有）**，点 Create。

### 2. 上传本文件夹的所有文件
最简单：在仓库页点 **Add file → Upload files**，把这个文件夹里的
`monitor.py`、`README.md`、`.gitignore`、`.github`（整个文件夹）拖进去，Commit。

> 如果你会用 git，也可以在本文件夹执行：
> ```bash
> git init && git add -A && git commit -m "init"
> git branch -M main
> git remote add origin https://github.com/你的用户名/bili-monitor.git
> git push -u origin main
> ```

### 3. 填入你的 key（Secrets 和 Variables）
进仓库 **Settings → Secrets and variables → Actions**：

在 **Secrets** 标签页点 *New repository secret*，加：
| 名字 | 值 |
|------|-----|
| `BARK_KEY` | 你的 Bark key（第一步拿到的那串）|
| `BILI_COOKIE` | **一整条完整浏览器 Cookie**（GitHub 必填，否则机房 IP 会被 412 拦）见下方「关于 BILI_COOKIE」|

在 **Variables** 标签页点 *New repository variable*，加：
| 名字 | 值 |
|------|-----|
| `BILI_UID` | `470672214`（要监控的 UP 主，想换人就改这里）|
| `BARK_SERVER` | `https://api.day.app`（用官方服务器就填这个）|

### 4. 开启 Actions 并测试
- 进仓库 **Actions** 标签页，若提示启用就点启用。
- 左侧选 **B站动态监控** → 右上 **Run workflow** 手动跑一次。
- 第一次运行只会「记录现有动态、不推送」（避免一次性刷屏历史）。
- 之后它每约 10 分钟自动检查，**UP 主一发新动态，你手机立刻收到 Bark 推送**，点通知直接跳转到那条动态。

> ⚠️ 两个注意：
> 1. GitHub 的定时任务在平台繁忙时可能延迟几分钟，正常。
> 2. 如果仓库 60 天没有任何提交，GitHub 会自动暂停定时任务；本脚本每次有新动态会自动提交状态，正常使用不会触发暂停。真的被暂停了，去 Actions 页点一下重新启用即可。

---

## 方式 B：本地电脑运行

适合电脑经常开着的时候。双击 `启动监控.command` 即可（第一次可能要右键→打开）。
它会每 10 分钟检查一次，发现新动态就推送。关掉窗口或关机就停止。

运行前先编辑 `启动监控.command`，把里面的 `BARK_KEY` 换成你自己的。

---

## 关于 BILI_COOKIE（GitHub / 云服务器必填）

GitHub Actions 和各家云函数用的都是**机房 IP**，B站 WAF 会直接返回 412 拦截。只填 SESSDATA 不够，**必须填一整条完整 Cookie**（里面有 B站认证过的 buvid 等值，WAF 才放行）。本地电脑（住宅 IP）则不需要。

获取方法（Network 法，一次复制一整条，最省事）：
1. 电脑 Chrome 登录 **bilibili.com**，打开要监控的 UP 动态页：`https://space.bilibili.com/470672214/dynamic`
2. 按 **F12** → 顶部选 **Network（网络）** 标签
3. 筛选框输入 `space`，然后**刷新页面（Cmd/Ctrl+R）**
4. 列表里点名字含 `feed/space` 的请求 → 右侧 **Request Headers** → 找到 **`cookie:`** 那行
5. **把 cookie: 后面的一整串全部复制**（很长，含 buvid3、SESSDATA、bili_ticket 等）
6. 作为 `BILI_COOKIE` 填进 GitHub Secret

> Cookie 是你的登录凭证，别发给别人、仓库务必设为 **Private**。它约一个月过期，到时若又收不到推送、日志报 412 或空列表，重新复制一条更新上去即可（代码不用动）。

> 本地方式 B 想更稳也可以用：编辑 `启动监控.command`，把完整 Cookie 填进 `export BILI_COOKIE="..."`（住宅 IP 其实不填也能跑）。

---

## 想换成监控别的 UP 主？
把 `BILI_UID` 改成那个 UP 主的 UID 即可（UID 就是他主页网址 `space.bilibili.com/` 后面那串数字）。改完后删掉 `seen.json`（如果有）再跑一次，重新建立基线。
