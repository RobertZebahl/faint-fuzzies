*** Settings ***
Documentation       fetch-dss: downloads one DSS cutout by name or by coordinates. The fetch itself always
...                 reaches a real external archive, so only what is checked before any network call is
...                 covered here - the --coordinates format.
Resource            ../../resources/cli.resource


*** Test Cases ***
Coordinates Not In The Right Format Are A Usage Error
    ${result}=    Run CLI    fetch-dss    --coordinates    bad    --output    ${OUTPUT DIR}${/}fetch_dss.jpg
    Should Fail With Usage Error    ${result}    is not in the COORDINATES format
