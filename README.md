# 北交所新股首日卖出窗口助手（云端 + Android）

一个可独立部署的 Web/PWA 软件，并附带可打包成 Android APK 的 Capacitor 工程。用户只需输入 6 位证券代码，可选填写持仓股数，服务会自动读取北交所发行资料与公开实时行情，并给出“观察 / 分批 / 全部退出”的可解释提示。

> 它识别的是当前卖出窗口，不预测全天最高价，不连接券商，也不会自动下单。任何执行必须以券商终端的可成交盘口为准。

## 与旧版的区别

- 不依赖 Windows、通达信、TdxQuant 或 Cloudflare 临时隧道。
- 自动查询证券名称、发行价和上市日期；非上市首日会拒绝生成卖出信号。
- 腾讯行情为主、东方财富行情自动降级；行情时间戳超过 20 秒时暂停强提示。
- 服务端保存当日状态：VWAP 持续失守、09:30—09:45 开盘区间、二次突破峰值、临停和复牌保护。
- 只有持仓股数是可选输入；不填写时只显示卖出百分比。
- Web 版符合 PWA 安装条件，可从 Android Chrome 直接“安装到手机”。
- Android APK 内置界面资源，只把实时 API 请求发送到指定的 HTTPS 云端后端。

## 判断规则（V1）

- 09:30—09:35：普通波动处于硬保护期，只有首分钟承接严重失败才分批。
- 守住开盘价和 VWAP：继续观察，不因涨幅大或高换手机械清仓。
- 极端高开尖峰回落：上冲至少 8%、高点回撤至少 6%且跌到 VWAP 下方时，先处理 70%。
- 开盘涨幅 40%—150%：首轮上冲至少 5%、回撤至少 3.5%并跌到 VWAP 下方时，先处理 50%；二次突破后使用峰值 5% 移动保护。
- 硬退出：开盘价和 VWAP 双破，并出现 5 分钟持续失守或 8%高点回撤。
- 14:30 后至少处理 50%，14:45 后处理全部剩余仓位，不留隔夜仓。
- 不足 200 股按“容错优先”：软性分批提示为 0 股，硬退出时一次处理。

北交所公开发行股票上市首日不设涨跌幅限制；盘中价格相对开盘价首次达到 ±30% 和 ±60%时可临时停牌 10 分钟。实现依据可参阅[中国证监会公开的《北京证券交易所交易规则（试行）》](https://www.csrc.gov.cn/shenzhen/c105632/c1562694/1562694/files/1638524949335_40064.pdf)。

## 本地运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

打开 <http://127.0.0.1:8000>。运行测试：

```bash
pytest -q
```

## 部署到 GitHub + Render（推荐）

GitHub Pages 只能托管静态文件，无法运行本项目的 Python 行情代理与状态机。因此推荐把源码和镜像放在 GitHub，运行服务部署到 Render：

1. 在 GitHub 新建空仓库 `bse-ipo-sell-cloud`，将本目录推送到 `main`。
2. 登录 Render，选择 **New → Blueprint**，连接这个 GitHub 仓库。
3. Render 会读取 `render.yaml` 和 `Dockerfile` 自动创建 Web Service。
4. 在 Render 环境变量中设置随机的 `APP_ACCESS_TOKEN`；不设置则网站公开。
5. 部署完成后访问 Render 分配的 HTTPS 地址。

Render 不依赖 GitHub Actions，连接仓库后即可构建。仓库在 `deploy/github-actions/` 提供 CI、镜像发布和 APK 构建模板；启用后，每次推送 `main` 都会运行测试和 Docker 构建，创建 `v1.1.0` 之类的 Git tag 可把镜像发布到 GitHub Container Registry。

## 安装到 Android 手机

### 方案一：PWA（最快，不需要 APK）

1. 先把本项目部署到带 HTTPS 的云平台。
2. 用 Android Chrome 打开部署地址。
3. 点击页面右上角“安装到手机”；如果按钮未出现，打开 Chrome 菜单并选择“安装应用”或“添加到主屏幕”。
4. 安装后会像普通 App 一样从桌面全屏启动。界面外壳可离线打开，但实时行情判断必须联网。

PWA 图标、manifest、Service Worker 和安装入口均已包含在服务端静态资源中。

私有部署可使用 `https://你的域名/#token=访问口令` 作为首次访问链接。页面会把口令保存到当前设备，并立即从地址栏移除；URL 片段不会发送到服务器访问日志。

### 方案二：生成 Android APK

APK 只打包本地界面，不把云端访问口令写进安装包。构建前必须先获得已部署后端的 HTTPS 地址：

```powershell
npm ci
$env:APP_API_BASE_URL = "https://你的后端地址"
npm run android:sync
npm run android:debug
```

调试安装包输出到：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

本地构建需要 Node.js 22+、JDK 21、Android Studio 与 Android SDK。也可在 GitHub Actions 中手动构建：启用 `deploy/github-actions/android-apk.yml` 后，运行 **Build Android APK**，输入后端 HTTPS 地址，再从该次任务的 Artifacts 下载 `bse-ipo-sell-debug-apk`。

首次打开 App 时，如果云端配置了 `APP_ACCESS_TOKEN`，在页面“访问口令”中输入即可；口令只保存在手机本地。正式对外分发应在 Android Studio 中配置自己的签名，生成签名版 AAB/APK，不能用调试签名上架。

当前 GitHub OAuth 令牌没有 `workflow` scope 时，GitHub 会拒绝直接推送 `.github/workflows`。重新授权后可一次性启用 CI、镜像发布和 APK 构建模板：

```powershell
gh auth refresh -h github.com -s workflow
New-Item -ItemType Directory -Force .github/workflows
git mv deploy/github-actions/*.yml .github/workflows/
git commit -m "Enable GitHub Actions"
git push
```

## 其他云平台

仓库同时提供 `Dockerfile` 和 `Procfile`，可部署到 Railway、Fly.io、Cloud Run、Azure Web Apps 或任意支持容器的平台。平台只需把 `PORT` 传给容器。

## 环境变量

| 名称 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ACCESS_TOKEN` | 空 | 可选访问口令；公网部署建议设置 |
| `APP_ALLOWED_ORIGINS` | 空 | 额外允许调用 API 的网页来源，多个来源用逗号分隔；Android 默认来源已内置 |
| `APP_API_BASE_URL` | 空 | 仅在构建 Android 时使用，必须是已部署后端的 HTTPS 根地址 |
| `ENABLE_API_DOCS` | `0` | 设为 `1` 时开放 `/api/docs` |
| `PORT` | `8000` | 云平台监听端口 |

## API

- `GET /api/health`
- `GET /api/analyze?code=920xxx&position=100`
- 若设置访问口令，使用请求头 `X-App-Token`，页面会把口令保存在当前浏览器的 `localStorage` 中。

## 数据与风险边界

1. 腾讯、东方财富接口属于公开网页行情兜底，不等同于交易所授权的低延迟行情；生产或多人使用应替换为有授权、带 SLA 的行情服务。
2. 云平台所在地区可能无法稳定访问中国大陆行情接口，系统会显式报错或降级，不会伪造数据。
3. 免费容器可能休眠；上市日使用前应提前唤醒并通过 `/api/health` 检查。
4. 进程重启会丢失 VWAP 持续时间、开盘区间和二次突破等内存状态；高可用部署应增加 Redis 状态存储。
5. 本项目仅为研究和辅助决策工具，不构成投资建议，使用者自行承担交易风险。
