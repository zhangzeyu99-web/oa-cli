@echo off
rem OA Report wrapper
where python >nul 2>&1 && goto :found
set "PATH=%USERPROFILE%\AppData\Local\Programs\Python\Python314;%USERPROFILE%\AppData\Local\Programs\Python\Python314\Scripts;%PATH%"
:found
set "PYTHONIOENCODING=utf-8"

oa report --config "%USERPROFILE%\.openclaw\workspace\my-analytics\config.yaml" %*
