#NoEnv
#SingleInstance, Force
SetBatchLines, -1
SetWorkingDir, %A_ScriptDir%

; ==============================================================================
; CONFIGURATION & GLOBAL VARIABLES
; ==============================================================================
Global SettingsMap := {}

; --- Common Options ---
SettingsMap["Token"] := ["CommonOptions", 0]
SettingsMap["SellEx"] := ["CommonOptions", 1]
SettingsMap["SellScrolls"] := ["CommonOptions", 0]
SettingsMap["SellNoGold"] := ["CommonOptions", 0]
SettingsMap["SellAll"] := ["CommonOptions", 1]
SettingsMap["SellNone"] := ["CommonOptions", 0]
SettingsMap["ExoticUpgrades"] := ["CommonOptions", 1]
SettingsMap["BuyEx"] := ["CommonOptions", 1]
SettingsMap["Chests"] := ["CommonOptions", 0]
SettingsMap["GearChestExclude"] := ["CommonOptions", "Mythic"]
SettingsMap["JewelChestExclude"] := ["CommonOptions", "Emerald"]
SettingsMap["Bless"] := ["CommonOptions", 1]
SettingsMap["Delay"] := ["CommonOptions", 0]
SettingsMap["Quests"] := ["CommonOptions", 0]
SettingsMap["Events"] := ["CommonOptions", 0]
SettingsMap["Mail"] := ["CommonOptions", 1]
SettingsMap["Awaken"] := ["CommonOptions", 0]
SettingsMap["Crystal"] := ["CommonOptions", 1]
SettingsMap["Chaos"] := ["CommonOptions", 1]
SettingsMap["PTree"] := ["CommonOptions", 0]
SettingsMap["GuardianTrain"] := ["CommonOptions", "Vermilion"]
SettingsMap["UpgradeSpecial"] := ["HeroOptions", 1]
SettingsMap["UpgradeGuardian"] := ["HeroOptions", 1]
SettingsMap["UpgradeH1"] := ["HeroOptions", 1]
SettingsMap["UpgradeH2"] := ["HeroOptions", 1]
SettingsMap["UpgradeH3"] := ["HeroOptions", 1]
SettingsMap["UpgradeH4"] := ["HeroOptions", 1]
SettingsMap["UpgradeH5"] := ["HeroOptions", 1]
; --- Mission Priority ---
SettingsMap["Priority1"] := ["MissionPriority", "2 Squad"]
SettingsMap["Priority2"] := ["MissionPriority", "War"]
SettingsMap["Priority3"] := ["MissionPriority", "Medium"]
SettingsMap["Priority4"] := ["MissionPriority", "Short"]
SettingsMap["Priority5"] := ["MissionPriority", "Leftover"]
SettingsMap["MapReset"] := ["MissionPriority", 0]
; --- QoL/Rare Options ---
SettingsMap["Beer"] := ["QoL/RareOptions", 0]
SettingsMap["Scarab"] := ["QoL/RareOptions", 0]
SettingsMap["NoGuild"] := ["QoL/RareOptions", 0]
SettingsMap["NoEng"] := ["QoL/RareOptions", 0]
SettingsMap["Pickaxes"] := ["QoL/RareOptions", 0]
SettingsMap["GNotif"] := ["QoL/RareOptions", 0]
SettingsMap["Alch"] := ["QoL/RareOptions", 0]
SettingsMap["Dust"] := ["QoL/RareOptions", 0]
SettingsMap["Coin"] := ["QoL/RareOptions", 0]
SettingsMap["Research"] := ["QoL/RareOptions", 0]
SettingsMap["SkipOracle"] := ["QoL/RareOptions", 0]
SettingsMap["NoHero"] := ["QoL/RareOptions", 0]
SettingsMap["NextMilestone"] := ["QoL/RareOptions", 0]
SettingsMap["DisableWarning"] := ["QoL/RareOptions", 1]

; --- Other Options ---
SettingsMap["Shop"] := ["OtherOptions", 0]
SettingsMap["DailyOracle"] := ["OtherOptions", 1]
SettingsMap["PVP"] := ["OtherOptions", 1]
SettingsMap["Liberation"] := ["OtherOptions", 1]
SettingsMap["UpgradeWM"] := ["OtherOptions", "Don't Upgrade WM's"]
SettingsMap["WMOptions"] := ["OtherOptions", "Level and Blueprints"]
SettingsMap["Blueprints"] := ["OtherOptions", "Damage and Health"]
SettingsMap["Talents450"] := ["OtherOptions", "Don't Upgrade Talents (0-450 Talent Points)"]
SettingsMap["Talents800"] := ["OtherOptions", "Don't Upgrade Talents (500+ Talent Points)"]

; --- SettingsNoGui (Maintained for code compatibility) ---
SettingsMap["DungeonQuest"] := ["SettingsNoGui", 0]

; --- Account / Discord ---
SettingsMap["DiscordID"] := ["SettingsNoGui", ""]

; --- Personal Tree ---
SettingsMap["AttDmg"] := ["PersonalTree", 0]
SettingsMap["AttHp"] := ["PersonalTree", 0]
SettingsMap["AttArm"] := ["PersonalTree", 0]
SettingsMap["Energy"] := ["PersonalTree", 0]
SettingsMap["Mana"] := ["PersonalTree", 0]
SettingsMap["Rage"] := ["PersonalTree", 0]
SettingsMap["Miner"] := ["PersonalTree", 0]
SettingsMap["Battle"] := ["PersonalTree", 0]
SettingsMap["MainAtt"] := ["PersonalTree", 0]
SettingsMap["Prest"] := ["PersonalTree", 0]
SettingsMap["Fire"] := ["PersonalTree", 0]
SettingsMap["Gold"] := ["PersonalTree", 0]
SettingsMap["Level"] := ["PersonalTree", 0]
SettingsMap["Guard"] := ["PersonalTree", 0]
SettingsMap["Fist"] := ["PersonalTree", 0]
SettingsMap["Prec"] := ["PersonalTree", 0]
SettingsMap["Magic"] := ["PersonalTree", 0]
SettingsMap["Tank"] := ["PersonalTree", 0]
SettingsMap["Damage"] := ["PersonalTree", 0]
SettingsMap["Heal"] := ["PersonalTree", 0]

; Load settings immediately
LoadSettings()

; ==============================================================================
; GUI CONSTRUCTION
; ==============================================================================
Gui, +OwnDialogs
Gui, Font, s10, Segoe UI
Gui, Color, White

; Tabs Structure
Gui, Add, Tab3, x0 y0 w960 h750, Home|General Options|Guild && Personal Tree|War Machines|Settings
; ------------------------------------------------------------------------------
; TAB 1: HOME (INSTRUCTIONS & START)
; ------------------------------------------------------------------------------
Gui, Tab, 1
    Gui, Font, s18 Bold
    Gui, Add, Text, x20 y50 w920 Center, DEAETH85'S FIRESTONE BOT v6.1.0
    Gui, Font, s10 Norm

    ; --- Instructions Group ---
    Gui, Add, GroupBox, x40 y90 w880 h500, Important Requirements & Instructions

    Gui, Font, Bold
    Gui, Add, Text, xp+20 yp+30 w840, SYSTEM & GAME SETTINGS:
    Gui, Font, Norm
    Gui, Add, Text, y+5 w840, - Use Steam or Epic version (Browser version has borders that break the bot).
    Gui, Add, Text, y+5 w840, - Monitor resolution must be 1920x1080.
    Gui, Add, Text, y+5 w840, - System DPI scaling must be set to 100`%.
    Gui, Add, Text, y+5 w840, - Taskbar must be at the bottom and NOT hidden.
    Gui, Add, Text, y+5 w840, - Game Settings (Top Right): Resolution 1920x1080, NOT Fullscreen.
    Gui, Add, Text, y+5 w840, - Game Language: Set to "English".

    Gui, Font, Bold
    Gui, Add, Text, y+20 w840, GAMEPLAY SETTINGS:
    Gui, Font, Norm
    Gui, Add, Text, y+5 w840, - Adventure Button style: Mobile or PC (NOT the new Adventure Style).
    Gui, Add, Text, y+5 w840, - Activate "Confirmation for purchase with jewels" (Safety).

    Gui, Font, Bold
    Gui, Add, Text, y+20 w840, BOT USAGE:
    Gui, Font, Norm
    Gui, Add, Text, y+5 w840, - Check all tabs and activate ONLY what you need. Deactivate the rest.
    Gui, Add, Text, y+5 w840, - After starting the game, click "Maximise" (Square icon next to X).
    Gui, Add, Text, y+5 w840, - DO NOT move or zoom the map. Leave it as it is on login. If moved, restart game.

    Gui, Font, Bold
    Gui, Add, Text, y+20 w840, TROUBLESHOOTING:
    Gui, Font, Norm
    Gui, Add, Text, y+5 w840, - If missions are not found: Ensure System Language/Fonts are English.
    Gui, Add, Text, y+0 w840,   Different system fonts can slightly change sizes and break pixel checks.

    ; --- Action Buttons ---
    Gui, Add, Button, x240 y620 w200 h60 gSaveSettings, SAVE SETTINGS
    Gui, Add, Button, x520 y620 w200 h60 gButtonStart, START BOT

; ------------------------------------------------------------------------------
; TAB 2: GENERAL OPTIONS
; ------------------------------------------------------------------------------
Gui, Tab, 2
    Gui, Font, Bold
    Gui, Add, Text, x20 y40 w900 h30 Center, GENERAL CONFIGURATION
    Gui, Font, Norm

    ; === COLUMN 1 ===
    ; --- Selling & Exotic ---
    Gui, Add, GroupBox, x20 y70 w300 h320, Selling & Exotic Merchant
    Gui, Add, Checkbox, xp+15 yp+30 vSellEx Checked%SellEx%, Open Exotic Merchant (Master)
    Gui, Add, Checkbox, y+10 vExoticUpgrades Checked%ExoticUpgrades%, Buy Exotic Upgrades
    Gui, Add, Checkbox, y+10 vBuyEx Checked%BuyEx%, Buy Exotic Chests

    Gui, Add, Text, y+20, Selling Strategy:
    Gui, Add, Radio, y+10 vSellScrolls Checked%SellScrolls%, 1. Sell ONLY Exotic Scrolls
    Gui, Add, Radio, y+10 vSellNoGold Checked%SellNoGold%, 2. Sell All But Gold Items
    Gui, Add, Radio, y+10 vSellAll Checked%SellAll%, 3. Sell All Exotic Items
    Gui, Add, Radio, y+10 vSellNone Checked%SellNone%, 4. Sell Nothing

    ; --- Other Automation ---
    Gui, Add, GroupBox, x20 y400 w300 h230, Other Automation
    Gui, Add, Checkbox, xp+15 yp+30 vNoEng Checked%NoEng%, Skip Engineer
    Gui, Add, Checkbox, y+10 vResearch Checked%Research%, Skip Research
    Gui, Add, Checkbox, y+10 vDisableWarning Checked%DisableWarning%, Disable Steam Warning

    Gui, Add, Text, y+15, Train Guardian:
    Gui, Add, DropDownList, w260 vGuardianTrain, Vermilion||Grace|Ankaa|Azhar
    if (GuardianTrain != "")
        GuiControl, ChooseString, GuardianTrain, %GuardianTrain%

    ; === COLUMN 2 ===
    ; --- Chests & Rewards ---
    Gui, Add, GroupBox, x335 y70 w300 h160, Chests & Rewards
    Gui, Add, Checkbox, xp+15 yp+30 vChests Checked%Chests%, Open Chests (General)
    Gui, Add, Text, y+10, Exclude Gear Chests:
    Gui, Add, DropDownList, w260 vGearChestExclude, Exclude All|Don't Exclude Any|Epic and Higher|Legendary and Higher|Mythic||
    if (GearChestExclude != "")
        GuiControl, ChooseString, GearChestExclude, %GearChestExclude%

    Gui, Add, Text, y+10, Exclude Jewel Chests:
    Gui, Add, DropDownList, w260 vJewelChestExclude, Exclude All|Don't Exclude Any|Diamond and Higher||Opal and Higher|Emerald
    if (JewelChestExclude != "")
        GuiControl, ChooseString, JewelChestExclude, %JewelChestExclude%

    ; --- Oracle ---
    Gui, Add, GroupBox, x335 y240 w300 h130, Oracle
    Gui, Add, Checkbox, xp+15 yp+30 vBless Checked%Bless%, Upgrade Blessings
    Gui, Add, Checkbox, y+10 vDailyOracle Checked%DailyOracle%, Claim Daily Oracle
    Gui, Add, Checkbox, y+10 vSkipOracle Checked%SkipOracle%, Skip Oracle

    ; --- Alchemy ---
    Gui, Add, GroupBox, x335 y380 w300 h120, Alchemy
    Gui, Add, Checkbox, xp+15 yp+30 vAlch Checked%Alch%, Skip Alchemy
    Gui, Add, Checkbox, y+10 vDust Checked%Dust%, Don't Use Dust in Alchemy
    Gui, Add, Checkbox, y+10 vCoin Checked%Coin%, Use Exotic Coins in Alchemy

; --- Hero Upgrades ---
    Gui, Add, GroupBox, x335 y510 w300 h200, Hero Upgrades
    Gui, Add, Checkbox, xp+15 yp+30 vNoHero Checked%NoHero%, Don't Upgrade Heroes (Master)
    Gui, Add, Checkbox, y+10 vNextMilestone Checked%NextMilestone%, Set upgrade to Next Milestone
    Gui, Add, Text, y+10, Select Upgrades to Perform:
    Gui, Add, Checkbox, y+5 vUpgradeSpecial Checked%UpgradeSpecial%, Special Upgrade
    Gui, Add, Checkbox, y+5 vUpgradeGuardian Checked%UpgradeGuardian%, Guardian

    ;Heroes list
    Gui, Add, Checkbox, y+10 vUpgradeH1 Checked%UpgradeH1%, Hero 1
    Gui, Add, Checkbox, x+30 vUpgradeH2 Checked%UpgradeH2%, Hero 2
    Gui, Add, Checkbox, x+30 vUpgradeH3 Checked%UpgradeH3%, Hero 3
    Gui, Add, Checkbox, x350 y+5 vUpgradeH4 Checked%UpgradeH4%, Hero 4
    Gui, Add, Checkbox, x+30 vUpgradeH5 Checked%UpgradeH5%, Hero 5

    ; === COLUMN 3 ===
    ; --- Daily Routine ---
    Gui, Add, GroupBox, x650 y70 w290 h220, Daily Routine
    Gui, Add, Checkbox, xp+15 yp+30 vMail Checked%Mail%, Check Mail
    Gui, Add, Checkbox, y+10 vQuests Checked%Quests%, Claim Quests
    Gui, Add, Checkbox, y+10 vEvents Checked%Events%, Claim Basic Events
    Gui, Add, Checkbox, y+10 vChaos Checked%Chaos%, Participate in Chaos Rift
    Gui, Add, Checkbox, y+10 vShop Checked%Shop%, Free Gift & Check-In

    Gui, Add, Text, y+20, End of Cycle Delay (Sec):
    Gui, Add, DropDownList, w150 vDelay, 0|30|60||90|120
    if (Delay != "")
        GuiControl, ChooseString, Delay, %Delay%

    ; --- Tavern / Scarab ---
    Gui, Add, GroupBox, x650 y300 w290 h130, Tavern / Scarab
    Gui, Add, Checkbox, xp+15 yp+30 vToken Checked%Token%, Use Tavern Tokens / Artifacts
    Gui, Add, Checkbox, y+10 vBeer Checked%Beer%, Skip Claiming Beer
    Gui, Add, Checkbox, y+10 vScarab Checked%Scarab%, Skip Using Scarab Token

; --- Mission Priority ---
    ; Augmentation de la hauteur (h) de 210 à 240 pour inclure la checkbox
    Gui, Add, GroupBox, x650 y440 w290 h240, Mission Priority Order
    PriorityList := "2 Squad|War|Medium|Short|Leftover"

    Gui, Add, Text, xp+10 yp+25, 1st:
    Gui, Add, DropDownList, x+10 w200 vPriority1, %PriorityList%
    if (Priority1 != "")
        GuiControl, ChooseString, Priority1, %Priority1%

    Gui, Add, Text, x660 y+15, 2nd:
    Gui, Add, DropDownList, x+10 w200 vPriority2, %PriorityList%
    if (Priority2 != "")
        GuiControl, ChooseString, Priority2, %Priority2%

    Gui, Add, Text, x660 y+15, 3rd:
    Gui, Add, DropDownList, x+10 w200 vPriority3, %PriorityList%
    if (Priority3 != "")
        GuiControl, ChooseString, Priority3, %Priority3%

    Gui, Add, Text, x660 y+15, 4th:
    Gui, Add, DropDownList, x+10 w200 vPriority4, %PriorityList%
    if (Priority4 != "")
        GuiControl, ChooseString, Priority4, %Priority4%

    Gui, Add, Text, x660 y+15, 5th:
    Gui, Add, DropDownList, x+10 w200 vPriority5, %PriorityList%
    if (Priority5 != "")
        GuiControl, ChooseString, Priority5, %Priority5%

    Gui, Add, Checkbox, x660 y+15 vMapReset Checked%MapReset%, Reset map cooldown with gems

; ------------------------------------------------------------------------------
; TAB 3: GUILD & PERSONAL TREE
; ------------------------------------------------------------------------------
Gui, Tab, 3
    ; --- TOP SECTION: GUILD ---
    Gui, Font, Bold
    Gui, Add, Text, x20 y40 w900 h20 Center, GUILD & HERO MANAGEMENT
    Gui, Font, Norm

    Gui, Add, GroupBox, x20 y60 w920 h130, Guild Options
    Gui, Add, Checkbox, xp+20 yp+30 vNoGuild Checked%NoGuild%, Skip Guild Functions
    Gui, Add, Checkbox, y+15 vGNotif Checked%GNotif%, Clear Guild Notifications

    Gui, Add, Checkbox, x350 y90 vPickaxes Checked%Pickaxes%, Skip Claiming Pickaxes
    Gui, Add, Checkbox, y+15 vCrystal Checked%Crystal%, Spend Pickaxes (Crystal)

    Gui, Add, Checkbox, x650 y90 vAwaken Checked%Awaken%, Awaken Heroes

    ; --- BOTTOM SECTION: PERSONAL TREE ---
    Gui, Font, Bold
    Gui, Add, Text, x20 y200 w900 h20 Center, PERSONAL TREE UPGRADES (Priority: Top to Bottom)
    Gui, Add, Checkbox, x40 y230 vPTree Checked%PTree%, > ENABLE PERSONAL TREE UPGRADES <
    Gui, Font, Norm

    ; --- Col 1: Attributes ---
    Gui, Add, GroupBox, x40 y260 w280 h380, Attributes & Heroes
    Gui, Add, Checkbox, xp+15 yp+30 vAttDmg Checked%AttDmg%, Attribute Damage
    Gui, Add, Checkbox, y+10 vAttHp Checked%AttHp%, Attribute Health
    Gui, Add, Checkbox, y+10 vAttArm Checked%AttArm%, Attribute Armor
    Gui, Add, Checkbox, y+10 vEnergy Checked%Energy%, Energy Heroes
    Gui, Add, Checkbox, y+10 vMana Checked%Mana%, Mana Heroes
    Gui, Add, Checkbox, y+10 vRage Checked%Rage%, Rage Heroes
    Gui, Add, Checkbox, y+10 vMiner Checked%Miner%, Miner
    Gui, Add, Checkbox, y+10 vMainAtt Checked%MainAtt%, All Main Attributes

    ; --- Col 2: Specializations ---
    Gui, Add, GroupBox, x340 y260 w280 h380, Specializations
    Gui, Add, Checkbox, xp+15 yp+30 vBattle Checked%Battle%, Battle Cry
    Gui, Add, Checkbox, y+10 vPrest Checked%Prest%, Prestigious
    Gui, Add, Checkbox, y+10 vFire Checked%Fire%, Firestone Effect
    Gui, Add, Checkbox, y+10 vGold Checked%Gold%, Raining Gold
    Gui, Add, Checkbox, y+10 vLevel Checked%Level%, Hero Level Up Cost
    Gui, Add, Checkbox, y+10 vGuard Checked%Guard%, Guardian
    Gui, Add, Checkbox, y+10 vFist Checked%Fist%, Fist Fight
    Gui, Add, Checkbox, y+10 vPrec Checked%Prec%, Precision

    ; --- Col 3: Classes ---
    Gui, Add, GroupBox, x640 y260 w280 h380, Classes
    Gui, Add, Checkbox, xp+15 yp+30 vMagic Checked%Magic%, Magic Spells
    Gui, Add, Checkbox, y+10 vTank Checked%Tank%, Tank Specialization
    Gui, Add, Checkbox, y+10 vDamage Checked%Damage%, Damage Specialization
    Gui, Add, Checkbox, y+10 vHeal Checked%Heal%, Healer Specialization

; ------------------------------------------------------------------------------
; TAB 4: WAR MACHINES
; ------------------------------------------------------------------------------
Gui, Tab, 4
    ; --- Misc ---
    Gui, Add, GroupBox, x40 y50 w880 h100, Battle & Miscellaneous
    Gui, Add, Checkbox, xp+15 yp+30 vPVP Checked%PVP%, Complete Arena Battles
    Gui, Add, Checkbox, x+20 vLiberation Checked%Liberation%, Complete Liberation Missions
    ; NEW CHECKBOX
    Gui, Add, Checkbox, x+20 vDungeonQuest Checked%DungeonQuest%, Complete Dungeon Missions

    ; --- War Machines ---
    Gui, Add, GroupBox, x40 y170 w880 h350, War Machines & Talents
    Gui, Add, Text, xp+15 yp+30, War Machine to Upgrade:
    Gui, Add, DropDownList, w350 vUpgradeWM, Don't Upgrade WM's||Upgrade Aegis|Upgrade Cloudfist|Upgrade Curator|Upgrade Earthshatterer|Upgrade FireCracker|Upgrade Fortress|Upgrade Goliath|Upgrade Harvester|Upgrade Hunter|Upgrade Judgement|Upgrade Sentinel|Upgrade Talos|Upgrade Thunderclap
    if (UpgradeWM != "")
        GuiControl, ChooseString, UpgradeWM, %UpgradeWM%

    Gui, Add, Text, y+20, Upgrade Mode:
    Gui, Add, DropDownList, w350 vWMOptions, Blueprints Only||Level Only|Level and Blueprints|
    if (WMOptions != "")
        GuiControl, ChooseString, WMOptions, %WMOptions%

    Gui, Add, Text, y+20, Blueprint Priority:
    Gui, Add, DropDownList, w350 vBlueprints, Upgrade All||Damage Only|Health Only|Armor Only|Damage and Health|Damage and Armor|Health and Armor
    if (Blueprints != "")
        GuiControl, ChooseString, Blueprints, %Blueprints%

    ; --- Talents ---
    Gui, Add, Text, x500 y200, Talent Options (Legacy/Specific):
    Gui, Add, DropDownList, x500 y225 w350 vTalents450, Don't Upgrade Talents (0-450 Talent Points)||
    if (Talents450 != "")
        GuiControl, ChooseString, Talents450, %Talents450%

    Gui, Add, DropDownList, x500 y280 w350 vTalents800, Don't Upgrade Talents (500+ Talent Points)||
    if (Talents800 != "")
        GuiControl, ChooseString, Talents800, %Talents800%


; ------------------------------------------------------------------------------
; TAB 5: SETTINGS
; ------------------------------------------------------------------------------
Gui, Tab, 5
    Gui, Font, Bold
    Gui, Add, Text, x20 y40 w900 h30 Center, BOT SETTINGS
    Gui, Font, Norm

    Gui, Add, GroupBox, x40 y80 w450 h120, Discord Configuration
    Gui, Add, Text, xp+20 yp+40, Discord ID:
    Gui, Add, Edit, x+10 w250 vDiscordID, %DiscordID%
    Gui, Add, Text, x60 y+10 w400,

Gui, Show, w960 h750, Firestone Bot V6.1.0
Return

; ==============================================================================
; FUNCTIONS & LABELS
; ==============================================================================

SaveSettings:
    Gui, Submit, NoHide
    SaveSettings()
    MsgBox, 64, Saved, Settings have been saved successfully!
Return

ButtonStart:
    Gui, Submit, NoHide
    If IsFunc("MainScript") {
        SetTimer, MainScript, -100
    } Else {
        MsgBox, 16, Error, The function 'MainScript' was not found.`nPlease ensure you are running 'firestone-bot.ahk' and NOT 'Gui.ahk'.
    }
Return


; --- INI Helper Functions ---
LoadSettings() {
    global
    For VarName, Info in SettingsMap {
        Section := Info[1]
        Default := Info[2]
        IniRead, Val, settings.ini, %Section%, %VarName%, %Default%
        If (Val = "ERROR")
            Val := Default
        %VarName% := Val
    }
}

SaveSettings() {
    global
    For VarName, Info in SettingsMap {
        Section := Info[1]
        ; Get value from GUI variable
        CurrentVal := %VarName%
        IniWrite, %CurrentVal%, settings.ini, %Section%, %VarName%
    }
}