# 同花顺自选股管理工具

一个用于管理同花顺自选股的 Python 工具，支持从浏览器获取登录状态，自动同步自选股分组数据，以及添加/删除自选股项目。

## 项目功能

- 自动从浏览器获取同花顺的登录Cookie
- 获取所有自选股分组数据
- 添加股票到指定自选股分组
- 从指定自选股分组删除股票
- 本地缓存自选股数据，减少网络请求

## 安装方法

### 1. 克隆代码库

```bash
git clone https://github.com/sunnysab/ths-favorite.git
cd ths-collection
```

### 2. 安装依赖

```bash
pip install httpx browser-cookie3
```

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

1. 首次使用前需确保浏览器已登录同花顺网站
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

