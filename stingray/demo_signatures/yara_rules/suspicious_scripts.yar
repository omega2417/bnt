rule Suspicious_PowerShell_Download
{
    meta:
        description = "Підозрілий PowerShell-скрипт з завантаженням"
        author = "Stingray"
        severity = "high"

    strings:
        $ps1 = "Invoke-WebRequest" nocase
        $ps2 = "DownloadFile" nocase
        $ps3 = "DownloadString" nocase
        $ps4 = "IEX" nocase
        $ps5 = "Invoke-Expression" nocase
        $hidden = "-WindowStyle Hidden" nocase
        $bypass = "-ExecutionPolicy Bypass" nocase

    condition:
        any of ($ps1, $ps2, $ps3) and any of ($ps4, $ps5) and
        any of ($hidden, $bypass)
}

rule Suspicious_Batch_Script
{
    meta:
        description = "Підозрілий BAT-скрипт"
        author = "Stingray"
        severity = "medium"

    strings:
        $del_shadow = "vssadmin delete shadows" nocase
        $disable_defender = "DisableRealtimeMonitoring" nocase
        $reg_run = "reg add.*\\CurrentVersion\\Run" nocase
        $schtasks = "schtasks /create" nocase

    condition:
        2 of them
}

rule Suspicious_VBS_Script
{
    meta:
        description = "Підозрілий VBS-скрипт"
        author = "Stingray"
        severity = "high"

    strings:
        $shell = "WScript.Shell" nocase
        $http = "MSXML2.XMLHTTP" nocase
        $stream = "ADODB.Stream" nocase
        $exec = ".Run " nocase

    condition:
        ($shell and $exec) and any of ($http, $stream)
}
