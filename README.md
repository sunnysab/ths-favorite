# 同花顺自选股管理工具

一个用于管理同花顺自选股的 Python 工具，支持从浏览器获取登录状态，自动同步自选股分组数据，以及添加/删除自选股项目。

> [!NOTE]
> 该项目代码主要由 AI 编写，可能存在一些 Bug 或考虑不周的地方。如有改进需求可以提 issue 或 PR。

## 项目功能

- 通过同花顺密码或浏览器Cookie登录
- 获取所有自选股分组数据
- 添加股票到指定自选股分组
- 从指定自选股分组删除股票
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

## 使用示例

### 基本用法

```python
from favorite import THSUserFavorite

# 创建实例，自动从浏览器获取 Cookie
with THSUserFavorite() as ths:
    # 获取所有分组
    groups = ths.get_all_groups()
    
    # 查看分组内容
    for name, group in groups.items():
        print(f"分组: {name}, ID: {group.group_id}")
        print(f"包含 {len(group.items)} 个股票")
    
    # 添加股票到分组中 (使用分组名称)
    ths.add_item_to_group("消费", "600519.SH")  # 添加贵州茅台
    
    # 也可以使用分组ID添加
    ths.add_item_to_group("0_35", "000858.SZ")  # 添加五粮液到消费分组
    
    # 从分组删除股票
    ths.delete_item_from_group("消费", "600519.SH")
```

## Cookie 获取与缓存

`THSUserFavorite` 提供三种方式来初始化会话：

- `auth_method="browser"`（默认）：通过 `browser_cookie3` 读取指定浏览器（默认 Firefox）中在 `*.10jqka.com.cn` 下的 Cookie。
- `auth_method="credentials"`：使用用户名和密码调用官方登录流程获取 Cookie，需要同时提供 `username` 和 `password`。
- `auth_method="none"`：跳过自动处理，此时可以通过 `cookies` 参数显式传入。

示例：

```python
# 使用 Chrome 浏览器提取 Cookie，并使用默认的一天有效期缓存
ths = THSUserFavorite(auth_method="browser", browser_name="chrome")

# 使用账号密码登录，并自定义缓存文件位置
ths = THSUserFavorite(
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

工具会自动将分组数据缓存到 `favorite.json` 文件中，减少网络请求次数，提高运行效率。

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

