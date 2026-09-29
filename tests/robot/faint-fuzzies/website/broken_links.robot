*** Settings ***
Documentation       The build's broken-link check (site/output.py's `_broken_page_links`/`_scan_links`):
...                 every page's `<a href>` is checked against the pages and anchors actually on disk,
...                 whether rendered this run (`page_hrefs`/`page_anchors`, passed in directly) or only
...                 seeded by `base`/the static folder (read from disk instead). Tested directly, against
...                 hand-built dicts and files - no data directory or full build needed.
Resource            ../../resources/cli.resource
Library             ../../libraries/BrokenLinkChecks.py


*** Test Cases ***
A Link To A Missing Page Is Reported
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["missing.php"]}}}    ${{{"en/home.php": []}}}
    Length Should Be    ${broken}    1
    Should Contain    ${broken}[0]    missing.php

A Link To An Existing Page With A Matching Anchor Is Not Reported
    [Documentation]    "target.php" is not in page_anchors at all, so its anchors are read from disk.
    Create File    ${OUTPUT DIR}${/}en${/}target.php    <a id="Foo" class="anchor"></a>
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["target.php#Foo"]}}}    ${{{"en/home.php": []}}}
    Should Be Empty    ${broken}

A Link To An Existing Page With A Missing Anchor Is Reported
    Create File    ${OUTPUT DIR}${/}en${/}target.php    <a id="Foo" class="anchor"></a>
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["target.php#Bar"]}}}    ${{{"en/home.php": []}}}
    Length Should Be    ${broken}    1
    Should Contain    ${broken}[0]    Bar

A Same-Page Anchor Is Checked Against The Page's Own Anchors
    Create File    ${OUTPUT DIR}${/}en${/}home.php    anything
    ${valid}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["#Foo"]}}}    ${{{"en/home.php": ["Foo"]}}}
    Should Be Empty    ${valid}
    ${invalid}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["#Foo"]}}}    ${{{"en/home.php": []}}}
    Length Should Be    ${invalid}    1

An External Href Is Never Checked
    [Documentation]    No files exist for any of these, and none is reported - there is no network access here.
    ${broken}=    Broken Links    ${OUTPUT DIR}
    ...    ${{{"en/home.php": ["http://example.com/missing", "mailto:x@y.com", "//cdn.example.com/x"]}}}
    ...    ${{{"en/home.php": []}}}
    Should Be Empty    ${broken}

A Query String Is Stripped Before Resolving The Page
    Create File    ${OUTPUT DIR}${/}en${/}home.php    anything
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["?list=foo"]}}}    ${{{"en/home.php": []}}}
    Should Be Empty    ${broken}

An Empty Href Or A Bare Hash Is Ignored
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["", "#"]}}}    ${{{"en/home.php": []}}}
    Should Be Empty    ${broken}

A Relative Path Cannot Escape The Output Folder
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["../../../../etc/evil.php"]}}}    ${{{"en/home.php": []}}}
    Length Should Be    ${broken}    1

A Media Reference Is Left To The Existing Missing-Image Check
    [Documentation]    "../images/dss/x.jpg" is not a page link - it is the existing check's job, and it must
    ...    never be reported here even though no such file exists in this test's output folder.
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["../images/dss/x.jpg"]}}}    ${{{"en/home.php": []}}}
    Should Be Empty    ${broken}

A Percent-Encoded Path Is Decoded Before Resolving The Page
    Create File    ${OUTPUT DIR}${/}en${/}target+page.php    anything
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["target%2Bpage.php"]}}}    ${{{"en/home.php": []}}}
    Should Be Empty    ${broken}

A PHP String Concatenation Is Not Mistaken For A Page
    [Documentation]    A language switcher built as `'<a href="'.$url.'">'` leaves a literal `'.$url.'` as the
    ...    href text once HTMLParser reads the quotes - a runtime PHP value no build-time scan can resolve.
    ${broken}=    Broken Links    ${OUTPUT DIR}    ${{{"en/home.php": ["'.$url.'"]}}}    ${{{"en/home.php": []}}}
    Should Be Empty    ${broken}

A Link Inside A PHP Echo Is Still Found
    [Documentation]    Jinja has already resolved every {{ }} placeholder before this text is ever written, so
    ...    the href is plain text by the time this runs, whichever side of the PHP "if" it is on.
    ${document}=    Catenate    SEPARATOR=\n
    ...    <?php if ($list) {
    ...    echo '<a href="project-double-stars.php?list=foo#STF999">x</a>';
    ...    } else {
    ...    echo '<a href="project-double-stars.php#STF999">x</a>';
    ...    } ?>
    ${hrefs}=    Scanned Hrefs    ${document}
    Should Be Equal    ${hrefs}
    ...    ${{['project-double-stars.php?list=foo#STF999', 'project-double-stars.php#STF999']}}

Both Id And Name Anchors Are Recognised
    ${anchors}=    Scanned Anchors    <a id="Foo" class="anchor"></a><a name="Bar" class="anchor"></a>
    Should Be Equal    ${anchors}    ${{['Bar', 'Foo']}}
