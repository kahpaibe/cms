

setlocal
set "NEWFOLDER=new"

REM Create the new folder
mkdir "%~dp0%NEWFOLDER%"

REM Copy content
copy "%~dp0c83\cms_C83.py" "%~dp0%NEWFOLDER%\cms_C83.py"
copy "%~dp0c83\cookies.json" "%~dp0%NEWFOLDER%\cookies.json"
copy "%~dp0c83\db_structs.py" "%~dp0%NEWFOLDER%\db_structs.py"


REM Call the elevated linking script
call "%~dp0new_elevated.bat" "%NEWFOLDER%"

endlocal
