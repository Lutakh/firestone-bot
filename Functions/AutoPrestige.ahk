CoordMode, Mouse, Client
CoordMode, Pixel, Client

;----------------------------------------------
; Fonction utilitaire : n’écrit que si Value n’est pas vide
;----------------------------------------------
SafeIniWrite(Section, Key, Value){
    if (Value != "") {
        IniWrite, %Value%, settings.ini, %Section%, %Key%
    }
}

;----------------------------------------------
; ParseClipboardNumber(raw)
;   -> renvoie un nombre (float) extrait de raw, gère :
;      • +, %, espaces
;      • notation scientifique e/E
;      • séparateurs milliers vs décimal
;----------------------------------------------
ParseClipboardNumber(raw) {
    local s, posDot, posCom, sep, other, tail, mantStr, mant, expn
    SendHeartbeat("[prestige] raw = " . raw, false, false)
    ; 1) Nettoyage de base
    s := RegExReplace(raw, "[+%\s]", "")
    s := Trim(s, " .")
    SendHeartbeat("[prestige] without% = " . s, false, false)
    ; 2) Notation scientifique e/E
    if RegExMatch(s, "i)^([0-9]+(?:[.,][0-9]+)?)[eE]([+-]?\d+)$", m) {
        mantStr := m1
        SendHeartbeat("[prestige] before e = " . mantStr, false, false)
        expn := m2 + 0
        SendHeartbeat("[prestige] after e = " . expn, false, false)
        StringReplace, mant, mantStr, `,, ., All   ; <--- OUTPUT ≠ INPUT
        SendHeartbeat("[prestige] replace , by . = " . mant, false, false)
        mant := mant + 0
        SendHeartbeat("[prestige] mant + 0 = " . mant, false, false)
        return mant * (10.0 ** expn)
    }

    ; 3) Positions des séparateurs
    posDot := InStr(s, ".", false, 0)
    posCom := InStr(s, ",", false, 0)

    if (posDot && posCom) {
        sep := (posDot > posCom) ? "." : ","
        other := (sep = ".") ? "," : "."
        StringReplace, s, s, %other%, ,   All
        StringReplace, s, s, %sep%,  .,   All
    }
    else if (posDot) {
        tail := SubStr(s, posDot+1)
        if (RegExMatch(tail, "^\d{3}$")) {
            StringReplace, s, s, ".", , All
        }
    }
    else if (posCom) {
        tail := SubStr(s, posCom+1)
        if (RegExMatch(tail, "^\d{3}$")) {
            StringReplace, s, s, ",", , All
        } else {
            StringReplace, s, s, ",", ".", All
        }
    }
    SendHeartbeat("[prestige] s = " . s, false, false)
    StringReplace, final, s, `,, ., All
    SendHeartbeat("[prestige] final = " . final, false, false)
    return final + 0.0
}


AutoPrestige(){
    global GetClipboard, config
     ControlFocus,, ahk_exe Firestone.exe
    ; --- 1) Lecture des valeurs INI ---
    IniRead, LastGoldStr, settings.ini, Prestige, LastPrestigeGold,      0
    IniRead, LastTickStr, settings.ini, Prestige, LastPrestigeTick,      0
    IniRead, MinGoldStr,  settings.ini, Prestige, MinimumPrestige,       0
    IniRead, DiffGoldStr, settings.ini, Prestige, DiffPrestigeGoldPerSec, 0

    LastPrestigeGold := LastGoldStr + 0
    LastPrestigeTick := LastTickStr + 0
    MinimumPrestige   := MinGoldStr + 0
    DiffPrestigeGold  := DiffGoldStr + 0

    SendInput, e
    Sleep, 1500
	MouseMove, 465, 437
    ZoneOCR := [1385, 420, 159, 39]
    ResultatTexte := OCR(ZoneOCR)
    ; ---------------------------------------------------------
    ; ÉTAPE 1 : CORRECTION DES ERREURS VISUELLES (OCR FIX)
    ; ---------------------------------------------------------
    ; On remplace les lettres qui ressemblent à des chiffres
    ; Le "H" devient un "4" (Ton problème spécifique)
    StringReplace, ResultatTexte, ResultatTexte, H, 4, All

    ; Autres classiques à prévoir (optionnel mais recommandé)
    StringReplace, ResultatTexte, ResultatTexte, O, 0, All  ; La lettre O devient Zéro
    StringReplace, ResultatTexte, ResultatTexte, S, 5, All  ; La lettre S devient 5
    StringReplace, ResultatTexte, ResultatTexte, Z, 2, All  ; La lettre Z devient 2
    StringReplace, ResultatTexte, ResultatTexte, B, 8, All  ; La lettre B devient 8
    ; ---------------------------------------------------------
    ResultatTexte := StrReplace(ResultatTexte, "`n", " ")
    ResultatTexte := RegExReplace(ResultatTexte, "^[^+]*")
    Raw := Trim(ResultatTexte)
    CurrentPrestigeGold := ParseClipboardNumber(Raw)
                SendHeartbeat("[prestige] CurrentPrestigeGold = " . CurrentPrestigeGold, false, false)
    ; --- 3) Détection de reset immédiat (gold a décru) ---
    if (CurrentPrestigeGold < LastPrestigeGold) {
		SendHeartbeat("Recent prestige detected. Old gold=" . LastPrestigeGold ". New gold=" . CurrentPrestigeGold ". gold/s=" . Round(GoldPerSec,2), false, false)
        Goto, DoReset
    }

    ; --- 4) Calcul du delta gold et du temps écoulé (en secondes) ---
    DeltaGold := CurrentPrestigeGold - LastPrestigeGold
    TickNow   := A_TickCount
    ; Si c’est la toute première exécution, on force le reset pour init
    if (LastPrestigeTick = 0) {
        LastPrestigeTick := TickNow
        Goto, DoResetInit
    }

    ElapsedMs  := TickNow - LastPrestigeTick
    ElapsedSec := ElapsedMs / 1000.0

    ; Protection div0
    if (ElapsedSec <= 0) {
        SendHeartbeat("Erreur time delta: " . ElapsedMs . " ms", false, false)
        Goto, DoReset
        BigClose()
        return
    }

    GoldPerSec := DeltaGold / ElapsedSec
    MsgBox, Texte lu : %GoldPerSec%
    ; --- 5) Si gold/sec dans les seuils, on prestige, sinon on reset ---
    if (GoldPerSec < DiffPrestigeGold && CurrentPrestigeGold > MinimumPrestige) {
        ControlFocus,, ahk_exe Firestone.exe
        ;PixelSearch, X, Y, 1351, 37, 1418, 101, 0xEB8518, 3, Fast RGB
        ;If (ErrorLevel == 0){
            ZoneOCR := [1406, 44, 72, 42]
            ResultatTexte := OCR(ZoneOCR)
            ResultatTexte := StrReplace(ResultatTexte, "`n", " ")
            Token := Trim(ResultatTexte)
            Token := Token + 0
            if (Token > 0){
                Click, 1347, 502
                Sleep, 2000
                Click, 972, 955
            } else {
                Click, 1347, 502
                Sleep, 2000
                Click, 972, 652
            }
        ;} else {
        ;    Click, 1168, 824
        ;}
        Sleep, 2000
        Click, 1111, 698
		Sleep, 5000
		Click, 973, 761
        global PushBoss := 0
        IniWrite, 0, settings.ini, SettingsNoGui, PushBoss ; Log the push button pressed
        FormatTime, CurrentHour,, yyyyMMddHH
        global LastPrestigeTime := CurrentHour
        IniWrite, %LastPrestigeTime%, settings.ini, Prestige, LastPrestigeTime ; Log the LastPrestigeTime
		Sleep, 2000
        SendHeartbeat("Max HeroUpgrade after prestige", false, false)
		HeroUpgrade(1)
        Sleep, 15000
        SendHeartbeat("Max HeroUpgrade after prestige", false, false)
        HeroUpgrade(1)
        SendHeartbeat("PRESTIGE! Gold/s = " . Round(GoldPerSec,2)" | Gold = " .  Round(CurrentPrestigeGold,0) "%", false, false)
		return
    } else {
		if (GoldPerSec > DiffPrestigeGold){
			SendHeartbeat("No prestige needed. Old gold=" .  Round(LastPrestigeGold,0) "%. New gold=" . Round(CurrentPrestigeGold,0) "%. Gold/s=" . Round(GoldPerSec,2)". Gold/s is good ", false, false)
		}
		if (CurrentPrestigeGold < MinimumPrestige){
			SendHeartbeat("Dont have reach yet the MinimumPrestige=" . Round(CurrentPrestigeGold,0) "%/" . MinimumPrestige "%. Gold/s=" . Round(GoldPerSec,2), false, false)
		}
        Goto, DoReset
    }


    ; --- Label Reset initial (pas de log) ---
DoResetInit:
    SafeIniWrite("Prestige", "LastPrestigeGold", CurrentPrestigeGold)
    SafeIniWrite("Prestige", "LastPrestigeTick", LastPrestigeTick)
    BigClose()

    ; --- Label Reset standard (avec log) ---
DoReset:
    SafeIniWrite("Prestige", "LastPrestigeGold", CurrentPrestigeGold)
    SafeIniWrite("Prestige", "LastPrestigeTick", TickNow)
    BigClose()
}