; ScarabToken.ahk

#Include Functions\subFunctions\BigClose.ahk
#Include Functions\subFunctions\MainMenu.ahk

lastExecutionTimeShop := 0

ScarabToken(){
    MsgBox, , Scarab's Token, Claiming Scarab's Token, 2
    ControlFocus,, ahk_exe Firestone.exe
    ; open Tavern
    MouseMove, 719, 957
    Sleep, 1000
    Click
    Sleep, 1000
    PixelSearch, X, Y, 1275, 320, 1310, 360, 0xF40000, 3, Fast RGB
    If (ErrorLevel = 0){
        ; Open Scarab's Game
        MouseMove, 1108, 500
        Sleep, 1000
        Click
        Sleep, 1000

        PixelSearch, X, Y, 1860, 667, 1900, 705, 0xF40000, 3, Fast RGB
        If (ErrorLevel = 0){
            MouseMove, 1809, 722
            Sleep, 1000
            Click
            Sleep, 1500
            ; claim Pharao's Token
            MouseMove, 685, 763
            Sleep, 1000
            Click
            Sleep, 1000

            BigClose()
        }
    }
    BigClose()
}
