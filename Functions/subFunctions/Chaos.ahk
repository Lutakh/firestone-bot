; Chaos.ahk

#Include Functions\subFunctions\BigClose.ahk

HitChaos(){
    global ChaosCountDaily, MaxChaos, LastChaosReset ; Accès aux variables globales
    IniRead, ChaosCountDaily, settings.ini, CommonOptions, ChaosCountDaily, 0
    IniRead, LastChaosReset, settings.ini, CommonOptions, LastChaosReset, %A_Space%
    IniRead, MaxChaos, settings.ini, CommonOptions, MaxChaos, 10
    ; --- 1. Vérification du Reset de 24h ---
    if (LastChaosReset != "") {
        TimeElapsed := A_Now
        EnvSub, TimeElapsed, %LastChaosReset%, Hours
        if (TimeElapsed >= 24) {
            ChaosCountDaily := 0
            LastChaosReset := ""
            SaveSettings() ; Sauvegarde le reset dans le fichier ini
        }
    }

    ; --- 2. Test de la limite utilisateur ---
    if (ChaosCountDaily >= MaxChaos) {
        return
    }

    ControlFocus,, ahk_exe Firestone.exe

    ; Check for Chaos notification on guild screen
    PixelSearch, X, Y, 1525, 695, 1555, 725, 0xF40000, 3, Fast RGB
    If (ErrorLevel = 0){
        MouseClick, Left, 1410, 625, 1, 0
        Sleep, 1500

        ; Hit Chaos button inside the rift
        PixelSearch, X, Y, 1019, 934, 1050, 991, 0x0AA008, 3, Fast RGB
        If (ErrorLevel = 0){
            ; --- 3. Enregistre l'heure au tout premier clic de la journée ---
            if (ChaosCountDaily = 0) {
                LastChaosReset := A_Now
                IniWrite, %LastChaosReset%, settings.ini, CommonOptions, LastChaosReset
            }

            MouseMove, 962, 918
            Sleep, 1000
            Click
            ChaosCountDaily++
            IniWrite, %ChaosCountDaily%, settings.ini, CommonOptions, ChaosCountDaily
            SendHeartbeat("HitChaosUse", false, true)
            Sleep, 1000
            SaveSettings() ; Sauvegarde immédiate du compteur
        }
        BigClose()
    }
}
