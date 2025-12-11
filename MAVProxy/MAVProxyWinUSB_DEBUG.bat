cd ..\
python.exe -m pip install --upgrade build . --user
python.exe .\MAVProxy\mavproxy.py --console --moddebug=3 --master=127.0.0.1:14550
pause