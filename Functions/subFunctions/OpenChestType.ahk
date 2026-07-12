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
        PixelSearch, X, Y, 1200, 850, 1313, 850, 0x0AA008, 3, Fast RGB
        If (ErrorLevel = 0){
            ; click 50/max
            MouseMove, 1209, 812
        } Else {
            ; click 1/10
            MouseMove, 914, 812
        }
        Sleep, 1000
        Click
        Sleep, 10000 ; long delay in case 10 or more chests are opened

        ; clicks equip or space it should be
        MouseMove, 962, 850
        Sleep, 1000
        Click
        Sleep, 1000

        Loop, 5{
            PixelSearch, X, Y, 1773, 932, 1831, 976, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0){
                ; click 50 or however many are left.
                MouseMove, 1797, 959
                Sleep, 1000
                Click
                Sleep, 10000 ; long delay in case 10 or more chests are opened

                ; clicks equip or space it should be
                MouseMove, 962, 850
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }

        BigClose()
        ; failsafe in case big close opens options
        MouseMove, 59, 181
        Sleep, 1000
        Click
        Sleep, 1000
    }
}