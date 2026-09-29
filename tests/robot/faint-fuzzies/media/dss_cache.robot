*** Settings ***
Documentation       The DSS image cache: file names in the `hhmmss.ss_±ddmmss.ss` notation, and clean-dss,
...                 which deletes the cached images no Object would fetch or read any more. The fixture in
...                 "fixtures/dss_datadir" has an object with the default surveys and a SIZE, one with a survey
...                 and field of view given by hand, one with DISABLE_DSS, and one with coordinates but no SIZE
...                 and no override - too, no image is ever fetched or kept for it. The cache files are created
...                 per test, in a copy.
Resource            ../../resources/cli.resource
Test Setup          Prepare Data Directory


*** Variables ***
${SOURCE}           ${FIXTURES}${/}dss_datadir
${ALPHA}            dss1_010447.80_+020704.00_5.jpg
${ALPHA_THUMB}      dss1_010447.80_+020704.00_5_web.jpg
${ALPHA_RED}        dss2red_010447.80_+020704.00_5.jpg
${BETA}             dss2blue_000001.70_-471628.30_15.jpg
${OLD_NAME}         dss1_01.07994_+02.11778_5.jpg
${OLD_NAME_THUMB}   dss1_01.07994_+02.11778_5_web.jpg
${OTHER_FIELD}      dss2blue_000001.70_-471628.30_10.jpg
${NO_SIZE}          dss1_020000.00_+150000.00_5.jpg


*** Test Cases ***
Unused Images Are Deleted And Used Ones Kept
    [Documentation]    Kept: an image of any survey the object may use, at its current field of view. Deleted: the
    ...    old decimal name, a different field of view, a disabled object's image, another catalogue's folder, and
    ...    a stale image for an object that has coordinates but no known size any more. A kept image's thumbnail
    ...    (see domain.dss.thumbnail_path) is kept with it; an unused image's thumbnail is deleted with it too,
    ...    whether or not the thumbnail itself still matches anything a fetch would produce.
    Create File    ${DSS}${/}objects${/}${ALPHA_THUMB}    x
    Create File    ${DSS}${/}objects${/}${OLD_NAME_THUMB}    x
    ${result}=    Run CLI    clean-dss    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    0
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${report}[dry_run]    ${False}
    ${expected}=    Create List    objects/${OLD_NAME}    objects/${OLD_NAME_THUMB}    objects/${NO_SIZE}
    ...    objects/dss1_gamma.jpg    objects/${OTHER_FIELD}    sac/${ALPHA}
    Should Be Equal    ${report}[removed]    ${expected}
    File Should Exist    ${DSS}${/}objects${/}${ALPHA}
    File Should Exist    ${DSS}${/}objects${/}${ALPHA_THUMB}
    File Should Exist    ${DSS}${/}objects${/}${ALPHA_RED}
    File Should Exist    ${DSS}${/}objects${/}${BETA}
    File Should Not Exist    ${DSS}${/}objects${/}${OLD_NAME}
    File Should Not Exist    ${DSS}${/}objects${/}${OLD_NAME_THUMB}
    File Should Not Exist    ${DSS}${/}objects${/}${OTHER_FIELD}
    File Should Not Exist    ${DSS}${/}objects${/}dss1_gamma.jpg
    File Should Not Exist    ${DSS}${/}objects${/}${NO_SIZE}

Empty Folders Are Removed And Other Files Are Left Alone
    ${result}=    Run CLI    clean-dss    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    0
    Directory Should Not Exist    ${DSS}${/}sac
    File Should Exist    ${DSS}${/}objects${/}notes.txt

A Dry Run Deletes Nothing
    ${result}=    Run CLI    clean-dss    --data-dir    ${DATADIR}    --dry-run
    Should Be Equal As Integers    ${result.rc}    0
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${report}[dry_run]    ${True}
    Length Should Be    ${report}[removed]    5
    File Should Exist    ${DSS}${/}objects${/}${OLD_NAME}
    File Should Exist    ${DSS}${/}sac${/}${ALPHA}

Nothing Is Deleted When A Catalogue Has Invalid Records
    [Documentation]    An invalid record has no DSS image to keep, so its file would look unused.
    Create File    ${DATADIR}${/}observations${/}owner${/}objects.json    [{"TYPE": "GC"}]
    ${result}=    Run CLI    clean-dss    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    invalid records
    File Should Exist    ${DSS}${/}objects${/}${ALPHA}
    File Should Exist    ${DSS}${/}objects${/}${OLD_NAME}

Without A DSS Folder There Is Nothing To Clean
    Remove Directory    ${DSS}    recursive=True
    ${result}=    Run CLI    clean-dss    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    0
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[removed]


*** Keywords ***
Prepare Data Directory
    ${DATADIR}=    Set Variable    ${TEMPDIR}${/}dss_datadir_test
    Remove Directory    ${DATADIR}    recursive=True
    Copy Directory    ${SOURCE}    ${DATADIR}
    ${DSS}=    Set Variable    ${DATADIR}${/}dss
    FOR    ${name}    IN    ${ALPHA}    ${ALPHA_RED}    ${BETA}    ${OLD_NAME}    ${OTHER_FIELD}    ${NO_SIZE}    dss1_gamma.jpg    notes.txt
        Create File    ${DSS}${/}objects${/}${name}    x
    END
    Create File    ${DSS}${/}sac${/}${ALPHA}    x
    Set Test Variable    ${DATADIR}
    Set Test Variable    ${DSS}
