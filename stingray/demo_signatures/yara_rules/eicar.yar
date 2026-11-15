rule EICAR_Test_File
{
    meta:
        description = "Виявлення тестового файлу EICAR"
        author = "Stingray"
        severity = "test"

    strings:
        $eicar = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

    condition:
        $eicar at 0
}
