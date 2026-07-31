# RESEARCH — 从开源项目吸收的技术笔记

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

## 路线图(按价值排序)

1. **contour 矩阵多声线分离**(basic-pitch model_output)—— 从源头解决"lead/arp 都要"
2. **`--engine piano`**(ByteDance 模型)—— 钢琴素材专线,带力度踏板
3. NeuralNote 式部分量化 `--quantize-strength`(需要"人味"时)
4. 变拍支持(ChordHUD meterMap 已支持,管线未利用)

## 基准记录 (Camellia S.A.T.E.L.L.I.T.E., 人工 GT, offset +2.04s)

| 指标 | 数值 |
|---|---|
| BPM | 149.995 / 真值 150.00,恒速网格锁定 |
| 和弦 root 逐字 | 34% |
| 和弦**和声兼容**(内容对) | **71.7%** |
| GT root 在 top1+备选内 | 53.7% |
| 人声旋律召回 | 45.5% |
| 复音草稿 Lead/Arp 覆盖 | 61% / 81%(过检 by design) |
