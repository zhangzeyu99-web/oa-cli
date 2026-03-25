@echo off
rem OA Collect + Heal pipeline — standardized for OpenClaw cron
where python >nul 2>&1 && goto :found
set "PATH=%USERPROFILE%\AppData\Local\Programs\Python\Python314;%USERPROFILE%\AppData\Local\Programs\Python\Python314\Scripts;%PATH%"
:found
set "PYTHONIOENCODING=utf-8"
set "OA_CONFIG=%USERPROFILE%\.openclaw\workspace\my-analytics\config.yaml"

echo [OA] Step 1: Collect
oa collect --config "%OA_CONFIG%" %*

echo [OA] Step 2: Heal (safe-only)
oa heal --config "%OA_CONFIG%" --safe-only

echo [OA] Done.
