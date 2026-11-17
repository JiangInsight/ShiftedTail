@echo off
setlocal
if defined VSCMD_VER goto compile
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCROOT=%%I"
if not defined VCROOT exit /b 1
call "%VCROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
:compile
set "CERT_FP="
if /I "%~nx1"=="verify_thresholds.cpp" set "CERT_FP=/fp:strict"
cl %CERT_FP% /nologo /O2 /Oi /GL /std:c++20 /EHsc /openmp:llvm /DNDEBUG /W3 "%~1" /Fe:"%~2" /link /LTCG /STACK:268435456
exit /b %errorlevel%
