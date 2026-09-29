*** Settings ***
Documentation       clean-orbits: deletes the cached orbit diagrams no pair would plot any more. The fixture
...                 "fixtures/datadir" has the WDS pairs STF999 (one solution here, so a plain name) and BU17 (AB
...                 and AC); orbits.txt and the cache files are created per test, in a copy.
Resource            ../../resources/cli.resource
Library             ../../libraries/OrbitChecks.py
Test Setup          Prepare Data Directory


*** Variables ***
${SOURCE}           ${FIXTURES}${/}datadir
${KEPT}             STF999-AB-orbit.jpg
${KEPT_TOO}         BU17-AB-orbit.jpg
${NUMBERED}         STF999-AB-orbit-solution-2.jpg
${CANNOT_PLOT}      BU17-AC-orbit.jpg
${UNKNOWN_PAIR}     XYZ1-AB-orbit.jpg
${OLD_NAME}          WDS11111+2222_STF999.jpg


*** Test Cases ***
Unused Diagrams Are Deleted And Used Ones Kept
    [Documentation]    Kept: a plottable solution of a matched pair. Deleted: a number the pair no longer has, a
    ...    solution that cannot be plotted, a pair that is not in the WDS.
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    0
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${report}[dry_run]    ${False}
    ${expected}=    Evaluate    sorted(["${CANNOT_PLOT}", "${NUMBERED}", "${UNKNOWN_PAIR}", "${OLD_NAME}", "stale.jpg"])
    Should Be Equal    ${report}[removed]    ${expected}
    File Should Exist    ${ORBITS}${/}${KEPT}
    File Should Exist    ${ORBITS}${/}${KEPT_TOO}
    File Should Not Exist    ${ORBITS}${/}${NUMBERED}
    File Should Not Exist    ${ORBITS}${/}${CANNOT_PLOT}

Other Files And The Folder Are Left Alone
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    0
    File Should Exist    ${ORBITS}${/}notes.txt
    Remove File    ${ORBITS}${/}notes.txt
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}
    Directory Should Exist    ${ORBITS}

A Dry Run Deletes Nothing
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}    --dry-run
    Should Be Equal As Integers    ${result.rc}    0
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${report}[dry_run]    ${True}
    Length Should Be    ${report}[removed]    5
    File Should Exist    ${ORBITS}${/}${NUMBERED}

Nothing Is Deleted Without Orbital Elements
    [Documentation]    Without orbits.txt every diagram would look unused.
    Remove File    ${DATADIR}${/}catalogues${/}orbits.txt
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    orbits.txt
    File Should Exist    ${ORBITS}${/}${NUMBERED}

Nothing Is Deleted When A Catalogue Has Invalid Records
    Create File    ${DATADIR}${/}observations${/}owner${/}objects.json    [{"TYPE": "GC"}]
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    invalid records
    File Should Exist    ${ORBITS}${/}${NUMBERED}

All Diagrams Are Deleted With --all
    [Documentation]    The yearly refresh: the ones in use go too, other files and the folder stay, and neither
    ...    orbits.txt nor valid catalogues are needed.
    Remove File    ${DATADIR}${/}catalogues${/}orbits.txt
    Create File    ${DATADIR}${/}observations${/}owner${/}objects.json    [{"TYPE": "GC"}]
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}    --all
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    ${expected}=    Evaluate    sorted(["${KEPT}", "${KEPT_TOO}", "${CANNOT_PLOT}", "${NUMBERED}", "${UNKNOWN_PAIR}", "${OLD_NAME}", "stale.jpg"])
    Should Be Equal    ${report}[removed]    ${expected}
    File Should Not Exist    ${ORBITS}${/}${KEPT}
    File Should Exist    ${ORBITS}${/}notes.txt

--all With A Dry Run Deletes Nothing
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}    --all    --dry-run
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[removed]    7
    File Should Exist    ${ORBITS}${/}${KEPT}

Without An Orbits Folder There Is Nothing To Clean
    Remove Directory    ${ORBITS}    recursive=True
    ${result}=    Run CLI    clean-orbits    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    0
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[removed]


*** Keywords ***
Prepare Data Directory
    ${DATADIR}=    Set Variable    ${TEMPDIR}${/}orbits_datadir_test
    Remove Directory    ${DATADIR}    recursive=True
    Copy Directory    ${SOURCE}    ${DATADIR}
    ${entries}=    Evaluate    [("WDS11111+2222", "STF 999", "y"), ("WDS02333+1234", "BU 17AB", "y"), ("WDS02333+1234", "BU 17AC", "d")]
    ${text}=    Orbits File Text    ${entries}
    Create File    ${DATADIR}${/}catalogues${/}orbits.txt    ${text}
    ${ORBITS}=    Set Variable    ${DATADIR}${/}orbits
    FOR    ${name}    IN    ${KEPT}    ${KEPT_TOO}    ${NUMBERED}    ${CANNOT_PLOT}    ${UNKNOWN_PAIR}    ${OLD_NAME}    stale.jpg    notes.txt
        Create File    ${ORBITS}${/}${name}    x
    END
    Set Test Variable    ${DATADIR}
    Set Test Variable    ${ORBITS}
