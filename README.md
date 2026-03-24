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

## 配置

所有常量（User-Agent、缓存文件路径、API URL 等）均集中在 `config.py` 中。作为库使用时，推荐直接修改该文件或在运行前以 `import config` 的方式动态覆盖对应常量：

```python
import config
config.DEFAULT_HEADERS["User-Agent"] = "MyCustomUA/1.0"
config.COOKIE_CACHE_FILE = "/tmp/ths_cookies.json"
```

调整配置时只需修改 `config.py` 或在应用启动阶段覆写上述常量即可。

## 使用示例

### 基本用法

```python
from service import PortfolioManager

# 创建实例，使用账号密码登录
with PortfolioManager(
    username="your_account",
    password="your_password",
) as portfolio:
    self_group = portfolio.get_self_stocks()
    print(f"分组: {self_group.name}, ID: {self_group.group_id}")
    print(f"包含 {len(self_group.items)} 个股票")

    # 获取所有分组
    groups = portfolio.get_all_groups()

    # 也可以把“我的自选”并入分组结果
    groups_with_self = portfolio.get_all_groups(include_self_stocks=True)
    
    # 查看分组内容并打印加入价/时间（来自 selfstock_detail）
    for name, group in groups.items():
        print(f"分组: {name}, ID: {group.group_id}")
        print(f"包含 {len(group.items)} 个股票")
        for item in group.items:
            line = f"- {item.code}.{item.market or ''}"
            if item.price is not None:
                line += f" @ {item.price}"
            if item.added_at:
                line += f" (added {item.added_at})"
            print(line)
    
    # 添加股票到分组中 (使用分组名称)
    portfolio.add_item_to_group("消费", "600519.SH")  # 添加贵州茅台
    
    # 也可以使用分组ID添加
    portfolio.add_item_to_group("0_35", "000858.SZ")  # 添加五粮液到消费分组
    
    # 从分组删除股票
    portfolio.delete_item_from_group("消费", "600519.SH")
```

#### 命令行基本用法

> CLI 依赖不属于基础安装。如需运行 `python main.py ...`，请先安装 `cli` 可选依赖。

命令行入口为 `python main.py`，支持与 Python API 相同的认证参数（`--username`, `--password`, `--cookie-cache`）。CLI 不再提供浏览器 Cookie 提取；如需访问远端接口，请显式提供账号密码，或在 Python API 中通过 `cookies=` / `set_cookies()` 注入现成 Cookie。常见操作如下：

```bash
# 列出全部分组或查看单个分组
python main.py list
python main.py list -g 消费          # 使用 -g 查看指定分组
python main.py self list            # 查看“我的自选”

# 添加 / 删除股票（代码格式为 CODE.MARKET）
python main.py stock add 消费 600519.SH
python main.py stock del 消费 600519.SH
python main.py stock add 我的自选 600519.SH
python main.py stock del 我的自选 600519.SH

# 管理和分享分组
python main.py group add "长线跟踪"
python main.py group del 消费
python main.py group share 消费 604800

# 使用账号密码登录再执行命令
python main.py --username 13300000000 --password yourpass list
```

详细 CLI 与 API 说明请参见 [使用指南](TUTORIAL.md)。

## Cookie 获取与缓存

`PortfolioManager` 会按传入参数自动决定是否登录：

- 同时提供 `username` 和 `password`：使用账号密码调用官方登录流程获取 Cookie。
- 仅提供 `username`：尝试读取该账号对应的缓存，未命中即提示补充密码。
- 提供 `cookies`：直接复用显式传入的 Cookie。
- 什么都不提供：不自动登录，适合后续通过 `set_cookies()` 注入 Cookie。

示例：

```python
# 使用账号密码登录，并自定义缓存文件位置
portfolio = PortfolioManager(
    username="your_account",
    password="your_password",
    cookie_cache_path="/tmp/ths_cookies.json"
)
```

通过账号密码获取到的 Cookie 会写入 `ths_cookie_cache.json`（或自定义的 `cookie_cache_path`），缓存 24 小时，未过期时优先复用，超时后自动重新获取。缓存中仅保存 Cookie 和时间戳，不再落盘明文密码。

命令行工具也支持同样的参数：

- 如果同时提供 `--username` 和 `--password`，CLI 会执行账号密码登录。
- 如果只提供 `--username`，CLI 会尝试读取该账号对应的缓存。
- 如果不提供认证参数，CLI 不会自动登录；这适合调用方已手动准备好 Cookie 的场景。

例如：

```bash
python main.py list
python main.py --username <13300000000> --password <yourpass> list
```

常用分组管理命令：

```bash
python main.py group add "新分组"
python main.py group del 消费
python main.py group share 消费 604800   # 有效期 7 天
```

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

## 数据缓存

工具会自动将分组数据缓存到 `ths_favorite_cache.json` 文件中，减少网络请求次数，提高运行效率。

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
