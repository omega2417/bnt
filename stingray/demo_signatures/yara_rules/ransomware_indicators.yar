rule Ransomware_Note_Pattern
{
    meta:
        description = "Типові ознаки записки-вимоги від шифрувальника"
        author = "Stingray"
        severity = "critical"

    strings:
        $btc = /[13][a-km-zA-HJ-NP-Z1-9]{25,34}/ ascii wide
        $ransom1 = "your files have been encrypted" nocase
        $ransom2 = "decrypt your files" nocase
        $ransom3 = "bitcoin" nocase
        $ransom4 = "pay the ransom" nocase
        $ransom5 = "restore your files" nocase

    condition:
        $btc and 2 of ($ransom1, $ransom2, $ransom3, $ransom4, $ransom5)
}

rule Crypto_Mining_Indicator
{
    meta:
        description = "Ознаки криптомайнера"
        author = "Stingray"
        severity = "medium"

    strings:
        $pool1 = "stratum+tcp://" nocase
        $pool2 = "pool.minexmr" nocase
        $pool3 = "xmrpool" nocase
        $algo1 = "cryptonight" nocase
        $algo2 = "randomx" nocase

    condition:
        any of ($pool*) or 2 of ($algo*)
}
