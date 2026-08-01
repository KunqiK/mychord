# RESEARCH — 从开源项目吸收的技术笔记

## 首次 BTC 微调 (2026-08-01 凌晨, 40 首数据集)

- 数据: `MIDIandMUSIC\dataset\` 38 首 × 0.25s 帧标签 (99 分钟), 8 质性×12根音映射进 large_voca; 验证集 6 首固定 (近重复对不跨界)
- 训练: CPU 16 分钟跑满 50 轮 (18s/轮, batch 8, lr 1e-4, 从预训练 ckpt 起步); 17 轮后过拟合, 按验证准确率选最佳
- **成绩: 验证准确率 24.3% (预训练基线) → 28.4% (第17轮, +4.1pp / 相对+17%)**; 模型在 `btc_finetune\best.pt`
- 结论: "用户数据教模型学曲风"路线打通; 瓶颈=数据量 (99 分钟 vs BTC 原版数百小时)。飞轮: 用户每修正一首歌→数据集加厚→16 分钟重训。下一步: best.pt 接进管线做第二意见, 38 首上量化投票收益

持续更新。每条注明:来源 → 学到什么 → 我们怎么用(或为什么不用)。

## NeuralNote (DamRsn/NeuralNote, v1.1.0 已安装)

交互式 audio→MIDI:独立版 `C:\Program Files (x86)\NeuralNote\NeuralNote.exe`(桌面有快捷方式),VST3 在 `C:\Program Files\Common Files\VST3\`(FL Studio 可扫到)。内核 = basic-pitch 的 CNN 移植(RTNeural/ONNX),**和我们管线同一个模型** —— 它的价值在交互层。

### 源码要点 (Lib/)

| 文件 | 内容 | 吸收状态 |
|---|---|---|
| `Model/Notes.h/cpp` | posteriorgram→音符事件。ConvertParams 语义:**onsetThreshold=0.3 是"分割/合并音符"旋钮, frameThreshold=0.5 是"更多/更少音符"旋钮**, minNoteLength=11帧(~127ms), inferOnsets, melodiaTrick, energyThreshold=11。另有 mergeOverlappingNotesWithSamePitch / dropOverlappingPitchBends | 参数语义已对齐我们的 predict() 调用;敏感复音草稿用 onset 0.3/frame 0.2 |
| `MidiPostProcessing/NoteOptions.cpp` | **音阶吸附**:Remove 模式(删调外音)/ Snap 模式(向上/向下贴最近调内音, 方向由 pitch-bend 累计符号决定);13 种音阶;min/max 音域过滤 | Remove 模式 → `--lines-scale-snap`。实测 SATELLITE 无效(草稿 98% 本来就在调内, 误检是调内泛音), 但其他风格可能有用, 默认关 |
| `Utils/TimeQuantizeUtils.h` | 量化分度表:1/1..1/64 **含三连音分度 (1/3, 1/6, 1/12, 1/24, 1/48)** | ✅ 已吸收:quantize_note 现在在"直16分 ∪ 八分三连"里就近吸附, 三连音乐句不再被抹平 |
| quantize force 滑杆 | **部分量化**(0-100% 向网格插值)而非硬吸附 | 未做 —— 用户明确要"按节拍写谱"的硬吸附;需要"人味"时在 DAW 里做 |

### 工作流定位
NeuralNote 不替代管线,做**难段补扒**:把 `cache\<歌>\stems\vocals.wav / other.wav` 拖进去(比原曲干净得多),滑杆实时调阈值看钢琴卷帘,手动修音符,导出 MIDI。

## Melodfy (HemantKArya/Melodfy)

**ByteDance 高精度钢琴转谱模型**的 ONNX 壳(reg_onset/reg_offset/frame/**velocity** + 踏板输出 + RegressionPostProcessor,16kHz/100fps mel 输入)。

- 学到:钢琴内容有专用 SOTA 模型,**带力度和踏板**,比 basic-pitch 通用模型准得多
- 路线图:给管线加 `--engine piano`(pip `piano_transcription_inference`,torch CPU 可跑,模型 ~160MB)——用户做钢琴曲分析时启用。EDM 不适用(域外)
- 它的 UI 只是文件对话框,交互价值低于 NeuralNote

## basic-pitch (spotify/basic-pitch, 已内置)

- 我们用 ONNX 后端 (`nmp.onnx` 随 pip 包内置, Windows py3.12 无 TF 也能跑)
- `predict()` 返回的 `model_output` 里有 note/onset/**contour** 三张 posteriorgram —— 未来做多声线分离可以直接吃 contour 矩阵(比音符事件级 skyline 信息多)⭐ 候选攻关方向
- 参数实测 (SATELLITE, 对照人工 GT):默认阈值 → other 轨只回收 25% Lead;**敏感 (onset 0.3/frame 0.2/minlen 60ms) → Lead 57% / Arp 81% / Piano 68%**,代价 1 万音符过检
- 过检修剪实验:amp>0.3 砍一半音符但 Lead 覆盖 61%→43% —— **Lead 音符天生低置信度(被 supersaw 掩蔽),不能一刀切**。方案:力度=置信度写进 MIDI,DAW 里拉力度过滤线 = 任意阈值交互调

## 合成器 Lead 自动提取 — 五路实验全部证伪 (2026-07-30, GT=SATELLITE Lead 轨)

用户问"为什么扒不出 lead"。系统性实验,帧级 pitch-class 正确率(GT Lead 活跃帧):

| 方法 | 结果 | 死因 |
|---|---|---|
| skyline(事件最高音) | ~22% 音符覆盖 | 抓到的是 arp/FX 最高音 |
| basic-pitch note PG + Viterbi 追踪 | 23% | **GT 音高在后验图中位排名第 8, top1 仅 11%** — 模型看不见被 supersaw 墙埋住的 lead |
| CQT 八度梳 salience + Viterbi | **31.5%(最好)** | 表示层 top3 只 43% = oracle 天花板 |
| 平稳性抑制(减时间中值) | 21% | lead 长音也被当 pad 减掉 |
| vocals 轨 / 全混音的 PG | 排名 36 / 18 | lead 不在 vocals;全混音更糟 |

**结论:瓶颈在表示层不在算法** —— lead 埋在强相关的 supersaw 堆里,需要专门训练的分离模型。已搜证:公开社区(UVR/MSST/MVSEP)现有模型全是人声方向(karaoke/lead vocal),**没有器乐 lead 分离模型**。

### 分离模型路线第一轮实测 (2026-07-31, 同 GT, eval_lead_stem.py)

| 分离 stem + basic-pitch 敏感阈值 | 帧级最高音 pc | 帧级任意音 pc | GT 音符覆盖 | 音符数 |
|---|---|---|---|---|
| lead-synth 专模 (SDR 4.99, ep1) | 24.4% | 38.9% | 40.1% | 4619 |
| **Mega-53 synth 轨** | **30.9%** | **53.6%** | **50.3%** | **5707** |
| (对照) demucs other 复音草稿 | 22-31.5% (各法) | — | 61% | ~10000 |

读法:**Mega-53 synth 轨让"普通 basic-pitch"直接摸到了原来定制 CQT 算法的 31.5% 天花板**,且用一半音符数覆盖 50% GT —— 表示层确实被分离模型改善了,但 synth 轨里 lead/pad/arp 仍混在一起,"最高音=lead"的假设还是不成立。lead-synth 专模 (仅 1 epoch) 低于基线,当"lead 活跃段门控"可能比当音高来源更有用。✅ synth 轨草稿已集成进 lines.mid (「Synth stem draft (cleaner)」轨, commit e7ef4db)。

### SW 6轨全曲验证 (2026-07-31, 全曲 CPU 32 分钟)

| stem | 指标 (vs GT 对应轨, 同法同阈值) | 对照 |
|---|---|---|
| **piano** | **音符覆盖 62.0%** (3103 音符), 帧级任意音 62.8% | htdemucs_6s 钢琴轨召回只有 24.5% (已证伪路线) → **2.5 倍提升, 钢琴路线复活** |
| vocals | 覆盖 74.7% / 任意音 53.8% | demucs vocals 73.4% / 50.0% — **无质差, demucs 继续当默认人声源** (快 30 倍) |
| guitar | RMS = 0.0 | 这首本来就没吉他 — **模型不幻觉内容, 精度可信**; 吉他质量待用户的吉他歌实测 |

结论: SW 的价值在**乐器 stem**(钢琴/吉他), 4 轨基础分离维持 demucs 不变。钢琴素材新推荐链: `--stems 6` → `--piano --piano-stem piano` (ByteDance 引擎吃专用钢琴轨)。

**可用的半自动路径(已验证数字)**:lines.mid 复音草稿覆盖 **Lead 61% / Arp 81%**(敏感阈值,力度=置信度)→ DAW 里力度过滤 + loop 对听删修。Arp 尤其可行:模式重复,修对一遍 pattern 即可复制。

## 乐器级分离生态大调查 (2026-07-31, 10 路并行研究)

**上面 07-30 的"社区没有乐器分离模型"结论已过时** —— 这一年 roformer 社区爆发了。已全部核实在线并接入管线 (`--stems` flag, MSST 引擎, `.venv-sep` 独立环境):

| 模型 | 覆盖 | 质量证据 | 状态 |
|---|---|---|---|
| **BS-Roformer-SW 6轨** (vocals/drums/bass/**guitar**/**piano**/other) | 667MB ckpt, HF enerjazzer/BS-ROFO-SW-Fixed 镜像 (jarredou 原库已 401) | **MVSEP 排行钢琴 SDR 7.8 第一 (LALAL.AI 只有 5.05, Logic Pro 7.79); 吉他 9.05 第一**; drums 14.11 / bass 14.62 | ✅ 已接入 `--stems 6` |
| **MVSep Mega-53** (ZFTurbo 官方, 53 乐器单模型 78MB/个: synth, electric-guitar, acoustic-guitar, strings, organ, saxophone, violin, brass, kick/snare/hh/toms…) | HF noblebarkrr/BS-Roformer-MVSep-Mega-53-stems | ZFTurbo 自述低于 MVSEP 站内专用模型, draft 级 | ✅ 已接入 (任意乐器名直接 `--stems organ` 就能用) |
| **lead-synth 专用分离** (oulianov/bsroformer-lead-synth, 2026-06-24) | 163MB, epoch 1 | SDR 4.99 (草稿级) — **第一个器乐 lead 分离模型**, 直击 SATELLITE 未解难题 | ✅ 已接入 `--stems leadsynth` |
| becruily 吉他 MelBand-Roformer | 43MB, 最快 | 社区口碑, 无发表 SDR | ✅ 已接入 `--stems guitar` |
| Banquet query-based 任意乐器 (kwatcharasupat/query-bandit, MIT) | 给一段目标乐器采样当 query | ISMIR 2024: 吉他/钢琴超 HTDemucs | ⏳ 跟踪 (CPU 可行性未证) |

- **引擎**: ZFTurbo/Music-Source-Separation-Training (MIT, `inference.py --force_cpu`), 浅克隆在 `msst/` (commit e247dfe), 独立 `.venv-sep` (torch 2.5.1 CPU + numpy 2 — 和主 venv 的 numpy 1.26 钉死互不干扰)。权重不入库 (多数社区 ckpt 无明确许可), 首次使用自动从 HF 下载到 `models/sep/`
- **CPU 代价是主要税**: roformer 比 demucs 重一个量级 (demucs 50s/歌 → roformer 每模型几十分钟, 见下方实测)。缓解: 结果按歌+模型缓存、按需单乐器、num_overlap 可降
- 备选路径 (未用, 记档): elicwhite/bs-roformer-sw-6stem-onnx (MIT, fp16 336MB, 可上 onnxruntime+DirectML 吃核显)、BSRoformer.cpp (GGML q8_0, Windows 预编译)、pip audio-separator / bs-roformer-infer (更省事但模型面窄)
- GUI 侧: UVR5 半死 (2023 停更, beta 补丁可载 roformer)、MSST-WebUI 进维护模式 (AGPL)、**继任者 pymss-studio** (2026-07-29 出 Windows-CPU 包, beta) — 都不如直接用我们的 `--stems`/桌面「拆乐器」入口 + FL/NeuralNote 消费 stems
- FL Studio 自带 stem 分离 = 同款 demucs 4轨, 无增益, 跳过

## 要不要上 LLM 扒谱/分离? — 答案: 不要 (2026-07-31, 硬数据)

- 音频 LLM 在扒谱任务上是灾难级: CMI-Bench (11 个开源音频 LLM) 旋律提取 5.06 vs 监督模型 65.3, 调性 8.55 vs 74.3; PitchBench: GPT-4o-audio **单音音高识别只有 6.1%**; MUSE: Gemini 2.5 Pro 和弦识别 58.3%。2025 AMT Challenge 零 LLM 参赛, 冠军全是任务专用 encoder-decoder
- **术语澄清**: MT3/YourMT3 是"长得像 LLM 的转录 transformer" (T5 输出 MIDI token), 不是聊天 LLM — 这类才是正解且有现成权重 (pip mt3-infer, MIT, CPU 可跑, YourMT3 536MB 多乐器 → 候选下一步)
- LLM 唯一有据可查的位置: 文本 LLM 对 MIR 工具输出做和弦推理修正 (+1~2.77% MIREX) — 这个角色 Claude 已经免费在干 (report.md 低置信度清单)

## 和弦级免费升级点 (调查副产品, 未做)

- **P0 (零依赖, 直击边界 F=0.44)**: Viterbi 换弦代价改成节拍位置相关 (正拍便宜/拍中贵) + 和声距离相关 (五度圈近的便宜) — SOTA 全在用平坦代价, 我们的恒速网格是他们没有的优势; 另加段落合并滞回后处理
- P1: BTC large-voca (MIT, 12MB ckpt 在库里, torch 2.5.1 兼容) 做第二意见, 边界求交
- P2: crema 的斜杠低音技巧 — 段内 bass-chroma 后验几何平均代替逐帧 argmax
- 校准认知: 发表 SOTA 也就 maj/min WCSR 82-84%, 大词表 63-65%, 人类标注者一致率才 70 中段 — 我们域外 EDM 71.7% 和声兼容 = 已在同一水平线; **差距只在边界, 不在词表**
- 节拍: beat_this (MIT, ISMIR 2024) 可自动定强拍相位, 退役 --downbeat-shift 手动 flag (变速歌备用)

## 路线图(按价值排序)

1. **✅ 乐器级分离已接入** — leadsynth/synth 已实测 (见上); SW 6轨钢琴/吉他验证进行中
1b. **synth 轨复音草稿进 lines.mid** (实测比 other 轨干净一倍, 覆盖 50%/5707 音符 vs 61%/1万) — 当 `--stems synth` 已跑时 melody 阶段追加一条轨
2. **和弦边界 P0 补丁** (节拍位置相关换弦代价, 零依赖)
3. **mt3-infer / YourMT3** 多乐器 MIDI 草稿实验 (对 GT 打分后决定去留)
4. 每乐器专家转录: SwiftF0 (人声 F0, pip, MIT), ADTOF-pytorch (鼓), transkun (钢琴 A/B)
5. NeuralNote 式部分量化 `--quantize-strength`(需要"人味"时)
6. 变拍支持(ChordHUD meterMap 已支持,管线未利用)
7. ~~contour 矩阵多声线分离~~ — 已证伪(表示层瓶颈,见上表)
8. 跟踪: pymss-studio 出正式版、Banquet CPU 试跑、AMT-2025 冠军 MIROS 放权重、deton24 文档新模型

## 和弦攻坚第三轮: 钢琴证据 + 图表口径修正 (2026-07-31 晚, user: "和弦仍然大错特错, 最在意和弦正确")

**新评测器 `eval_chords_ref.py`** — 直接对 `gt\correct chord.mid` 打分 (这才是用户耳中的"对")。

### 三个被推翻的旧认知

1. **"0.89s 换弦"是错的图表读法**: correct chord.mid 里 ≥3 音的完整 voicing 才是和弦事件 (99 个, **真实和声节奏 1.82s/换弦**), 单音/双音是华彩填充。旧读法把填充当换弦, 导致 CHANGE_COST 被调低到 3.5 → 2.4 倍过分段。已改回 8.0 + MIN_SEG_BEATS 2.0
2. **"root-on-bass 加分"方向反了**: 用户的 root 只有 38% 在最低音上 — 贝斯通常是踏板音 (Fm7/Bb), 大加分产生 Bbm9 之类的错根读法。STAGE2_BASS_ROOT_BONUS 1.5→0.5
3. **分离 stem 做 chroma 不可行** (实测): 钢琴/synth 轨在弱段被 max 归一化放大残留噪声成假音级 (44.6s 处 C#maj9 的 chroma 全是 Bb/A 垃圾)。chroma 保持 other 轨; **钢琴轨改在标注层进入** ↓

### 有效的新架构: 钢琴音符符号证据

- `--stems 6` 跑过的歌自动启用: ByteDance 引擎转录 SW 钢琴轨 (1430 音符, 对 chart 音级精确/召回 ~76%) → chords 阶段 (a) **分段内音级权重 = 时长×力度** 代替 chroma 中位数 (钢琴真在弹时), (b) **钢琴 voicing onset 处换弦代价 ×0.5** (行为学: 用户就是照 comping 乐器扒的)
- **候选证据强度重打分** (EVIDENCE_W 6.0 / ROOT_EV_W 3.0): 旧打分只看音级在不在, 弱 bleed 音级能撑起错误候选; 新打分按模板音实际强度均值+根音强度, 杀掉"Bb 弱证据当根音"类错误
- piano→chords 依赖已进 cache.DOWNSTREAM; pev/harm 进 params

### 结果 (vs correct chart, 全部同日拿到)

| 指标 | 改前 | 改后 |
|---|---|---|
| root 正确率 | 21.2% | **35.5%** (第四轮终值) |
| 和声兼容 (音级) | 67.2% | **77.7%** |
| root 在 top1+备选 | 45.3% | **66.7%** |
| 换弦边界 F1 | 0.34 | **0.43** |
| 段数 (真值 99) | 238 | **161** |

vs GT 全和声轨 (evaluate_gt): compat 72.8%, root 31.3% — 同向。selftest 始终 16/16。

### 第四轮加时 (同晚, "想办法想办法想办法"): 21.2 → 35.5%

系统性排除后的净增益与证伪清单:

| 实验 | 结果 |
|---|---|
| synth 音符做第二证据源 (钢琴门控失败段接管) | ✅ +0.9 (drop 段被 pad 救回) |
| synth 以低权重 (0.15) 融进钢琴门控段 | ✅ +0.5 → **35.5% 终值** |
| ❌ 滞回合并 (相邻段并起来重标) | 级联合并到全曲 1 段 — 废弃 |
| ❌ 钢琴 onset 强制切分 | root 35→30 (短段丢上下文), compat/边界略升 — 留开关 |
| ❌ 覆盖惩罚 (候选没解释的在响音级扣分) | 证据集 ~25% 杂音, "全覆盖"反噬 — UNCOV_W=0 |
| ❌ 延音降权 (BLEED_FACTOR) | 踏板长音是真和声 — 1.0 中性 |
| ❌ synth 当主证据 | bucket 里 58% 是选择效应, 全局只有 24% |

**判决性测量 (最重要的认知)**:
1. **完美边界天花板 = 28.3%** (用图表自己的窗口分段) — 分段不是墙, **"音级集合→和弦名"这最后一步才是墙**
2. **候选生成缺根音**: 28/81 事件用户的 root 根本不在候选列表里 — 钢琴 stem 转录把安静的中声部音吞了, **而且吞的常是根音本身** (Fm7/Bb 的证据 = {Ab,Bb,C,Eb}, 没有 F); detect_chords 只在在场音级上生根 → F 根候选无法生成
3. GT root 在候选列表时排名: top1 仅 18/53 — 排序也弱

### 第五轮加时补充

- ✅ **候选列表加宽 (cap 8→16, `_candidates_ext`)**: top1 不变但**正确 root 进备选 66.7→72.6%** — 无根 shell 读法活到了 alt chips。缺音惩罚不能降 (1.5→1.2 就伤 top1)
- ❌ **循环传播已证伪**: 按证据轮廓余弦相似把高置信段标签传给低置信段 — 18 种配置全部低于基线 (root 35.5→30-35)。**置信度不是可靠的质量信号**, 传错的和传对的一样多。勿重做

- ❌ **transkun A/B 已证伪** (2.0.1, CPU 3.9min/曲, 已装进主 venv 可复用): 精确 84% 但召回仅 58%, **根音在场率 45% vs ByteDance 69%**, 并集≈ByteDance。**缺根问题在音频层 (SW 分离把安静中声部埋了), 不是转录引擎** — ByteDance 保留

- ❌ **BTC 第二意见已实测证伪 (投票用途)**: 大词表模型单独跑 SATELLITE = root 25.2% / 兼容 44.9% (我们 35.5/77.7), 且错误方向相同 (Dbmaj7↔Fm7 相对替代) — 投票只会强化错误侧。2019 rock/pop 训练, EDM 域外。**但基础设施已就绪且宝贵**: `btc\` 克隆 + 3 处 py3.12 补丁已打, 15 秒/曲 CPU 推理, 12MB 可训练 — **将来用户攒够 20-50 首修正歌后, 微调 BTC 学"用户的命名习惯"是最现实的 ML 路线** (相对替代陷阱正是微调能修的)

### 下轮明确方向 (按预期收益)

1. **等用户的多轨 GT 数据** (基础设施已好: gt_tracks.py 自动认轨 + evaluate_gt --auto) — 多首歌校准通用性, 攒微调数据
2. **无根 voicing 判别信号**: 候选已能生成 (cap 16), 缺的是把 Fm7 排到 Abadd9 前面的证据 — 需要低音轨迹/功能和声分析
3. 分离层再攻: SW 之外试 Mega-53 piano 头, 看谁不吞中声部
4. 攒数据后: 微调 BTC (12MB, CPU 可训) 于用户命名习惯

## 用户 correct 参照驱动的第二轮 (2026-07-30 晚)

用户提供 `correct chord.mid`(=编曲里的钢琴和弦声部, 202 个和弦事件, **平均 0.89s 换弦**)和 `correct vocal melody.mid`(154 音符, 51-68)并判"扒得很错"。诊断:

1. **用户听的 wrong 文件 = 当天早上第一版**(BPM 误判 112 + 生跟踪网格 → MIDI 时间拉伸 1.56 倍, 从解析跨度 298s vs 实际 192s 实锤)。听感灾难主因, 当天下午已修
2. **和声节奏过慢**: 换弦代价 6.0 把 0.89s 的真实和声节奏糊成 2s+ 长段 → 调回 3.5/minseg 1.0, 换弦边界召回 47%→67%
3. **htdemucs_6s 钢琴轨路线证伪**: SATELLITE 的"钢琴"是合成音色, 6s 分不出来 (音符召回 24.5%, 和弦 root 7%); piano+guitar chroma 也不优于 4-stem other
4. **人声幽灵音符 = vocal chops**(人声采样当乐器, demucs 归入 vocals 轨没错, 但不是"唱的旋律")。段落门控 (人声/混音能量比 3s 平滑 ≥0.25, 自适应下限) + 音域夹取 45-83 → F1 0.32→0.40, 精确率 21.8→34.6%, 真人声段内 P/R ≈ 60%/59%。唱句 vs 切片的声学区分是残留难题(都是人声)

**当前 vs 用户参照**: 和弦内容吻合 ~57%, 换弦边界 F 0.44; 人声 F1 0.40 (段内 0.6), 八度 100%。

## 基准记录 (Camellia S.A.T.E.L.L.I.T.E., 人工 GT, offset +2.04s)

| 指标 | 数值 |
|---|---|
| BPM | 149.995 / 真值 150.00,恒速网格锁定 |
| 和弦 root 逐字 | 34% |
| 和弦**和声兼容**(内容对) | **71.7%** |
| GT root 在 top1+备选内 | 53.7% |
| 人声旋律召回 | 45.5% |
| 复音草稿 Lead/Arp 覆盖 | 61% / 81%(过检 by design) |
