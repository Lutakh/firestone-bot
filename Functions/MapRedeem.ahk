; MapRedeem.ahk

#Include Functions\subFunctions\ClaimCampaign.ahk
#Include Functions\subFunctions\MapClose.ahk
#Include Functions\subFunctions\MapStart.ahk

; Function to redeem the missions
MapRedeem(){
    ControlFocus,, ahk_exe Firestone.exe
    ; check if missions can be reset for free
    MsgBox, , Mission Restart, Checking if we can reset missions for free, 1.5
    ControlFocus,, ahk_exe Firestone.exe
    PixelSearch, X, Y, 221, 878, 277, 891, 0xFCAC47, 3, Fast RGB
    If (ErrorLevel = 0){
        MouseMove, 173, 918
        MsgBox, , Mission Restart, WOOHOO! FREE BUTTON!, 1.5
        Click
        Sleep, 1000
    }
    Checks:
    ; check for active missions and their progress
    MsgBox, , Mission Check, Checking Mission Progress, 1.5
    ControlFocus,, ahk_exe Firestone.exe
    ; look for no missions
    PixelSearch, X, Y, 117, 249, 208, 334, 0x1452B4, 3, Fast RGB
    If (ErrorLevel = 0){
        MsgBox, , Mission Check, No active missions found, 1.5
        ControlFocus,, ahk_exe Firestone.exe
        Goto, Troops
    }

    ; check for already completed missions
    PixelSearch, X, Y, 207, 305, 244, 348, 0x0AA008, 3, Fast RGB
    If (ErrorLevel = 0){
        MouseMove, 162, 334
        MsgBox, , Mission Check, Mission is already complete!, 1.5
        Click
        Sleep, 1000
        MouseMove, 971, 628
        Sleep, 1000
        Click
        Sleep, 1000
        Goto, Checks
    }
    ; look for greater than 3 minutes left
    MouseMove, 162, 334
    Sleep, 1000
    Click
    Sleep, 1000
    PixelSearch, X, Y, 1427, 730, 1481, 762, 0x916A38, 0, Fast RGB
    If (ErrorLevel = 0){
        MsgBox, , Mission Check, Mission has more than 3 minutes reamining, 1.5
        MapClose()
        Goto, Troops
    } Else {
        ; check for free to complete early missions
        PixelSearch, X, Y, 1427, 730, 1481, 762, 0xF9AA47, 10, Fast RGB
        If (ErrorLevel = 0){
            MouseMove, 1365, 758
            MsgBox, , Mission Check, Mission can be completed early for free, 1.5
            Click
            Sleep, 1000
            MouseMove, 971, 628
            Sleep, 1000
            Click
            Sleep, 1000
            Goto, Checks
        }
    }
    ; check 2nd mission in case of greyed out first mission bug
    PixelSearch, X, Y, 205, 443, 242, 484, 0x0AA008, 3, Fast RGB
    If (ErrorLevel = 0){
        MsgBox, , Mission Check, Second mission is not complete, 1.5
        Goto, Troops
    }
    Troops:
    MsgBox, , Troop Check, Checking for idle troops., 1.5
    ControlFocus,, ahk_exe Firestone.exe
    ; Check if there are idle troops
    PixelSearch, X, Y, 1175, 996, 1187, 1012, 0x542710, 10, Fast RGB
        If (ErrorLevel = 0){
            MsgBox, , Troop Check, Idle troops found - starting maps, 1.5
            MapStart()
        } Else {
            MsgBox, , Troop Check, No troops found - leaving maps, 1.5
        }
        ; Reset the memory if we found the reset map mission button
    ControlFocus,, ahk_exe Firestone.exe
    Sleep, 500
    PixelSearch, X, Y, 104, 878, 300, 977, 0xED00EF, 3, Fast RGB
    If (ErrorLevel = 0){
        stateFile := "MapStartState.ini"
        ClickedPoints := ""
        SessionStart := A_Now
        IniWrite, %SessionStart%, %stateFile%, Memory, SessionStart
        IniWrite, %ClickedPoints%, %stateFile%, Memory, ClickedPoints
        global MapReset
        IniRead, MapReset, settings.ini, MissionPriority, MapReset, 0
        if (MapReset = 1){
            MouseMove, 200, 930
            MsgBox, , Reset mission, Reset map mission, 1.5
            ControlFocus,, ahk_exe Firestone.exe
            Sleep, 500
            Click
            Sleep, 1500
            MouseMove, 961, 675
            Click
            Sleep, 500
            Goto, Troops
        }
    }
    ClaimCampaign()
}
