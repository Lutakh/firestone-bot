; OpenChestType.ahk

#Include Functions\subFunctions\BigClose.ahk

OpenChestType(colorHex, colorDistance := 2){
;PixelSearch, FoundX, FoundY, 1543, 307, 1887, 905, colorHex, colorDistance, Fast RGB
;if (ErrorLevel=0) {
;    MouseMove, FoundX, FoundY
;    Sleep, 1000
;    return
;}
    PixelSearch, FoundX, FoundY, 1543, 307, 1887, 905, colorHex, colorDistance, Fast RGB
    If (ErrorLevel=0){
        MouseMove, FoundX, FoundY
        Sleep, 1000
        Click
        Sleep, 1000
        ; Check for open 11-50 button
        PixelSearch, X, Y, 1200, 773, 1300, 850, 0x0AA008, 1, Fast RGB
        If (ErrorLevel = 0){
            ; click 50/max
            MouseMove, 1209, 812
        } Else {
            ; Check for open 2-10 button
            PixelSearch, X, Y, 1090, 773, 1173, 850, 0x0AA008, 1, Fast RGB
            If (ErrorLevel = 0){
                ; click 2-10
                MouseMove, 1089, 812
            } Else {
                ; Check for open 1 button
                PixelSearch, X, Y, 860, 773, 1055, 850, 0x0AA008, 1, Fast RGB
                If (ErrorLevel = 0){
                    ; click 1/10
                    MouseMove, 914, 812
                } Else {
                    Goto, NoOpenButton
                }
            }
        }
        Sleep, 1000
        ; To test, comment out the following two lines.
        Click
        Sleep, 10000 ; long delay in case 10 or more chests are opened

        ; clicks equip or space it should be
        PixelSearch, X, Y, 860, 860, 1084, 892, 0x0AA008, 1, Fast RGB
        If (ErrorLevel = 0){
            MouseMove, 964, 880
            Sleep, 1000
            Click
            Sleep, 1000
        }

        Loop, 5{
            PixelSearch, X, Y, 1773, 932, 1831, 976, 0x0AA008, 1, Fast RGB
            If (ErrorLevel = 0){
                ; click 50 or however many are left.
                MouseMove, 1797, 959
                Sleep, 1000
                Click
                Sleep, 10000 ; long delay in case 10 or more chests are opened

                ; clicks equip or space it should be
                PixelSearch, X, Y, 860, 860, 1084, 892, 0x0AA008, 1, Fast RGB
                If (ErrorLevel = 0){
                    MouseMove, 964, 880
                    Sleep, 1000
                    Click
                    Sleep, 1000
                }
            }
        }

        Goto, ClickClose

        NoOpenButton:
        MsgBox, , Open Chests, No Open Button Available, 1.5

        ClickClose:
        BigClose()
        ; failsafe in case big close opens options
        MouseMove, 59, 181
        Sleep, 1000
        Click
        Sleep, 1000
    }
}