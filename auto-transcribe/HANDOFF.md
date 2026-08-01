# auto-transcribe 项目交接 (2026-07-31 更新)

> 07-31 新增:**乐器级分离** (`--stems`, MSST + 社区 roformer, 桌面「拆乐器」入口, 独立 `.venv-sep`)。
> 详见 README「乐器级分离」节 + RESEARCH.md「乐器级分离生态大调查」。
> "社区没有乐器/lead 分离模型" 的旧结论已被推翻 —— SW 6轨 (钢琴/吉他 MVSEP 双第一)、
> Mega-53 (53 种乐器)、lead-synth 实验模型都已接入。LLM 问题也有了硬数据答案:不用 LLM
> (音频 LLM 单音音高识别只有 6.1%),MT3 类转录 transformer 才是正解 (pip mt3-infer, 待实验)。

给下一个 agent:两分钟看完这份就能接手。用户是 Kunqi,做和声分析视频,上支视频 60 小时花在人工扒谱上。

---

## 项目位置

```
K:\Claude Projects\!!!ChordHUD\auto-transcribe\     ← 代码 (ChordHUD 同 repo)
git: KunqiK/mychord, master, HEAD = da51c76 (已推送)
```

文档:`README.md`(技术)· `使用说明.md`(给用户)· **`RESEARCH.md`(研究档案,含所有失败实验 —— 先读这个避免重做)**

---

## ⚠️ 环境陷阱(踩过的坑,别再踩)

| 陷阱 | 后果 / 解法 |
|---|---|
| PATH 上的 `python` 是 **MSYS2 MinGW** | 装不了任何 wheel。**一律用 `.venv\Scripts\python.exe`**(由 `py -3.12` 建) |
| torch **必须 2.5.1** | 2.6 改了 `torch.load` 默认值,demucs 载权重会炸 |
| **setuptools<81** | ≥81 删了 pkg_resources,pretty_midi 要用 |
| basic-pitch 用 `--no-deps` 装 | 它在 Win+py≥3.11 强制要 tensorflow<2.15.1(py3.12 不存在),推理实际走 ONNX |
| **onnxruntime 已升到 1.28.0** | Melodfy 钢琴模型含新版融合节点,1.19.2 加载失败。basic-pitch 在 1.28 下已复验正常 |
| demucs 4.0.1 **没有** `demucs.api` | `separate.py` 直接驱动 `apply_model` |
| PowerShell 里写含引号的 commit message 会炸 | 用 heredoc `@'...'@` 且**消息里不要有英文引号** |

---

## 入口

```bash
# 用户日常用(桌面图标,拖歌上去)
C:\Users\kunqi\Desktop\拖歌扒谱.cmd

# 开发用
transcribe.cmd "<歌>" [--click --bpm N --key "Ab Major" --downbeat-shift 0..3
                       --piano --force <stage>|all --vocal-gate 0.25]

# 回归测试(改任何算法后必跑,基线 16/16 和弦 + 32/32 旋律)
.venv\Scripts\python.exe selftest.py

# 对标准答案打分
.venv\Scripts\python.exe evaluate_gt.py --midi <GT.mid> --cache cache\<slug> [--offset 2.04] [--details]
```

阶段缓存:`separate → beats → {key,chroma,bass} → chords → 输出`;melody/piano 独立。
改参数只需 `--force chords`(秒级),不用重跑 5 分钟的分离。**改了算法要记得在 cli.py 的 run_stage params 里 bump `'v'` 号,否则读旧缓存。**

---

## 📌 基准文件(千万别删)

| 文件 | 内容 |
|---|---|
| **`gt\S.A.T.E.L.L.I.T.E.mid`(已入库)** | 人工全曲扒谱,24 轨(Pad/Piano/String 和声,Lead/Vocal 旋律),150 BPM |
| 音频 | `D:\!!!Production\Reference Tracks\Camellia\[C95] かめるかめりあ — heart of android {CTCD-0018} [CD-FLAC]\07. S.A.T.E.L.L.I.T.E..flac` |
| cache slug | `07_S_A_T_E_L_L_I_T_E-374430a1` · **对齐偏移 = +2.04s**(音频减 MIDI) |

⚠️ 2026-07-31:用户清理 Downloads 时把 GT 删进了回收站 —— 已抢救回 `gt\` 并入 git。
`correct chord.mid`(202 事件)没能找回;`correct vocal melody.mid` 内容 = GT 的 Vocal 轨(154 音符),无损失。
**评测一律用 `gt\S.A.T.E.L.L.I.T.E.mid`,别再引用 Downloads 路径。**

⚠️ 输出文件夹里的 `wrong chords.mid` / `wrong vocal.mid` 是**用户重命名的早版(有时间拉伸 bug)输出**,不代表当前质量,别拿它们评估。

---

## 当前水平(对上述基准实测)

| 项目 | 数字 | 判断 |
|---|---|---|
| BPM | 149.995 / 真值 150.00 | ✅ 已解决 |
| 调性 | Ab Major,正确 | ✅ |
| 和弦内容吻合 | **77.5%**(vs correct chord.mid,07-31 钢琴证据架构后;曾 67%)| ⚠️ 仍是最大短板,user 最在意 |
| 和弦 root | **34.1%**(chart 口径,曾 21%);top1+备选内 66.6% | ⚠️ 修正入口=备选 chip |
| 和弦换弦边界 | F=0.43,段数 159(真实 99;曾 238)| ⚠️ 好转但仍过分段 |
| 人声旋律 | F1 0.40(召回 48.1% / 精确 34.6%),**八度 74/74 全对** | ⚠️ 草稿级 |
| 复音草稿覆盖 | Lead 61% / Arp 81%(故意过检供删) | ✅ 可用 |
| 钢琴引擎 (--piano) | vs GT Piano 召回 45%(电子乐属域外) | ℹ️ 真钢琴素材才是主场 |

---

## ❌ 已证伪(别重做,详见 RESEARCH.md)

1. **合成器 Lead 自动提取** —— 五路实验(skyline / basic-pitch PG+Viterbi / CQT 八度梳+Viterbi / 平稳性抑制 / vocals 轨与全混音),最好 31.5%。**根因是表示层**:GT lead 音高在后验图里中位排名第 8,被 supersaw 墙掩蔽。公开社区(UVR/MSST/MVSEP)**没有器乐 lead 分离模型**,全是人声向。→ 只能等社区出模型
2. **htdemucs_6s 钢琴轨 → 和弦** —— 合成钢琴音色分不出来,root 仅 7%
3. **人声混进和声 chroma** —— 有害,已关(`--chroma-vocals` 默认 0)
4. **调外音过滤 (`--lines-scale-snap`)** —— 无效,草稿 98% 本来在调内(其他曲风可能有用,保留为选项)
5. **按力度裁剪复音草稿** —— lead 天生低置信,砍一半音符会把覆盖从 61% 打到 43%。→ 不预裁,交给用户在 DAW 拉力度线

---

## 🔧 待攻关(按价值)

1. **和弦内容 57% → 更高**(最痛)。已知:过分段(精确率 33%),换弦代价目前 3.5。未试方向:和弦模板先验按调性加权、段落级重打分、beat-sync 分辨率
2. **唱句 vs vocal chops 区分** —— 人声轨里的切片采样在声学上就是人声,当前靠段落能量门控只能压住一部分
3. 变拍支持(ChordHUD 的 meterMap 已支持,管线还没利用)
4. 跟踪社区 lead/melody 分离模型,一出就接入

---

## 已安装的外部工具

| 工具 | 位置 | 用途 |
|---|---|---|
| NeuralNote v1.1.0 | `C:\Program Files (x86)\NeuralNote\` + VST3 + 桌面快捷方式 | 交互式补扒难段(拖 stems 进去)。**注意:内核=basic-pitch,和我们同模型,救不了 lead** |
| Melodfy | `K:\DEV Tools\Melodfy\Melodfy\Melodfy.exe` + 桌面快捷方式 | ByteDance 钢琴模型 GUI。其 ONNX 模型已 vendored 进管线(`autoscribe/melodfy_vendor/`, MIT) |

---

## 用户沟通要点

- **用户不写代码** —— 别甩命令行,一切以桌面「拖歌扒谱」为准,解释要用大白话
- 用户明确说过:**和弦名字的记法约定不重要,内容对才重要**
- 用户要求:旋律**必须对齐节拍网格**(已做:硬吸附 16 分 ∪ 八分三连)
- 用户要求:**不止人声,Lead/Arp 也要**(现状:lines.mid 复音草稿供 DAW 删修 = 当前技术上限)
- 用户方针:**持续吸收开源来提升工具,慢慢来** —— 每次吸收记进 RESEARCH.md
- **Pending**:用户尚未重听修复后的输出(早版有时间拉伸 bug,他听的是那个)。等他反馈"新版最刺耳的前三个问题"再定优先级

---

## 提交历史速览

```
da51c76  用户 correct 参照驱动:和声节奏 + 人声门控 + Melodfy 集成
cc1381d  拖放启动器(给非命令行用户)
53d7283  Lead 提取五路证伪研究
fb82cfd  吸收 NeuralNote/Melodfy + RESEARCH.md
f6911c7  硬网格量化 + 多线 lines.mid
ebf834e  GT 驱动的第一轮精度攻坚
5f73778  管线初版
```
