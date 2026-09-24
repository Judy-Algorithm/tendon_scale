# 同事交接：数据 → 个体手部缩放 → 动作与视频

## 目标和当前完成范围

产品目标是用户上传手部运动数据，在共享 OpenSim 基准上生成个人尺寸并查看运动。当前已经完成数据目录读取、左右手缩放、动作拟合、肌腱路径导出、模型/视频同步展示。**当前没有网页文件上传按钮和上传接口**，需由操作者先将 RRD 放到服务器指定目录；不要把产品目标误认为上传功能已实现。

此仓库包含运行基准的两份原始 XML 及 33 份几何资产，见 `models/README.md`。不依赖前一位开发者的电脑目录、服务器账号或六条私有样本。真实 RRD、视频和个人结果不在公开仓库。

## 接手顺序

1. 克隆仓库，运行 `python3 scripts/setup-models.py` 核对基准。
2. 按 `docs/scaling-runtime.md` 配好 RRD 读取环境和 OpenSim 4.5.2 解算环境。
3. 运行 `python3 scripts/setup-models.py --runtime /absolute/path/runtime`，放置基准资产。
4. 将一条有权使用且符合字段约定的 RRD 放到私人输入目录。配置 `TENDON_RUNTIME`、`TENDON_SOURCE_ROOT`、`TENDON_READER_PYTHON`、`TENDON_SOLVER_PYTHON` 后启动 `server/all_service.py`。
5. 同机用 `TENDON_CATALOG_PORT=8770 npm start`；远端按运行指南建隧道。访问 `/?mode=personal` 选择记录、左右手并加载。
6. 确认尺寸表、视频同步和肌腱通道都有结果，再开发网页上传。换用其他模型或 Chord 输出前，先核对适配，不绕过摘要和数据字段校验。

## 代码路线

`all_catalog.py` 扫描输入 → `all_service.py` 接收已登记记录 ID → `prepare_record.py` 抽取原始点及视频 → `solve_record.py` 调用 `personalize.py` → `personal.js` 显示结果。

- 骨段长度、稳健统计、缩放可行性：`scaling_core.py`。
- 掌部位置调整：`palm_scaling.py`；指尖代理：`landmark_estimates.py`。
- 左手修复：`left_adapter.py`；包绕修复及检查：`path_repairs.py`、`scale_checks.py`。
- 肌腱通路长度表：`tendon-scale.js`；视频时钟：`video-sync.js`。
- 可取消等待、防旧请求覆盖：`personal-loading.js`。停止等待不取消服务器任务。

基准 XML 不按人覆盖；缩放在内存完成，结果、方案和视频在私人运行目录缓存。运行指南列出已实现的十五项观测跨度与四根掌骨保留基准等边界。不能宣称全部骨头的宽厚都是实测，也不能把当前可视化直接用于可信肌力 QP。

## 网页上传的后续工作

这是待开发项：增加文件选择与进度，后端受限上传接口、大小/格式检查和私人存储，上传成功后刷新目录并返回记录 ID，再复用现有 jobs/result 流程。现有目录仅在服务启动时扫描，因此只把文件传进去还不能立即出现在列表里。若要多人远程使用，必须先设计身份认证、权限、数据隔离和任务资源限制，不能直接把回环服务改为公网监听。

## 验证状态

交接版本已验证前端测试、基础统计规则测试和资产校验；未在本次交接中重新连接私人服务器或重跑真实数据完整解算。模型相关集成测试需要 OpenSim 及对应私有样例。第一次接入新环境时请完成上述单样本检查，不以“能打开页面”代替解算验收。
