@echo off
chcp 65001 >nul
title sheet-to-midi
rem 把五线谱截图 (png/jpg) 拖到本图标上 → 同目录生成 .mid (以及 .musicxml 中间文件)
set V=K:\Claude Projects\!!!ChordHUD\omr\venv
if "%~1"=="" (
  echo 用法: 把五线谱截图拖到这个图标上, 不要双击。
  pause
  exit /b
)
set /p TS=拍号: 直接回车=按谱子上的, 或输入正确拍号如 4/4 :
echo 正在识别五线谱: %~nx1  (每页约 15-30 秒)
"%V%\Scripts\homr.exe" "%~1"
"%V%\Scripts\python.exe" "K:\Claude Projects\!!!ChordHUD\omr\xml2mid.py" "%~1" %TS%
echo.
echo 提示: MIDI 速度默认 120, 请在 DAW 里改成真实 BPM; 三连音/变拍可能被简化。
pause
