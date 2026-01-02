ConnectedToInternet() {
    return DllCall("Wininet.dll\InternetGetConnectedState", "Str", 0x00, "Int", 0)
}

SendHeartbeat(msg, isStop, isImportant := false) {
    if (ConnectedToInternet()) {
        global ServerURL, MyID, DiscordID
        ServerURL := "https://fs-bot-logs.lutak.ovh/api/heartbeat"
        IniRead, DiscordID, settings.ini, SettingsNoGui, DiscordID, 0
        MyID := GetUniqueID()
        ; Conversion booléens pour JSON
        stopBool := isStop ? "true" : "false"
        impBool := isImportant ? "true" : "false"

        json_str = {"client_id": "%MyID%", "discord_id": "%DiscordID%", "message": "%msg%", "is_stop": %stopBool%, "is_important": %impBool%}
        try
        {
            HTTP := ComObjCreate("WinHttp.WinHttpRequest.5.1")
            HTTP.Open("POST", ServerURL, true)
            HTTP.SetRequestHeader("Content-Type", "application/json")
            HTTP.Send(json_str)
            HTTP.WaitForResponse()
        }
        Catch e
        {
            return
        }
    }
}


GetUniqueID() {
    Key := "ClientID"
    ; Try to read the ID from the INI file.
    ; If the file or key doesn't exist, 'StoredID' will be set to "ERROR".
    IniRead, StoredID, settings.ini, SettingsNoGui, %Key%, ERROR

    ; If no ID was found, generate a new one
    if (StoredID = "ERROR") {
        ; Generate a random number
        Random, RandNum, 100000, 999999

        ; Create a unique ID using the current Timestamp + Random Number
        ; Example format: 20251216153000-582931
        NewID := A_Now . "-" . RandNum

        ; Save the new ID to the INI file for future use
        IniWrite, %NewID%, settings.ini, SettingsNoGui, %Key%

        return NewID
    }

    ; If an ID was found, return it
    return StoredID
}