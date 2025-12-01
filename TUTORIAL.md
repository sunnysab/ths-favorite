# 使用指南

本文档详细说明项目附带 CLI 命令与 Python API 的可选参数、调用方式及常见场景。

## 1. 命令行工具

### 1.1 环境与入口
- 确保已按 README 安装依赖：`pip install -e .` 或 `pip install ths-favorite`。
- 所有命令均通过 `python main.py <command>` 触发，可使用 `--help` 查看完整帮助。

### 1.2 全局选项
| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--auth-method {browser,credentials,none}` | `browser` | 选择获取 Cookie 的方式。`browser` 自动从浏览器读取；`credentials` 使用账号密码；`none` 表示手动传入 Cookie（需结合 `favorite.THsUserFavorite(cookies=...)` ）。 |
| `--browser <name>` | `firefox` | `auth-method=browser` 时使用的浏览器标识，`browser_cookie3` 支持 `chrome`、`edge`、`firefox` 等。 |
| `--username` / `--password` | `None` | `auth-method=credentials` 时必填的账号、密码。 |
| `--cookie-cache <path>` | `ths_cookie_cache.json` | 覆盖默认的 Cookie 缓存文件路径，缓存有效期 24 小时。 |

> 这些全局选项可放在任意子命令之前，例如 `python main.py --auth-method credentials --username 13300000000 --password pass list`。

### 1.3 子命令总览
| 子命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `list` | 列出所有分组，或使用 `-g/--group` 查看单个分组内股票。 | `-g/--group <名称或ID>` （可选） |
| `add` | 向分组添加股票。 | `group`：名称或 ID；`stock`：`代码.市场`（如 `600519.SH`） |
| `delete` | 从分组删除股票。 | 与 `add` 相同 |
| `group-add` | 新建分组。 | `name`：分组名称 |
| `group-delete` | 删除现有分组。 | `group`：名称或 ID |
| `group-share` | 分享分组生成临时链接。 | `group`：名称或 ID；`valid_time`：有效期秒数 |

### 1.4 命令详解
- `list`
  ```bash
  python main.py list                # 列出全部分组及股票数量
  python main.py list -g 消费        # 仅输出“消费”分组下的股票代码
  ```
- `add`
  ```bash
  python main.py add 消费 600519.SH  # 向“消费”分组添加贵州茅台
  python main.py add 0_35 000858.SZ  # 支持使用分组 ID
  ```
- `delete`
  ```bash
  python main.py delete 消费 600519.SH
  ```
- `group-add`
  ```bash
  python main.py group-add "长线跟踪"
  ```
- `group-delete`
  ```bash
  python main.py group-delete 消费
  ```
- `group-share`
  ```bash
  python main.py group-share 消费 604800  # 分享 7 天有效链接
  ```

### 1.5 常见场景
1. **浏览器 Cookie 登录**：保持浏览器已登录同花顺，直接运行 `python main.py list`。
2. **账号密码登录**：
   ```bash
   python main.py --auth-method credentials --username 13300000000 --password pass list
   ```
3. **批量维护分组**：
   ```bash
   python main.py group-add "事件驱动"
   python main.py add 事件驱动 300750.SZ
   python main.py group-share 事件驱动 86400
   ```

## 2. Python API

### 2.1 初始化 `THSUserFavorite`
```python
from favorite import THSUserFavorite

with THSUserFavorite(
    auth_method="browser",      # 或 "credentials" / "none"
    browser_name="chrome",      # 仅在 browser 模式下使用
    username="13300000000",     # credentials 模式参数
    password="yourpass",
    cookie_cache_path="/tmp/ths_cookie_cache.json",  # 可选
    cookie_cache_ttl_seconds=24*3600                  # 默认 24 小时
) as ths:
    ...
```
- 直接传入 `cookies`（字符串或字典）时会跳过自动认证。
- `api_client` 可注入已有的 `THSHttpApiClient` 实例以共享连接或定制超时。

### 2.2 缓存策略
- Cookie 会写入 `cookie_cache_path`（默认 `ths_cookie_cache.json`），命中缓存即复用，失效后自动刷新。
- 分组及股票列表会序列化到 `ths_favorite_cache.json`，`get_all_groups(use_cache=True)` 可在 API 不可用时读取本地缓存。

### 2.3 常用方法
| 方法 | 说明 | 返回值 |
| --- | --- | --- |
| `get_all_groups(use_cache=False)` | 拉取并解析所有分组；`use_cache=True` 时在网络失败时回退到内存缓存。 | `Dict[str, THSFavoriteGroup]` |
| `add_item_to_group(group, code)` | `group` 可为名称或 ID；`code` 需包含市场后缀，如 `000001.SZ`。 | API 返回的字典（含版本信息）或 `None` |
| `delete_item_from_group(group, code)` | 删除指定股票。 | 同上 |
| `add_group(name)` | 新增分组。 | 同上 |
| `delete_group(group)` | 删除分组（不可恢复，谨慎操作）。 | 同上 |
| `share_group(group, valid_time)` | 创建分享链接，`valid_time` 为秒。 | `dict`，通常包含 `share_url` |
| `refresh_selfstock_detail(force=False)` | 调用 selfstock_detail 接口，刷新加入价格/时间缓存。 | 版本号或 `None` |
| `get_item_snapshot("600519.SH")` | 读取指定股票的加入价格/时间，必要时自动刷新缓存。 | `dict` 或 `None` |
| `set_cookies(cookies)` | 直接替换底层客户端 Cookie。 | `None` |
| `close()` | 手动关闭客户端（`with` 语句会自动调用）。 | `None` |

> `selfstock_detail_version` 属性可查看最近一次下载的 selfstock_detail 版本号；每个 `THSFavorite` 实例也新增了 `price` 与 `added_at` 字段。

### 2.4 示例：全流程自动化
```python
with THSUserFavorite(auth_method="browser") as ths:
    groups = ths.get_all_groups()
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
- 捕获 `None` 返回值即可判断 API 是否成功，例如：
  ```python
  result = ths.add_item_to_group("消费", "600519.SH")
  if not result:
      raise RuntimeError("添加失败，请检查网络或认证信息")
  ```

以上内容覆盖了 CLI 与 API 的全部命令与方法，更多实现细节可直接查阅源码。