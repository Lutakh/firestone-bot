; MysteryBox.ahk

#Include Functions\subFunctions\BigClose.ahk

MysteryBox(){
    ; Scroll to the bottom to look for Mystery Box
    MouseMove, 1720, 608
    MsgBox, , Mystery Box, Scrolling to ensure bottom gifts are visible, 1.5
    Loop, 5{
        Send, {WheelDown}
        Sleep, 200
    }
    PixelSearch, FoundX, FoundY, 1543, 307, 1887, 905, 0xF78BF1, 1, Fast RGB
    If (ErrorLevel=0){
        MouseMove, FoundX, FoundY
        Sleep, 1000
        Click
        Sleep, 1000
;        ; click 1
;        MouseMove, 904, 724
;        Sleep, 1000
;        Click
;        Sleep, 10000 ; long delay in case 10 or more chests are opened

        ; click 1
        MouseMove, 950, 892
        Sleep, 1000
        Click
        Sleep, 10000 ; long delay in case 10 or more chests are opened

        Loop, 5{
            PixelSearch, X, Y, 1773, 932, 1831, 976, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0){
                ; click 50 or however many are left.
                MouseMove, 1797, 959
                Sleep, 1000
                Click
                Sleep, 10000 ; long delay in case 10 or more chests are opened
            }
            Sleep, 100 ; Small delay in case there is no button.
        }
        BigClose()
        ; failsafe in case big close opens options
        MouseMove, 59, 181
        Sleep, 1000
        Click
        Sleep, 1000
    }
}