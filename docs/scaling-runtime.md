# OpenSim 缩放与数据读取

## 模型与依赖

右手基准：`Hand_Wrist_Model_for_development.osim`，SHA-256 `9a88909ca27da9397abe22599e51ae9699162bdf274f65d2a83d7b02793b24cc`。
左手基准：`Hand_Wrist_Model_LEFT_GlobalX180.osim`，SHA-256 `45c45732788afd4fcc78b89c97cf7a5da51de82dcb735d480459ee4e8770207b`。
`personalize.py` 还保留历史个性化模型的摘要白名单。其他模型不能仅改文件名接入，必须重新核对关节、几何及路径适配。

将有权使用的 XML 及它引用的几何放在运行目录 `base/`，保持模型引用的相对路径。原始模型和几何未随此仓库重新分发；模型许可与来源由资产提供方决定。

- 网页：Node.js 20 或更高版本，无构建步骤；Three.js 已附带许可。
- 解算环境：OpenSim 4.5.2 Python 绑定、NumPy、SciPy；建议使用已有兼容 OpenSim 环境。
- 读取环境：Python 3.12，`pip install -r server/requirements-reader.txt`。与 OpenSim 环境分离。
- 视频转码使用 imageio-ffmpeg 提供的 FFmpeg。

## 本机或服务器运行

以下路径为占位示例，必须替换成自己的路径。环境变量需要传给服务进程，不需要写进仓库。

```sh
TENDON_RUNTIME=/absolute/path/runtime \
TENDON_SOURCE_ROOT=/absolute/path/private-rrd-directory \
TENDON_READER_PYTHON=/absolute/path/reader-env/bin/python \
TENDON_SOLVER_PYTHON=/absolute/path/opensim-env/bin/python \
python3 server/all_service.py
```

服务固定监听 `127.0.0.1:8770`，按需扫描指定目录内全部 RRD。新部署全部使用稳定的 `record-` ID，不依赖以前的六条私人样本服务。首次选择才抽取、转码和解算；单工作队列最多等待八项，单个子进程限时十五分钟。

同机运行网页：

```sh
TENDON_CATALOG_PORT=8770 npm start
```

如果计算在远端，在自己的终端建立 SSH 隧道：

```sh
ssh -N -L 127.0.0.1:18770:127.0.0.1:8770 -p YOUR_PORT YOUR_USER@YOUR_HOST
npm start
```

打开 `http://127.0.0.1:4173/?mode=personal`，选择记录和左右手后加载。视频与模型采用同一记录及时间表；“停止等待”只取消浏览器等待，不终止服务器计算。网页和计算服务均应保持回环监听，不要直接暴露到公网。本项目不是仅上传静态网站即可运行的个人解算服务。

## 输入契约

RRD 读取器目前限定已适配结构，不自动猜测单位或左右手顺序：

| 字段 | 形状/约定 |
| --- | --- |
| joints_world_raw | N × 2 × 21 × 3，米，cam0 坐标系 |
| valid | N × 2 |
| valid_joints | N × 2 × 21 |
| capture_timestamp_ns | N，严格递增的纳秒时间戳 |

左右手顺序为 left、right。提取时只用原始重建点，不用平滑结果替代。点序为腕点、拇指四点、其余四指各四点；必须核对上游输出符合 WiLoR/MANO21 约定。

视频实体 `/video/fixed/cam0` 需要 HEVC 包、关键帧标志与 `capture_time`；相机实体 `/world/fixed_cameras/cam0` 需要 `Pinhole:image_from_camera`。处理器核对来源哈希、视频帧数和时钟，拒绝未适配的 B 帧重排。其他 Chord/RRD 导出结构需要新增适配，不能直接保证兼容。

## 缩放规则与边界

1. 使用有效观测的稳健跨度统计估计固定尺寸，不逐帧改变骨长。九个关节间跨度加五个末节至指尖跨度和拇指掌骨跨度，共十五项有观测跨度。
2. 优先局部 Y 轴缩放；斜向跨度无法满足几何边界时，可按观测与基准跨度之比等比例缩放。整体比例需在 0.5–1.8 范围内。
3. 波动较大时检查不重叠三秒窗口：至少三十帧、80% 覆盖、相对 MAD 不超过 2.5%、前后半段中位数差不超过 3%。至少三个窗口且覆盖 20% 有效观测；各窗口需在 max(1 mm, 5%) 内一致。
4. 窗口不一致但比例可行时，可应用全段稳健中位数作为固定候选，保留 review 标记；不足数据或不可行时不应用。质量标记不是临床诊断。
5. 五个指尖采用模板骨端代理；拇指基部采用 CMC1b 对应。宽厚按模板估计。四指 CMC2–5 缺少独立观测，掌骨长度保留基准，根部布局按 MCP 点阵推断。
6. OpenSim 同步处理关节偏置、网格、肌腱路径点及包绕几何，随后复测跨度。肌纤维长度和肌腱松弛长度由最终/原始参考路径比例更新，Fmax 保留。不是实测肌腱长度。
7. 拟合二十个手指坐标与整体手部位姿，导出骨骼变换和 OpenSim 求得的绕行路径。缺少前臂参考，不能把腕角当作实测。
8. `dynamicsReady=false`。运动可视化通过不等于动力学、肌力、碰撞或解剖精度验证。未实现外力提取、37 肌肉映射或 QP。

默认拟合 30–42 秒；短记录从开始取最多十二秒，不足两秒拒绝处理。缓存位于运行目录 `cache/all-records/<代码摘要>/<记录ID>/`；模型、数据与缓存必须留在私人环境。

## 检查

```sh
npm test
cd server
python3 -m unittest test_all_catalog test_recording_catalog test_scaling test_palm -v
```

需要 OpenSim、基础模型和私有样本的集成测试不能由空仓库独立运行。旧样本测试用于历史回归，不代表所有导入记录均已验证。
