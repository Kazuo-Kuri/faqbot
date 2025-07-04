@echo off
cd /d %~dp0

echo [%date% %time%] 実行開始 >> log.txt

venv\Scripts\python.exe update_faq_json.py >> log.txt 2>&1

echo [%date% %time%] 実行終了 >> log.txt
echo. >> log.txt
