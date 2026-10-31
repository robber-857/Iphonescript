# Cardbox · Gmail 礼品卡 PIN 提取

独立的 Python 后台与中文前端，不依赖第三方 Python 包。需要 Python 3.12+。

双击 `start.cmd`，打开 http://127.0.0.1:8876 。已有的 iPhone 程序使用另一端口，不受影响。

## 使用

1. 首次配置 Google 登录：在 Google Cloud 项目中启用 Gmail API，配置 OAuth 同意屏幕（External 测试模式时，将所有要使用的邮箱加入测试用户），创建 **Desktop app / 桌面应用** OAuth 客户端并下载 JSON。在后台“Google 登录配置”中导入。不要使用 Web application 客户端。配置保存到 Git 忽略的 `../data/giftcard-oauth-client.json`，仅包含应用客户端信息。Google Cloud：https://console.cloud.google.com/auth/clients 。
2. 点击 **使用 Google 登录**，浏览器跳转到 Google 官方页面，选择邮箱并授权 Gmail 只读权限。无需应用专用密码。邮箱字段是可选的登录提示，以 Google 实际授权的邮箱为准。支持保存多个邮箱地址、选择后通过 Google 切换账号。切换成功清空上一邮箱的结果，失败或取消保留原连接。地址存本机浏览器；access/refresh token 只保存在后台内存，重启后重新登录。断开连接清除本地 token，不会撤销 Google 账户已授予的权限；如需撤销，前往 https://myaccount.google.com/connections 。
3. Filter 默认是“标题短语 / 自动识别邮箱”：直接输入完整邮箱（如 `sender@example.com`）会按发件人搜索，生成 `from:"sender@example.com"`；也可选择“发件人地址”模式。输入 `Chen sent you` 会自动转换为 `subject:"Chen sent you"`，保持词序，不将输入拆成多个词。标题可以有前后缀，例如 `Fwd: Chen sent you an Apple Gift Card.`。可切换到“整封邮件包含完整短语”（标题/正文等 Gmail 可搜索内容），或“高级 Gmail 搜索”自行填写 `from:someone@gmail.com subject:"Gift Card"` 等表达式。页面同时显示将提交的搜索条件和当前结果对应的条件。Gmail 引号搜索不是逐字符、区分大小写的整个标题相等比较。刷新页面会恢复已有关键词；含搜索语法的旧条件恢复为高级模式，普通关键词采用新的默认模式。旧结果始终显示原查询，条件改变后需重新搜索。搜索不含垃圾邮件与回收站，按 Gmail API 返回顺序处理。
4. 选择每批 10 / 25 / 50 / 100 封，点击“提取下一批”。100 是邮件数，一封邮件的多个 PIN 各显示一行。处理中可点击“暂停”：当前邮件读取完成后暂停，保留进度与结果；点击“继续提取”接着处理剩余邮件。暂停时可导出已提取结果；切换邮箱或重新搜索需等待本批完成。反复点击直到本轮处理完成。重新搜索才会包含搜索后新收到的邮件。
5. 切换结果分类、每页条数、上一页/下一页；显示完整 PIN 或复制。修改 Filter 后必须重新搜索才能继续提取，避免误混结果。
6. 导出真正的 `.xlsx` 文件，包含本轮已经处理的所有结果（不受表格当前页或分类限制），包括 PIN、状态、主题、发件人、日期、邮件 ID、失败原因。所有单元格为文本，保留开头的零、避免公式执行。

## 提取与数据

- 支持文本与 HTML 正文，包括 Apple 转发邮件 `Your Gift Card PIN` 后的字母数字代码，以及 `PIN number`、`PIN code`、卡密等明确标记。
- 同一邮件重复 PIN 去重；不同邮件相同 PIN 保留来源。没有匹配标记的邮件保留“待核对”，不会把金额、订单号或普通正文当成 PIN。
- 不自动访问兑换链接、不兑换卡、不加载邮件图片。图片、PDF 附件、其他外部网页不做 OCR 或读取。
- 读取失败保留行并支持重试；大于 12 MB 的邮件转人工核对。不会修改已读状态、标签或邮件内容。
- 后台仅监听 127.0.0.1，限制 Host、Origin 和写操作 token；不记录请求、凭据或 PIN 日志。运行中的结果保存在内存；关闭程序后消失，先导出再关闭。
- 独立程序不能复用 Codex 的 Gmail 插件登录状态。可用 `python server.py --import-messages ../data/giftcard-messages.json` 查看通过插件读取的本地 MIME 快照；启动脚本在此文件存在时自动载入。快照和导出的 Excel 含真实 PIN，应当作为个人文件保管；`data/` 已被 Git 忽略。删除快照后重启不会再次载入。
- 关闭浏览器不等于停止后台。后台重启前请导出结果。断开连接会清空运行内存中的结果。

## 验证

在此目录运行 `python -m unittest -v`。覆盖 Apple HTML、多个 PIN、去重、前导零、误识别、附件排除、Excel XML 与公式防护、100 封批次、读取失败重试、Unicode 搜索、OAuth state/过期/重复回调、PKCE、配置校验、Gmail API 分页、令牌刷新与原始邮件解码。真实 Google 授权需导入有效客户端配置后完成验证。

Google 官方说明：https://developers.google.com/identity/protocols/oauth2/native-app 。使用授权码流程、PKCE S256、10 分钟有效且一次性校验的 state、本机回调；仅申请 `gmail.readonly`。测试模式/Workspace 管理策略可能限制可授权的邮箱；对外发布应按 Google 要求处理应用验证。

搜索构造验证：`node test_search.cjs`。
