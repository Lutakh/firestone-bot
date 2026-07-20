; OpenChests.ahk

#Include Functions\subFunctions\MainMenu.ahk
#Include Functions\subFunctions\BigClose.ahk
;#Include Functions\subFunctions\Comet.ahk
;#Include Functions\subFunctions\Common.ahk
;#Include Functions\subFunctions\Cosmic.ahk
;#Include Functions\subFunctions\Diamond.ahk
;#Include Functions\subFunctions\Emerald.ahk
;#Include Functions\subFunctions\Epic.ahk
;#Include Functions\subFunctions\Galaxy.ahk
;#Include Functions\subFunctions\Golden.ahk
;#Include Functions\subFunctions\Iron.ahk
;#Include Functions\subFunctions\Legendary.ahk
;#Include Functions\subFunctions\Lunar.ahk
#Include Functions\subFunctions\MysteryBox.ahk
;#Include Functions\subFunctions\Mythic.ahk
;#Include Functions\subFunctions\Nebula.ahk
;#Include Functions\subFunctions\Opal.ahk
#Include Functions\subFunctions\OpenChestType.ahk
#Include Functions\subFunctions\OraclesGift.ahk
;#Include Functions\subFunctions\Rare.ahk
;#Include Functions\subFunctions\Solar.ahk
;#Include Functions\subFunctions\Titan.ahk
;#Include Functions\subFunctions\Uncommon.ahk
;#Include Functions\subFunctions\Wooden.ahk

OpenChests(){
    ; open bag
    MouseMove, 1581, 939
    Sleep, 1000
    Click
    Sleep, 1000
    ; click chests tab
    MouseMove, 1487, 460
    Sleep, 1000
    Click
    Sleep, 1000
    ; looks for Gear Chests
    GuiControlGet, SelectedItem, ,GearChestExclude,
    If (SelectedItem="Exclude All"){
        Goto, JewelChests
    }
    GuiControlGet, SelectedItem, ,GearChestExclude,
    If (SelectedItem="Don't Exclude Any"){
        Goto, Titan
    }
    GuiControlGet, SelectedItem, ,GearChestExclude,
    If (SelectedItem="Titan"){
        Goto, Mythic
    }
    GuiControlGet, SelectedItem, ,GearChestExclude,
    If (SelectedItem="Mythic and Higher"){
        Goto, Legendary
    }
    GuiControlGet, SelectedItem, ,GearChestExclude,
    If (SelectedItem="Legendary and Higher"){
        Goto, Epic
    }
    GuiControlGet, SelectedItem, ,GearChestExclude,
    If (SelectedItem="Epic and Higher"){
        Goto, Rare
    }    
    Titan:
    MsgBox, , Open Chests, Opening Titan Chests, 1.5
    ;Titan()
    OpenChestType("0x08BAC6", 1)
    Mythic:
    MsgBox, , Open Chests, Opening Mythic Chests, 1.5
    ;Mythic()
    OpenChestType("0xF09C15", 1)
    Legendary:
    MsgBox, , Open Chests, Opening Legendary Chests, 1.5
    ;Legendary()
    OpenChestType("0xC63A07", 1)
    Epic:
    MsgBox, , Open Chests, Opening Epic Chests, 1.5
    ;Epic()
    OpenChestType("0xB273F5", 1)
    Rare:
    MsgBox, , Open Chests, Opening Rare Chests, 1.5
    ;Rare()
    OpenChestType("0x5C98FB", 1)
    MsgBox, , Open Chests, Opening Uncommon Chests, 1.5
    ;Uncommon()
    OpenChestType("0xB54424", 1)
    MsgBox, , Open Chests, Opening Common Chests, 1.5
    ;Common()
    OpenChestType("0xC9782B", 1)

    JewelChests:
    ; look for Jewel Chests
    GuiControlGet, SelectedItem, ,JewelChestExclude,
    If (SelectedItem="Exclude All"){
        Goto, Gifts
    }
    GuiControlGet, SelectedItem, ,JewelChestExclude,
    If (SelectedItem="Don't Exclude Any"){
        Goto, Platinum
    }
    GuiControlGet, SelectedItem, ,JewelChestExclude,
    If (SelectedItem="Diamond and Higher"){
        Goto, Golden
    }
    GuiControlGet, SelectedItem, ,JewelChestExclude,
    If (SelectedItem="Opal and Higher"){
        Goto, Diamond
    }
    GuiControlGet, SelectedItem, ,JewelChestExclude,
    If (SelectedItem="Emerald and Higher"){
        Goto, Opal
    }
    GuiControlGet, SelectedItem, ,JewelChestExclude,
    If (SelectedItem="Platinum"){
        Goto, Emerald
    }
    Platinum:
    MsgBox, , Open Chests, Opening Platinum Chests, 1.5
    ;Platinum()
    OpenChestType("0xFFB2DC", 1)
    Emerald:
    MsgBox, , Open Chests, Opening Emerald Chests, 1.5
    ;Emerald()
    OpenChestType("0x7B6926", 1)
    Opal:
    MsgBox, , Open Chests, Opening Opal Chests, 1.5
    ;Opal()
    OpenChestType("0xA1F3E3", 1)
    Diamond:
    MsgBox, , Open Chests, Opening Diamond Chests, 1.5
    ;Diamond()
    OpenChestType("0xF60151", 1)
    Golden:
    MsgBox, , Open Chests, Opening Golden Chests, 1.5
    ;Golden()
    OpenChestType("0xCF7029", 1)
    MsgBox, , Open Chests, Opening Iron Chests, 1.5
    ;Iron()
    OpenChestType("0x071250", 1)
    MsgBox, , Open Chests, Opening Wooden Chests, 1.5
    ;Wooden()
    OpenChestType("0x442522", 1)
    
    Gifts:
    ; look for Gifts
    MsgBox, , Open Chests, Opening Oracle Gifts, 1.5
    OraclesGift()
    MsgBox, , Open Chests, Opening Mystery Boxes, 1.5
    MysteryBox()
    
    ;check if Upgrade Blessings is checked
    GuiControlGet, Checked, , Bless,
        If (Checked = 1){
            OpenBlessChests()
        } Else {
            Return
        }

    ;close bag
    MouseMove, 1870, 246
    Sleep, 1000
    Click
    Sleep, 1500
    Return
}

; section will trigger if Upgrade Blessings is selected and Open Chests is not
OpenBlessChests(){
    GuiControlGet, Checked, , Chests,
    If (Checked = 1){
        Goto, OpenBlessChestsNoBag
    }
    GuiControlGet, Checked, , BlessingChests,
    If (Checked = 0){
        Return
    }
    ; open bag
    MouseMove, 1581, 939
    Sleep, 1000
    Click
    Sleep, 1000
    ; click chests tab
    MouseMove, 1487, 460
    Sleep, 1000
    Click
    Sleep, 1000
    ; start here if also claiming other chests
    OpenBlessChestsNoBag:

    ; Scroll to the bottom to look for Celestial Chests
    MouseMove, 1720, 608
    MsgBox, , Open Chests, Scrolling to ensure bottom gifts are visible, 1.5
    Loop, 5{
        Send, {WheelDown}
        Sleep, 200
    }

    ; look for blessing chests
    GuiControlGet, SelectedItem, ,CelestialChestExclude,
    If (SelectedItem="Exclude All"){
        Goto, CloseBag
    }
    GuiControlGet, SelectedItem, ,CelestialChestExclude,
    If (SelectedItem="Don't Exclude Any"){
        Goto, Galaxy
    }
    GuiControlGet, SelectedItem, ,CelestialChestExclude,
    If (SelectedItem="Solar and Higher"){
        Goto, Lunar
    }
    GuiControlGet, SelectedItem, ,CelestialChestExclude,
    If (SelectedItem="Nebula and Higher"){
        Goto, Galaxy
    }
    GuiControlGet, SelectedItem, ,CelestialChestExclude,
    If (SelectedItem="Cosmic and Higher"){
        Goto, Galaxy
    }
    GuiControlGet, SelectedItem, ,CelestialChestExclude,
    If (SelectedItem="Galaxy"){
        Goto, Cosmic
    }
    Galaxy:
    MsgBox, , Open Chests, Opening Galaxy Chests, 1.5
    ;Galaxy()
    OpenChestType("0xFF82FF", 1)
    Cosmic:
    MsgBox, , Open Chests, Opening Cosmic Chests, 1.5
    ;Cosmic()
    OpenChestType("0xD326C0", 1)
    Nebula:
    MsgBox, , Open Chests, Opening Nebula Chests, 1.5
    ;Nebula()
    OpenChestType("0x5B1D84", 1)
    Solar:
    MsgBox, , Open Chests, Opening Solar Chests, 1.5
    ;Solar()
    OpenChestType("0xFEF343", 1)
    Lunar:
    MsgBox, , Open Chests, Opening Lunar Chests, 1.5
    ;Lunar()
    OpenChestType("0x00F694", 1)
    MsgBox, , Open Chests, Opening Comet Chests, 1.5
    ;Comet()
    OpenChestType("0x9F3C29", 1)
    CloseBag:
    ; close bag
    MouseMove, 1870, 246
    Sleep, 1000
    Click
    Sleep, 1000
    Return
}
