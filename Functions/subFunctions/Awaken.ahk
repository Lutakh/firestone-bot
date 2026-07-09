; Awaken.ahk

#Include Functions\subFunctions\BigClose.ahk

AwakenRun(){
    ControlFocus,, ahk_exe Firestone.exe
    ; Check for awaken heroes notification on guid screen
    PixelSearch, X, Y, 1107, 745, 1367, 944, 0xF40000, 3, Fast RGB
    If (ErrorLevel = 0){
        SendHeartbeat("AwakenRun (Improved): found notif", false, true)
        MouseMove, 1192, 847
        Sleep, 1000
        Click
        Sleep, 1500
        ; look for and click highest x#
        ;PixelSearch, X, Y, 1839, 313, 1902, 328, 0x0AA008, 3, Fast RGB
        ;If (ErrorLevel = 0){
        ;    MouseMove, 1865, 338
        ;    Sleep, 1000
        ;    Click
        ;    Sleep, 1000
        ;} Else {
        ;    PixelSearch, X, Y, 1739, 316, 1802, 330, 0x0AA008, 3, Fast RGB
        ;    If (ErrorLevel = 0){
        ;        MouseMove, 1767, 342
        ;        Sleep, 1000
        ;        Click
        ;        Sleep, 1000
        ;    } Else {
        ;        PixelSearch, X, Y, 1639, 315, 1706, 319, 0x0AA008, 3, Fast RGB
        ;        If (ErrorLevel = 0){
        ;            MouseMove, 1676, 339
        ;            Sleep, 1000
        ;            Click
        ;            Sleep, 1000
        ;        }
        ;    }
        ;}

        ; First check that the Awaken Button Is Enabled
        MouseMove, 1577, 400
        Sleep, 1000
        Click
        Sleep, 1000
        PixelSearch, X, Y, 1600, 566, 1845, 612, 0x0A9F05, 1, Fast RGB
        If (ErrorLevel = 0) {
            PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0) {
                Goto, Automatic
            }
            ; Look for x160
            PixelSearch, X, Y, 1825, 632, 1910, 692, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1872, 666
                Sleep, 1000
                Click
                Sleep, 1000
                PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
                If (ErrorLevel = 0) {
                    Goto, Automatic
                }
            }
            ; Look for x80
            PixelSearch, X, Y, 1727, 632, 1815, 692, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1772, 666
                Sleep, 1000
                Click
                Sleep, 1000
                PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
                If (ErrorLevel = 0) {
                    Goto, Automatic
                }
            }
            ; Look for x40
            PixelSearch, X, Y, 1630, 632, 1716, 692, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1679, 666
            Sleep, 1000
            Click
            Sleep, 1000
            PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0) {
                Goto, Automatic
                }
            }
            ; Look for x20
            PixelSearch, X, Y, 1535, 632, 1615, 692, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1577, 666
                Sleep, 1000
                Click
                Sleep, 1000
                PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
                If (ErrorLevel = 0) {
                    Goto, Automatic
                }
            }
            ; Look for x10
            PixelSearch, X, Y, 1825, 365, 1910, 423, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1872, 400
                Sleep, 1000
                Click
                Sleep, 1000
                PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
                If (ErrorLevel = 0) {
                    Goto, Automatic
                }
            }
            ; Look for x5
            PixelSearch, X, Y, 1727, 365, 1815, 423, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1772, 400
                Sleep, 1000
                Click
                Sleep, 1000
                PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
                If (ErrorLevel = 0) {
                    Goto, Automatic
                }
            }
            ; Look for x2
            PixelSearch, X, Y, 1630, 365, 1716, 423, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1679, 400
                Sleep, 1000
                Click
                Sleep, 1000
                PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
                If (ErrorLevel = 0) {
                    Goto, Automatic
                }
            }
            ; Look for x1
            PixelSearch, X, Y, 1535, 365, 1615, 423, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0){
                MouseMove, 1577, 400
                Sleep, 1000
                Click
                Sleep, 1000
                PixelSearch, X, Y, 1650, 955, 1900, 1015, 0x0A9F05, 1, Fast RGB
                If (ErrorLevel = 0) {
                    Goto, Automatic
                }
            }

            ; Change to auto
            Automatic:
            SendHeartbeat("AwakenRun: auto button", false, false)
            MouseMove, 1774, 993
            Sleep, 1000
            Click
            Sleep, 20000
        } Else {
            PixelSearch, X, Y, 1600, 566, 1845, 612, 0x0A9F05, 1, Fast RGB
            If (ErrorLevel = 0) {
                MouseMove, 1725, 582
                Sleep, 1000
                Click
                Sleep, 3000
            }
        }
        BigClose()
    }
}
