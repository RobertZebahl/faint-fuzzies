*** Settings ***
Documentation       Filter operations against JSON catalogues in the common format.
...                 Every row of a template names the filter, the fixture catalogue and the
...                 first names of the objects that must come back, in catalogue order.
Resource            ../../resources/cli.resource


*** Variables ***
${OBJECTS}      objects.json


*** Test Cases ***
Empty Filter Matches Every Object
    [Template]    Filter Should Return
    {}    ${OBJECTS}    3C48    H1.1    NGC752    Mond    78P/Gehrels    2 Sge    HDS2753    STFA41    STF1884

Name Matches Exactly And Ignores Case
    [Template]    Filter Should Return
    {"name": "NGC1055"}                 ${OBJECTS}    H1.1
    {"name": "ngc1055"}                 ${OBJECTS}    H1.1
    {"name": "NGC105"}                  ${OBJECTS}
    {"name": ["3C48", "ngc752"]}        ${OBJECTS}    3C48    NGC752

Every Language Variant Of A Name Matches
    [Template]    Filter Should Return
    {"name": "Moon"}    ${OBJECTS}    Mond
    {"name": "mond"}    ${OBJECTS}    Mond

Abbreviated Forms Are Added To Names And Groups In Memory
    [Documentation]    "Messier 31" also matches as "M31", "Trumpler 37" as "Tr37"; the abbreviation is
    ...    never in the record itself, only added when the catalogue is loaded - here from an explicit
    ...    --object-name-abbreviations file, since there is no --data-dir to find one in by itself.
    ${abbreviations}=    Fixture    sample_object_name_abbreviations.json
    ${result}=    Run Filter    {"name": "M31"}    ${{['name_abbreviations.json']}}    --names-only
    ...    --object-name-abbreviations    ${abbreviations}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects]    ${{['Messier 31']}}
    ${result}=    Run Filter    {"group": "Tr37"}    ${{['name_abbreviations.json']}}    --names-only
    ...    --object-name-abbreviations    ${abbreviations}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects]    ${{['Trumpler 37']}}

The Abbreviated Form Is Not Written Back
    ${abbreviations}=    Fixture    sample_object_name_abbreviations.json
    ${result}=    Run Filter    {"name": "M31"}    ${{['name_abbreviations.json']}}    --object-name-abbreviations    ${abbreviations}
    ${data}=    Parse JSON    ${result.stdout}
    Lists Should Be Equal    ${data}[objects][0][names]    ${{['Messier 31', 'M31', 'NGC224']}}
    ${path}=    Fixture    name_abbreviations.json
    ${check}=    Run CLI    format    --check    ${path}
    Should Be Equal As Integers    ${check.rc}    0    msg=${check.stderr}

Group Filter Matches The Group And Its Members
    [Template]    Filter Should Return
    {"group": "2 sge"}    ${OBJECTS}    2 Sge    HDS2753    STFA41
    {"group": "400"}      ${OBJECTS}    H1.1

Type Filter Matches Any Listed Type Ignoring Case
    [Template]    Filter Should Return
    {"type": "gx"}                ${OBJECTS}    H1.1
    {"type": ["Gx", "OC"]}        ${OBJECTS}    H1.1    NGC752
    {"type": "S"}                 ${OBJECTS}    Mond    78P/Gehrels

Type Exclude Works For Multi Character Codes
    [Documentation]    Multi-character type codes, such as OC or Gx, match as whole codes.
    [Template]    Filter Should Return
    {"type": ["Gx", "OC"], "type_exclude": "OC"}      ${OBJECTS}    H1.1
    {"type": ["Gx", "OC"], "type_exclude": ["gx"]}    ${OBJECTS}    NGC752
    {"type": ["S", "Q"], "type_exclude": "S"}         ${OBJECTS}    3C48

Constellation Filter Ignores Case
    [Template]    Filter Should Return
    {"constellation": "sge"}             ${OBJECTS}    2 Sge    HDS2753    STFA41
    {"constellation": ["Cet", "and"]}    ${OBJECTS}    H1.1    NGC752

Patterns Are Case Insensitive Regular Expressions That Match Completely
    [Documentation]    name_pattern, group_pattern and constellation_pattern are regular expressions.
    [Template]    Filter Should Return
    {"name_pattern": "NGC10.*"}                        ${OBJECTS}    H1.1
    {"name_pattern": "ngc10"}                          ${OBJECTS}
    {"name_pattern": ["3C.*", "STF1.*"]}               ${OBJECTS}    3C48    STF1884
    {"group_pattern": "2 .*"}                          ${OBJECTS}    2 Sge    HDS2753    STFA41
    {"constellation_pattern": "S.*"}                   ${OBJECTS}    2 Sge    HDS2753    STFA41
    {"constellation_pattern": "[ac].*"}                ${OBJECTS}    H1.1    NGC752
    {"name_pattern": "H1[.].*", "type": "Gx"}          ${OBJECTS}    H1.1

Criteria Are Combined With And
    [Template]    Filter Should Return
    {"type": "Gx", "constellation": "Cet"}    ${OBJECTS}    H1.1
    {"type": "Gx", "constellation": "And"}    ${OBJECTS}

Is Group Selects Group Records
    [Template]    Filter Should Return
    {"is_group": true}                            ${OBJECTS}    2 Sge
    {"is_group": false, "constellation": "Sge"}    ${OBJECTS}    HDS2753    STFA41

Excluding Group Members Only Affects Members Of Double Star Groups
    [Template]    Filter Should Return
    {"type": "**"}                                       ${OBJECTS}    2 Sge    HDS2753    STFA41    STF1884
    {"type": "**", "exclude_group_members": true}        ${OBJECTS}    2 Sge    STF1884
    {"group": "400", "exclude_group_members": true}      ${OBJECTS}    H1.1

Several Catalogues Are Searched In Order
    ${labels}=    Filter Labels    {"type": "Gx"}    ${OBJECTS}    more_objects.json
    Lists Should Be Equal    ${labels}    ${{['H1.1', 'UGC1', 'Große Magellansche Wolke']}}

Filter Can Be Read From A File
    ${path}=    Fixture    filter_galaxies.json
    ${result}=    Run Filter    ${path}    ${{['objects.json']}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Lists Should Be Equal    ${data}[objects]    ${{['H1.1']}}

Without A Filter Every Object Matches
    ${result}=    Run Filter    ${EMPTY}    ${{['objects.json']}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${data}[count]    9

Full Records Are Returned Unless Names Only Is Given
    ${result}=    Run Filter    {"name": "STFA41"}    ${{['objects.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${data}[count]    1
    ${match}=    Set Variable    ${data}[objects][0]
    Should Be Equal    ${match}[catalogue]    objects.json
    Should Be Equal    ${match}[constellation]    Sge
    Lists Should Be Equal    ${match}[names]    ${{['STFA41', '2 Sge']}}
    Lists Should Be Equal    ${match}[groups]    ${{['2 Sge']}}
    Lists Should Be Equal    ${match}[types]    ${{['**']}}
    Should Be Equal    ${match}[record][COMPONENT]    AB

Catalogue Restricts The Objects To The Named Catalogues
    [Documentation]    All the catalogues are queried together; the criterion names the catalogues, as the results
    ...    show them, ignoring case. Several names mean "any of them".
    ${both}=    Create List    community/own.json    community/wds.json
    ${wds}=    Filter Labels    {"catalogue": "wds.json"}    @{both}
    Lists Should Be Equal    ${wds}    ${{['WDS02333+1234', 'BU17', 'BU17', 'STF999', '2 Sge', 'HDS2753', 'STFA41', 'XYZ1']}}
    ${own}=    Filter Labels    {"catalogue": ["OWN.json"], "type": "**"}    @{both}
    Lists Should Be Equal    ${own}    ${{['alpha Lyr', 'H5 39', 'STFB9', '2 Sge', 'HDS2753', 'STFA41']}}
    ${either}=    Filter Labels    {"catalogue": ["wds.json", "own.json"], "name": "STFA41"}    @{both}
    Lists Should Be Equal    ${either}    ${{['STFA41', 'STFA41']}}
    ${none}=    Filter Labels    {"catalogue": "nowhere.json"}    @{both}
    Should Be Empty    ${none}

The Catalogue Is Shown With Every Object
    ${both}=    Create List    community/own.json    community/wds.json
    ${result}=    Run Filter    {"name": "STFA41"}    ${both}
    ${data}=    Parse JSON    ${result.stdout}
    ${catalogues}=    Evaluate    [o["catalogue"] for o in $data["objects"]]
    Should Be Equal    ${catalogues}    ${{['own.json', 'wds.json']}}

Broken Records Are Skipped With A Notice
    ${result}=    Run Filter    ${EMPTY}    ${{['broken.json']}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0
    ${data}=    Parse JSON    ${result.stdout}
    Lists Should Be Equal    ${data}[objects]    ${{['NGC752', 'Extra']}}
    Should Contain    ${result.stderr}    3 broken record(s) skipped

Invalid Filters Are Rejected
    [Template]    Filter Should Be Rejected
    {"colour": "blue"}         unknown filter key 'colour'
    {"type": "Galaxy"}         unknown object type 'Galaxy'
    {"is_group": "yes"}        'is_group' must be true or false
    {"name": 5}                'name' must be a string or a list of strings
    {"catalogue": 5}           'catalogue' must be a string or a list of strings
    {"project": "nonsense"}    unknown project 'nonsense'
    {"name_pattern": "("}      invalid regular expression '('
    {"type": }                 invalid JSON in filter
    missing_filter.json        cannot read filter file

Filter File Must Contain A JSON Object
    ${path}=    Fixture    filter_list.json
    ${result}=    Run Filter    ${path}    ${{['objects.json']}}
    Should Fail With Usage Error    ${result}    a filter specification must be a JSON object

Unusable Catalogues Are Rejected
    [Template]    Catalogue Should Be Rejected
    missing.json        cannot read
    invalid.json        invalid JSON
    not_a_list.json     does not contain a JSON list

Catalogue Parameter Is Required
    ${result}=    Run CLI    filter
    Should Fail With Usage Error    ${result}    --catalogue


*** Keywords ***
Filter Should Be Rejected
    [Arguments]    ${filter}    ${message}
    ${result}=    Run Filter    ${filter}    ${{['objects.json']}}
    Should Fail With Usage Error    ${result}    ${message}

Catalogue Should Be Rejected
    [Arguments]    ${catalogue}    ${message}
    ${result}=    Run Filter    {}    ${{['${catalogue}']}}
    Should Fail With Usage Error    ${result}    ${message}
