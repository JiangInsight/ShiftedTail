@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
set SRC=%~1
set OUT=%~2
if "%OUT%"=="" set OUT=%~n1.exe
cl /nologo /O2 /Oi /GL /std:c++20 /EHsc /openmp:llvm /DNDEBUG /W3 "%SRC%" /Fe:"%OUT%" /link /LTCG /STACK:268435456
endlocal
