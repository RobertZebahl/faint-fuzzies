*** Settings ***
Documentation       The own catalogue's double-star attach-records under --data-dir: here, the double stars they reach
...                 in the global list. How the records and the Alternative-names file are matched, and their
...                 findings, are unit tests (tests/unit/importers/test_owner_double_stars.py, which also describes
...                 the fixture "double_star_attach_datadir").
Resource            ../resources/cli.resource
Suite Setup         Read The Global List


*** Variables ***
${DATADIR}          ${FIXTURES}${/}double_star_attach_datadir


*** Test Cases ***
The Global List Reaches A Double Star With No Own-Catalogue Record
    [Documentation]    STFZ4 has no own-catalogue record at all - only a Global-scope observer's community
    ...    row. A first_catalogue_only list still needs a double star through its rank gate at any rank
    ...    (see domain/lists.py build_list), regardless of who observed it.
    ${labels}=    Evaluate    [e["names"][0] if e["names"] else e["groups"][0] for e in $GLOBAL["entries"]]
    Should Contain    ${labels}    STFZ4

Double Stars Sort After Everything Else, In The WDS's Own File Order
    [Documentation]    ZZZ Deep Sky Object (own catalogue) first; then the five double-star entries
    ...    reachable through attach-records/community rows, in the WDS file's own order: the eps Aql group
    ...    (file position 1, renamed "Old Catalog Name" by its Alternative-names entry), STFY3 (position 4),
    ...    STFZ4 (position 5), STFV6 (position 7), STFU7 (position 8) - not alphabetical order, which
    ...    would put STFY3 before "Old Catalog Name".
    ${labels}=    Evaluate    [e["names"][0] if e["names"] else e["groups"][0] for e in $GLOBAL["entries"]]
    Should Be Equal    ${labels}    ${{['ZZZ Deep Sky Object', 'Old Catalog Name', 'STFY3', 'STFZ4', 'STFV6', 'STFU7']}}


*** Keywords ***
Read The Global List
    ${global}=    Run CLI    list    global    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${global.rc}    0    msg=${global.stderr}
    ${global_data}=    Parse JSON    ${global.stdout}
    Set Suite Variable    ${GLOBAL}    ${global_data}
