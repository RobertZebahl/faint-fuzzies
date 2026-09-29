*** Settings ***
Documentation       The lists behind the website's menu, defined on the Global list (fixture "website_lists": an own
...                 catalogue of small cases and a Herschel catalogue). The menu
...                 shows a count beside each list, so a list is defined here even when its page is not built yet.
Library             ../../libraries/WebsiteListChecks.py
Resource            ../../resources/cli.resource
Suite Setup         Build The Website Lists


*** Variables ***
${WORLD}            ${FIXTURES}${/}website_lists


*** Test Cases ***
Name And Type Rules
    [Documentation]    "Berkeley 2b" is not "Berkeley" and a number: names are matched whole.
    [Template]    List Should Hold
    berkeley-clusters          Berkeley 1
    king-clusters              King 5
    abell-planetary-nebulae    Abell 21
    ring-galaxies              NGC2685
    messier                    Messier 16    Messier 31

Groups And Local Group
    [Documentation]    The Local Group is a GROUP of the galaxies; Hickson and Arp groups are group records.
    [Template]    List Should Hold
    local-group        NGC224
    hickson-groups     Hickson 1
    arp-galaxies       Arp10    Arp20

Thin Galaxies Are Judged By The Ratio Of The Two Diameters
    [Documentation]    5:1 is thin, 7:1 is also superthin; a zero minor diameter or a missing one has no ratio.
    [Template]    List Should Hold
    thin-galaxies         NGC1    NGC2
    superthin-galaxies    NGC2

Red Stars Are Carbon Stars Or Flagged Stars
    List Should Hold    red-stars    Carbonstar    Redstar

Herschel Lists Follow The References To The Herschel Catalogue
    [Documentation]    NGC1055 references a Herschel object of the list 400; NGC2775 one of the list 2500.
    [Template]    List Should Hold
    herschel-400     NGC1055
    herschel-2500    NGC1055    NGC2775

The Complete List Leaves Out The Solar System
    ${labels}=    Members Of    complete-object-list
    Should Not Contain    ${labels}    Mond
    Should Not Contain    ${labels}    Comet1
    Should Contain    ${labels}    Plainstar

Galaxies And Groups Are One List
    List Should Hold    galaxies-and-groups    Arp10    Arp20    Hickson 1    Messier 31    NGC1    NGC1055    NGC2    NGC224    NGC2685    NGC2775    NGC3    NGC4

Sketch Lists Need A Public Sketch
    [Template]    List Should Hold
    sketches-gallery    Comet1    Sketchy    Sketchy too
    sketches-deepsky    Sketchy    Sketchy too
    sketches-comets     Comet1

The Menu Counts Distinct Messier Names And Distinct Sketches
    [Documentation]    Messier 16 and Messier 17 are one object with two names, so three names in two entries; the
    ...    gallery has three different sketches (a.jpg is on two objects).
    Should Be Equal As Integers    ${LISTS}[messier][1]    3
    Should Be Equal As Integers    ${LISTS}[sketches-gallery][1]    3
    Should Be Equal As Integers    ${LISTS}[complete-object-list][1]    23


The Size Ratio Criterion Of The Filter Uses The Same Rule
    ${result}=    Run CLI    filter    --catalogue    ${WORLD}${/}own.json    --filter    {"size_ratio": [5, null]}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects]    ${{["NGC1", "NGC2"]}}
    ${result}=    Run CLI    filter    --catalogue    ${WORLD}${/}own.json    --filter    {"size_ratio": [null, 3]}    --names-only
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects]    ${{["NGC2685"]}}


*** Keywords ***
Build The Website Lists
    ${lists}=    Website Lists    ${WORLD}${/}own.json    ${WORLD}${/}herschel.json
    Set Suite Variable    ${LISTS}    ${lists}

Members Of
    [Arguments]    ${name}
    RETURN    ${LISTS}[${name}][0]

List Should Hold
    [Arguments]    ${name}    @{expected}
    ${labels}=    Members Of    ${name}
    Should Be Equal    ${labels}    ${expected}
