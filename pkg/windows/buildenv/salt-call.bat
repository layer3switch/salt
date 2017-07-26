@ echo off
:: Script for starting the Salt-Minion
:: Accepts all parameters that Salt-Minion Accepts

:: Define Variables
Set SaltDir=%~dp0
Set SaltDir=%SaltDir:~0,-1%
Set Python=%SaltDir%\bin\python.exe
Set Script=%SaltDir%\bin\Scripts\salt-call

:: Set PYTHONPATH
Set PYTHONPATH=C:\salt\bin;C:\salt\bin\Lib\site-packages

:: Launch Script
"%Python%" "%Script%" %*

