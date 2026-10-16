# ai-dialogue-shorts

对话短视频流水线：**文案进 → 分镜表 → AI 视频 → 双人配音 → 双语字幕 → 成片出**。

整合了两个开源项目的核心思想：

- **MoneyPrinterTurbo**（harry0703/MoneyPrinterTurbo）：自定义文案驱动的流水线——每个环节可用自定义内容，一句对白一镜，逐镜配料再合成。
- **Toonflow**（HBAI-Ltd/Toonflow-app）：角色资产管理——每个角色一份 YAML（固定外貌描述 + 参照图 + 配音），分镜提示词注入一字不差的角色锁定块，跨镜不串脸。

## 快速开始

```bash
pip install -r requirements.txt

# 1) 写文案（examples/zheng.md 为示例）
# 2) 建角色（characters/*.yaml）
# 3) 生成分镜表
python cli.py board examples/zheng.md --chars characters/ -o work/shots.json

# 4) 看分镜
python cli.py md work/shots.json -o work/board.md

# 5) 全链路出片（需 MODELSCOPE_API_KEY）
export MODELSCOPE_API_KEY=ms-xxx
python cli.py build examples/zheng.md --chars characters/ --work work -o final.mp4
```

## 文案格式

```markdown
# 争

场景：晨雾茶山

[远景] 晨雾漫过层层茶山 / Mist rolling over layered tea mountains

老茶农：小伙子，记住——赢了争吵的人，其实都输了。 / Everyone who wins an argument has lost.
```

- `# 标题`、`场景：xxx`
- `[景别] 中文动作 / EN action`：远景/全景/全身/中景/近景/特写；不写则自动轮转
- `人名：中文对白 / English`：一句对白 = 一镜，`/` 后英文可省

## 角色资产

`characters/<id>.yaml`：

```yaml
name: 老茶农
name_en: old tea farmer
appearance: 60多岁中国老茶农，饱经风霜的皱纹脸，灰白短发，深蓝色粗布衣
appearance_en: an elderly Chinese tea farmer in his 60s, sun-weathered wrinkled face, short grey hair, dark blue coarse cloth shirt
reference_image: ref/laochanong.png   # 可选
voice: zh-CN-YunxiNeural              # edge-tts
```

## 环境变量

| 变量 | 用途 |
|---|---|
| `MODELSCOPE_API_KEY` | 通义万相 Wan2.1 视频生成（魔搭 `访问令牌` 页申请，建议写权限及以上） |
| `MODELSCOPE_API_BASE` | 可选，覆盖 API 地址 |

配音用 edge-tts（免费、无 key），字幕/合成用本机 ffmpeg。

## 许可证

MIT。整合思想致敬上游开源项目，具体实现均为原创。
