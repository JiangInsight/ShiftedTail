@echo off
setlocal
if defined VSCMD_VER goto compile
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCROOT=%%I"
if not defined VCROOT exit /b 1
call "%VCROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
:compile
if not defined CUDA_PATH set "CUDA_PATH=%~dp0..\..\tools\cuda13.1"
if not defined CUDA_ARCH set "CUDA_ARCH=sm_120"
set "PATH=%CUDA_PATH%\bin;%CUDA_PATH%\bin\x64;%PATH%"
cd /d "%~dp0"
"%CUDA_PATH%\bin\nvcc.exe" -allow-unsupported-compiler -D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH -O3 -std=c++17 -arch=%CUDA_ARCH% -rdc=true -Xcompiler "/O2,/utf-8,/openmp,/EHsc" kernel.cu graph_gpu.cu uco.cu refactor.cu global_buffer.cu partitioned_buffer.cu -o gatd.exe
exit /b %errorlevel%
