*** Settings ***
Documentation       `serve --no-dss-fetch` and `serve --no-orbits-generation`: the app fetches no DSS image, or generates
...                 no orbit diagram, in the background. Here: that serve offers the switches; what they do to the app's
...                 background work is a unit test (tests/unit/ui/test_state_background.py).
Resource            ../../resources/cli.resource


*** Test Cases ***
The Switches Are Offered By Serve
    ${result}=    Run CLI    serve    --help
    Should Contain    ${result.stdout}    --no-dss-fetch
    Should Contain    ${result.stdout}    --no-orbits-generation
