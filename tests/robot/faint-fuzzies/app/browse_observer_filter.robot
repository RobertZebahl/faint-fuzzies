*** Settings ***
Documentation       The Observer filter dropdown of the Browse page (ui/browse.py: _observer_options), tested
...                 directly against hand-built domain objects (BrowseObserverChecks.py) - no browser, no data
...                 directory needed. An own-catalogue observation never carries an Observer even though it is
...                 the owner's, so the registered OWNER-scope observer would otherwise vanish from the
...                 dropdown as soon as the owner stops also having a community-imported observation (such
...                 as a project CSV submission).
Library             ../../libraries/BrowseObserverChecks.py


*** Test Cases ***
The Owner Appears From An Own Observation Alone
    [Documentation]    Regression case: the owner removed their project-double-stars submission folder, keeping
    ...    only their own-catalogue observations (now that photographs can be attached there directly) - they
    ...    must still be offered in the Observer filter.
    ${ids}=    Observer Ids With Only An Own Observation
    Should Contain    ${ids}    owner-example

The Owner Is Left Out With No Observation At All
    [Documentation]    The dropdown only ever offers an observer with something to filter for.
    ${ids}=    Observer Ids With No Observation At All
    Should Not Contain    ${ids}    owner-example

A Community-Imported Observation Still Works Without An Observers File
    ${ids}=    Observer Ids With A Community Observation Only
    Should Contain    ${ids}    owner-example
