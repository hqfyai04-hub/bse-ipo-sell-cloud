# 北交所新股首日卖出窗口助手（云端版）

一个可独立部署的 Web 软件。用户只需输入 6 位证券代码，可选填写持仓股数，服务会自动读取北交所发行资料与公开实时行情，并给出“观察 / 分批 / 全部退出”的可解释提示。

> 它识别的是当前卖出窗口，不预测全天最高价，不连接券商，也不会自动下单。任何执行必须以券商终端的可成交盘口为准。

## 与旧版的区别

- 不依赖 Windows、通达信、TdxQuant 或 Cloudflare 临时隧道。
- 自动查询证券名称、发行价和上市日期；非上市首日会拒绝生成卖出信号。
- 腾讯行情为主、东方财富行情自动降级；行情时间戳超过 20 秒时暂停强提示。
- 服务端保存当日状态：VWAP 持续失守、09:30—09:45 开盘区间、二次突破峰值、临停和复牌保护。
- 只有持仓股数是可选输入；不填写时只显示卖出百分比。

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

Render 不依赖 GitHub Actions，连接仓库后即可构建。仓库在 `deploy/github-actions/` 提供 CI 与镜像发布模板；启用后，每次推送 `main` 都会运行测试和 Docker 构建，创建 `v1.0.0` 之类的 Git tag可把镜像发布到 GitHub Container Registry。

当前 GitHub OAuth 令牌没有 `workflow` scope 时，GitHub 会拒绝直接推送 `.github/workflows`。重新授权后可启用模板：

```bash
gh auth refresh -h github.com -s workflow
mkdir -p .github/workflows
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
