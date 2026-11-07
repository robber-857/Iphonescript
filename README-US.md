# 美国版实现与实测记录

当前版本 **1.4.3**，工作目录 **D:\duo\us**，普通独立 Git 仓库，分支 **USDEV**。AU 保留在 **D:\duo**，原 Collector 和本地修改已恢复。C 盘旧工作树已完整备份到 `D:\duo\us\.tmp\us-worktree-migration-20261106`，迁移核对了 1488 个文件的 SHA-256。

## 2026-11-07 Pro 自动电话

Pro 测试模式现在与 Duo 共用自动电话流程：仅处理 50 km 内首次有货或缺货后的补货，整轮合并一次；持续有货不重复拨号，两次拨号至少间隔 60 秒，冷却持久化，失败或结果不明不会自动补拨。仍需保存 Twilio 配置并开启自动电话。Windows 提醒开关不控制电话开关。

本次为后台与网页更新，采集器仍为 1.4.3。更新后必须停止旧的 US 后台再启动，并刷新管理页面。已有的有货记录保留，不因升级重复拨号；若要重新测试首次发现，可在暂停状态下切换到 Duo 保存，再切回 Pro 保存，以清空库存记录，然后启动监测。不要删除 `data-us/phone-usage.json`，它保存电话冷却记录。

## 1.4.3 选页修复

同时支持美国 `/shop/` 与 `/us/shop/` 商品页，补全后台选页和两种页面脚本的注入规则；商品配置与运营商仍严格校验。升级后在 `chrome://extensions` 重新加载 `D:\duo\us\collector`，刷新 Apple 页面并重新点击美国扩展选页。

## 50 km 实际监测范围（1.4.2）

- 固定范围 `0 <= distance_km <= 50`。后端过滤发生在持久化、补货变化判断、事件记录、Windows 通知、电话聚合之前。
- 未知、负数、非数值、NaN、Infinity 距离均拒收；旧采集协议拒收。失败仍保留上次近店结果，但显示待确认。
- Apple 可返回较远门店；采集器校验完整列表，服务器只保留范围内门店。远店不在表格中，也不产生补货提醒。
- 全部返回门店都超过 50 km 时，记录一次成功的空近店结果，不发送提醒。
- 升级时移除旧结果中的远店/未知距离，并清理旧范围的 stock 动态；不重放旧提醒。
- UI 将原来的距离筛选替换为“监测与提醒：50 km 内”，无法切回远店范围。

34 项 Python、29 项 JavaScript 回归通过，覆盖精确 50 km 边界、50.00001 km 排除、远店整轮有货零通知/零电话、近店提醒去重、未知距离拒收和旧数据迁移。电话调用在测试中模拟，没有真实拨号。

## 1.4.2 迁移后实测

后台进程实际从 `D:\duo\us\server.py` 启动，ZIP 97204。真实 Pro 页面返回 8 家门店，服务器仅记录 3 家近店、排除 5 家远店，补货动态也恰好只有 3 条近店事件。UI 显示“监测与提醒：50 km 内”，原距离开关已移除。实测关闭了 Windows 通知和电话，提醒抑制/聚合由上述回归测试验证。

证据：`output/playwright/pro-97204-radius142.json` 和 `pro-97204-radius142.png`。Duo 全配置验证结果保存于 `output/playwright/duo-97204-radius142.json`。

## 1.4.1 的真实页面验证记录（2026-11-06，Sydney 时间）

目标 ZIP 为 **97204**。Duo 8 个配置 × 8 家返回门店真实采集成功，测试当时均无货；Pro 256GB Black 8 家门店均返回 Available Today。这一阶段的 50 km 只是表格筛选，已由 1.4.2 的实际后端范围替代。

近店实测距离：Pioneer Place 0.31 mi（0.5 km）、Washington Square 7.14 mi（11.5 km）、Bridgeport Village 9.37 mi（15.1 km）。其余 Tacoma、Tukwila、Bellevue、Seattle、Lynnwood 门店约 189–259 km，现已排除。

页面集成测试通过 Playwright CLI 向真实 Apple 页面加载原采集器脚本，将扩展消息桥接到本地 API，没有伪造库存。隔离 Chromium 的实际扩展已完成绑定、任务回传、Cookie 清理和清理后 300 秒排期，但 Apple `/shop/fulfillment-messages` 返回 HTTP 541，没有生成库存入口，因此不能宣称实际扩展长期自动采集已全面通过。正常 Chrome 中仍需继续验收。

历史证据保留于 `output/playwright/`。扩展失败记录可能含上次成功 stores，必须同时看 error 与 checked，不能把旧数据当成该次成功。未验证实际 Windows 声音/弹窗展示，未真实拨号。

## 安装路径

- AU Collector：`D:\duo\collector`；后台 8765；原有 AU 本地文件不变。
- US Collector：`D:\duo\us\collector`；后台 8766；本地数据 `D:\duo\us\data-us`。
- US 启动：`D:\duo\us\start.cmd`。
- US 分享包：`D:\duo\us\dist\Iphonescript-US.zip`，不包含本地配置或凭据。
- Chrome 中移除旧 C 盘的美国扩展后加载 US 新目录；不要移除 AU 扩展。

## 重复开发验证

在 `D:\duo\us` 执行：

```powershell
python -m unittest test_monitor test_backend test_us test_phone -v
node --test test_page_input.cjs test_inventory_scope.cjs test_pickup_trigger.cjs test_collector_binding.cjs test_cookie_cleanup.cjs
```

实际扩展测试使用隔离持久化 Chromium。它暂停现有 US 监测、选择测试 ZIP/机型、关闭声音通知，在隔离配置中测试 Cookie 清理；最后暂停并恢复间隔/通知/Cookie 偏好。自动电话必须事先关闭。

```powershell
npm install --prefix .tmp/browser-tools --no-save playwright
$env:PLAYWRIGHT_MODULE = Join-Path $PWD '.tmp/browser-tools/node_modules/playwright'
& .tmp/browser-tools/node_modules/.bin/playwright.cmd install chromium
node scripts/live_us_extension.cjs 97204 pro-test
```

页面集成函数 `scripts/live_us_page_step.js` 每次读取后台一个任务。先启动后台、选择 ZIP 和机型并关闭自动电话，再开始监测，在已打开 Apple 页的 Playwright CLI 会话中执行：

```powershell
npx --yes --package @playwright/cli playwright-cli -s=us-stock run-code --filename=scripts/live_us_page_step.js
```

Duo 执行 8 次后，再执行一次推进整轮完成，最后暂停。此辅助测试不能代替完整扩展验收。
