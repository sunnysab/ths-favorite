# 同花顺自选股管理工具

一个用于管理同花顺自选股的 Python 工具，支持从浏览器获取登录状态，自动同步自选股分组数据，以及添加/删除自选股项目。

> [!NOTE]
> 该项目代码主要由 AI 编写，可能存在一些 Bug 或考虑不周的地方。如有改进需求可以提 issue 或 pull request。

## 项目功能

- 通过同花顺密码或浏览器Cookie登录
- 获取所有自选股分组数据，并自动附带 selfstock_detail 接口提供的加入价格/时间
- 添加股票到指定自选股分组
- 从指定自选股分组删除股票
- 新增或删除自选分组 （by @Kerwin1202）
- 分享分组生成短期链接 (by @Kerwin1202)
- 本地缓存自选股数据，减少网络请求

由于同花顺的“自选列表更新推送”依赖一个基于 TCP 长连接的 v4 协议，该协议较为复杂，网络上鲜有逆向后的资料，因此这里不提供该功能。
你可以定时刷新自选分组，检测是否有更新。

## 安装方法

### 1. 克隆代码库

```bash
git clone https://github.com/sunnysab/ths-favorite.git
cd ths-favorite
```

### 2. 安装依赖

使用 pip 安装项目依赖:

```bash
pip install -e .
```

如果需要从浏览器获取 Cookie 功能，请额外安装可选依赖:

```bash
pip install 'ths-collection[browser]'
# 或者直接安装
pip install browser-cookie3
```

注意，`browser-cookie3` 库用于读取浏览器的 Cookie。在 Windows 下，它依赖了卷影服务以强行读出存储文件（[原理](https://www.cnblogs.com/zpchcbd/p/18860664)，[issue](https://github.com/sunnysab/ths-favorite/issues/2)），该操作**需要管理员权限**（[shadowcopy](https://pypi.org/project/shadowcopy/)）。请阅读代码并了解潜在的安全风险。

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

# 创建实例，自动从浏览器获取 Cookie
with PortfolioManager() as portfolio:
    # 获取所有分组
    groups = portfolio.get_all_groups()
    
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

命令行入口为 `python main.py`，支持与 Python API 相同的认证参数（`--auth-method`, `--browser`, `--username`, `--password`, `--cookie-cache`）。常见操作如下：

```bash
# 列出全部分组或查看单个分组
python main.py list
python main.py list -g 消费          # 与 group list -g 相同
python main.py group list -g 消费    # 层级命令写法

# 添加 / 删除股票（代码格式为 CODE.MARKET）
python main.py stock add 消费 600519.SH
python main.py stock del 消费 600519.SH

# 管理和分享分组
python main.py group add "长线跟踪"
python main.py group del 消费
python main.py group share 消费 604800

# 使用账号密码登录再执行命令
python main.py --auth-method credentials --username 13300000000 --password yourpass list
```

详细 CLI 与 API 说明请参见 [使用指南](TUTORIAL.md)。

## Cookie 获取与缓存

`PortfolioManager` 提供三种方式来初始化会话：

- `auth_method="browser"`（默认）：通过 `browser_cookie3` 读取指定浏览器（默认 Firefox）中在 `*.10jqka.com.cn` 下的 Cookie。
- `auth_method="credentials"`：使用用户名和密码调用官方登录流程获取 Cookie，需要同时提供 `username` 和 `password`。
- `auth_method="none"`：跳过自动处理，此时可以通过 `cookies` 参数显式传入。

示例：

```python
# 使用 Chrome 浏览器提取 Cookie，并使用默认的一天有效期缓存
portfolio = PortfolioManager(auth_method="browser", browser_name="chrome")

# 使用账号密码登录，并自定义缓存文件位置
portfolio = PortfolioManager(
    auth_method="credentials",
    username="your_account",
    password="your_password",
    cookie_cache_path="/tmp/ths_cookies.json"
)
```

无论是通过浏览器还是账号密码获取的 Cookie，都会写入 `ths_cookie_cache.json`（或自定义的 `cookie_cache_path`），缓存 24 小时，未过期时优先复用，超时后自动重新获取。

命令行工具也支持同样的参数，例如：

```bash
python main.py --auth-method credentials --username <13300000000> --password <yourpass> list
```

常用分组管理命令：

```bash
python main.py group add "新分组"
python main.py group del 消费
python main.py group share 消费 604800   # 有效期 7 天
```

### 自选股价格/时间元数据

`PortfolioManager` 会在每次成功刷新分组数据后调用 `selfstock_detail` 接口，将每个自选股的加入价格 (`StockItem.price`) 与时间 (`StockItem.added_at`) 注入结果。你也可以手动刷新或查看这些信息：

```python
with PortfolioManager() as portfolio:
    portfolio.refresh_selfstock_detail(force=True)
    snapshot = portfolio.get_item_snapshot("600519.SH")
    print(snapshot)  # {'code': '600519', 'market': 'SH', 'price': 123.45, 'added_at': '20231101', 'version': '105'}
```

- `refresh_selfstock_detail(force=True)` 会立即重新下载最新的价格/时间快照。
- `selfstock_detail_version` 属性提供最近一次下载的版本号，便于与同花顺客户端保持一致。
- `get_item_snapshot` 可单独查询任意股票的加入信息（自动复用/刷新缓存）。

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

1. 如需使用从浏览器读取 Cookie 功能（需安装 browser-cookie3 依赖），请确保浏览器已登录同花顺网站
2. 默认从 Firefox 浏览器读取 Cookie，如需使用其他浏览器可修改代码
3. Cookie 过期后需重新登录浏览器

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

