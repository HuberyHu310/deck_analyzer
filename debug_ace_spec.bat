@echo off
setlocal
chcp 65001 >NUL
cd /d %~dp0

:: 允許以第一個參數指定關鍵字；若未提供則互動輸入，預設 ACE SPEC
set KW=%~1
if "%KW%"=="" (
  set /p KW=請輸入關鍵字 (預設: ACE SPEC)：
  if "%KW%"=="" set KW=ACE SPEC
)

echo Running ACE SPEC crawler in DEBUG (stop after step 2)...
echo keyword="%KW%"
python ace_spec_crawler.py --keyword "%KW%" --pages 1 --limit 5 --format both --debug-stop-after-step2 --keep-browser-open
echo.
echo Done. Press any key to close.
pause >NUL
