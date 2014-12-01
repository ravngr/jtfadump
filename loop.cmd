:loop

python runexp.py global.cfg pulse.cfg

ping 1.1.1.1 -n 1 -w 900000 > nul

if errorlevel 1 (
	goto loop
)
