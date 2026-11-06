# 美国版实现与实测记录

基线：USDEV `ad11dcb`。本次实现基于该分支，采集器版本 **1.4.1**。使用说明见 [README.md](README.md)。

## 本次修复

- 统一使用美国 `-unlocked` 商品 URL，自动完成不折抵 / Buy / Connect to any carrier later。
- US 部分自提弹窗为空标题、容量颜色 radio 未选中。此时必须同时通过商品页 URL、容量、颜色、运营商、查询入口产品名称和 SKU 校验，并验证弹窗主商品和每家门店 SKU 一致。显式冲突仍拒收；不读取 Similar models 推荐库存。
- 校验“nearest stores”声明数量，避免接受尚未完整渲染的缺货名单。
- 采集 Apple 门店距离；英里乘 1.609344，50 km 筛选默认开启，未知距离不纳入。筛选只影响显示，不改变通知范围。
- 查询失败保留已知门店并显示待确认；暂停、切换 ZIP 和重启作废旧任务/清理租约；支持大于 4 KB 的动态门店回传。
- 更新美国测试数据、README、打包；忽略 data-us/，防止电话配置或本地记录被误提交。

## 2026-11-06 实测（Australia/Sydney）

目标 ZIP：**97204**。这些是测试当时结果，不是持续库存保证。

| 验证层级 | 结果 |
| --- | --- |
| Python 回归 | 29 项通过：任务/邮编/调度、去重、错误保留、暂停作废、电话聚合与冷却等 |
| JavaScript 回归 | 28 项通过：页面输入、主商品范围/SKU、美国选项、绑定、Cookie、距离换算与边界 |
| Apple 真实页面 → 原采集器脚本 → 本地 API | Duo 8 配置 × 8 门店采集成功；当时 64 格均为 unavailable。Pro 256GB Black 8 门店均返回 Available Today |
| 50 km UI | 真实距离下显示 3 / 8 家；关闭筛选显示 8 家，与仅看有货组合正常；375px 页面无整体横向溢出 |
| 实际扩展加载与任务回传 | 隔离 Chromium 已加载 1.4.1、绑定指定页、执行任务并回传错误；Apple `/shop/fulfillment-messages` 返回 HTTP 541，自提入口未生成，因此完整扩展库存成功链路尚未通过 |
| 扩展 Cookie 与间隔 | 隔离测试配置中实际清理 Apple Cookie、后台收到成功回执，回执后 300 秒排期通过；不代表 Cookie 能消除 HTTP 541 |
| 电话/桌面弹窗 | 电话模块使用模拟调用测试，未真实拨号；本轮未验证实际 Windows 声音/弹窗展示 |

页面集成测试通过 Playwright CLI 向真实 Apple 页面加载仓库 `page-input.js` 和 `content.js`，仅将扩展消息通道桥接到本地 API，**没有伪造或注入库存数据**。这不等于已验证实际 Chrome 扩展的长期自动运行。

隔离浏览器的 HTTP 541 不按缺货处理。日常使用需在正常 Chrome 中手动加载扩展、打开具体商品页并绑定后继续验收；本次没有安装或替换用户日常 Chrome 中的扩展，也未改动 AU 服务。

50 km 内实际门店：

| 门店 | Apple 原始距离 | 换算显示 |
| --- | --- | --- |
| Apple Pioneer Place | 0.31 mi | 0.5 km |
| Apple Washington Square | 7.14 mi | 11.5 km |
| Apple Bridgeport Village | 9.37 mi | 15.1 km |

其余返回门店位于 Tacoma、Tukwila、Bellevue、Seattle、Lynnwood，约 189–259 km，开启筛选时隐藏。

本地证据（均在 Git 忽略目录）：`output/playwright/duo-97204-live.json`、`pro-97204-live.json`、`pro-97204-50km.png`、`pro-97204-mobile.png`，及隔离扩展失败记录 `pro-test-97204-extension.json`。失败记录里的旧 stores 保留上次成功数据，必须同时检查 error 与 checked 时间，不能当作此次成功。

## 重复开发测试

普通用户无须安装以下开发工具。

```powershell
python -m unittest test_monitor test_backend test_us test_phone -v
node --test test_page_input.cjs test_inventory_scope.cjs test_pickup_trigger.cjs test_collector_binding.cjs test_cookie_cleanup.cjs
```

实际扩展测试使用 Playwright 官方的持久化 Chromium 上下文方案（[官方说明](https://playwright.dev/docs/chrome-extensions)），独立临时浏览器配置，自动电话必须关闭。它会短暂开启 Cookie 清理，仅作用于隔离测试配置，结束后暂停监测并恢复间隔/通知/Cookie 偏好，保留测试 ZIP、机型及结果。

```powershell
npm install --prefix .tmp/browser-tools --no-save playwright
$env:PLAYWRIGHT_MODULE = Join-Path $PWD '.tmp/browser-tools/node_modules/playwright'
& .tmp/browser-tools/node_modules/.bin/playwright.cmd install chromium
node scripts/live_us_extension.cjs 97204 pro-test
# Apple 正常允许访问时，再测整轮：
node scripts/live_us_extension.cjs 97204 duo
```

`live_us_page_step.js` 是 Playwright CLI 的单配置真实页面集成函数。先启动后台并保存 ZIP / 机型、关闭自动电话、开启监测，然后在 CLI 管理的 Apple 页面中运行：

```powershell
npx --yes --package @playwright/cli playwright-cli -s=us-stock run-code --filename=scripts/live_us_page_step.js
```

一次领取并提交一个配置；Duo 完成 8 次后，再运行一次推进整轮完成，最后在管理页暂停。此辅助测试不能替代实际扩展验收。
