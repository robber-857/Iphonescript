# 美国版本地运行（初版）

保留原界面及轮询、库存变化提醒逻辑。美国版使用五位 ZIP Code、Apple 美国商品地址、附近动态门店，后台端口 8766，配置在 data-us/。时间按浏览器本地时区显示。

## 安装

1. 解压项目到独立目录，例如 Iphonescript-US；不要复制澳洲版 data/。
2. 安装 Python 3.10 或更新版本（Windows 安装时勾选 Add Python to PATH）。不需要 pip 依赖。
3. Windows 双击 start.cmd。macOS/Linux 在项目目录运行 `python3 server.py`。
4. 打开 http://127.0.0.1:8766 。
5. Chrome 打开 chrome://extensions，启用开发者模式，选择“加载已解压的扩展程序”，选此项目的 collector 文件夹。
6. 在 Apple 美国官网打开所选型号的具体商品配置页，点击“Duo 美国库存采集器”图标，出现“已选”。填写五位 ZIP（例如 10001、02108），保存并开始监测。
7. 保持 Chrome、后台及电脑运行。Windows 提供声音和弹窗；其他系统当前仅有终端提示。电话配置在本地界面填写。

## 验证范围

已验证美国 URL、ZIP 校验（包括前导零）、动态门店结果接收和电话模块单元测试，以及 JavaScript 语法。
尚未完成真实美国 Apple 页面端到端测试。型号与配置沿用原仓库 Duo / iPhone 18 Pro；这些美国商品地址及页面结构未核实。若官网不提供对应商品，需按实际型号调整 monitor.py 和扩展匹配规则；不能把此初版视为已验证可持续监测。采集失败会显示待确认。

美国多运营商/付款选项可能需要手动选好再绑定采集页；当前没有新增自动选择运营商逻辑。

原 README.md 和原测试文件保留为上游参考，其中澳洲说明不适用于本版本。运行本版本验证：`python -m unittest test_us test_phone`。

源码来源：robber-857/Iphonescript，提交 ca1be60c5705eafc3a6a37eac0486600364f8ed4。USDEV 分支保留上游其他文件，仅修改库存监测相关源码。美国版开发请使用 USDEV 分支。
