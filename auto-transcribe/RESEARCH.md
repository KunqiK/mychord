# RESEARCH — 从开源项目吸收的技术笔记

## 全自动化「假设→验证」闭环: 大调查 + 阶段0 落地 (2026-08-01)

背景: user 问"人类扒谱四步 (①调性先验 ②进行套路 ③功能推根音 ④弹奏对比验证) 能否全自动化"。6-agent workflow 调查 (1 代码勘察 + 4 网络 + 1 汇总), 完整方案清单 12 项见 plan 文件; 排名前列: BTC 双权重打分 > NNLS 谐波拟合残差 (Mauch ISMIR2010, MIREX 74→80%) > 段级 lattice 二次 Viterbi > 移调增强 > Chordonomicon 进行先验 > Claude 符号裁决 (仅裁分歧段; 先例 arXiv 2509.18700 在 80% 基线 +1~2.77%) > HookTheory 22k 段数据集 (绝对上限最大, user 已授权 yt-dlp 子集下载)。

**已调查排除 (勿重做)**: 本地 7B LLM 裁决 (MusicTheoryBench 7B≈随机, 且 20-40min/首); 音频域重合成 log-mel/MFCC 对比 (Simonetta 2022 反证, NNLS 是此思路在 chroma 域的正确实现); madmom (MSVC 编译+CC-NC 模型, 价值被本地 BTC 官方权重覆盖); crema/essentia/autochord/omnizart Windows 不可行; RNBert (fairseq Win 深坑+古典→电子双域移); Harmonix Set 无和弦标注; ChordFormer/MIREX24-25 新系统无代码; Sethares roughness 无 ACE 背书 (可半天小实验)。

**阶段0 落地 (同日): BTC 双权重后验打分器 — 首个天花板外证据源**
- 发现: 官方 large_voca 预训练权重一直就在本地 `btc\test\btc_model_large_voca.pt` (12MB, 471 首训练, in-domain root 83.5%); 我们的微调本来就从它初始化 (train.log "FRESH start from pretrained")
- 实现: `autoscribe/btc_score.py` (双 ckpt 各出 170 类逐帧 posterior → btc.npz 缓存, 特征照抄 prep_features 含分块帧钟 times); chords.py `_label_segment` 候选重打分加 `BTC_ROOT_W 2.5 ×根音边际 + BTC_QUAL_W 1.0 ×精确后验` (SFX_TO_VOCA 22→14 质性映射); cli.py 新增 btc 缓存阶段 (软失败降级), cache.py DOWNSTREAM `btc→chords`; 权重 mtime 进 params → 重训后自动失效
- **成绩 (34 首 batch_eval 同集对照): root 平均 37.2→39.6% (+2.4pp), 中位 37.2→42.1% (+4.9pp), 兼容 43.5→44.5%**; 32 首实际重跑中 23 涨/5 平/4 微跌 (最大 −1.8); selftest 16/16 不变; 代价每首 +3~10s CPU
- 移调增强 ×12 (CQT 24bins/oct → 半音=2bin 纯矩阵 roll, 训练时随机 -5..+6, 验证集不增强, -1/N 标签不动) 写进 train.py 并单元验证; run 2 从官方权重重训中 (epoch 0 基线 24.30% 与 run 1 一致)

**阶段0/1 消融全记录 (2026-08-01 下午, 34 首 batch_eval 同集, selftest 全程 16/16)**

| 轮 | 配置 | root均值 | root中位 | 兼容 | 判决 |
|---|---|---|---|---|---|
| A | 基线 | 37.2 | 37.2 | 43.5 | — |
| B | +BTC双权重(run1微调) | **39.6** | **42.1** | 44.5 | ✅ 保留 |
| C | +BTC(run2增强微调) | 39.0 | 40.9 | 44.4 | ✅ 保留 run2 |
| D | C+NNLS原始谱 | 38.8 | 41.3 | 43.4 | ❌ 中性 |
| E | C+NNLS对数压缩 | 38.8 | 42.5 | 42.0 | ❌ 中性 |
| F | C+lattice先验 W1.2 | 38.5 | 40.0 | 44.0 | ❌ 微负 |
| G | C+lattice先验 W0.5 | 38.7 | 41.1 | 44.7 | ❌ 中性偏负 |

- **B→C 之差是训练歌泄露假象**: 34 首评测歌里 28 首是微调训练歌; run1 训练损失压到 1.17 (背得更死) 在背过的歌上占虚便宜, run2 (增强, 训练损失 2.70, val 29.23% > 28.4%) 在 4 首 held-out 验证歌上与 run1 完全打平 → **对没见过的新歌 run2 = 更优, 保留 run2-epoch28 为 best.pt** (run1 归档 best_run1.pt)。教训: 微调模型的好坏只能用 held-out 判, 34 首批量分反而会骗人
- **NNLS 谐波拟合 (Mauch) 两变体证伪于当前实现**: 段中位 CQT + 受限拟合残差重排 top-8, 原始谱和 log1p 压缩谱都中性 (机制单元测试正确: 合成 Cmaj7 下真和弦残差最低)。要兑现文献 +6pp 需要 Mauch 完整前端 (调音校正/背景减除/音色适配字典) — 已降级为实验开关 (NNLS_W=0), 勿简单重试
- **Chordonomicon 进行先验证伪于本曲库**: 67.9 万歌/5054 万 bigram 蒸馏成 (8,12,8) 转移表 (`models\progressions.npz`, build_progressions.py, 榜首=属七五度圈解决/sus4回解, 统计学到的乐理完全正确), 但接进段级 lattice 后 W=1.2 −0.5pp / W=0.5 −0.3pp — **本曲库爱用非常规进行, UG 系套路先验把对的读法拽向陈词滥调**。默认关 (PROG_W=0); lattice 机制保留 (是未来 edge/node 打分器的容器); 解析陷阱: 该数据集升号写作 s (Cs=C#), 但 Dsus4 的 s 不是升号 (regex 需 s(?!us))
- **今日净战果: root 37.2 → 39.0 (+1.8pp 真实泛化口径) / 中位 +3.7pp, 全部来自 BTC 双权重投票**; 微调换代照常自动生效 (best.pt mtime 进缓存 params)
- 下一步 (按价值重排): ①HookTheory 子集微调 (user 已授权, 数据大招, 直接强化已被证明有效的 BTC 路线) ②Claude 符号裁决器 (分歧段, 订阅 headless) ③Chordino 异质第三票 ④条件高斯 p(chroma|和弦)
- **HookTheory 落料已开动 (08-01 傍晚)**: `models\hooktheory\Hooktheory.json.gz` (19MB, SHA256 验证, CC BY-NC-SA 不入 git) → `btc_finetune\prep_hooktheory.py` 转换: 17,853 段标注 → **10,847 个 youtube id / 107.6 小时和声** (clips.jsonl, 和弦已是绝对音高+精化对齐, 直接映射进 8 质性词表); pilot.txt = 按标注时长排序前 300 (10.8h = 现有数据 6.5 倍)。**坑: yt-dlp --download-sections 走 ffmpeg 会被 YouTube 节流卡死 — 整曲 bestaudio 反而快 10 倍** (3-4MB/首), 裁剪推迟到特征构建。

**HookTheory 试点全链闭环 (08-01 晚, 当天完成)**
- 下载: 300 试点 246 成 (54 首已下架, 正常损耗), 1.18GB; `--features` 建特征 246/246 零失败 (裁 [t0,t1] 标注段, 未覆盖帧=-1 不是 N)
- run3 混合训练: 32 用户歌×2 + 246 HT = 6,586 窗口 (7 倍), 137s/轮×50, ~2h; **验证 (6 首用户 held-out) 31.56% @epoch31** — 天梯: 官方 24.3 → run1 28.4 → run2 29.2 → **run3 31.6**; best.pt=run3-ep31 (run2 归档 best_run2.pt)
- **关键联动规律: 模型变强后端到端最初持平 (I 轮 39.1) — 票权还是按弱模型定的 (2.5/1.0)。加重票权扫描: 4.0/1.5→39.7, 6.0/2.0→40.0/42.3, 8.0/2.5→40.0/42.6 (平台)。定格 BTC_ROOT_W=8.0/BTC_QUAL_W=2.5。规矩: 每次重训完必须复扫票权** (btc.npz 有缓存, 每档只重跑 chords ~4min)
- **今日终盘 (34 首): root 均值 37.2→40.0 (+2.8pp), 中位 37.2→42.6 (+5.4pp), 兼容 43.5→44.9**
- 下一班: ①扩量下载 (pilot.txt 改成 1000-2000 首或全量 10.8k, 后台限速跑) ②重训+复扫票权 ③Claude 符号裁决器 (分歧段) ④Once Again 钢琴基线迭代 (user 另一优先项, F1 0.54)

**run4 + 票权渐近线 + 全自动收丹链 (08-01 深夜)**
- 扩量下载 2000 首中途被 YouTube 反爬 (Sign in to confirm 240 次) → 停车降温, sleep 加倍 (8-20s); 到手 723 首/3.13GB, 特征 723 全建
- run4 (32 用户×2 + 723 HT = 12,288 窗口, 240s/轮×50 ≈ 4.5h): **val 33.5% @ep37** — 天梯 24.3→28.4→29.2→31.6→**33.5**, 数据每翻倍 val 稳涨 ~2pp, 曲线远未饱和
- **流程自动化落地** (今日 12 轮人肉流水线的教训): train.py 加早停 (patience 12); 票权改 env > models/btc_weights.json > 默认 三级解析; `sweep_btc_weights.py` 网格扫+--apply 落盘; **`harvest.py <tag>` 一条命令 = 选最佳轮+换权重+归档+清存档+扫票权+验收** — 已实战 run4 全自动通过
- **票权渐近线**: 4/1.5→39.4, 8/2.5→39.8, 16/4.5→40.3/44.4, 24→40.5, 32/8→**40.5/44.7**, 64/16 持平 → 定格 32/8。结构性结论: **root 决策已实质移交 BTC (模板证据只剩 tie-break 和质性裁判)** — "音级证据→模板"旧体系从主引擎退役, 与"28% 天花板"判决完全自洽
- **当日最终盘 (34 首): root 均值 37.2→40.5 (+3.3pp), 中位 37.2→44.7 (+7.5pp), 兼容 43.5→44.5**
- **评测卡尺待校准**: 垫底 4 首 (Alb 5.4/AMARA 8.9/Alexandrite(1) 10.9/playable edit 13.6) offset 可疑 (playable edit 判 0.000 而原版 +1.40) — 拖累均值且掩盖真实涨幅, 下一班先做诊断; 校准会改变基准, 前后数字要分开记
- 下一班顺序: ①评测 offset 诊断 ②冷却后续下载 (脚本 sleep 已加倍) ③满 1500+ 首再 run5 (早停已生效) + harvest ④Claude 符号裁决器

**评测卡尺 v2 (08-02 凌晨): 旧卡尺一直低估 ~6pp**
- 诊断 (offset 网格扫描 vs auto): 1fle33 25.7→41.0 (+5.2s)、playable edit 25.0→38.6、Abiogenesis 真实 offset +13.9s、Aleph −3.6s — 旧 bass-agreement 扫描范围 (−2..+8) 装不下且 pyin 弱
- 修复①: evaluate_gt 加 `estimate_offset_root` (根音一致性直接扫 −6..+16, 0.25 细化) 为主对齐器 — offset 本就是评测的干扰参数, 全体歌统一适用, 版本间可比
- 修复②: gt_tracks.pick 双手钢琴抢救 — 'Piano (L)' 落在 bass (太复音) 和 harmony (太低) 之间被丢弃, 右手单线撑不起和弦真值; 和声池 ≤1 轨时把落选音高轨全部并入 (playable edit 兼容 4.5→44.7%)
- **卡尺 v2.1 基准 (同一管线, 数字不与 v1 可比): root 均值 46.3% / 中位 49.1% / 兼容 50.5%** (v1 口径同状态 = 40.5/44.7/44.5)
- 残余真差 3 首 (Alb/AMARA/Alexandrite(1) 12-14%): 全 offset 扫描也救不动, 疑音频版本/编曲不对, 属数据问题非管线问题

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
