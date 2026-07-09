; ClickBless.ahk

; simple script to click the Bless box to save on coding
ClickBless(){
    Loop, 5{
        PixelSearch, X, Y, 1249, 763, 1498, 861, 0x0AA008, 3, Fast RGB
        If (ErrorLevel = 0){
            MouseMove, 1371, 812
            Sleep, 1000
            Click
            Sleep, 1000
        }
    }
    MouseMove, 1661, 229
    Sleep, 1000
    Click
    Sleep, 1000
}