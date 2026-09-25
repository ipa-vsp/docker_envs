@ECHO OFF
REM Minimal Sphinx build script for Windows.
pushd %~dp0

if "%SPHINXBUILD%" == "" set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "" goto help
if "%1" == "strict" (
	%SPHINXBUILD% -W --keep-going -b html %SOURCEDIR% %BUILDDIR%\html %SPHINXOPTS% %O%
	goto end
)
if "%1" == "clean" (
	if exist %BUILDDIR% rmdir /s /q %BUILDDIR%
	if exist _generated rmdir /s /q _generated
	goto end
)

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%

:end
popd
