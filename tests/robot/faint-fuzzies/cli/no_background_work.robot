*** Settings ***
Documentation       `serve --no-dss-fetch` and `serve --no-orbits-generation`: the app fetches no DSS image, or generates no orbit diagram,
...                 in the background, so a data directory is left as it is (both jobs are stubbed here, so nothing goes to
...                 the network). Fixture "site_datadir", in a copy, with an orbit file for its pair STF999.
Library             ../../libraries/AppStateChecks.py
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${FIXTURES}${/}site_datadir


*** Test Cases ***
The App Fetches DSS Images And Draws Orbits By Default
    ${result}=    Background Work Of State    ${DATADIR}    ${True}    ${True}
    Should Be Equal    ${result}[queued]    ${{['dss', 'orbit']}}
    Should Be True    ${result}[dss_calls] > 0
    Should Be True    ${result}[orbit_calls] > 0

No DSS Image Is Queued Or Fetched Without The DSS Switch
    ${result}=    Background Work Of State    ${DATADIR}    ${False}    ${True}
    Should Be Equal    ${result}[queued]    ${{['orbit']}}
    Should Be Equal As Integers    ${result}[dss_calls]    0
    Should Be True    ${result}[orbit_calls] > 0

No Orbit Diagram Is Queued Or Drawn Without The Orbit Switch
    ${result}=    Background Work Of State    ${DATADIR}    ${True}    ${False}
    Should Be Equal    ${result}[queued]    ${{['dss']}}
    Should Be Equal As Integers    ${result}[orbit_calls]    0
    Should Be True    ${result}[dss_calls] > 0

With Both Switches Nothing Runs And Nothing Is Written
    ${result}=    Background Work Of State    ${DATADIR}    ${False}    ${False}
    Should Be Empty    ${result}[queued]
    Should Be Equal As Integers    ${result}[dss_calls]    0
    Should Be Equal As Integers    ${result}[orbit_calls]    0
    Should Be Equal As Integers    ${result}[written]    0

The Switches Are Offered By Serve
    ${result}=    Run CLI    serve    --help
    Should Contain    ${result.stdout}    --no-dss-fetch
    Should Contain    ${result.stdout}    --no-orbits-generation
