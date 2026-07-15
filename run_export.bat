@echo off

echo === START CAD PIPELINE ===

REM 1. версия по времени
set VERSION=%date:~-4%_%time:~0,2%%time:~3,2%%time:~6,2%
set VERSION=%VERSION: =0%

echo Version: %VERSION%

REM 2. путь
set DWG=cad\dwg\project.dwg
set DXF=cad\dxf\project_%VERSION%.dxf

REM 3. копируем как "экспорт-заглушку"
REM (пока AutoCAD сам делает DXF вручную или через LISP)
copy cad\dwg\project.dwg %DXF%

REM 4. Git
git add cad/
git commit -m "DXF export %VERSION%"

echo === DONE ===
pause