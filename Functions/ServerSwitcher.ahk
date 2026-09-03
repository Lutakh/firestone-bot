; ServerSwitcher.ahk


ServerSwitcher(){
	global CurrentServer, OtherServer

	; CurrentServer is informational; OtherServer is the target.
	serverNumber := OtherServer
	
	; --------------------------------------------------------------------------
    ; Open settings
    ; --------------------------------------------------------------------------
    MouseMove, 1862, 78
    Sleep, 1000
    Click
    Sleep, 1500

    ; --------------------------------------------------------------------------
    ; Find and open Switch Server
    ; Retry because Firestone may take longer to render after running for hours.
    ; --------------------------------------------------------------------------
	
	switchServerFound := false

    Loop, 5
    {
        ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\SwitchServer.png

        if (ErrorLevel = 0)
        {
            switchServerFound := true
            break
        }

        Sleep, 2000
    }

    if (!switchServerFound)
    {
        TrayTip, Could not find Switch Server after 5 attempts. Server switch aborted., 1, 1
        return
    }
	
	MouseMove, X, Y
    Sleep, 1000
    Click
    Sleep, 1500
	
    ; --------------------------------------------------------------------------
    ; Find and open Your Servers
    ; --------------------------------------------------------------------------
    yourServersFound := false

    Loop, 5
    {
        ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\Your_Servers.png

        if (ErrorLevel = 0)
        {
            yourServersFound := true
            break
        }

        Sleep, 2000
    }

    if (!yourServersFound)
    {
        TrayTip, Could not find Your Servers after 5 attempts. Server switch aborted., 1, 1
        return
    }

    MouseMove, X, Y
    Sleep, 1000
    Click
    Sleep, 1500

	TrayTip, Server, Switching from server %CurrentServer% to server %serverNumber%, 1, 1
	
	; --------------------------------------------------------------------------
    ; Find the target server
    ; Retry several times in case the server list is still loading.
    ; --------------------------------------------------------------------------
	serverFound := false

    Loop, 5
    {
        ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\%serverNumber%.png

        if (ErrorLevel = 0)
        {
            serverFound := true
            break
        }

        Sleep, 2000
    }

    if (!serverFound)
    {
        TrayTip, Could not find the image for server %serverNumber% after 5 attempts. Server switch aborted., 1, 1
        return
    }

    MouseMove, X, Y
    Sleep, 1000
    Click
    Sleep, 1500
	
	; confirm server switch
	confirmFound := false

    Loop, 8
    {
        ImageSearch, X, Y, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\Servers\Confirm.png

        if (ErrorLevel = 0)
        {
            confirmFound := true
            break
        }

        Sleep, 2000
    }

    if (!confirmFound)
    {
        TrayTip, Could not confirm the server switch to server %serverNumber%. The server values were NOT swapped., 1, 1
        return
    }

    MouseMove, X, Y
    Sleep, 1000
    Click
    Sleep, 3000
	
	tempServer := CurrentServer
    CurrentServer := OtherServer
    OtherServer := tempServer

    GuiControl, ChooseString, CurrentServer, %CurrentServer%
    GuiControl, ChooseString, OtherServer, %OtherServer%
    SaveSettings()

    TrayTip, Server, Successfully switched to server %CurrentServer%, 2, 1
	
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

	PixelSearch, X, Y, 770, 420, 780, 430, 0xF4E0C6, 2, Fast RGB
	if (ErrorLevel = 0){
		; close firestone
		TrayTip, Server, Closing firestone, 1, 1
		Process, Close, Firestone.exe
        Sleep, 15000
		; open firestone
		TrayTip, Server, Opening firestone, 1, 1
		Run, explorer.exe steam://rungameid/1013320
		Sleep, 15000
		ImageSearch, ErrorX, ErrorY, 0, 0, A_ScreenWidth, A_ScreenHeight, *20 Images\SteamAuthError.png
        If (ErrorLevel = 0) {
            authErrorFound := true
        }
	}	else {
		TrayTip, Server, Pixel not found, 1, 1
	}
	
	If (authErrorFound) {

		TrayTip, Server, Steam authentication error detected. Restarting Steam., 2, 1 

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