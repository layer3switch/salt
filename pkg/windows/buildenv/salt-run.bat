@ echo off
:: Script for invoking salt-run
:: Accepts all parameters that salt-run accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-run

:: Set PYTHONPATH
Set PYTHONPATH=C:\salt\bin;C:\salt\bin\Lib\site-packages

:: Launch Script
"%Python%" "%Script%" %*

