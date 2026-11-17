@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
set "CUDA_PATH=%~dp0..\..\tools\cuda13.1"
set "PATH=%CUDA_PATH%\bin;%CUDA_PATH%\bin\x64;%PATH%"
cd /d "%~dp0"
"%CUDA_PATH%\bin\nvcc.exe" -allow-unsupported-compiler -D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH -O3 -std=c++17 -arch=sm_120 -rdc=true -Xcompiler "/O2,/utf-8,/openmp,/EHsc" kernel.cu graph_gpu.cu uco.cu refactor.cu global_buffer.cu partitioned_buffer.cu -o gatd.exe
