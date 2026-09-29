*** Settings ***
Documentation       DSS fetching, checked directly against the real functions with no network ever reached: the
...                 order _dss_run tries sources in (faint_fuzzies.media_pool), and the live app's lazy, shared
...                 thumbnail and its fallback to the full-size image's own URL when making it fails
...                 (faint_fuzzies.ui.media._thumbnail_url, used by get_dss_status).
Library             ../../libraries/DssFetchChecks.py


*** Test Cases ***
Every Source Is Tried By Name Before Any By Coordinates
    [Documentation]    By-name task, two sources, nothing ever succeeds: both sources are tried by name
    ...    first, in order, and only then does it fall back to coordinates, also in source order.
    ${result}=    Dss Fetch Calls    ${True}
    Should Be Equal    ${result}[calls]    ${{[('name', 'dss1'), ('name', 'dss2red'), ('coordinates', 'dss1'), ('coordinates', 'dss2red')]}}
    Should Be Equal    ${result}[succeeded]    ${False}

A Task Not Marked By Name Skips Straight To Coordinates
    ${result}=    Dss Fetch Calls    ${False}
    Should Be Equal    ${result}[calls]    ${{[('coordinates', 'dss1'), ('coordinates', 'dss2red')]}}

The Fetch Stops At The First Success, By Name
    [Documentation]    A less-preferred by-name source succeeding still wins over ever trying coordinates.
    ${result}=    Dss Fetch Calls    ${True}    succeed_at=${{('name', 'dss2red')}}
    Should Be Equal    ${result}[calls]    ${{[('name', 'dss1'), ('name', 'dss2red')]}}
    Should Be Equal    ${result}[succeeded]    ${True}

Coordinates Are Only Tried After Every Name Attempt Fails
    ${result}=    Dss Fetch Calls    ${True}    succeed_at=${{('coordinates', 'dss1')}}
    Should Be Equal    ${result}[calls]    ${{[('name', 'dss1'), ('name', 'dss2red'), ('coordinates', 'dss1')]}}
    Should Be Equal    ${result}[succeeded]    ${True}

A Readable Cached Image Gets A Shared Thumbnail
    [Documentation]    The app makes the same shared, 200x200 thumbnail the website builder would, next to the
    ...    full-size image, and returns its URL.
    ${result}=    Thumbnail Url For Cached Image    ${True}
    Should Be Equal    ${result}[url]    /media/dss/objects/dss1_010000.00_+200000.00_5_web.jpg
    Should Be True    ${result}[thumbnail_written]

When Making The Thumbnail Fails The Full-Size Image's Own Url Is Used Instead
    [Documentation]    An unreadable "cached image" (here: not actually an image) makes thumbnailing fail;
    ...    get_dss_status then falls back to the full-size image's own URL, exactly as if no thumbnail-sharing
    ...    existed - this only checks the half that _thumbnail_url itself is responsible for (returning None).
    ${result}=    Thumbnail Url For Cached Image    ${False}
    Should Be Equal    ${result}[url]    ${None}
    Should Not Be True    ${result}[thumbnail_written]
