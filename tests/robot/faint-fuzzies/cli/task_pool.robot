*** Settings ***
Documentation       TaskPool.add: one task queued between Reloads, at the back or the front, counted in the
...                 progress, and ignored when its key is already queued or running.
Library             ../../libraries/TaskPoolChecks.py


*** Test Cases ***
Add Queues One Task Without Replacing The Batch
    ${result}=    Run Added Tasks
    Should Be Equal    ${result}[returned]    ${{[True, True, False, True, False]}}
    Should Be Equal    ${result}[order]    ${{["front", "back", "third"]}}
    Should Be Equal    ${result}[before]    ${{{"dss": (0, 4)}}}
    Should Be Equal    ${result}[after]    ${{{"dss": (4, 4)}}}

A Task That Returns False Or Raises Is Recorded As A Failure
    [Documentation]    With what it was for and what happened; a task that works is not, and a Reload (reset) starts again.
    ${result}=    Run Failing Tasks
    Should Be Equal    ${result}[failures]    ${{[("no-result", "dss", "M 13 (objects.json)", "no DSS image could be fetched"), ("raised", "orbit", "STF 1 AB", "RuntimeError: boom")]}}
    Should Be Empty    ${result}[after_reset]
