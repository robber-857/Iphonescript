# iPhone 美国门店库存监测

Windows 本机后台 + 中文管理网页 + Chrome 扩展。保留澳洲版的表格设计、按配置轮询、库存变化提醒、Windows 声音弹窗及可选 Twilio 电话功能。

美国版使用 **Apple US / 五位 ZIP / 端口 8766 / 独立 data-us/**。当前采集器 **1.4.2**。澳洲版继续使用 `D:\duo` 和端口 8765；美国版使用独立目录 `D:\duo\us` 和端口 8766。两个 collector、配置与启动脚本分开。

## 安装与启动

1. 安装 Python 3.12+ 和 Google Chrome。普通使用者不需要 Node.js 或 pip 依赖。
2. 将美国版源码放在独立目录，例如 `D:\duo\us`，双击 `start.cmd`。
3. 打开 [美国站后台](http://127.0.0.1:8766)。首次安装默认暂停监测、电话关闭。
4. Chrome 地址栏输入 `chrome://extensions`，开启开发者模式 → 加载已解压的扩展程序 → 选择本项目的 `collector` 文件夹，确认名称 **Duo 美国库存采集器**、版本 **1.4.2**。
5. 手动打开 [Duo 256GB Night Sky 美国商品页](https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-256gb-night-sky-unlocked)，点击扩展图标，看到“已选”。
6. 后台填写目标五位 ZIP，例如 **97204**，保存设置，再开始监测。保留 ZIP 开头的零，例如 02108。

后台复用指定的 Apple 标签页依次查询，不新建标签页。关闭、离开商品页或重启浏览器后，需要重新指定。采集时不要手动改动商品选项。

## 监测范围和筛选

- Duo：256GB / 512GB / 1TB / 2TB × Night Sky / Star White，共 8 个配置。
- 美国站统一使用 **Buy（全款）/ Connect to any carrier later** 配置。扩展自动完成不折抵、付款方式、运营商选项，只读取公开自提库存，不加入购物袋、不下单。
- 门店由 Apple 对当前 ZIP 的返回结果决定，没有固定纽约或悉尼名单。
- **实际监测与补货提醒固定限制在 50 km 内**：英里按 `1 mi = 1.609344 km` 换算，恰好 50 km 包含在内。后台在写入库存、计算补货变化、Windows 通知及电话聚合前排除远店。距离缺失或无效时整项查询失败并显示待确认，不会触发提醒。
- 50 km 是后端强制范围，界面没有“查看全部远店”的开关。颜色、容量、仅看有货仅影响这一区域内的表格展示。Apple 页面可能返回更远门店；采集器读取完整区域进行配置与完整性校验，后台仅保留近店。距离不承诺是驾车里程。
- 间隔可选 30 秒、1、2、5、10、15、20、30 分钟，从整轮完成后计时。浏览器采集器约每 30 秒唤醒，实际开始可能稍晚。
- 仅明确可自提才显示绿色。未知文案、配置/SKU 不匹配、请求错误、过期数据均显示“待确认”，不会伪装成缺货。
- 首次发现有货或缺货后再次有货时提醒，持续有货不重复提醒。
- 暂停会作废进行中的采集任务；切换 ZIP 或机型会清空旧结果，拒收旧任务回传。
- 页面时间使用此电脑的浏览器时区。

## 真实库存测试

选择 **iPhone 18 Pro（测试 · 256GB Black）**、保存并检查。读取真实 Apple 页面，可用于验证有货显示。测试机型不触发自动电话。测试完成后切回 Duo。

2026-11-06 已使用 ZIP 97204 进行真实页面验证，具体范围、证据及可重复测试命令见 [README-US.md](README-US.md)。库存会变化，测试结果不代表现在仍有货。

## 提醒和可选电话

“测试提醒”用于检查 Windows 声音与弹窗。保持 Python、Chrome、Apple 采集标签页和电脑联网运行，关闭后台网页不会停止监测；休眠或退出 Chrome 会停止采集。

Twilio 设置包括 Account SID、Auth Token、Twilio 拨出号码与接听号码，号码使用 E.164 格式（例如美国 `+1…`）。保存后，点击“拨打测试电话”会确认目标尾号与费用。自动电话默认关闭，需自行启用。Pro 测试机型不自动拨号。

自动电话在整轮结束合并一次，至少间隔 1 分钟，测试、失败或结果不明的尝试也计入冷却，不自动补拨。来电使用 Twilio 官方示例语音，请查看后台确认库存。“Twilio 已接受请求”不等于接听成功；试用账户和地域拨号权限以 Twilio 账户设置为准。

凭据仅保存于本机 **data-us/phone.json**，未加密，不通过 `/api/state` 返回。不要公开或分享 `data-us/`，不要复制澳洲版凭据。电话真实拨打需要用户自己的账户和费用。

## 更新、Cookie 与打包

更新 Python 代码后须真正退出该目录的旧后台并重启；重复双击启动文件只会打开已运行的服务。扩展更新后在 Chrome 扩展页重新加载，再刷新 Apple 商品页、重新指定采集页。迁移路径后，应移除旧 C 盘的美国版扩展，再加载 `D:\duo\us\collector`；不要移除 `D:\duo\collector` 的澳洲扩展。1.4.2 后台拒收旧采集协议。

升级时会过滤旧结果中的远店/未知距离，并清理旧范围的补货动态，不补发历史提醒。

每轮清理 Apple Cookie 默认关闭。启用后会清理指定 Chrome Cookie 存储区的 apple.com 及子域 Cookie，影响同一配置的 Apple 登录、购物袋和偏好；建议专用浏览器配置。清理成功后才开始等待间隔，失败会暂停监测。不会清理其他网站，也不保证避免请求限制。

运行 `powershell -ExecutionPolicy Bypass -File package.ps1` 生成 **dist/Iphonescript-US.zip**，只打包源码、扩展及说明，不打包本机数据。分享这个 ZIP，不要直接压缩工作目录。

## 开发检查

```powershell
python -m unittest test_monitor test_backend test_us test_phone -v
node --test test_page_input.cjs test_inventory_scope.cjs test_pickup_trigger.cjs test_collector_binding.cjs test_cookie_cleanup.cjs
```

遇到 HTTP 541、验证码或页面结构变化时，暂停并检查正常 Apple 页面。本程序不绕过访问验证。提供问题记录时请只提供版本、时间及脱敏错误，不提供 Auth Token 或完整电话号码。
