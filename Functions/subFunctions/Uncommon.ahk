; Uncommon.ahk

#Include Functions\subFunctions\BigClose.ahk

Uncommon(){
    PixelSearch, FoundX, FoundY, 1543, 307, 1887, 905, 0xB54424, 1, Fast RGB
    If (ErrorLevel=0){
        MouseMove, FoundX, FoundY
        Sleep, 1000
        Click
        Sleep, 1000
        ; click 1
        MouseMove, 914, 812
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
            }
            Sleep, 100 ; Small delay in case there is no button.

            ; clicks equip or space it should be
            MouseMove, 962, 850
            Sleep, 1000
            Click
            Sleep, 1000
        }

        BigClose()
        ; failsafe in case big close opens options
        MouseMove, 59, 181
        Sleep, 1000
        Click
        Sleep, 1000
    }
}