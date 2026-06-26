Set WshShell = CreateObject("WScript.Shell")
' Run the python script silently without console window popup
WshShell.Run "uv run main.py", 0, True
