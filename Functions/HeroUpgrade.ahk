; HeroUpgrade.ahk

#Include Functions\subFunctions\BigClose.ahk
#Include Functions\subFunctions\MainMenu.ahk

; Loop for upgrade until we dont have upgrade available
ClickHeroIfPixelFound(x1, y1, x2, y2, color, clickX, clickY, clickCount := 20)
{
    MouseMove, %x1%, %y1%
    Sleep, 300
    loop
    {
        PixelSearch, X, Y, x1, y1, x2, y2, color, 3, Fast RGB
        if (ErrorLevel = 0){
            ; Pixel found -> click
            SendHeartbeat("HeroUpgrade: found pixel", false, true)
            MouseClick, Left, clickX, clickY, 1, 0
            Sleep, 300  ; wait between clicks
        } else {
            break
        }
    }
}

; function that upgrades heros
HeroUpgrade(){
    ControlFocus,, ahk_exe Firestone.exe

    ; Fetch GUI settings locally
    GuiControlGet, NoHeroVal, , NoHero
    if (NoHeroVal = 1)
        Return

    ; Load specific upgrade preferences
    GuiControlGet, UpgradeSpecial, , UpgradeSpecial
    GuiControlGet, UpgradeGuardian, , UpgradeGuardian
    GuiControlGet, UpgradeH1, , UpgradeH1
    GuiControlGet, UpgradeH2, , UpgradeH2
    GuiControlGet, UpgradeH3, , UpgradeH3
    GuiControlGet, UpgradeH4, , UpgradeH4
    GuiControlGet, UpgradeH5, , UpgradeH5
    GuiControlGet, NextMilestoneVal, , NextMilestone

    ; open upgrade menu
    MsgBox, , Hero Upgrades, Opening Hero Upgrade Menu, 2
    Send, U
    Sleep, 1500

    ; Check if Next Milestone Daily Quests is checked
    If (NextMilestoneVal = 1)
    {
        ; Set to Next Milestone
        MaxTries := 10
        Count := 0
        Loop
        {
            PixelSearch, X, Y, 1500, 975, 1504, 985, 0x542710, 3, Fast RGB
            if (ErrorLevel = 0)
            {
                ; Found the toggle button color indicating we are NOT on max/milestone yet?
                ; Or clicking to toggle. Based on your code, this clicks until satisfied.
                MouseClick, Left, 1599, 951, 1, 0
                Sleep, 300
                break
            }
            ; Try clicking to switch mode
            MouseClick, Left, 1599, 951, 1, 0
            Sleep, 300
            Count++
            if (Count >= MaxTries)
            {
                MsgBox, , Hero Upgrades, Failed to find pixel after %Count% tries., 2
                break
            }
        }

        ; --- Special Upgrade ---
        If (UpgradeSpecial = 1)
            ClickHeroIfPixelFound(1874, 207, 1889, 249, 0x16BC15, 1670, 205)

        ; --- Heroes upgrades (from 5th to 1st) ---
        If (UpgradeH5 = 1)
            ClickHeroIfPixelFound(1868, 880, 1885, 912, 0x16BC15, 1670, 873)  ; 5th hero
        If (UpgradeH4 = 1)
            ClickHeroIfPixelFound(1864, 770, 1889, 802, 0x16BC15, 1670, 772)  ; 4th hero
        If (UpgradeH3 = 1)
            ClickHeroIfPixelFound(1866, 654, 1889, 693, 0x16BC15, 1670, 650)  ; 3rd hero
        If (UpgradeH2 = 1)
            ClickHeroIfPixelFound(1866, 545, 1885, 584, 0x16BC15, 1670, 539)  ; 2nd hero
        If (UpgradeH1 = 1)
            ClickHeroIfPixelFound(1862, 434, 1888, 469, 0x16BC15, 1670, 427)  ; 1st hero

        ; --- Guardian Upgrade ---
        If (UpgradeGuardian = 1)
            ClickHeroIfPixelFound(1869, 319, 1890, 352, 0x16BC15, 1670, 317)

    } else {
        ; --- Standard Single Check Mode ---

        ; check special upgrade
        If (UpgradeSpecial = 1) {
            PixelSearch, X, Y, 1874, 207, 1889, 249, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0 ){
                MouseMove, 1670, 205
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }

        ; check 5th hero
        If (UpgradeH5 = 1) {
            PixelSearch, X, Y, 1868, 880, 1885, 912, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0 ){
                MouseMove, 1670, 873
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }

        ; check 4th hero
        If (UpgradeH4 = 1) {
            PixelSearch, X, Y, 1864, 770, 1889, 802, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0 ){
                MouseMove, 1670, 772
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }

        ; check 3rd hero
        If (UpgradeH3 = 1) {
            PixelSearch, X, Y, 1866, 654, 1889, 693, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0 ){
                MouseMove, 1670, 650
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }

        ; check 2nd hero
        If (UpgradeH2 = 1) {
            PixelSearch, X, Y, 1866, 545, 1885, 584, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0 ){
                MouseMove, 1670, 539
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }

        ; check 1st hero
        If (UpgradeH1 = 1) {
            PixelSearch, X, Y, 1862, 434, 1888, 469, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0 ){
                MouseMove, 1670, 427
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }

        ; check guardian
        If (UpgradeGuardian = 1) {
            PixelSearch, X, Y, 1869, 319, 1890, 352, 0x0AA008, 3, Fast RGB
            If (ErrorLevel = 0 ){
                MouseMove, 1670, 317
                Sleep, 1000
                Click
                Sleep, 1000
            }
        }
    }
    BigClose()
}