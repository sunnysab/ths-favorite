# 使用指南

本文档详细说明项目附带 CLI 命令与 Python API 的可选参数、调用方式及常见场景。

## 1. 命令行工具

### 1.1 环境与入口
- 作为 Python 库使用时，基础安装即可：`pip install -e .` 或 `pip install ths-favorite`。
- 如需运行 CLI，请额外安装 `cli` 可选依赖：`pip install -e '.[cli]'` 或 `pip install 'ths-favorite[cli]'`。
- 所有命令均通过 `python main.py <command>` 触发，可使用 `--help` 查看完整帮助。

### 1.2 全局选项
| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--auth-method {credentials,none}` | `none` | 选择获取 Cookie 的方式。`credentials` 使用账号密码登录；`none` 表示不自动登录，适合调用方已经准备好 Cookie 的场景。 |
| `--username` / `--password` | `None` | `auth-method=credentials` 时必填的账号、密码。 |
| `--cookie-cache <path>` | `ths_cookie_cache.json` | 覆盖默认的 Cookie 缓存文件路径，缓存有效期 24 小时。 |

> 未提供任何认证参数时，CLI 默认按 `none` 模式启动，不会自动尝试浏览器或缓存登录。
> 仅提供 `--username` 而不提供 `--password` 时，CLI 会按 `credentials` 模式尝试读取该账号的缓存，未命中会直接提示补充密码。
> 这些全局选项可放在任意子命令之前；如果已提供账号密码，也可以省略 `--auth-method credentials`，例如 `python main.py --username 13300000000 --password pass list`。

### 1.3 子命令总览
| 子命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `list` | 列出所有分组，或使用 `-g/--group` 查看单个分组内股票。 | `-g/--group <名称或ID>` （可选） |
| `self list` | 列出“我的自选”虚拟分组中的股票。 | 无 |
| `group add` | 新建分组。 | `name`：分组名称 |
| `group del` | 删除现有分组。 | `group`：名称或 ID |
| `group share` | 分享分组生成临时链接。 | `group`：名称或 ID；`valid_time`：有效期秒数 |
| `stock add` | 向分组添加股票。 | `group`：名称或 ID；`stock`：`代码.市场`（如 `600519.SH`） |
| `stock del` | 从分组删除股票。 | 与 `stock add` 相同 |

### 1.4 命令详解
- `list`
  ```bash
  python main.py list                # 列出全部分组及股票数量
  python main.py list -g 消费        # 仅输出“消费”分组下的股票代码
  ```
- `self list`
  ```bash
  python main.py self list
  ```
- `stock add`
  ```bash
  python main.py stock add 消费 600519.SH  # 向“消费”分组添加贵州茅台
  python main.py stock add 0_35 000858.SZ  # 支持使用分组 ID
  python main.py stock add 我的自选 600519.SH
  ```
- `stock del`
  ```bash
  python main.py stock del 消费 600519.SH
  python main.py stock del 我的自选 600519.SH
  ```
- `group add`
  ```bash
  python main.py group add "长线跟踪"
  ```
- `group del`
  ```bash
  python main.py group del 消费
  ```
- `group share`
  ```bash
  python main.py group share 消费 604800  # 分享 7 天有效链接
  ```

### 1.5 常见场景
1. **账号密码登录**：
   ```bash
   python main.py --username 13300000000 --password pass list
   python main.py --auth-method credentials --username 13300000000 --password pass list
   ```
2. **批量维护分组**：
   ```bash
   python main.py group add "事件驱动"
   python main.py stock add 事件驱动 300750.SZ
   python main.py group share 事件驱动 86400
   ```

## 2. Python API

### 2.1 初始化 `PortfolioManager`
```python
from service import PortfolioManager

with PortfolioManager(
    auth_method="credentials",  # 或 "none"
    username="13300000000",     # credentials 模式参数
    password="yourpass",
    cookie_cache_path="/tmp/ths_cookie_cache.json",  # 可选
    cookie_cache_ttl_seconds=24*3600                  # 默认 24 小时
) as ths:
    ...
```
- 直接传入 `cookies`（字符串或字典）时会跳过自动认证。
- `api_client` 可注入已有的 `ApiClient` 实例以共享连接或定制超时。

### 2.2 缓存策略
- Cookie 会写入 `cookie_cache_path`（默认 `ths_cookie_cache.json`），命中缓存即复用，失效后自动刷新。
- Cookie 缓存仅保存 Cookie 和时间戳，不再保存明文密码。
- 分组及股票列表会序列化到 `ths_favorite_cache.json`，`get_all_groups(use_cache=True)` 可在 API 不可用时读取本地缓存。
- “我的自选”会单独缓存到 `ths_self_stock_cache.json`。
- “我的自选”的底层读写走新版 Cookie 自选接口，直接复用当前会话或缓存中的 Cookie。

### 2.3 常用方法
| 方法 | 说明 | 返回值 |
| --- | --- | --- |
| `get_all_groups(use_cache=False)` | 拉取并解析所有分组；`use_cache=True` 时在网络失败时回退到内存缓存。 | `Dict[str, StockGroup]` |
| `get_self_stocks(refresh=False, name=None)` | 拉取“我的自选”，返回虚拟分组。 | `StockGroup` |
| `add_item_to_group(group, symbol)` | `group` 可为名称或 ID；`symbol` 需包含市场后缀，如 `000001.SZ`。 | API 返回的字典（含版本信息） |
| `delete_item_from_group(group, symbol)` | 删除指定股票。 | 同上 |
| `add_group(name)` | 新增分组。 | 同上 |
| `delete_group(group)` | 删除分组（不可恢复，谨慎操作）。 | 同上 |
| `share_group(group, valid_time)` | 创建分享链接，`valid_time` 为秒。 | `dict`，通常包含 `share_url` |
| `refresh_selfstock_detail(force=False)` | 调用 selfstock_detail 接口，刷新加入价格/时间缓存。 | 版本号或 `None` |
| `get_item_snapshot("600519.SH")` | 读取指定股票的加入价格/时间，必要时自动刷新缓存。 | `dict` 或 `None` |
| `set_cookies(cookies)` | 直接替换底层客户端 Cookie。 | `None` |
| `close()` | 手动关闭客户端（`with` 语句会自动调用）。 | `None` |

> `selfstock_detail_version` 属性可查看最近一次下载的 selfstock_detail 版本号；每个 `StockItem` 实例也新增了 `price` 与 `added_at` 字段。
> 如果 `selfstock_detail` 临时失败，`get_all_groups()` 与 `get_self_stocks()` 仍会返回基础列表，只是缺少价格和加入时间增强信息。

> “我的自选”默认以名称 `我的自选`、保留 ID `__selfstock__` 暴露；也可通过 `get_all_groups(include_self_stocks=True)` 并入所有分组结果。

### 2.4 示例：全流程自动化
```python
with PortfolioManager(
    auth_method="credentials",
    username="13300000000",
    password="yourpass",
) as ths:
    self_group = ths.get_self_stocks()
    print(self_group.items[:3])

    groups = ths.get_all_groups()
    groups_with_self = ths.get_all_groups(include_self_stocks=True)
    print(groups["消费"].items[:3])
    first_item = groups["消费"].items[0]
    print("加入价格:", first_item.price, "加入时间:", first_item.added_at)

    ths.add_item_to_group("消费", "600519.SH")
    ths.delete_item_from_group("消费", "000858.SZ")

    ths.add_group("长线跟踪")
    ths.add_item_to_group("长线跟踪", "300750.SZ")
    share_info = ths.share_group("长线跟踪", 604800)
    print("分享链接:", share_info.get("share_url"))
```

### 2.5 错误处理与日志
- 关键路径已使用 `loguru` 记录日志；根据需要调整日志等级或输出位置。
- 当网络异常或接口返回业务错误时，API 会抛出 `THSNetworkError` 或 `THSAPIError`，CLI 也会捕获并输出友好提示；在 Python 代码中可自行捕获：
  ```python
  from exceptions import THSAPIError, THSNetworkError

  try:
      ths.add_item_to_group("消费", "600519.SH")
  except THSNetworkError as exc:
      print("网络异常:", exc)
  except THSAPIError as exc:
      print("业务失败:", exc)
  ```

以上内容覆盖了 CLI 与 API 的全部命令与方法，更多实现细节可直接查阅源码。
