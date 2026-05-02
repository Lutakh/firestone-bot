RestartGameRoutine() {
    global lastRestartTime

    ; 1. Détecter la plateforme AVANT de fermer le jeu
    WinGet, exePath, ProcessPath, ahk_exe Firestone.exe
    platformDetected := ""

    If (exePath != "") {
        ; Recherche de mots clés dans le chemin de l'exécutable
        If InStr(exePath, "steam") {
            platformDetected := "Steam"
        } Else If InStr(exePath, "Epic") {
            platformDetected := "Epic"
        } Else {
            platformDetected := "Unknown"
        }
    }

    ; Sécurité si le jeu n'est pas détecté
    If (platformDetected = "" || platformDetected = "Unknown") {
        SendHeartbeat("Error: Could not determine if game is Steam or Epic.", false, true)
        lastRestartTime := A_TickCount
        Return
    }

    Loop {
        ; 2. Fermeture du processus
        Process, Close, Firestone.exe
        Sleep, 15000 ; Laisse 5 secondes au système pour fermer complètement

        ; 3. Lancement selon la plateforme détectée
        If (platformDetected = "Steam") {
            Run, steam://rungameid/1017490
            SendHeartbeat("Game Restarted via Steam, waiting for pixel...", false, true)
        }
        Else If (platformDetected = "Epic") {
            ; Recherche et lancement du raccourci sur le bureau pour Epic
            shortcutFound := false

            ; Cherche un raccourci internet (.url)
            Loop, Files, %A_Desktop%\*Firestone*.url
            {
                Run, "%A_LoopFileFullPath%"
                shortcutFound := true
                break
            }

            ; Si pas de .url, on cherche un raccourci classique (.lnk)
            If (!shortcutFound) {
                Loop, Files, %A_Desktop%\*Firestone*.lnk
                {
                    Run, "%A_LoopFileFullPath%"
                    shortcutFound := true
                    break
                }
            }

            ; Si aucun raccourci n'est trouvé sur le bureau, on annule pour ne pas tourner en boucle
            If (!shortcutFound) {
                SendHeartbeat("Error: No Firestone shortcut found on the Desktop.", false, true)
                lastRestartTime := A_TickCount
                Break
            }
            SendHeartbeat("Game Restarted via Epic, waiting for pixel...", false, true)
        }

        ; 4. Boucle d'attente de 5 minutes (300 000 ms) pour trouver le pixel
        startTime := A_TickCount
        pixelFound := false

        While ((A_TickCount - startTime) < 300000) {
            ; === PARAMÉTRAGE DU PIXEL À CHANGER ICI ===
            ; Remplacez X et Y par les coordonnées du pixel attestant que le jeu est prêt (ex: bouton Aventure)
			ControlFocus,, ahk_exe Firestone.exe
			Sleep, 500
			MouseMove, 900, 900
            Sleep, 1000
			PixelSearch, X, Y, 845, 860, 1080, 937, 0x16BC15, 3, Fast RGB
            If (ErrorLevel = 0){
                Click
                Sleep, 1000
                pixelFound := true
                Break
            }
            Sleep, 5000 ; Attendre 5 secondes entre chaque vérification pour ne pas surcharger le processeur
        }

        ; 5. Reprise ou nouvelle tentative
        If (pixelFound) {
            SendHeartbeat("Pixel found. Resuming bot.", false, true)
            lastRestartTime := A_TickCount
            Break ; Succès, on sort de la boucle principale
        } Else {
            SendHeartbeat("Pixel not found after 5 min. Retrying restart...", false, true)
            ; La boucle va recommencer (kill -> restart)
        }
    }
}