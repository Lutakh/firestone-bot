; Deaeth85 Firestone Bot.ahk

#SingleInstance Force
#Include Gui.ahk
#Include Functions\Alchemist.ahk
#Include Functions\Arena.ahk
#Include Functions\CheckMail.ahk
#Include Functions\ClaimBeer.ahk
#include Functions\Scarab.ahk
#Include Functions\ClaimEngineer.ahk
#Include Functions\ClaimEvents.ahk
#Include Functions\ClaimRituals.ahk
#Include Functions\ExoticMerchant.ahk
#Include Functions\Guardian.ahk
#Include Functions\Guild.ahk
#Include Functions\HeroUpgrade.ahk
#Include Functions\MapRedeem.ahk
#Include Functions\OpenChests.ahk
#Include Functions\Quests.ahk
#Include Functions\Research.ahk
#Include Functions\Shop.ahk
#Include Functions\SendHeartbeat.ahk
#Include Functions\subFunctions\BigClose.ahk
#Include Functions\subFunctions\GetColor.ahk
#Include Functions\subFunctions\GoMap.ahk
#Include Functions\subFunctions\MainMenu.ahk
#Include Functions\subFunctions\MapClose.ahk
#Include Functions\subFunctions\OpenTown.ahk

SetWorkingDir %A_ScriptDir%
#NoEnv
SetBatchLines, -1

global lastExecutionTimeArena := 0
global MapPoints :=

; start of main script
MainScript(){
loop:
    ControlFocus,, ahk_exe Firestone.exe
    ; do main screen sections
    SendHeartbeat("Starting Bot", false, true)
    MsgBox, , Main Menu Check, Checking to ensure we are on main screen at loop start, 2
    MainMenu()
    ControlFocus,, ahk_exe Firestone.exe
    GuiControlGet, Checked, , Events,
        If (Checked = 1){
            ClaimEvents()
        }
    ; check if Claim Quests is checked
    GuiControlGet, Checked, , Quests,
    If (Checked = 1){
        SendHeartbeat("ClaimQuests", false)
        ClaimQuests()
    }
    MsgBox, , Main Menu Check, Checking to ensure we are on main screen after claiming quests, 2
    MainMenu()
    ControlFocus,, ahk_exe Firestone.exe
    ;~ ; check if Claim Free Gift and Check-in is checked
    GuiControlGet, Checked, , Shop,
    If (Checked = 1){
        SendHeartbeat("Shop", false)
        Shop()
    }
    ; check if Check Mail is checked
    GuiControlGet, Checked, , Mail
        If (Checked = 1){
            SendHeartbeat("CheckMail", false)
            CheckMail()
        }
    ; check if Open Chests is checked
    GuiControlGet, Checked, , Chests,
        If (Checked = 1){
            SendHeartbeat("OpenChests", false)
            OpenChests()
        } Else {
        ;check if Upgrade Blessings is checked
        GuiControlGet, Checked, , Bless,
            If (Checked = 1){
                SendHeartbeat("OpenBlessChests", false)
                OpenBlessChests()
            }
        }
    ; start town section
    OpenTown()
    ; check for guardian upgrade
    SendHeartbeat("Guardian", false)
    Guardian()
    ; tavern
    SendHeartbeat("ClaimBeer", false)
    ClaimBeer()
    SendHeartbeat("Scarab", false)
    Scarab()
    ; claim rituals
    GuiControlGet, Checked, , SkipOracle,
        If (Checked = 1){
            Goto, Engineer
        }
    SendHeartbeat("ClaimRituals", false)
    ClaimRituals()
    Engineer:
    ; check if skip engineer is checked
    GuiControlGet, Checked, , NoEng,
        If (Checked = 1){
            Goto, ExoticSection
        }
    SendHeartbeat("ClaimEngineer", false)
    ClaimEngineer()
    ExoticSection:
    ; check if sell exotic is checked (sell all check is internal to sell exotic script)
    GuiControlGet, Checked, , SellEx,
        If (Checked = 1){
            SendHeartbeat("ExoticMerchant", false)
            ExoticMerchant()
    }
    ; check if do arena is checked
    GuiControlGet, Checked, , PVP,
        If (Checked = 1){
            ; get current time
            currentTimeArena := A_TickCount
            ;check if it's been 24 hours since last execution
            If (lastExecutionTimeArena <= 0 || currentTimeArena - lastExecutionTimeArena >= 6 * 60 * 60 * 1000){
                SendHeartbeat("Arena", false)
                Arena()
                lastExecutionTimeArena := currentTimeArena
            }
        }
    ; check if we are skipping alchemy
    GuiControlGet, Checked, , Alch,
        If (Checked = 1){
            Goto, ResearchStart
        } Else {
            SendHeartbeat("Alchemist", false)
            Alchemist()
        }
    ; check if we are skipping research
    ResearchStart:
    GuiControlGet, Checked, , Research,
        If (Checked = 1){
            Goto, FinishTown
        } Else {
            SendHeartbeat("GoResearch", false)
            GoResearch()
        }
    FinishTown:
    BigClose()
    GuiControlGet, Checked, , NoGuild,
    If (Checked = 1){
        Goto, MapStartUp
    }
    Guild()
    MapStartUp:
    GoMap()
    SendHeartbeat("MapRedeem", false)
    MapRedeem()
    UpgradeHero:
    GuiControlGet, Checked, , NoHero,
    If (Checked = 1){
        Goto, EndingMouseMove
    }
    SendHeartbeat("HeroUpgrade", false)
    HeroUpgrade()
    EndingMouseMove:
    SendHeartbeat("Delay ending bot", false)
    GuiControlGet, SelectedItem, ,Delay,
    If (SelectedItem="0"){
        Goto, Loop
    }
    GuiControlGet, SelectedItem, ,Delay,
    If (SelectedItem="30"){
        MouseMove, 947, 755
        Sleep, 30000
        Goto, Loop
    }
    GuiControlGet, SelectedItem, ,Delay,
    If (SelectedItem="60"){
        MouseMove, 947, 755
        Sleep, 60000
        Goto, Loop
    }
    GuiControlGet, SelectedItem, ,Delay,
    If (SelectedItem="90"){
        MouseMove, 947, 755
        Sleep, 90000
        Goto, Loop
    }
    GuiControlGet, SelectedItem, ,Delay,
    If (SelectedItem="120"){
        MouseMove, 947, 755
        Sleep, 120000
        Goto, Loop
}
}

GuiEscape:
GuiClose:
    $Esc::
    SendHeartbeat("Exit Bot", true, true)
    ExitApp