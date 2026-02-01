#Include Functions\subFunctions\BigClose.ahk
#Include Functions\subFunctions\MapClose.ahk

MapStart(){
    stateFile := "MapStartState.ini"

    ; --- 1. Memory and Timer Management ---
    IniRead, SessionStart, %stateFile%, Memory, SessionStart, %A_Space%
    IniRead, ClickedPoints, %stateFile%, Memory, ClickedPoints, %A_Space%

    ; If it's the first time or empty, initialize
    if (SessionStart = "" or SessionStart = 0) {
        SessionStart := A_Now
        IniWrite, %SessionStart%, %stateFile%, Memory, SessionStart
    }

    ; Calculate time difference in Hours
    TimeDiff := A_Now
    EnvSub, TimeDiff, %SessionStart%, Hours

    ; --- 2. Mission Definitions ---
    Squad2 := []
    Squad2.Insert(Object("x",384,"y",1009)) ; Pirate Cove
    Squad2.Insert(Object("x",484,"y",920)) ; Dragon Island
    Squad2.Insert(Object("x",543,"y",1032)) ; Hydra
    Squad2.Insert(Object("x",633,"y",576)) ; Dragon's Cave
    Squad2.Insert(Object("x",616,"y",204)) ; Frostfire Gorge
    Squad2.Insert(Object("x",1150,"y",340)) ; Irongard's Harbor
    Squad2.Insert(Object("x",883,"y",460)) ; Lake's Terror
    Squad2.Insert(Object("x",1130,"y",546)) ; Collect The Bounty
    Squad2.Insert(Object("x",836,"y",1039)) ; Open Sea
    Squad2.Insert(Object("x",970,"y",810)) ; Orc Lieutenant
    Squad2.Insert(Object("x",1486,"y",770)) ; Ships On Fire
    Squad2.Insert(Object("x",1255,"y",853)) ; Trade Route
    Squad2.Insert(Object("x",1533,"y",98))
    Squad2.Insert(Object("x",1608,"y",119))
    Squad2.Insert(Object("x",1534,"y",123))
    Squad2.Insert(Object("x",1440,"y",140))
    Squad2.Insert(Object("x",1207,"y",32))
    Squad2.Insert(Object("x",1290,"y",99))
    Squad2.Insert(Object("x",1177,"y",35))
    Squad2.Insert(Object("x",1104,"y",43))
    War := []
    War.Insert(Object("x",672,"y",423)) ; Tipsy Wisp Tavern
    War.Insert(Object("x",720,"y",675)) ; Ambush in the Trees
    War.Insert(Object("x",780,"y",845)) ; Stop The Pirate Raids
    War.Insert(Object("x",812,"y",637)) ; Xandor Dock
    War.Insert(Object("x",849,"y",794)) ; Protect The Fishermen
    War.Insert(Object("x",910,"y",759)) ; Confront The Orcs
    War.Insert(Object("x",929,"y",609)) ; Moonglen's Festival
    War.Insert(Object("x",980,"y",228)) ; North Sea
    War.Insert(Object("x",1017,"y",426)) ; Recruit Soldiers
    War.Insert(Object("x",1055,"y",780)) ; The Pit
    War.Insert(Object("x",1145,"y",626)) ; Protect The Shore
    War.Insert(Object("x",1152,"y",969)) ; Sea Monsters
    War.Insert(Object("x",1224,"y",312)) ; Free The Prisoners
    War.Insert(Object("x",1228,"y",550)) ; Forest Rangers
    War.Insert(Object("x",1252,"y",392)) ; Mission To Bayshire
    War.Insert(Object("x",1326,"y",798)) ; Train Elf Archers
    War.Insert(Object("x",1424,"y",777)) ; Chase the Monster
    War.Insert(Object("x",1452,"y",498)) ; Defend Mythshore

    Medium := []
    Medium.Insert(Object("x",463,"y",433))
    Medium.Insert(Object("x",460,"y",670))
    Medium.Insert(Object("x",502,"y",330)) ; Snow Wolves
    Medium.Insert(Object("x",581,"y",295)) ; Expose the Spy
    Medium.Insert(Object("x",671,"y",755)) ; Cursed Bay
    Medium.Insert(Object("x",705,"y",592)) ; The Lost Chapter
    Medium.Insert(Object("x",797,"y",504)) ; Visit the Abbey
    Medium.Insert(Object("x",867,"y",543)) ; Calamindor Ruins
    Medium.Insert(Object("x",1041,"y",518)) ; Silverwood's Militia
    Medium.Insert(Object("x",1044,"y",676)) ; The Resistance of Goldeff
    Medium.Insert(Object("x",1314,"y",306)) ; Firestone Power
    Medium.Insert(Object("x",1340,"y",545)) ; Explore Hinterlands
    Medium.Insert(Object("x",1435,"y",683)) ; Library of Talamer
    Medium.Insert(Object("x",1438,"y",871))
    Medium.Insert(Object("x",1442,"y",418)) ; Close The Portal
    Medium.Insert(Object("x",1481,"y",261)) ; Dreadland Shore

    Short := []
    Short.Insert(Object("x",490,"y",190)) ; Visit the Northern Tribes
    Short.Insert(Object("x",556,"y",500)) ; Jungle Terror
    Short.Insert(Object("x",655,"y",357)) ; The Hombor King
    Short.Insert(Object("x",712,"y",517))
    Short.Insert(Object("x",733,"y",229)) ; Dark Cavern
    Short.Insert(Object("x",828,"y",375)) ; Riverside
    Short.Insert(Object("x",874,"y",664)) ; Escort the Merchants
    Short.Insert(Object("x",884,"y",233)) ; Stormspire Accident
    Short.Insert(Object("x",1099,"y",894)) ; The Port of Thal Badur
    Short.Insert(Object("x",1162,"y",454)) ; Find the Librarian
    Short.Insert(Object("x",1224,"y",463)) ; Dark River
    Short.Insert(Object("x",1276,"y",694)) ; Border Patrol
    Short.Insert(Object("x",1297,"y",193)) ; Search For Survivors
    Short.Insert(Object("x",1357,"y",429))
    Short.Insert(Object("x",1364,"y",646)) ; Watchtower
    Short.Insert(Object("x",1394,"y",355)) ; Retrieve Water Sample
    Short.Insert(Object("x",1460,"y",580)) ; Search The Shipwreck


    Leftover := []
    Leftover.Insert(Object("x",923,"y",369))
    Leftover.Insert(Object("x",1221,"y",467))
    Leftover.Insert(Object("x",742,"y",389))
    Leftover.Insert(Object("x",967,"y",547))

    ; --- 3. Priority List Construction ---
    Point := []
    ; Read the 5 priorities (Default values defined in the Gui)
    IniRead, P1, settings.ini, MissionPriority, Priority1, 2 Squad
    IniRead, P2, settings.ini, MissionPriority, Priority2, War
    IniRead, P3, settings.ini, MissionPriority, Priority3, Medium
    IniRead, P4, settings.ini, MissionPriority, Priority4, Short
    IniRead, P5, settings.ini, MissionPriority, Priority5, Leftover

    Priorities := [P1, P2, P3, P4, P5]
    For index, type in Priorities {
        currentList := ""
        If (type = "2 Squad")
            currentList := Squad2
        Else If (type = "War")
            currentList := War
        Else If (type = "Medium")
            currentList := Medium
        Else If (type = "Short")
            currentList := Short
        Else If (type = "Leftover")
            currentList := Leftover

        if (IsObject(currentList)) {
            ; Add points from the chosen category to the main list
            For i, obj in currentList {
                Point.Insert(obj)
            }
        }
    }

    ; --- 4. Main Loop (Max 2 attempts) ---
    ; Attempt 1: Skip what is in memory.
    ; Attempt 2: If troops remain at the end, clear memory and redo everything.
    Loop, 2
    {
        AttemptNum := A_Index
        total := Point.MaxIndex()

        Loop, % total
        {
            idx := A_Index
            x := Point[idx].x
            y := Point[idx].y

            ; Unique identifier for this point (x|y)
            CoordID := "|" . x . "|" . y . "|"

            ; Memory check: if already clicked, skip
            if (InStr(ClickedPoints, CoordID)) {
                Continue
            }

            ; Click Action
            ControlFocus,, ahk_exe Firestone.exe
            Click %x%, %y%
            Sleep, 1000

            ; Add to memory immediately
            ClickedPoints .= CoordID
            IniWrite, %ClickedPoints%, %stateFile%, Memory, ClickedPoints

            ; Check Start Button (Green)
            PixelSearch, X, Y, 953, 822, 1205, 898, 0x0AA008, 10, Fast RGB
            If(ErrorLevel=0){
                MouseMove, 1084, 865
                MsgBox, , Mission Start, Mission found - Starting, 1.5
                Click
                Sleep, 500

                MsgBox, , Troop Check, Looking for more idle troops, 2
                ; Check Troops (Brown Pixel)
                PixelSearch, X, Y, 1175, 996, 1187, 1012, 0x542710, 10, Fast RGB
                If(ErrorLevel=0){
                    ; Troops available -> Continue the list
                    Continue
                } Else {
                    ; No more troops -> End of function
                    MsgBox, , Troop Check, No idle troops found - ending mission search, 2
                    Return
                }
            } Else {
                ; No start button (Mission in progress or unavailable) -> Close popup
                MapClose()
            }

            ; Check Troops after each interaction (even if not started)
            PixelSearch, X, Y, 1175, 996, 1187, 1012, 0x542710, 10, Fast RGB
            If(ErrorLevel != 0){
                MsgBox, , Troop Check, No idle troops found - ending mission search, 2
                Return
            }
        }

        ; --- End of list ---
        ; If we are here, we have traversed everything (or skipped everything).
        ; Check if troops remain (Requested case: "reset if clicked everywhere but troops available")
        PixelSearch, X, Y, 1175, 996, 1187, 1012, 0x542710, 10, Fast RGB
        If (ErrorLevel=0 and AttemptNum == 1) {
            ; Troops available + 1st attempt finished = We missed something because of memory.
            ; RESET and start over (Loop 2)
            ClickedPoints := ""
            ; Also reset the timer because it's a forced "fresh start"
            SessionStart := A_Now
            IniWrite, %SessionStart%, %stateFile%, Memory, SessionStart
            IniWrite, %ClickedPoints%, %stateFile%, Memory, ClickedPoints
            Continue
        }

        ; If attempt 2 finished or no troops, stop.
        Break
    }
}