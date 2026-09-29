*** Settings ***
Documentation       Sketch, Photograph and Image: the has_sketch/has_photograph/has_image
...                 filter criteria, and (for the own catalogue, which is only checked within a data
...                 directory) that referenced files exist under observations/owner/ and that a SKETCH
...                 always states its OPTIC.
Resource            ../../resources/cli.resource


*** Variables ***
${HAS_MEDIA}        has_media.json
${OWN_MEDIA_DIR}     ${FIXTURES}${/}own_media_datadir


*** Test Cases ***
Has Sketch Photograph And Image Criteria
    [Template]    Filter Should Return
    {"has_sketch": true}          ${HAS_MEDIA}    WithSketch
    {"has_photograph": true}      ${HAS_MEDIA}    WithPhotograph
    {"has_image": true}           ${HAS_MEDIA}    WithImage
    {"has_photograph": false}     ${HAS_MEDIA}    WithSketch    WithImage    Plain

Missing Own Media Files Are Reported
    [Documentation]    SKETCH, PHOTOGRAPH and IMAGE on the own catalogue's observations are checked
    ...    against observations/owner/sketches, photographs and images - only within a data directory,
    ...    since only there does that folder exist.
    ${result}=    Run Validate    ${{[]}}    --data-dir    ${OWN_MEDIA_DIR}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["object"], p["attribute"], p["severity"], p["observation"]) for p in $report["findings"]]
    ${expected}=    Evaluate
    ...    [(7, "SketchWithoutOptic", "SKETCH", "error", 1), (2, "MissingFiles", "SKETCH", "error", 1), (2, "MissingFiles", "PHOTOGRAPH", "error", 1), (5, "MissingImage", "IMAGE", "error", 1), (6, "MultipleSketches", "SKETCH", "error", 1)]
    Should Be Equal    ${found}    ${expected}
    Should Contain    ${report}[findings][1][message]    file 'missing_sketch.jpg' not found in sketches/
    Should Contain    ${report}[findings][2][message]    file 'missing_photo.jpg' not found in photographs/
    Should Contain    ${report}[findings][3][message]    file 'missing_header.jpg' not found in images/
    Should Contain    ${report}[findings][4][message]    file 'missing_sketch2.jpg' not found in sketches/

Several Files On One Attribute Are Each Checked On Their Own
    [Documentation]    MultipleSketches has SKETCH "sketch1.jpg,sketch2.jpg,missing_sketch2.jpg": the first
    ...    two exist and are not reported, only the third is - one attribute holding several files is not
    ...    treated as all-or-nothing.
    ${result}=    Run Validate    ${{[]}}    --data-dir    ${OWN_MEDIA_DIR}
    ${report}=    Parse JSON    ${result.stdout}
    ${messages}=    Evaluate    [p["message"] for p in $report["findings"] if p["object"] == "MultipleSketches"]
    Length Should Be    ${messages}    1
    Should Contain    ${messages}[0]    missing_sketch2.jpg

Sketch Requires An Optic
    ${result}=    Run Validate    ${{[]}}    --data-dir    ${OWN_MEDIA_DIR}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${report}[findings][0][message]
    ...    SKETCH requires OPTIC to be stated

Image May Accompany A Sketch Or Photograph
    [Documentation]    SketchWithImage combines OPTIC, SKETCH and IMAGE on one observation - no longer an
    ...    error now that an Image may accompany a Sketch or Photograph instead of only standing alone as
    ...    a Header.
    ${result}=    Run Validate    ${{[]}}    --data-dir    ${OWN_MEDIA_DIR}
    ${report}=    Parse JSON    ${result.stdout}
    ${objects}=    Evaluate    {p["object"] for p in $report["findings"]}
    Should Not Contain    ${objects}    SketchWithImage

Existing Own Media Files Are Not Reported
    ${result}=    Run Validate    ${{[]}}    --data-dir    ${OWN_MEDIA_DIR}
    ${report}=    Parse JSON    ${result.stdout}
    ${objects}=    Evaluate    {p["object"] for p in $report["findings"]}
    Should Not Contain    ${objects}    GoodSketch
    Should Not Contain    ${objects}    GoodHeader

Own Media Is Not Checked Without A Data Directory
    [Documentation]    Without --data-dir there is no observations/owner/ to check against, so a missing
    ...    file is never reported - unlike a parse-time problem such as SketchWithoutOptic's, which does not
    ...    need a data directory and is reported either way.
    ${own}=    Set Variable    ${OWN_MEDIA_DIR}${/}observations${/}owner${/}objects.json
    ${result}=    Run CLI    validate    ${own}
    ${report}=    Parse JSON    ${result.stdout}
    ${messages}=    Evaluate    [p["message"] for p in $report["findings"]]
    FOR    ${message}    IN    @{messages}
        Should Not Contain    ${message}    not found in
    END
