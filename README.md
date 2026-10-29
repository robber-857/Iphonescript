# iPhone 悉尼库存监测

Windows 本机后台 + 中文管理网页 + Chrome 扩展。默认监测 Apple 澳洲 **iPhone Duo：256GB / 512GB / 1TB / 2TB × Night Sky / Star White**，覆盖悉尼 7 家门店。另有 **iPhone 18 Pro 256GB Black** 真实库存测试选项。

读取公开自提库存，不登录 Apple、不加购物车、不自动下单。库存以 Apple 最终下单页面为准。

## 给朋友使用（Windows）

1. 下载本仓库：GitHub → **Code → Download ZIP**，解压到固定文件夹，例如 `C:\Iphonescript`。不要在 ZIP 内直接运行。
2. 安装 [Python 3.12 或更新版本](https://www.python.org/downloads/windows/)，安装时勾选 **Add python.exe to PATH**；安装最新版 [Google Chrome](https://www.google.com/chrome/)。无需 Node.js，也无需 pip 安装第三方依赖。
3. 双击 `start.cmd`，打开本地后台 `http://127.0.0.1:8765`。重复启动会打开现有后台。
4. 在 Chrome 地址栏输入 `chrome://extensions` → 打开 **开发者模式** → **加载已解压的扩展程序** → 选解压目录内的 **collector 文件夹**（不是项目根目录）。
5. 回到后台，默认选择 **iPhone Duo**、邮编 **2000**；保存设置并点击 **开始监测**。
6. 先点击 **测试提醒** 验证 Windows 弹窗。电话提醒需要另外配置，见下文。

每个人都在自己的电脑安装同一个 collector 文件夹即可，不需要你给他们单独制作扩展。此版本未上架 Chrome Web Store，故需要手动加载；企业管理的 Chrome 可能禁止开发者扩展。不要移动已加载的 collector 文件夹。更新文件后，在扩展管理页点击该扩展的刷新按钮，重启后台并刷新管理网页。

**分享仓库链接、GitHub 下载 ZIP 或 `dist/Iphonescript.zip` 即可。不要直接打包你的工作目录，更不要分享 `data/`，其中包含个人电话凭据和监测记录。** `package.ps1` 会只打包源码、说明和扩展，不包含个人数据。

## 运行和监测设置

- 机型：默认 Duo 全部 8 个配置；Pro 测试仅检查 256GB Black，避免把测试机型库存误认为 Duo 补货。
- 邮编可编辑，默认 2000；更改查询中心后仍监测以下固定 7 家店：Sydney、Broadway、Bondi、Chatswood Chase、Miranda、Castle Towers、Penrith。
- 每轮完成后等待：30 秒、1 分钟、2 分钟、5 分钟（默认）。扩展 1.1.2 约每 30 秒唤醒一次，浏览器调度可能导致实际开始稍晚；一轮查询自身也需要时间。
- 关闭管理网页不影响采集；必须保持 **Python 后台、Chrome、Apple 采集标签页** 运行，电脑联网且不休眠。采集标签可以在后台。
- 退出 Python 后台或 Chrome 会停止检查；不开机自启。重启电脑后再次双击 `start.cmd`，会恢复已保存的监测开关。
- 颜色/容量筛选只改变表格展示；“监测机型”保存后才改变采集范围，切换会清空旧结果。
- 绿色 **● 可自提** 表示页面明确有货；查询错误、未知文案或过期显示 **待确认**，不会误报无货。
- 首次发现有货、或缺货后再次有货才触发提醒，持续有货不重复提醒。

## 用 iPhone 18 Pro 验证有货界面

设置中选 **iPhone 18 Pro（测试 · 256GB Black）** → 保存 → 立即检查（如已在查询，等待完成）。页面会采集真实 Apple 库存，有货时显示绿色格子并产生带 **Pro 测试** 标记的 Windows 提醒。测试机型**不触发自动电话**；测试完成切回 Duo 并保存。

2026-10-29 手动读取 Apple 官方页面时，以上 Pro 配置的 7 家监测门店均显示 `Available Tomorrow`。这只是当时快照，不保证你使用时仍有货。

## 电话提醒：Twilio Voice

推荐 [Twilio Programmable Voice](https://www.twilio.com/docs/voice/api/call-resource)。后台直接向 Twilio 发起外呼并提供朗读文字，无需公网服务器、域名或端口映射。真实电话会产生服务商费用；本项目不提供电话服务账户。

1. 自行注册 [Twilio](https://www.twilio.com/try-twilio)，按控制台指引完成账户验证。
2. 准备支持 Voice 的 Twilio 拨出号码，确认可拨打接听号码所在国家/地区、余额及相应地域拨号权限。号码购买、身份/地址材料要求及价格以控制台为准。
3. 从 Twilio 控制台获取 **Account SID** 与 **Auth Token**。不要把它们发到 GitHub 或公开聊天。
4. 在本地后台“电话提醒 · Twilio”填写 SID、Token、Twilio 拨出号码、自己的接听号码。号码用 E.164 格式，例如澳洲 `04xx...` 转为 `+614xx...`。
5. 保存后点击 **拨打测试电话**，界面会确认目标号码尾号及费用；接听后会听到英文测试语音。试用账户只允许已验证号码，并受国家及其他试用限制，参见 [官方试用说明](https://www.twilio.com/docs/usage/trials/try-out-voice)。
6. 测试成功后，勾选 **开启 Duo 自动电话提醒** 并保存。Windows 弹窗开关与电话开关独立。

补货时整轮合并为一通电话，英文播报机型和门店（最多摘要前 5 个配置，其余见后台日志）。至少间隔 **10 分钟**，每 **UTC 日期最多 3 次**，含测试和失败/结果不明的尝试，重启后限制仍保留。限流时仅记日志、不补拨；持续有货不重拨。电话未接听也不会无限重试；账户未开通或网络异常时请检查后台记录及 Twilio 通话日志。

界面的“Twilio 已接受拨号请求”**不代表对方已接听**；接通/忙线/失败以 Twilio 通话日志为准。没有填入真实凭据时不会打电话。

凭据保存到本机 `data/phone.json`（未加密，只应由你信任的本机账户访问），不在 `/api/state` 返回；页面只显示号码尾号，重新保存时留空保留旧值。每位使用者应使用自己的 Twilio 账户和号码，避免共用你的密钥和账单。

## 开发和打包

仅 Python 标准库。测试：

```powershell
python -m unittest test_monitor test_backend test_phone -v
node --test test_page_input.cjs
```

Node.js 仅用于开发测试，不是使用脚本的依赖。运行 `powershell -ExecutionPolicy Bypass -File package.ps1` 生成干净分享包 `dist/Iphonescript.zip`。

- `server.py`：API、任务分发、持久化、Windows 提醒。
- `monitor.py`：机型、门店和补货状态判断。
- `phone.py`：Twilio 外呼、凭据、冷却和次数限制。
- `collector/`：Chrome 扩展 1.1.2，真实页面采集。
- `web/`：本地管理页面。
- `data/`：仅本机数据，禁止分享。

此工具只在 `127.0.0.1:8765` 监听。Apple 页面变化、访问限制或验证码可能中断采集；无法保证持续可用。它不会绕过验证或自动购买商品。

扩展 1.1.2 同时识别 Check availability 和库存区域的门店名称入口（如 Apple Sydney）。更新后需在 Chrome 扩展管理页重新加载一次扩展。

采集页会在管理网页所在的 Chrome 窗口中新建标签页并切到前台；没有打开管理网页时使用最近聚焦的 Chrome 普通窗口。后续配置查询复用采集标签页并切到前台。
