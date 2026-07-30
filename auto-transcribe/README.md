# auto-transcribe — 扒谱自动化管线

一条命令把歌曲音频变成:**ChordHUD 可直接载入的和弦工程** + **主旋律 MIDI** + **可试听校对的 preview.wav** + **按最差优先排序的修正清单**。纯本地、纯 CPU、免费。

把 60 小时的"听写"变成 1-2 小时的"校对"。

## 用法

```
transcribe.cmd "歌曲.flac" [选项]
```

产出在 `output\<歌名>-<hash>\`:

| 文件 | 用途 |
|---|---|
| `<歌名>.chordhud.json` | ChordHUD → 📂 载入工程,时间轴/和弦/备选/音级/罗马数字全部预填 |
| `report.md` | 调性、BPM、**低置信度段清单(先听这些)** |
| `preview.wav` | 和弦垫混在原曲下 — 错和弦一听就打架;`--click` 加节拍 click(强拍高音) |
| `melody.mid` / `melody_raw.mid` | 主旋律(量化 / 未量化),导入 DAW 对格 |
| `chords.mid` | 柱式和弦(力度=置信度),DAW 里看 |

### 常用选项

```
--bpm 128                 # BPM 检测不对时手动指定(报告里会给半/双倍候选)
--key "Eb Major"          # 调性覆盖("C# Minor" 也行)
--downbeat-shift 0..3     # click 试听发现强拍相位不对时修正
--grid-zero               # 平移时间轴使 bar1=0(配合视频同裁)
--melody-source auto|vocals|other|none   # 旋律来源(默认自动判断人声)
--lead-floor C4           # 器乐 lead 的 skyline 音域下限
--model htdemucs_ft       # 更慢更细的分离(顽固歌曲用)
--click --preview-melody  # preview.wav 加 click / 旋律正弦
--force separate|beats|key|chroma|bass|chords|melody|all   # 强制重跑某阶段
```

分离结果等全部缓存(`cache\`),调参数重跑不用再等 demucs。

## 工作流

1. `transcribe.cmd "歌.flac" --click` (首次约 5-15 分钟,大头是 CPU 跑 demucs)
2. 听 `preview.wav` 开头 — click 是否踩拍、强拍(高音 click)是否在小节头;不对 → `--downbeat-shift N` 重跑(秒级,分离已缓存)
3. 读 `report.md` 低置信度清单
4. ChordHUD 载入 `.chordhud.json`,对着清单逐段听,备选和弦一键切换
5. `melody.mid` 进 DAW 校对

## 环境(重要)

- **PATH 上的 `python` 是 MSYS2 MinGW 版,装不了本管线的依赖** — 一律用 `transcribe.cmd`(内部硬编码 `.venv\Scripts\python.exe`)
- venv 用 py launcher 的官方 CPython 3.12 创建:
  ```
  py -3.12 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  .venv\Scripts\python.exe -m pip install basic-pitch==0.4.0 --no-deps
  .venv\Scripts\python.exe -m pip install mir_eval "resampy>=0.2.2,<0.4.3"
  ```
  basic-pitch 必须 `--no-deps`:它在 Windows py≥3.11 强制要 tensorflow<2.15.1(py3.12 无此版本);实际推理走 **ONNX**(onnxruntime 已在 requirements 里)
- `setuptools<81`(≥81 移除了 pkg_resources,pretty_midi 还在用)
- torch 钉在 2.5.1(2.6 改了 `torch.load` 默认值会弄坏 demucs 载权重),**不要盲目升级**
- demucs 4.0.1 没有 `demucs.api`,`autoscribe/separate.py` 直接驱动 `apply_model`
- ffmpeg:解码 mp3/m4a 用;wav/flac 不需要。找不到时会自动搜 winget 安装目录
- 首次运行联网下载 htdemucs 权重 ~80MB(之后离线)

## 验证

```
transcribe.cmd --verify-install      # 环境自检(含 basic-pitch ONNX 正弦测试)
.venv\Scripts\python.exe selftest.py # 合成回归测试:已知16小节进行→全链路→对答案
```

selftest 基线:16/16 和弦(含 G/B 斜杠、Gsus4、G7、Cmaj7)、BPM 120.00、C Major、旋律 32/32。

## 结构

```
autoscribe\
  hud_port.py    ChordHUD v17.4 逐字移植:22模板 detectChords / keyNotes 拼写引擎
  separate.py    demucs htdemucs 四轨分离 (CPU)
  beats.py       BPM/拍网格(drums轨) + 强拍相位启发式
  chroma.py      other轨 HPSS→CQT chroma(36bin)→半拍同步
  bassline.py    bass轨 pyin 根音 + 低频chroma回退
  keydetect.py   Krumhansl-Schmuckler 24调
  chords.py      ★ Viterbi分段(97态) + ChordHUD精标 + 置信度
  melody.py      basic-pitch(ONNX)/pyin + 单音化/skyline
  midi_out.py    拍网格映射写MIDI(DAW里完美对格)
  hud_json.py    ChordHUD v5工程输出(罗马数字表在文件顶部,可改口味)
  synthesize.py  numpy和弦垫/click合成 + preview混音
  report.py      report.md
  cli.py cache.py audio_io.py
```

## 评测(有标准答案 MIDI 时)

```
.venv\Scripts\python.exe evaluate_gt.py --midi GT.mid --cache cache\<slug> [--details]
```
自动用 bass 声部吻合度对齐音频↔MIDI 偏移;输出 root/质性/全名/**和声兼容**(我们的和弦音 ⊆ 实际在响的和声 = 合法读法)/root-in-alts 五级指标 + 旋律音符级 P/R。基准 (Camellia S.A.T.E.L.L.I.T.E., 人工全曲扒谱 MIDI): root 34.8%, 和声兼容 71.3%, BPM 149.995/150。

## 已知边界

- 和弦精度预期:嘈杂电子乐分离后三和弦级约 70-85%,七和弦/挂留质性更低 — 所以有备选 chip 和低置信度清单,**修正才是设计核心**
- **无根音配置 (jazz 式 pad) 的根音本质上是记法约定**:pad 只弹上层结构时 (如 Ab C Eb G / 低音 Db),Abmaj7/Db 与 Dbmaj9 都是合法读法 — 管线按"pad 定和弦名 + 斜杠标低音"约定输出;和声兼容率才是真实听感指标
- **密集电子混音里的合成器 lead 旋律提取很弱** (skyline 在 arp/pad/lead 堆叠的 other 轨上 F1≈0.1) — 人声旋律可用 (vocals 轨 recall ~50%),纯器乐主旋律目前仍需人工;这是下一个值得攻关的点
- drop/纯打击段落输出 N(无和弦),不入时间轴
- 四踩强拍相位有本质歧义 — 一定用 `--click` 听一遍
- 拍号默认 4/4(`--beats-per-bar` 可改),变拍歌曲当前只支持单一拍号(ChordHUD 的 meterMap 支持变拍,管线暂未利用)
