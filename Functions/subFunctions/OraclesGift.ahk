; OraclesGift.ahk

#Include Functions\subFunctions\BigClose.ahk

OraclesGift(){
    ; Scroll to the bottom to look for Oracle's Gifts
    MouseMove, 1720, 608
    MsgBox, , Oracle's Gift, Scrolling to ensure bottom gifts are visible, 1.5
    Loop, 5{
        Send, {WheelDown}
        Sleep, 200
    }
    PixelSearch, FoundX, FoundY, 1543, 307, 1887, 905, 0xFFD800, 1, Fast RGB
    If (ErrorLevel=0){
        MouseMove, FoundX, FoundY
        Sleep, 1000
        Click
        Sleep, 1000

;        ; click 1
;        MouseMove, 1047, 892 ; 950
;        Sleep, 1000
;        Click
;        Sleep, 10000 ; long delay in case 10 or more chests are opened
        PixelSearch, X, Y, 1200, 862, 1300, 930, 0x0AA008, 1, Fast RGB
        If (ErrorLevel = 0){
            ; click 50/max
            MouseMove, 1209, 898
        } Else {
            ; Check for open 2-10 button
            PixelSearch, X, Y, 1090, 862, 1173, 930, 0x0AA008, 1, Fast RGB
            If (ErrorLevel = 0){
                ; click 2-10
                MouseMove, 1089, 898
            } Else {
                ; Check for open 1 button
                PixelSearch, X, Y, 860, 862, 1055, 930, 0x0AA008, 1, Fast RGB
                If (ErrorLevel = 0){
                    ; click 1/10
                    MouseMove, 914, 898
                } Else {
                    Goto, OraclesGiftClose
                }
            }
        }
        Sleep, 1000
        ; To test, comment out the following two lines.
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
            } Else {
                Goto, OraclesGiftClose
            }
            Sleep, 100 ; Small delay in case there is no button.
        }

        OraclesGiftClose:
        BigClose()
        ; failsafe in case big close opens options
        MouseMove, 59, 181
        Sleep, 1000
        Click
        Sleep, 1000
    }
}