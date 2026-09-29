*** Settings ***
Documentation       The pages of the Website lists: which lists have one, how their rows are ordered (by the
...                 catalogue number, the Herschel number) and what titles and descriptions they carry.
Library             ../../libraries/ListPageChecks.py


*** Test Cases ***
Every List Of The Menu Has A Page Except The Gallery
    [Documentation]    The gallery is a page of its own, not a list of rows.
    ${missing}=    Lists Of The Menu Without A Page
    Should Be Equal    ${missing}    ${{["sketches-gallery"]}}

Catalogue Numbers Are Ordered As Numbers
    ${rows}=    Rows In Page Order    berkeley-clusters    Berkeley 10    Berkeley 9    Berkeley 100    Berkeley 1
    Should Be Equal    ${rows}    ${{["Berkeley 1", "Berkeley 9", "Berkeley 10", "Berkeley 100"]}}

The Last Name With A Number Decides
    [Documentation]    Joined names are matched greedily, so the last "Messier n" counts.
    ${rows}=    Rows In Page Order    messier    IC4703,Messier 16    NGC224,Messier 31    Messier 1,Messier 2
    Should Be Equal    ${rows}    ${{["Messier 1", "IC4703", "NGC224"]}}

A Group Without Names Is Ordered By Its Group Names
    ${rows}=    Rows In Page Order    hickson-groups    Hickson 44    group:Hickson 7    Hickson 100
    Should Be Equal    ${rows}    ${{["Hickson 7", "Hickson 44", "Hickson 100"]}}

Herschel Numbers Are Ordered Part By Part
    [Documentation]    H2.5 before H2.14 before H2.14.1 before H10.1; an object without a Herschel name comes first.
    ${rows}=    Rows In Page Order    herschel-2500    NGC3,H10.1    NGC2,H2.14.1    NGC1,H2.14    NGC0,H2.5    NGC9
    Should Be Equal    ${rows}    ${{["NGC9", "NGC0", "NGC1", "NGC2", "NGC3"]}}

The Other Lists Keep The Order Of The Global List
    ${found}=    Pages Without Sort Key
    Should Be Equal    ${found}    ${{sorted(["asterisms", "bright-nebulae", "complete-object-list", "dark-nebulae", "double-stars", "galaxies-and-groups", "galaxies-in-messier-44", "globular-clusters", "local-group", "open-clusters", "planetary-nebulae", "red-stars", "ring-galaxies", "sketches-comets", "sketches-deepsky", "sketches-moon", "sketches-planets", "sketches-sun", "superthin-galaxies", "thin-galaxies"])}}

Only Four Pages Have A Description
    [Documentation]    Descriptions come from fixtures/site/page_descriptions.json, not from ListPage itself.
    ${found}=    Pages With Description
    Should Be Equal    ${found}    ${{["galaxies-in-messier-44", "red-stars", "superthin-galaxies", "thin-galaxies"]}}
    ${text}=    Description    thin-galaxies    de
    Should Contain    ${text}    mindestens 1:5
    ${text}=    Description    superthin-galaxies    en
    Should Contain    ${text}    at least 1:7

The Title Of A Page Is Not The Name In The Menu
    ${english}=    Title    berkeley-clusters    en
    ${german}=    Title    red-stars    de
    Should Be Equal    ${english}    Open Clusters of the Berkeley Catalogue
    Should Be Equal    ${german}    Kohlenstoffsterne & Rote Sterne

The Solar System Comes First In The Global List
    [Documentation]    The Moon, the Sun, the planets in the order of the sky, asteroids, comets; then everything else.
    ${found}=    Global Order    NGC1:GC    Comet2:C    Jupiter:P    Ceres:A    Mars:P    Mond,Moon:S    Sonne,Sun:S    15 Aql:**    Comet1:C
    Should Be Equal    ${found}    ${{["Mond", "Sonne", "Mars", "Jupiter", "Ceres", "Comet1", "Comet2", "15 Aql", "NGC1"]}}
