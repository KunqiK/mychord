@echo off
chcp 65001 >nul
title sheet-to-midi
rem 把五线谱截图 (png/jpg) 拖到本图标上 → 同目录生成 .musicxml + .mid
rem 引擎: homr (拍照级 OMR, 音高准确率实测 ~92%) + music21 转 MIDI
set V=K:\Claude Projects\!!!ChordHUD\omr\venv
echo 正在识别五线谱: %~nx1
echo (每页约 15-30 秒, 首次运行要下载 90MB 模型请耐心)
"%V%\Scripts\homr.exe" "%~1"
"%V%\Scripts\python.exe" -c "import sys,os,music21; b=os.path.splitext(sys.argv[1])[0]; music21.converter.parse(b+'.musicxml').write('midi', b+'.mid'); print('MIDI 已生成: ' + b + '.mid')" "%~1"
echo.
echo 完成! MIDI 和截图在同一个文件夹里。注意: 复杂变拍/三连音可能需要 DAW 里微调, 速度默认 120 需自己设。
pause
