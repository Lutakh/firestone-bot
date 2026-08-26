; ServerSwitcher.ahk


ServerSwitcher(){
	ControlFocus,, ahk_exe Firestone.exe
	Send, !{Tab}
    Sleep, 1000
    WinActivate, ahk_exe Firestone.exe
	; opens settings
	Mousemove, 1862, 78
	Sleep, 1000
	Click
	Sleep, 1500
	; opens switch server
	ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\SwitchServer.png
	if (ErrorLevel = 0){
		Mousemove, X, Y
		Sleep, 1000
		Click
		Sleep, 1500
	}
	
	; opens Your Servers list
	ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\Your_Servers.png
	if (ErrorLevel = 0){
		Mousemove, X, Y
		Sleep, 1000
		Click
		Sleep, 1500
	}
	global CurrentServer, OtherServer

	; CurrentServer is informational; OtherServer is the target.
	serverNumber := OtherServer

	TrayTip, Server, Switching from server %CurrentServer% to server %serverNumber%, 1, 1
	ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\%serverNumber%.png
	if (ErrorLevel = 0){
		MouseMove, X, Y
		Sleep, 1000
		Click
		Sleep, 1500

		; The switch succeeded, so the two roles are reversed for the next cycle.
		tempServer := CurrentServer
		CurrentServer := OtherServer
		OtherServer := tempServer

		; Keep the GUI and settings.ini synchronized.
		GuiControl, ChooseString, CurrentServer, %CurrentServer%
		GuiControl, ChooseString, OtherServer, %OtherServer%
		SaveSettings()
	} else {
		MsgBox, Could not find the image for server %serverNumber%.
		return
	}
	
	; confirm server switch
	ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\Confirm.png
	if (ErrorLevel = 0){
		Mousemove, X, Y
		Sleep, 1000
		Click
	}
	
	
	; closing offline page and current events
	Sleep, 8000
	Mousemove, 1829, 776
	Sleep, 1000
	Click
	Sleep, 1000
	Click
	Sleep, 1000
	Click
	Sleep, 1500

	PixelSearch, X, Y, 626, 493, 630, 493, 0xF3DFC6, 2, Fast RGB
	if (ErrorLevel = 0){
		; close firestone
		Process, Close, Firestone.exe
        Sleep, 15000
		; open firestone
		Run, explorer.exe steam://rungameid/1013320
		Sleep, 15000
		ImageSearch, ErrorX, ErrorY, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\SteamAuthError.png
        If (ErrorLevel = 0) {
            authErrorFound := true
        }
	}
	
	If (authErrorFound) {

		SendHeartbeat("Steam authentication error detected. Restarting Steam.", false, true)

		; Close Firestone
		Process, Close, Firestone.exe
		Sleep, 5000

		; Close Steam
		Process, Close, steam.exe
		Sleep, 10000

		; Start Steam again
		Run, steam://open/main
		Sleep, 15000

		; Launch Firestone again
		Run, explorer.exe steam://rungameid/1013320

		Sleep, 15000
	}
}