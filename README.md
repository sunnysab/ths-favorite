# 同花顺自选股管理工具

一个用于管理同花顺自选股的 Python 工具，支持使用账号密码获取会话 Cookie、显式注入 Cookie，并自动同步自选股分组数据以及添加/删除自选股项目。

> [!NOTE]
> 该项目代码主要由 AI 编写，可能存在一些 Bug 或考虑不周的地方。如有改进需求可以提 issue 或 pull request。

## 项目功能

- 通过同花顺账号密码登录，或显式传入 Cookie
- 获取所有自选股分组数据，并自动附带 selfstock_detail 接口提供的加入价格/时间
- 获取“我的自选”列表，并支持将其作为虚拟分组并入结果
- 添加股票到指定自选股分组
- 从指定自选股分组删除股票
- 新增或删除自选分组 （by @Kerwin1202）
- 分享分组生成短期链接 (by @Kerwin1202)
- 本地缓存自选股数据，减少网络请求

由于同花顺的“自选列表更新推送”依赖一个基于 TCP 长连接的 v4 协议，该协议较为复杂，网络上鲜有逆向后的资料，因此这里不提供该功能。
你可以定时刷新自选分组，检测是否有更新。（经过观察，同花顺远航版就是这么做的，1分钟请求一次）

## 安装方法

### 1. 克隆代码库

```bash
git clone https://github.com/sunnysab/ths-favorite.git
cd ths-favorite
```

### 2. 安装依赖

如果你只是把项目作为 Python 库依赖使用，基础依赖即可:

```bash
pip install -e .
```

如果需要命令行表格输出，请额外安装 `cli` 可选依赖:

```bash
pip install -e '.[cli]'
pip install 'ths-favorite[cli]'
```

## 快速开始

### 1. 首次使用 CLI

首次运行时，推荐显式提供账号密码登录：

```bash
python main.py --username 13300000000 --password yourpass list
```

登录成功后，会把当前会话 Cookie 缓存到本地，后续可直接复用。

### 2. 后续复用缓存

如果本地已有未过期的凭据缓存，可以直接运行：

```bash
python main.py list
python main.py self list
python main.py list -g 消费
```

如果缓存失效或本地没有缓存，CLI 会以未登录态启动；此时请重新提供 `--username` / `--password`。

### 3. Python API

使用账号密码登录：

```python
from service import PortfolioManager

with PortfolioManager(
    username='your_account',
    password='your_password',
) as portfolio:
    groups = portfolio.get_all_groups()
    self_group = portfolio.get_self_stocks()
    print(len(groups), len(self_group.items))
```

显式注入 Cookie：

```python
from service import PortfolioManager

with PortfolioManager(cookies='userid=...; sessionid=...') as portfolio:
    groups = portfolio.get_all_groups()
    print(groups.keys())
```

## 常用命令

```bash
# 查看分组
python main.py list
python main.py list -g 消费
python main.py self list

# 添加 / 删除股票
python main.py stock add 消费 600519.SH
python main.py stock del 消费 600519.SH
python main.py stock add 我的自选 600519.SH
python main.py stock del 我的自选 600519.SH

# 分组管理
python main.py group add "长线跟踪"
python main.py group del 消费
python main.py group share 消费 604800
```

更完整的 CLI / API 参数说明、命令矩阵和场景示例见 [使用指南](TUTORIAL.md)。

## 认证与缓存

`PortfolioManager` 会按传入参数自动决定是否登录：

- 同时提供 `username` 和 `password`：使用账号密码调用官方登录流程获取 Cookie。
- 仅提供 `username`：尝试读取该账号对应的缓存，未命中即提示补充密码。
- 提供 `cookies`：直接复用显式传入的 Cookie。
- 什么都不提供：尝试复用最近一次有效的凭据缓存；若没有命中，则保持未登录。

Cookie 缓存行为如下：

- 缓存文件默认是 `ths_cookie_cache.json`，可通过 `cookie_cache_path` 或 `--cookie-cache` 覆盖。
- 缓存有效期默认 24 小时。
- 缓存中仅保存 Cookie 和时间戳，不再落盘明文密码。
- 分组数据会缓存到 `ths_favorite_cache.json`，“我的自选”会缓存到 `ths_self_stock_cache.json`。

## 配置

所有常量（User-Agent、缓存文件路径、API URL 等）均集中在 `config.py` 中。作为库使用时，优先推荐在应用启动时以 `import config` 的方式动态覆盖对应常量，而不是直接修改包内文件：

```python
import config
config.DEFAULT_HEADERS["User-Agent"] = "MyCustomUA/1.0"
config.COOKIE_CACHE_FILE = "/tmp/ths_cookies.json"
```

调整配置时只需在应用启动阶段覆写上述常量即可；如需查看全部可调项，请直接参考 [config.py](config.py)。

### “我的自选”与分组

项目把“我的自选”作为一个虚拟分组对外暴露：

- 默认名称为 `我的自选`
- 保留 ID 为 `__selfstock__`
- 可通过 `get_self_stocks()` 单独获取
- 也可通过 `get_all_groups(include_self_stocks=True)` 并入全部分组结果

对调用方来说，`stock add/del` 可以直接对 `我的自选` 生效，但其底层协议与普通分组不同，走的是新版 Cookie 自选接口，并直接复用当前会话的 Cookie。

### 自选股价格/时间元数据

`PortfolioManager` 会在每次成功刷新分组数据后调用 `selfstock_detail` 接口，将每个自选股的加入价格 (`StockItem.price`) 与时间 (`StockItem.added_at`) 注入结果。你也可以手动刷新或查看这些信息：

```python
with PortfolioManager() as portfolio:
    self_group = portfolio.get_self_stocks()
    print(self_group.items[:3])

    portfolio.refresh_selfstock_detail(force=True)
    snapshot = portfolio.get_item_snapshot("600519.SH")
    print(snapshot)  # {'code': '600519', 'market': 'SH', 'price': 123.45, 'added_at': '20231101', 'version': '105'}
```

- `refresh_selfstock_detail(force=True)` 会立即重新下载最新的价格/时间快照。
- `selfstock_detail_version` 属性提供最近一次下载的版本号，便于与同花顺客户端保持一致。
- `get_item_snapshot` 可单独查询任意股票的加入信息（自动复用/刷新缓存）。
- 如果 `selfstock_detail` 接口临时失败，`get_all_groups()` / `get_self_stocks()` 仍会返回基础股票列表，只是缺少价格与加入时间增强信息。

### 股票代码格式

添加或删除股票时，股票代码格式为 `code.market`，其中:

- `code`: 股票代码，如 `600519`
- `market`: 市场代码，如 `SH`(上海), `SZ`(深圳)

常用市场代码:
- `SH`: 上海证券交易所
- `SZ`: 深圳证券交易所
- `HK`: 香港联合交易所
- `BJ`: 北京证券交易所
- `KC`: 科创板
- `CY`: 创业板

## 注意事项

1. 推荐优先使用 CLI 的 `--username/--password` 或 Python API 的 `username=` / `password=` 获取会话。
2. 如果使用显式注入的 Cookie，请确保其中至少包含可访问接口所需的登录态。
3. Cookie 过期后需重新登录或重新注入。

## 授权协议

本项目采用 [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html) 授权。

```
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
